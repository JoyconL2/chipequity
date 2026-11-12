// one-off: this season (2026-27) with the current teammate adjustment (a.html) vs the per-side fix (b.html)
import http from "http"; import fs from "fs"; import path from "path"; import { chromium } from "playwright";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36";
const DIR = process.argv[2]; const out = [];
const srv = http.createServer((q, r) => { const f = path.join(DIR, q.url.split("?")[0].replace(/^\/+/, "")); if (!fs.existsSync(f)) { r.writeHead(404); return r.end(); } r.writeHead(200, {"content-type": f.endsWith(".html") ? "text/html" : "application/json"}); fs.createReadStream(f).pipe(r); });
await new Promise(r => srv.listen(0, "127.0.0.1", r)); const port = srv.address().port;
const b = await chromium.launch(); const cache = new Map();
const res = {};
for (const v of ["a", "b"]) {
  const ctx = await b.newContext({ timezoneId: "America/New_York", userAgent: UA }); const p = await ctx.newPage();
  await p.route(/^https:\/\/[a-z.]*espn\.com\//, async r => { const u = r.request().url();
    if (!cache.has(u)) { const x = await r.fetch({ headers: { "user-agent": UA, accept: "application/json" } }); cache.set(u, { status: x.status(), body: await x.body() }); }
    const c = cache.get(u); await r.fulfill({ status: c.status, body: c.body, contentType: "application/json", headers: { "access-control-allow-origin": "*" } }); });
  await p.goto(`http://127.0.0.1:${port}/${v}.html`);
  res[v] = await p.evaluate(async () => {
    for (let i = 0; i < 60 && typeof CUR === "undefined"; i++) await new Promise(r => setTimeout(r, 500));
    await CUR.ensure(); const st = CUR.state(), T = st.teams;
    const S = DATA.seasons, si = S.length - 1, nm = DATA.names;
    const rows = DATA.rw.rows.filter(r => r[1] === si && r[2] === 1);
    const lead = rows.filter(r => r[7] >= 436).sort((a, b) => b[5] - a[5]).slice(0, 20).map(r => [nm[r[0]], r[5], r[3], r[4]]);
    const days = []; const today = new Date(); today.setHours(12,0,0,0);
    for (let d = new Date(CUR.seasonStart); d < today; d.setDate(d.getDate() + 1)) { const x = new Date(d); x.setHours(12,0,0,0); days.push(x); }
    let w = 0, l = 0, w0 = 0, l0 = 0, n = 0;
    const pre = ab => T[ab] && T[ab].preseason;
    for (const d of days) { let L; try { L = await feedESPN(d); } catch (e) { continue; }
      for (const g of L) { if (g.state !== "post" || g.stype === 1 || g.start < CUR.seasonStart) continue; n++;
        const hw = g.home.score > g.away.score, q = gamePred(g); if (q) ((q.pHome >= 0.5) === hw) ? w++ : l++;
        const ph = pre(g.home.ab), pa = pre(g.away.ab); if (ph != null && pa != null) ((ph - pa + 2.5 >= 0) === hw) ? w0++ : l0++; } }
    const tm = Object.values(T).filter(t => t.gp > 0); const xs = tm.map(t => t.preseason), ys = tm.map(t => t.mov);
    const mx = xs.reduce((a, b) => a + b) / xs.length, my = ys.reduce((a, b) => a + b) / ys.length;
    const cov = xs.reduce((s, x, i) => s + (x - mx) * (ys[i] - my), 0), r = cov / Math.sqrt(xs.reduce((s, x) => s + (x - mx) ** 2, 0) * ys.reduce((s, y) => s + (y - my) ** 2, 0));
    const err = Math.sqrt(tm.reduce((s, t) => s + (t.preseason - t.mov) ** 2, 0) / tm.length);
    return { src: st.src, games: n, rec: [w, l], rosterOnly: [w0, l0], r, err, lead, teams: tm.map(t => [t.ab, +t.preseason.toFixed(2), +t.mov.toFixed(2)]).sort((a, b) => b[2] - a[2]) };
  });
  await ctx.close();
}
await b.close(); srv.close();
const lines = [];
for (const v of ["a", "b"]) { const x = res[v]; lines.push(`${v === "a" ? "CURRENT" : "PER-SIDE FIX"} (rosters ${x.src}, ${x.games} games)`);
  lines.push(`  recount with today's ratings: ${x.rec.join("-")} | roster-only picks (no record): ${x.rosterOnly.join("-")} | roster rating vs actual margin r=${x.r.toFixed(3)}, miss ${x.err.toFixed(2)} pts/game`);
  x.lead.forEach((r, i) => lines.push(`  ${String(i + 1).padStart(2)}. ${r[0]} ${r[1].toFixed(2)} (${r[2]} / ${r[3]})`)); }
lines.push("team: roster rating current -> fix | actual margin");
const B = Object.fromEntries(res.b.teams.map(t => [t[0], t[1]]));
res.a.teams.forEach(t => lines.push(`  ${t[0]} ${t[1]} -> ${B[t[0]]} | ${t[2]}`));
fs.mkdirSync("oneoff/out", { recursive: true }); fs.writeFileSync("oneoff/out/tm.txt", lines.join("\n") + "\n"); console.log(lines.join("\n"));
