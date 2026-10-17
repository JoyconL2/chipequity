// Export every real playoff series with the model's inputs, for fit2.py.  usage: node export_series.js
const {buildModel} = require('../site/model.js'); const D = require('../site/data.json'); const M = buildModel(D);
const out = [];
for (const x of M.SERIES){ const ia = M.teamRow(x.w, x.s, 0), ib = M.teamRow(x.l, x.s, 0); if (ia<0 || ib<0) continue;
  const A = M.tm[ia], B = M.tm[ib], ra = M.roster(ia), rb = M.roster(ib);
  out.push({s:D.seasons[x.s], round:x.round, home:M.homeFor(x), need:M.needFor(x), netA:A.net, netB:B.net, luckA:A.luck*100, luckB:B.luck*100,
    paceA:A.pace, paceB:B.pace, t3A:ra.top3Score, t3B:rb.top3Score, availA:x.aw, availB:x.al, lateA:D.T.late[ia], lateB:D.T.late[ib], expA:ra.exp, expB:rb.exp}); }
require('fs').writeFileSync('series2.json', JSON.stringify(out)); console.log(out.length, 'series');
