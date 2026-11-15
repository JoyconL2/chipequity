import sys, os, json as _json
d = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(d,'template.html')).read()
data = open(os.path.join(d,'data.json')).read()
model = open(os.path.join(d,'model.js')).read()
assert '</script' not in data and '</script' not in model
alt = open(os.path.join(d,'alt_headshots.json')).read().strip() if os.path.exists(os.path.join(d,'alt_headshots.json')) else '{}'
assert '</' not in alt
mtxt = open(os.path.join(d,'METHOD_technical.txt')).read() if os.path.exists(os.path.join(d,'METHOD_technical.txt')) else ''
# JSON.parse reads a big data blob faster than an object literal
page = t.replace('/*__DATA__*/null', 'JSON.parse(' + _json.dumps(data) + ')').replace('/*__MODEL__*/', model).replace('/*__ALTFACES__*/{}', alt).replace('/*__METHODTXT__*/""', _json.dumps(mtxt).replace('</', '<\\/'))
open(os.path.join(d,'courtside_page.html'),'w').write(page)
he = page.index('</style>') + len('</style>')
full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        + page[:he] + '\n</head>\n<body>\n' + page[he:] + '\n</body>\n</html>\n')
open(os.path.join(d,'Courtside_Stats.html'),'w').write(full)
print('built', round(len(full)/1e6,2), 'MB')
