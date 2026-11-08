/* ================= Courtside model v3 =================
   Players: box-score stats plus career peak Chip Equity and decade Chip Equity (our own Chip Equity from every possession since 1996-97). No composite rating, no single-season Chip Equity.
   Team matchup: net rating, record vs. point differential, home court, and a playoff-résumé adjustment for
   teams from different seasons, and the top two players' decade Chip Equity as a stand-in for player strength (wDec).
   Game margins ~ Normal; series = best-of-7.  */
function buildModel(DATA, PARAMS_IN){
  const S = DATA.seasons, P = DATA.P, T = DATA.T;
  const NP = P.p.length, NT = T.a.length;
  const key = (s,t) => s*2 + t;
  const nz = v => (v === null || v === undefined) ? NaN : v;
  const LGA = DATA.league || [];
  const SERIES = (DATA.series || []).map(x => ({s:x[0], round:x[1], w:x[2], l:x[3], ww:x[4], lw:x[5], aw:x[6], al:x[7]}));
  // availability Chip Equity: roster Chip Equity weighted by who actually played going in (last 15 games, or the earlier playoff rounds)
  const availMap = new Map();
  for (const x of SERIES){ if (x.aw!=null) availMap.set(`${x.s}|${x.w}|${x.l}`, x.aw); if (x.al!=null) availMap.set(`${x.s}|${x.l}|${x.w}`, x.al); }
  const ROUND_NAME = {1:"first round", 2:"conference semifinals", 3:"conference finals", 4:"NBA Finals"};

  /* ---------------- teams ---------------- */
  const teamIdx = new Map();
  const tm = [];
  for (let i=0;i<NT;i++){
    teamIdx.set(T.a[i]+"|"+T.s[i]+"|"+T.t[i], i);
    const fga = T.fg2a[i] + T.fg3a[i];
    const r = {
      i, a:T.a[i], s:T.s[i], t:T.t[i], gp:T.gp[i],
      off: T.pts[i]/T.op[i]*100, def: T.opp[i]/T.dp[i]*100, pace: nz(T.pace[i]),
      efg: (T.fg2m[i] + 1.5*T.fg3m[i])/fga, ts: T.pts[i]/(2*(fga + 0.44*T.fta[i])),
      tov: T.tov[i]/T.op[i]*100, oreb: nz(T.oreb[i])*100, dreb: nz(T.dreb[i])*100,
      ftr: T.fta[i]/fga*100, par3: T.fg3a[i]/fga*100, stl: T.stl[i]/T.dp[i]*100,
      blk: T.blk[i]/T.dp[i]*100, fouls: T.sf[i]/T.dp[i]*100,
      ppg: T.pts[i]/T.gp[i], oppg: T.opp[i]/T.gp[i],
      w: T.w ? T.w[i] : null, l: T.l ? T.l[i] : null
    };
    r.net = r.off - r.def;
    r.wpct = (r.w!=null && r.l!=null) ? r.w/(r.w+r.l) : NaN;
    const pa = Math.pow(T.pts[i],14), pb = Math.pow(T.opp[i],14);
    r.pyth = pa/(pa+pb);                       // expected win% from points scored/allowed
    r.luck = Number.isNaN(r.wpct) ? 0 : r.wpct - r.pyth;
    tm.push(r);
  }
  const TEAM_METRICS = { net:true, off:true, def:false, pace:null, efg:true, ts:true, tov:false, oreb:true, dreb:true,
    ftr:true, par3:null, stl:true, blk:true, fouls:false, wpct:true, rts:true };
  const lg = {}, groups = {};
  tm.forEach(r => (groups[key(r.s,r.t)] ||= []).push(r));
  for (const k in groups){
    const g = groups[k], s = g[0].s, t = g[0].t;
    const sum = f => g.reduce((a,r)=>a+f(r),0);
    const L = { n:g.length };
    L.off = sum(r=>T.pts[r.i]) / sum(r=>T.op[r.i]) * 100;
    L.def = L.off; L.net = 0;
    L.efg = sum(r=>T.fg2m[r.i]+1.5*T.fg3m[r.i]) / sum(r=>T.fg2a[r.i]+T.fg3a[r.i]);
    // league true shooting: league averages (regular season) when available
    const lga = LGA[s];
    L.ts = lga && lga["TS%"] ? lga["TS%"] : sum(r=>T.pts[r.i]) / (2*(sum(r=>T.fg2a[r.i]+T.fg3a[r.i]) + 0.44*sum(r=>T.fta[r.i])));
    for (const m of ["pace","tov","oreb","dreb","ftr","par3","stl","blk","fouls"]) L[m] = sum(r=>r[m])/g.length;
    L.wpct = 0.5;
    g.forEach(r => r.rts = r.ts - L.ts);
    L.rts = 0;
    L.sd = {};
    for (const m of Object.keys(TEAM_METRICS)){
      const mean = m==="net"||m==="rts" ? 0 : (m==="off"||m==="def") ? L.off : L[m];
      L.sd[m] = Math.sqrt(sum(r=>Number.isNaN(r[m]) ? 0 : (r[m]-mean)**2)/g.length) || 1;
    }
    lg[k] = L;
    for (const m of Object.keys(TEAM_METRICS)){
      const hb = TEAM_METRICS[m];
      for (const r of g){
        r.rank ||= {};
        r.rank[m] = Number.isNaN(r[m]) ? null : 1 + g.filter(o => hb===null ? o[m] > r[m] : (hb ? o[m] > r[m] : o[m] < r[m])).length;
      }
    }
  }
  // regular-season league TS is the reference for player relative TS% (playoffs included, the usual convention)
  const lgTS = s => (lg[key(s,0)] || lg[key(s,1)]).ts;
  const leagueOf = r => lg[key(r.s, r.t)];
  const rel = (r, m) => { const L = leagueOf(r); return m==="net" ? r.net : m==="rts" ? r.rts : r[m] - ((m==="off"||m==="def") ? L.off : L[m]); };
  const z = (r, m) => rel(r,m) / leagueOf(r).sd[m];
  const teamRow = (a, s, t=0) => { const i = teamIdx.get(a+"|"+s+"|"+t); return i==null ? -1 : i; };

  /* ---------------- players ---------------- */
  const MIN_SEC = [1000*60, 150*60];
  const rowsByPlayer = Array.from({length: DATA.ids.length}, () => []);
  for (let i=0;i<NP;i++) rowsByPlayer[P.p[i]].push(i);
  rowsByPlayer.forEach(r => r.sort((a,b)=>P.s[a]-P.s[b] || P.t[a]-P.t[b]));
  const rowsOf = (k, t) => rowsByPlayer[k].filter(i=>P.t[i]===t);
  const rsRowOf = (k, s) => rowsByPlayer[k].find(i=>P.t[i]===0 && P.s[i]===s);

  /* Chip Equity: single-season regularized adjusted plus-minus (regular season), points per 100 possessions vs. an average player */
  const CEPM = DATA.rapm || {rows:[], n:{}};
  const rapmMap = new Map();
  for (const [k,s,r,o,d,rank,la] of CEPM.rows) rapmMap.set(k*64+s, {r,o,d,rank,la,s});
  const rapmSeasons = [...new Set(CEPM.rows.map(x=>x[1]))].sort((a,b)=>a-b);
  const rapmOf = (k, s) => rapmMap.get(k*64+s) || null;
  const rapmRow = i => rapmOf(P.p[i], P.s[i]);
  const rapmPool = s => CEPM.n[s] || null;
  const hasRapm = s => rapmSeasons.includes(s);
  // career view: average over the seasons that have Chip Equity, weighted by regular-season minutes
  function rapmSummary(k, rows){
    const seen = new Set(), list = [];
    for (const i of rows){ const s = P.s[i]; if (seen.has(s)) continue; seen.add(s);
      const v = rapmOf(k, s); if (!v) continue; const j = rsRowOf(k, s); list.push({...v, w: j!=null ? P.sec[j] : 0}); }
    if (!list.length) return {n:0, avg:NaN, avgO:NaN, avgD:NaN, best:null, top10:0, top25:0, list};
    const W = list.reduce((a,x)=>a+x.w,0) || 1, wa = f => list.reduce((a,x)=>a+f(x)*x.w,0)/W;
    const best = list.slice().sort((a,b)=>b.r-a.r)[0];
    return {n:list.length, avg:wa(x=>x.r), avgO:wa(x=>x.o), avgD:wa(x=>x.d), best, list,
            top10:list.filter(x=>x.rank<=10).length, top25:list.filter(x=>x.rank<=25).length};
  }

  /* Peak + decade data (our Chip Equity: best 2- to 5-season windows and one fit per decade): career-level, no seasons attached.
     Peak windows are for career comparisons. Decade Chip Equity is only a stand-in for player strength in seasons
     without single-season Chip Equity; it is never shown as a season's value. */
  // ranks on the number as shown (one decimal): equal shown values share a rank, the next one skips (1, 1, 3)
  const shown = (v, dec = 1) => Number.isFinite(v) ? +v.toFixed(dec) : -Infinity;
  function tieRank(items, key = x => x.r, field = "rank", dec = 1){
    const a = items.slice().sort((x, y) => shown(key(y), dec) - shown(key(x), dec));
    let prev = null, rk = 0; a.forEach((x, i) => { const v = shown(key(x), dec); if (v !== prev){ rk = i + 1; prev = v; } x[field] = rk; });
    return a;
  }
  const PEAK = DATA.peak || {ds:[], n:[], rows:[]};
  const peakMap = new Map();
  for (const [k,j,o,d,r,rank] of PEAK.rows){ let a = peakMap.get(k); if (!a){ a = []; peakMap.set(k, a); } a[j] = {o,d,r,rank,n:PEAK.n[j],ds:PEAK.ds[j]}; }
  const PEAK_DS = PEAK.ds;
  { const lists = PEAK_DS.map(() => []); for (const a of peakMap.values()) a.forEach((v, j) => { if (v) lists[j].push(v); });
    lists.forEach(l => { tieRank(l); tieRank(l, v => v.o, "orank"); tieRank(l, v => v.d, "drank"); l.forEach(v => v.n = l.length); }); }
  const peakOf = (k, name) => { const a = peakMap.get(k); const j = PEAK_DS.indexOf(name); return a && j>=0 ? (a[j] || null) : null; };
  // which decade lists a season belongs to (boundary seasons like 2009-10 appear in both)
  const decadesOf = s => { const y = +S[s].slice(0,4); const d = Math.floor(y/10)*10; return y%10===9 ? [`${d}s Chip Equity`, `${d+10}s Chip Equity`] : [`${d}s Chip Equity`]; };
  function decOf(k, s){
    const v = decadesOf(s).map(n=>peakOf(k,n)).filter(Boolean);
    if (!v.length) return null;
    const m = f => v.reduce((a,x)=>a+x[f],0)/v.length;
    return {o:m("o"), d:m("d"), r:m("r"), label: v.length>1 ? v.map(x=>x.ds.slice(0,5)).join("/") : v[0].ds.slice(0,5)};
  }

  /* 1- to 5-year Chip Equity windows (our Chip Equity, regular season only). A window "ending" in season s covers s and the
     season(s) before it. Stored per player per ending season. */
  const RW = DATA.rw || {rows:[], n:{}};
  const rwMap = new Map();
  for (const [k,s,w,o,d,r,rank,poss] of RW.rows) rwMap.set((k*64+s)*8+w, {o,d,r,rank,poss,s,w,n:RW.n[s+"_"+w]||null});
  { const g = new Map(); for (const v of rwMap.values()){ const key = v.s*8 + v.w; (g.get(key) || g.set(key, []).get(key)).push(v); }
    for (const l of g.values()){ tieRank(l); tieRank(l, v => v.o, "orank"); tieRank(l, v => v.d, "drank"); l.forEach(v => v.n = l.length); } }
  const rwOf = (k, s, w) => rwMap.get((k*64+s)*8+w) || null;
  // regular-season-only 3-year Chip Equity used by the playoff model (the displayed numbers include playoff games)
  const rwmMap = new Map(); for (const [k,s,r] of (DATA.rwm||[])) rwmMap.set(k*64+s, r);
  const rwmOf = (k, s) => rwmMap.has(k*64+s) ? rwmMap.get(k*64+s) : null;
  const rwSeries = (k, w) => { const out=[]; for (let s=0;s<S.length;s++){ const v = rwOf(k,s,w); if (v) out.push(v); } return out; };

  function sumRows(rows){
    const a = {gp:0,sec:0,pts:0,reb:0,ast:0,stl:0,blk:0,tov:0,fg2a:0,fg3a:0,fg3m:0,fta:0,pos:0,ptsAdded:0};
    for (const i of rows){
      for (const k of ["gp","sec","pts","reb","ast","stl","blk","tov","fg2a","fg3a","fg3m","fta","pos"]) a[k] += P[k][i];
      a.ptsAdded += P.pts[i] - 2*lgTS(P.s[i])*(P.fg2a[i]+P.fg3a[i]+0.44*P.fta[i]);
    }
    const tsa = a.fg2a + a.fg3a + 0.44*a.fta;
    a.ts = tsa ? a.pts/(2*tsa) : NaN;
    a.rts = tsa ? a.ptsAdded/(2*tsa) : NaN;             // true shooting relative to league average
    const p75 = v => a.pos ? v/a.pos*75 : NaN;
    a.p75 = { pts:p75(a.pts), reb:p75(a.reb), ast:p75(a.ast), stl:p75(a.stl), blk:p75(a.blk), tov:p75(a.tov), fg3m:p75(a.fg3m), fta:p75(a.fta) };
    return a;
  }

  const possv = n => /s$/i.test(n) ? n + "'" : n + "'s";
  const ordinal = n => n + (n%100>=11&&n%100<=13 ? "th" : ({1:"st",2:"nd",3:"rd"}[n%10] || "th"));

  /* ---------------- playoff results ---------------- */
  const seriesIn = s => SERIES.filter(x=>x.s===s);
  const teamPath = (s, a) => SERIES.filter(x=>x.s===s && (x.w===a || x.l===a)).sort((x,y)=>x.round-y.round);
  const findSeries = (s, a, b) => SERIES.find(x=>x.s===s && ((x.w===a && x.l===b) || (x.w===b && x.l===a))) || null;
  function playoffResume(ti){
    const r = tm[ti], pi = teamRow(r.a, r.s, 1);
    const path = teamPath(r.s, r.a);
    if (pi<0 || !path.length) return {made:false, path:[]};
    let wins=0, losses=0, oppNet=0, games=0;
    for (const x of path){
      const won = x.w===r.a, opp = won ? x.l : x.w, g = x.ww + x.lw, oi = teamRow(opp, r.s, 0);
      if (oi>=0) oppNet += tm[oi].net * g;
      games += g; wins += won ? x.ww : x.lw; losses += won ? x.lw : x.ww;
    }
    const oppAvg = games ? oppNet/games : 0;
    const last = path[path.length-1];
    const champ = last.round===4 && last.w===r.a;
    return {made:true, path, wins, losses, games, net: tm[pi].net, oppAvg, adj: tm[pi].net + oppAvg, champ,
            exit: champ ? "Won the title" : `Lost in the ${ROUND_NAME[last.round]}`};
  }

  /* ---------------- team strength + matchup ---------------- */
  // weights fit on all 390 playoff series 2001-2026 (log loss); wStar = points per 100 per point of top-2 Chip Equity gap, only when both seasons have Chip Equity
  const cerm = new Map(); for (const [k,s,v] of (DATA.cerm || [])) cerm.set(k*64+s, v);   // Chip Equity, regular-season-only 3-year Chip Equity
  const PARAMS = Object.assign({ k:1.0, wNet:0.66, wAv:0.38, wRot:0, wStar:0.75, wDec:0.5, starSrc:"w2prev", starMode:"top3", wTop:0.41, wRapm:0, wLuck:0.31, starN:2, wPO:0.25, hca:2.5, sigma:12 }, PARAMS_IN||{});
  const rosterIdx = new Map();
  for (let i=0;i<NP;i++){ const kk = P.tm[i]+"|"+P.s[i]+"|"+P.t[i]; (rosterIdx.get(kk) || rosterIdx.set(kk, []).get(kk)).push(i); }
  rosterIdx.forEach(v => v.sort((x,y)=>P.sec[y]-P.sec[x]));
  const rosterCache = new Map();
  function roster(ti){
    if (rosterCache.has(ti)) return rosterCache.get(ti);
    const r = tm[ti], rows = rosterIdx.get(r.a+"|"+r.s+"|"+r.t) || [];
    const top8 = rows.slice(0,8);
    let num=0, den=0;
    for (const i of top8){ const v = nz(P.oo[i]) - nz(P.od[i]); if (!Number.isNaN(v)){ num += v*P.sec[i]; den += P.sec[i]; } }
    const rotNet = den ? num/den : r.net;
    let exp = 0;
    for (const i of top8) for (const j of rowsByPlayer[P.p[i]]) if (P.t[j]===1 && P.s[j] < r.s) exp += P.gp[j];
    // Chip Equity (regular season only, never sees the playoffs)
    const rv = i => { const v = rapmOf(P.p[i], r.s); return v ? v.r : NaN; };
    const covered = hasRapm(r.s);
    const ranked = rows.filter(i=>P.sec[i] >= 500*60 && !Number.isNaN(rv(i))).sort((x,y)=>rv(y)-rv(x));
    const starRows = ranked.slice(0, PARAMS.starN || 2);
    const star = starRows.length ? starRows.reduce((a,i)=>a+rv(i),0)/starRows.length : NaN;
    // player-strength stand-in: decade Chip Equity, or the 2y/3y Chip Equity window ending this season (or last season)
    const src = PARAMS.starSrc || "w2";
    const dv = i => { const k = P.p[i];
      if (src === "dec"){ const v = decOf(k, r.s); return v ? v.r : NaN; }
      const w = (src==="w3" || src==="w3prev") ? 3 : 2, s = /prev$/.test(src) ? r.s-1 : r.s;
      const v = s >= 0 ? rwOf(k, s, w) : null; return v ? v.r : NaN; };
    const dRanked = rows.filter(i=>P.sec[i] >= 500*60 && !Number.isNaN(dv(i))).sort((x,y)=>dv(y)-dv(x));
    const decRows = dRanked.slice(0, PARAMS.starN || 2);
    const decStar = decRows.length ? decRows.reduce((a,i)=>a+dv(i),0)/decRows.length : NaN;
    // top 3 performers: 3-year Chip Equity (window ending LAST season, so it never sees these playoffs) x share of the game on the floor
    const teamSec = r.gp * 48 * 60;
    const t3s = PARAMS.t3Prev ? r.s-1 : r.s;   // our Chip Equity is regular season only, so the window ending this season never sees these playoffs
    const r3 = i => { const v = t3s >= 0 ? rwmOf(P.p[i], t3s) : null; return v==null ? NaN : v; };
    const floor = i => Math.min(1, P.sec[i] / teamSec);
    // top 3 by Chip Equity (data.json cerm, load/ce_build2.py); falls back to Chip Equity x floor share
    const impact = i => { const v = cerm.get(P.p[i]*64 + r.s); return v != null ? v : r3(i) * floor(i); };
    const t3Pool = rows.filter(i => !Number.isNaN(r3(i)) && P.sec[i] >= 300*60).sort((x,y) => impact(y) - impact(x));
    const top3 = t3Pool.slice(0, 3);
    const top3Score = top3.length ? top3.reduce((a,i)=>a+impact(i),0) : NaN;          // points per 100 the top 3 add, given their minutes
    const top3Info = top3.map(i => ({ i, r3: r3(i), floor: floor(i), impact: impact(i), mpg: P.sec[i]/60/P.gp[i], w: (v => v==null ? null : {r:v})(rwmOf(P.p[i], t3s)) }));
    const best = top3.length ? top3 : top8.slice(0,3);
    // minutes-weighted team Chip Equity: roughly the net rating the roster "should" have (players without Chip Equity count as average)
    let rs=0, ss=0; for (const i of rows){ ss += P.sec[i]; const v = rv(i); if (!Number.isNaN(v)) rs += v*P.sec[i]; }
    const teamRapm = covered && ss ? 5*rs/ss : NaN;
    const out = {rows, top8, rotNet, exp, best, starRows, star, decRows, decStar, teamRapm, covered, top3, top3Score, top3Info};
    rosterCache.set(ti, out);
    return out;
  }
  const Phi = x => { const t = 1/(1+0.2316419*Math.abs(x)), d = 0.3989422804014327*Math.exp(-x*x/2);
    const p = d*t*(0.3193815+t*(-0.3565638+t*(1.781478+t*(-1.821256+t*1.330274)))); return x>0 ? 1-p : p; };
  function seriesDist(pGame, need=4){
    const out = {A:new Array(need).fill(0), B:new Array(need).fill(0)};
    const walk = (wa, wb, pr) => {
      if (wa===need){ out.A[wb] += pr; return; }
      if (wb===need){ out.B[wa] += pr; return; }
      const p = pGame(wa+wb+1); walk(wa+1, wb, pr*p); walk(wa, wb+1, pr*(1-p));
    };
    walk(0,0,1);
    return out;   // out.A[j] = P(A wins in need+j games)
  }
  // home pattern 2-2-1-1-1 (best-of-7) / 2-2-1 (best-of-5)
  const hostOf = (g, home, need) => home==="N" ? 0 : ((need===4 ? [1,2,5,7] : [1,2,5]).includes(g) ? (home==="A"?1:-1) : (home==="A"?-1:1));
  // mode: "season" = both seasons have single-season Chip Equity; "decade" = fall back to decade Chip Equity for both; null = neither
  function availOf(ti, oi){
    const r = tm[ti], o = oi!=null ? tm[oi] : null;
    if (o && o.s === r.s && r.t === 0){ const v = availMap.get(`${r.s}|${r.a}|${o.a}`); if (v!=null) return v; }
    const v = T.late ? T.late[ti] : null; return v==null ? NaN : v;
  }
  function strengthParts(ti, crossSeason, prm, mode, oi){
    const r = tm[ti], ro = roster(ti);
    const av = availOf(ti, oi);
    const star = mode==="season" ? prm.wStar*ro.star : mode==="decade" ? (prm.starMode==="top3" ? prm.wTop*ro.top3Score : prm.wDec*ro.decStar) : 0;
    const parts = {net: (prm.wNet==null?1:prm.wNet)*r.net, avail: Number.isNaN(av) ? 0 : (prm.wAv||0)*av, availRaw: av, rot: prm.wRot*(ro.rotNet - r.net), star: star || 0,
                   rapm: mode==="season" && prm.wRapm ? prm.wRapm*(ro.teamRapm - r.net) : 0, luck: prm.wLuck*r.luck*100, po: 0};
    let res = null;
    if (crossSeason){ res = playoffResume(ti); if (res.made){ const relia = Math.min(1, res.games/16); parts.po = prm.wPO*relia*(res.adj - r.net); } }
    parts.total = parts.net + parts.avail + parts.rot + parts.star + parts.rapm + parts.luck + parts.po;
    return {parts, roster: ro, resume: res};
  }
  function probs(ia, ib, home, prm, crossSeason, need=4){
    const ra = roster(ia), rb = roster(ib);
    const mode = (hasRapm(tm[ia].s) && hasRapm(tm[ib].s) && !Number.isNaN(ra.star) && !Number.isNaN(rb.star) && !prm.forceDecade) ? "season"
               : (prm.starMode==="top3" ? (!Number.isNaN(ra.top3Score) && !Number.isNaN(rb.top3Score) && prm.wTop)
                                        : (!Number.isNaN(ra.decStar) && !Number.isNaN(rb.decStar) && prm.wDec)) ? "decade" : null;
    const useRapm = mode !== null;
    const A = strengthParts(ia, crossSeason, prm, mode, ib), B = strengthParts(ib, crossSeason, prm, mode, ia);
    const poss = (tm[ia].pace + tm[ib].pace)/2;
    const m = prm.k*(A.parts.total - B.parts.total)*poss/100;
    const pGame = g => Phi((m + hostOf(g, home, need)*prm.hca)/prm.sigma);
    const dist = seriesDist(pGame, need);
    const pA = dist.A.reduce((x,y)=>x+y,0);
    return {A, B, poss, m, pGame, dist, pA, useRapm, mode};
  }

  /* backtest on every real series: home court to the better record (2019-20 bubble = neutral) */
  function homeFor(x){
    if (S[x.s]==="2019-20") return "N";
    const a = tm[teamRow(x.w, x.s, 0)], b = tm[teamRow(x.l, x.s, 0)];
    if (a.wpct !== b.wpct) return a.wpct > b.wpct ? "A" : "B";
    return a.net >= b.net ? "A" : "B";
  }
  const needFor = x => (x.round===1 && +S[x.s].slice(0,4) <= 2001) ? 3 : 4;   // first round was best-of-5 through 2002
  function backtest(prmIn, filter){
    const prm = Object.assign({}, PARAMS, prmIn||{});
    let n=0, ll=0, br=0, acc=0; const bins = [[0.5,0.6],[0.6,0.75],[0.75,0.9],[0.9,1.01]].map(([lo,hi])=>({lo,hi,n:0,won:0,p:0}));
    for (const x of SERIES){
      if (filter && !filter(x)) continue;
      const ia = teamRow(x.w, x.s, 0), ib = teamRow(x.l, x.s, 0); if (ia<0||ib<0) continue;
      const pW = probs(ia, ib, homeFor(x), prm, false, needFor(x)).pA;
      n++; ll += -Math.log(Math.max(1e-9,pW)); br += (1-pW)**2; if (pW>0.5) acc++;
      const fav = Math.max(pW, 1-pW), favWon = pW>=0.5;
      const bin = bins.find(b=>fav>=b.lo && fav<b.hi); if (bin){ bin.n++; bin.p+=fav; if (favWon) bin.won++; }
    }
    return {n, logloss: ll/n, brier: br/n, acc: acc/n, bins};
  }

  /* full matchup with reasons */
  function matchup(ia, ib, home, names){
    const A = tm[ia], B = tm[ib], LA = leagueOf(A), LB = leagueOf(B);
    const cross = A.s !== B.s;
    const pr = probs(ia, ib, home, PARAMS, cross, 4);
    const rA = pr.A.roster, rB = pr.B.roster;
    const {m, poss, pGame, dist, pA} = pr, pB = 1-pA;
    const outcomes = [...dist.A.map((p,j)=>({team:"A", games:4+j, p})), ...dist.B.map((p,j)=>({team:"B", games:4+j, p}))];
    const likely = outcomes.slice().sort((x,y)=>y.p-x.p)[0];
    const expGames = outcomes.reduce((a,o)=>a+o.games*o.p,0);
    const lgAvg = (LA.off + LB.off)/2;
    const ortgA = lgAvg + (A.off-LA.off) + (B.def-LB.off), ortgB = lgAvg + (B.off-LB.off) + (A.def-LA.off);
    const total = (ortgA + ortgB)*poss/100;
    const score = {A: total/2 + m/2, B: total/2 - m/2};

    const fav = m >= 0 ? "A" : "B", dog = fav==="A" ? "B" : "A", oth = x => x==="A" ? "B" : "A";
    const N = {A:names.A, B:names.B}, SN = {A:names.sA||names.A, B:names.sB||names.B}, R = {A, B}, RO = {A:rA, B:rB}, LL = {A:LA, B:LB}, PRT = {A:pr.A, B:pr.B};
    const rk = (x, metric) => `${ordinal(R[x].rank[metric])} of ${LL[x].n}`;
    const sign = v => (v>=0?"+":"") + v.toFixed(1);
    const inSeason = x => cross ? ` in ${S[R[x].s]}` : "";
    const reasons = [];
    const rec = x => R[x].w!=null ? `${R[x].w}-${R[x].l}` : "";
    reasons.push({tag:"Strength", text:`Net rating: ${N.A} ${sign(A.net)} per 100 possessions (${rk("A","net")}${inSeason("A")}, ${rec("A")}), ${N.B} ${sign(B.net)} (${rk("B","net")}${inSeason("B")}, ${rec("B")}).`});
    if (Math.abs(A.luck) >= 0.05 || Math.abs(B.luck) >= 0.05){
      const x = Math.abs(A.luck) >= Math.abs(B.luck) ? "A" : "B", w = Math.round(R[x].luck*(R[x].w+R[x].l));
      reasons.push({tag:"Record", text:`${N[x]} (${rec(x)}) won ${Math.abs(w)} ${w>0?"more":"fewer"} games than point differential predicts. In past playoffs, teams that beat their point differential did a bit better than their net rating alone suggests, so the model ${w>0?"adds":"takes away"} about ${Math.abs(R[x].luck*100*PARAMS.wLuck*PARAMS.k).toFixed(1)} points per 100.`});
    }
    const rotShift = (rA.rotNet - A.net) - (rB.rotNet - B.net);
    if (Math.abs(rotShift) >= 1.5){ const who = rotShift > 0 ? "A" : "B";
      reasons.push({tag:"Rotation", text:`Top 8 on the floor: ${N[who]} ${sign(RO[who].rotNet)} per 100, against ${sign(R[who].net)} for the full season, so ${N[who]} gain more when playoff rotations shrink.${PARAMS.wRot ? "" : " Context only: it added nothing in testing."}`}); }
    else reasons.push({tag:"Rotation", text:`Top 8 on the floor: ${N.A} ${sign(rA.rotNet)} per 100, ${N.B} ${sign(rB.rotNet)}. Shorter playoff rotations don't change much here.`});
    const side = (o, d) => {
      const oz = z(R[o],"off"), dz = -z(R[d],"def"), exp = (R[o].off - LL[o].off) + (R[d].def - LL[d].off), edge = oz - dz;
      const who = Math.abs(edge) < 0.35 ? "Even matchup" : (edge>0 ? `Edge: ${N[o]}` : `Edge: ${N[d]}`);
      const proj = Math.abs(exp) < 0.05 ? "right at league average" : `${Math.abs(exp).toFixed(1)} points per 100 ${exp>0?"above":"below"} league average`;
      return {tag:`${SN[o]} offense`, text:`${N[o]} offense ${sign(R[o].off-LL[o].off)} vs. league (${rk(o,"off")}) against ${N[d]} defense ${sign(R[d].def-LL[d].off)} (${rk(d,"def")}). Projected: ${proj}. ${who}.`};
    };
    reasons.push(side("A","B"), side("B","A"));
    reasons.push({tag:"Shooting vs. league", text:`True shooting relative to each league: ${N.A} ${sign(A.rts*100)} (${rk("A","rts")}${inSeason("A")}), ${N.B} ${sign(B.rts*100)} (${rk("B","rts")}${inSeason("B")}).`});
    const battles = [];
    for (const [o,d] of [["A","B"],["B","A"]]){
      const O = R[o], D = R[d];
      battles.push({tag:"Turnovers", edge: -z(O,"tov") - z(D,"stl"), o, d, lever:["taking care of the ball","forcing turnovers"],
        text:`${N[o]} turnover rate ${O.tov.toFixed(1)}% (${rk(o,"tov")}) vs. ${N[d]} ${D.stl.toFixed(1)} steals per 100 (${rk(d,"stl")}).`});
      battles.push({tag:"Second chances", edge: z(O,"oreb") - z(D,"dreb"), o, d, lever:["offensive rebounding","finishing possessions with defensive rebounds"],
        text:`${N[o]} offensive rebound rate ${O.oreb.toFixed(1)}% (${rk(o,"oreb")}) vs. ${N[d]} defensive rebound rate ${D.dreb.toFixed(1)}% (${rk(d,"dreb")}).`});
      battles.push({tag:"Free throws", edge: z(O,"ftr") + z(D,"fouls"), o, d, lever:["getting to the free-throw line","defending without fouling"],
        text:`${N[o]} ${O.ftr.toFixed(1)} free throws per 100 shots (${rk(o,"ftr")}) vs. ${N[d]} ${D.fouls.toFixed(1)} shooting fouls per 100 (${D.rank.fouls===1 ? "fewest" : ordinal(D.rank.fouls)+"-fewest"}).`});
    }
    battles.sort((x,y)=>Math.abs(y.edge)-Math.abs(x.edge));
    for (const b of battles.slice(0,2)){ if (Math.abs(b.edge) < 0.5) continue; reasons.push({tag:b.tag, text:`${b.text} Edge: ${N[b.edge > 0 ? b.o : b.d]}.`}); }
    // impact players by Chip Equity (regular season)
    const pname = i => DATA.names[P.p[i]];
    const rp = i => rapmOf(P.p[i], P.s[i]);
    const starTxt = x => RO[x].starRows.map(i=>`${pname(i)} ${sign(rp(i).r)}`).join(", ");
    const starGap = rA.star - rB.star;
    const inOdds = pr.mode==="season" && (PARAMS.wStar || PARAMS.wRapm);
    const srcW = /3/.test(PARAMS.starSrc) ? 3 : 2, srcPrev = /prev$/.test(PARAMS.starSrc);
    const decTxt = x => RO[x].decRows.map(i=>{ const k = P.p[i], s0 = srcPrev ? R[x].s-1 : R[x].s; const v = s0>=0 ? rwOf(k, s0, srcW) : null; return v ? `${pname(i)} ${sign(v.r)}` : pname(i); }).join(", ");
    const spanTxt = x => { const e = srcPrev ? R[x].s-1 : R[x].s; if (e < 0) return ""; const y = +S[e].slice(0,4) + 1; return `${S[Math.max(0,e-srcW+1)]} to ${S[e]}`; };
    const t3Txt = x => RO[x].top3Info.map(p => `${pname(p.i)} ${sign(p.r3)} × ${Math.round(p.floor*100)}% of minutes = ${sign(p.impact)}`).join(", ");
    const prevSpan = x => R[x].s > 0 ? `${+S[R[x].s-1].slice(0,4)-2}–${S[R[x].s-1].slice(-2)}` : "";
    if (pr.mode==="decade"){
      const gap = rA.top3Score - rB.top3Score;
      reasons.push({tag:"Top performers", text:`${N.A}: ${RO.A.top3Info.map(p=>pname(p.i)).join(", ")}. ${N.B}: ${RO.B.top3Info.map(p=>pname(p.i)).join(", ")}. ${Math.abs(gap) < 0.5 ? "About even." : `Edge: ${N[gap>0?"A":"B"]}.`}`});
    } else if (!rA.top3.length || !rB.top3.length){
      reasons.push({tag:"Top 3 performers", text:`No 3-year Chip Equity for ${!rA.top3.length ? N.A : N.B}, so player impact is left out of the odds.`});
    } else if (rA.covered || rB.covered){
      const missing = [rA.covered ? null : "A", rB.covered ? null : "B"].filter(Boolean).map(x=>`no Chip Equity data for ${N[x]}'s season`).join("; ");
      reasons.push({tag:"Impact (Chip Equity)", text: missing ? `Top Chip Equity players: ${["A","B"].filter(x=>RO[x].covered).map(x=>`${N[x]} ${starTxt(x)}`).join(" · ")}. ${missing[0].toUpperCase()+missing.slice(1)}, so Chip Equity is left out of the odds.`
        : `Top two players by regular-season Chip Equity (points per 100 possessions above an average player): ${N.A} ${starTxt("A")} · ${N.B} ${starTxt("B")}. Minutes-weighted roster Chip Equity: ${N.A} ${sign(rA.teamRapm)}, ${N.B} ${sign(rB.teamRapm)}. ${Math.abs(starGap) < 0.5 ? "About even at the top." : `Edge at the top: ${N[starGap>0?"A":"B"]}.`}${inOdds ? "" : " Shown as context; it isn't part of the odds."}`});
    }
    { const avA = PRT.A.parts.availRaw, avB = PRT.B.parts.availRaw;
      if (!Number.isNaN(avA) && !Number.isNaN(avB) && PARAMS.wAv){
        const gap = avA - avB;
        reasons.push({tag:"Available roster", text:`Roster Chip Equity weighted by who was actually playing going in (last 15 games, or the earlier playoff rounds): ${N.A} ${sign(avA)}, ${N.B} ${sign(avB)}. ${Math.abs(gap) < 1 ? "About even." : `Edge: ${N[gap>0?"A":"B"]}.`}`});
      } }
    // playoff résumé for cross-season matchups
    if (cross){
      const resTxt = x => { const rs = PRT[x].resume; if (!rs || !rs.made) return `${N[x]} missed the playoffs`;
        return `${N[x]} went ${rs.wins}-${rs.losses} in the playoffs (${rs.exit.toLowerCase()}), ${sign(rs.net)} per 100, ${sign(rs.adj)} after adjusting for opponents`; };
      reasons.push({tag:"Playoff résumé", text:`${resTxt("A")}. ${resTxt("B")}. Because these teams are from different seasons, the model gives each team's playoff run some weight.`});
    }
    const ea = rA.exp, eb = rB.exp;
    if (Math.abs(ea-eb) >= 40){ const w = ea>eb ? "A":"B";
      reasons.push({tag:"Experience", text:`Career playoff games for the top 8 before this season: ${N[w]} ${Math.max(ea,eb)}, ${N[oth(w)]} ${Math.min(ea,eb)}${Math.min(A.s,B.s) < 10 ? " (counted from 1996-97, so late-1990s teams are undercounted)" : ""}.`}); }
    const fast = A.pace >= B.pace ? "A" : "B";
    reasons.push({tag:"Tempo", text: Math.abs(A.pace-B.pace) < 0.5 ? `Expect about ${Math.round(poss)} possessions a game. Both teams play at almost the same pace.`
      : `Expect about ${Math.round(poss)} possessions a game. Faster team: ${N[fast]} (${R[fast].pace.toFixed(1)} vs ${R[oth(fast)].pace.toFixed(1)}).`});
    const d = R[dog];
    const dogEdges = battles.filter(b => (b.edge>0 ? b.o : b.d) === dog && Math.abs(b.edge) >= 0.5);
    let path;
    if (z(d,"par3") > 0.5) path = `${N[dog]} three-point share: ${d.par3.toFixed(1)}% of shots (${d.rank.par3===1 ? "most" : ordinal(d.rank.par3)+"-most"}), so a hot shooting series is the best route to an upset.`;
    else if (dogEdges.length){ const b = dogEdges[0]; path = `Best route for ${N[dog]}: ${b.o===dog ? b.lever[0] : b.lever[1]}, where this matchup favors them.`; }
    else if (RO[dog].starRows.length && RO[fav].starRows.length && rp(RO[dog].starRows[0]).r > rp(RO[fav].starRows[0]).r + 0.5) path = `Best route for ${N[dog]}: a takeover series from ${pname(RO[dog].starRows[0])}, the highest-Chip Equity player in the series.`;
    else path = `Best route for ${N[dog]}: winning the possession battles (turnovers and rebounds) to close the gap.`;
    reasons.push({tag:"Upset path", text:path});
    if (home!=="N") reasons.push({tag:"Home court", text:`${N[home]} (Games 1, 2, 5 and 7), worth about ${PARAMS.hca} points a game.`});
    if (cross) reasons.push({tag:"Different seasons", text:`Every rating is measured against its own season's league average, so eras compare fairly.`});

    // tale of the tape
    const tapeDefs = [
      ["Record","wpct",()=>null], ["Net rating","net",v=>sign(v)], ["Offensive rating","off",v=>v.toFixed(1)], ["Defensive rating","def",v=>v.toFixed(1)],
      ["True shooting vs. league","rts",v=>sign(v*100)], ["Effective FG%","efg",v=>(v*100).toFixed(1)+"%"], ["Turnover rate","tov",v=>v.toFixed(1)+"%"],
      ["Off. rebound rate","oreb",v=>v.toFixed(1)+"%"], ["Def. rebound rate","dreb",v=>v.toFixed(1)+"%"], ["Free throws per 100 shots","ftr",v=>v.toFixed(1)],
      ["Steals per 100","stl",v=>v.toFixed(1)], ["Blocks per 100","blk",v=>v.toFixed(1)], ["3-point attempt share","par3",v=>v.toFixed(1)+"%"], ["Pace","pace",v=>v.toFixed(1)]];
    const tape = tapeDefs.map(([label, mtr, f]) => {
      const hb = TEAM_METRICS[mtr], ra = rel(A,mtr), rb = rel(B,mtr);
      let better = null; if (hb !== null && Math.abs(ra-rb) > 1e-9) better = (hb ? ra>rb : ra<rb) ? "A" : "B";
      const show = (r) => mtr==="wpct" ? `${r.w}-${r.l}` : f(r[mtr]);
      return {label, a:show(A), b:show(B), ra:A.rank[mtr], rb:B.rank[mtr], better};
    });
    tape.push({label:"Top-8 on-court net", a:sign(rA.rotNet), b:sign(rB.rotNet), ra:null, rb:null, better: Math.abs(rA.rotNet-rB.rotNet)<1e-9?null:(rA.rotNet>rB.rotNet?"A":"B")});
    if (rA.covered && rB.covered){
      tape.push({label:"Top-2 player Chip Equity", a:sign(rA.star), b:sign(rB.star), ra:null, rb:null, better: Math.abs(rA.star-rB.star)<0.05?null:(rA.star>rB.star?"A":"B")});
      tape.push({label:"Roster Chip Equity (minutes-weighted)", a:sign(rA.teamRapm), b:sign(rB.teamRapm), ra:null, rb:null, better: Math.abs(rA.teamRapm-rB.teamRapm)<0.05?null:(rA.teamRapm>rB.teamRapm?"A":"B")});
    }
    tape.push({label:"Prior playoff games (top 8)", a:String(ea), b:String(eb), ra:null, rb:null, better: ea===eb?null:(ea>eb?"A":"B")});

    // what actually happened
    const actual = { same: !cross, series: cross ? null : findSeries(A.s, A.a, B.a), pathA: playoffResume(ia), pathB: playoffResume(ib) };
    if (actual.series){
      const x = actual.series, winSide = x.w===A.a ? "A" : "B", games = x.ww + x.lw;
      const o = outcomes.find(q=>q.team===winSide && q.games===games);
      actual.winSide = winSide; actual.games = games; actual.pWinner = winSide==="A" ? pA : pB; actual.pExact = o ? o.p : null;
    }
    return {A, B, LA, LB, rA, rB, useRapm: pr.useRapm, mode: pr.mode, parts:{A:pr.A.parts, B:pr.B.parts}, poss, m, pGame, host:g=>hostOf(g,home,4), dist, pA, pB, outcomes, likely, expGames, score, fav, dog, reasons, tape, actual,
            single:{neutral:Phi(m/PARAMS.sigma), homeA:Phi((m+PARAMS.hca)/PARAMS.sigma), homeB:Phi((m-PARAMS.hca)/PARAMS.sigma)}};
  }

  return {tieRank, S, P, T, tm, lg, LGA, leagueOf, rel, z, teamIdx, teamRow, MIN_SEC, possv, PEAK_DS, peakOf, decOf, decadesOf, rwOf, rwSeries,
          rowsByPlayer, rowsOf, rsRowOf, sumRows, rapmOf, rapmRow, rapmPool, rapmSeasons, hasRapm, rapmSummary, RAPM_SRC: CEPM.src,
          roster, matchup, probs, backtest, homeFor, needFor, Phi, seriesDist, ordinal,
          SERIES, seriesIn, teamPath, findSeries, playoffResume, ROUND_NAME, PARAMS, lgTS};
}
if (typeof module !== "undefined") module.exports = { buildModel };
