import sys, os
d = os.path.dirname(os.path.abspath(__file__))
t = open(os.path.join(d,'template.html')).read()
data = open(os.path.join(d,'data.json')).read()
model = open(os.path.join(d,'model.js')).read()
assert '</script' not in data and '</script' not in model
page = t.replace('/*__DATA__*/null', data).replace('/*__MODEL__*/', model)
open(os.path.join(d,'courtside_page.html'),'w').write(page)
he = page.index('</style>') + len('</style>')
full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        + page[:he] + '\n</head>\n<body>\n' + page[he:] + '\n</body>\n</html>\n')
open(os.path.join(d,'Courtside_Stats.html'),'w').write(full)
print('built', round(len(full)/1e6,2), 'MB')
