// Save the model's pick for every game today that hasn't started yet, exactly as the site shows it right now
// (the built site in dist/, opened in a headless browser, with ESPN's live rosters and injury list).
// Writes dist/picks.json: {season, base: {through, w, l}, games: {espnGameId: [day, home, away, pHome, savedAt]}}.
// A game's pick is only replaced while the game is still "pre"; once it starts, it stays as last saved.
// The site's model record counts these saved picks (site/template.html, modelRecord).
// usage: node update/snap_picks.mjs        (needs: npm i playwright && npx playwright install chromium)
import http from "http";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { chromium } from "playwright";

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const DIST = path.join(ROOT, "dist"), OUT = path.join(DIST, "picks.json");
const TYPES = { ".html": "text/html", ".json": "application/json", ".js": "text/javascript", ".png": "image/png", ".css": "text/css" };
const srv = http.createServer((req, res) => {
  const f = path.join(DIST, decodeURIComponent(req.url.split("?")[0]).replace(/^\/+/, "") || "index.html");
  if (!f.startsWith(DIST) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { "content-type": TYPES[path.extname(f)] || "application/octet-stream" }); fs.createReadStream(f).pipe(res);
});
await new Promise(r => srv.listen(0, "127.0.0.1", r));
const port = srv.address().port;

const browser = await chromium.launch(process.env.CHROMIUM ? { executablePath: process.env.CHROMIUM } : {});
const ctx = await browser.newContext({ timezoneId: "America/New_York" });     // game days are Eastern, like ESPN's
const page = await ctx.newPage();
if (process.env.ESPN_MOCK) await page.route(/site\.api\.espn\.com\/.*\/scoreboard/, r => r.fulfill({ contentType: "application/json", body: fs.readFileSync(process.env.ESPN_MOCK, "utf8") }));   // local testing only
page.on("pageerror", e => console.log("page error:", e.message));
await page.goto(`http://127.0.0.1:${port}/index.html`, { waitUntil: "load" });
const got = await page.evaluate(async () => {
  for (let i = 0; i < 60 && typeof CUR === "undefined"; i++) await new Promise(r => setTimeout(r, 500));
  await CUR.ensure();
  if (!CUR.ready()) return { err: "season model not ready: " + JSON.stringify(CUR.state().status) };
  const day = new Date(); day.setHours(12, 0, 0, 0);
  const L = await feedESPN(day), games = [];
  for (const g of L) {
    if (g.state !== "pre" || g.stype === 1) continue;                    // started already, or preseason
    const p = gamePred(g); if (!p) continue;
    games.push([g.id, isoDay(day), g.home.ab, g.away.ab, Math.round(p.pHome * 1000) / 1000]);
  }
  return { season: DATA.seasons[DATA.seasons.length - 1], src: CUR.state().src || null, games, all: L.length };
});
await browser.close(); srv.close();
if (got.err) { console.error(got.err); process.exit(1); }

let P = fs.existsSync(OUT) ? JSON.parse(fs.readFileSync(OUT, "utf8")) : null;
if (!P || P.season !== got.season) P = { season: got.season, base: null, games: {} };
const now = new Date().toISOString().slice(0, 16) + "Z";
let changed = 0;
for (const [id, day, h, a, p] of got.games) {
  const old = P.games[id];
  if (!old || old[3] !== p || old[1] !== day) { P.games[id] = [day, h, a, p, now]; changed++; }
}
console.log(`${got.season}: ${got.all} games today, ${got.games.length} not started; ${changed} picks new or changed (rosters: ${got.src})`);
for (const [id, day, h, a, p] of got.games) console.log(`  ${day} ${a} @ ${h}: home ${(p * 100).toFixed(1)}% -> pick ${p >= 0.5 ? h : a}`);
if (changed) fs.writeFileSync(OUT, JSON.stringify(P, null, 0) + "\n");
