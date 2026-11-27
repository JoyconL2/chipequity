import sys, os, json as _json
d = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(d,'template.html')).read()
data = open(os.path.join(d,'data.json')).read()
# six-factor ratings (factors/factor_rapm.py): single seasons, players with 300+ possessions
_fc = os.path.join(d, '..', 'factors', 'factor_cepm.csv')
if os.path.exists(_fc):
    import csv as _csv
    _D = _json.loads(data); _SI = {x: i for i, x in enumerate(_D["seasons"])}; _K = {int(x): i for i, x in enumerate(_D["ids"])}
    _F = ["o_efg", "o_tov", "o_orb", "o_ftr", "d_efg", "d_tov", "d_orb", "d_ftr"]; _rows = []
    for r in _csv.DictReader(open(_fc)):
        if r["w"] != "1" or float(r["poss"]) < 300: continue
        k, si = _K.get(int(r["player"])), _SI.get(r["window_end"])
        if k is None or si is None: continue
        _rows.append([k, si, int(float(r["poss"]))] + [round(float(r[c]) * 100, 3) for c in _F])
    _pw = _json.load(open(os.path.join(d, '..', 'factors', 'factor_params.json')))["points"]
    _D["fac"] = {"cols": ["k", "s", "poss"] + _F, "rows": _rows, "pts": {c: round(_pw[c] / 100, 4) for c in ("efg", "tov", "orb", "ftr")}}
    data = _json.dumps(_D, separators=(",", ":"))
model = open(os.path.join(d,'model.js')).read()
assert '</script' not in data and '</script' not in model
alt = open(os.path.join(d,'alt_headshots.json')).read().strip() if os.path.exists(os.path.join(d,'alt_headshots.json')) else '{}'
assert '</' not in alt
mtxt = open(os.path.join(d,'METHOD_technical.txt')).read() if os.path.exists(os.path.join(d,'METHOD_technical.txt')) else ''
# JSON.parse reads a big data blob faster than an object literal
page = t.replace('/*__DATA__*/null', 'JSON.parse(' + _json.dumps(data) + ')').replace('/*__MODEL__*/', model).replace('/*__ALTFACES__*/{}', alt).replace('/*__ERAFACES__*/{}', open('era_faces.json').read().strip() if __import__('os').path.exists('era_faces.json') else '{}').replace('/*__METHODTXT__*/""', _json.dumps(mtxt).replace('</', '<\\/'))
open(os.path.join(d,'courtside_page.html'),'w').write(page)
he = page.index('</style>') + len('</style>')
full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        + page[:he] + '\n</head>\n<body>\n' + page[he:] + '\n</body>\n</html>\n')
open(os.path.join(d,'Courtside_Stats.html'),'w').write(full)
print('built', round(len(full)/1e6,2), 'MB')
