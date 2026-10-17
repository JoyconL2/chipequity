import re, json, sys
s=open('orig.html',encoding='utf-8').read()
man=json.loads(re.search(r'<script type="__bundler/manifest">(.*?)</script>', s, re.S).group(1))
L=open('template.html').read()
st1_a=L.find('<style>'); st1_b=L.find('</style>',st1_a)+8
fonts=L[st1_a:st1_b]
for uid,v in man.items(): fonts=fonts.replace(f'url("{uid}")', f'url("data:{v["mime"]};base64,{v["data"]}")')
theme=L[11754:L.find('</style>',11754)+8]
headmeta=L[:st1_a]
b0=L.find('<body>')+6; hdr=L.find('<header class="top">'); scene=L[b0:hdr]
ls=L.rfind('<script>'); extra=L[ls:L.find('</script>',ls)+9]
P=open('../site/courtside_page.html').read()
my_css=P[P.find('<style>')+7:P.find('</style>')]
need=[]
for blk in ['/* games */','/* game center (live play-by-play) */','/* front page */']:
    i=my_css.find(blk); j=my_css.find('/*', i+len(blk)); need.append(my_css[i:j])
extra_css='<style>\n/* added: games tab + live play-by-play, compact header */\n'+'\n'.join(need)+'\n'+open('overrides.css').read()+'\n</style>'
body_main=P[P.find('</style>')+8:]
body_main=body_main.replace('<h1 class="brand">Courtside <span>Stats</span></h1>','<h1 class="brand">Basketball <span>Done Right</span></h1>')
scene=scene.replace('<div class="ghost">COURTSIDE</div>','<div class="ghost">DONE RIGHT</div>').replace('Courtside // loadout bay 07 // 2000-01 → 2025-26','Basketball Done Right // 1996-97 → 2025-26')
headmeta=headmeta.replace('<title>Courtside Stats — Loadout</title>','<title>Basketball Done Right</title>')
# link preview (iMessage, Discord, X, LinkedIn...): pass your site address as the 2nd argument
SITE = (sys.argv[2] if len(sys.argv) > 2 else "https://YOUR-SITE.netlify.app").rstrip("/")
DESC = ("Every NBA player and team since 1996-97. Chip Equity impact ratings built from every possession, "
        "head-to-head comparisons, playoff series odds that pick 75% of winners, and live games with play-by-play.")
OG = f"""<meta name="description" content="{DESC}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Basketball Done Right">
<meta property="og:title" content="Basketball Done Right">
<meta property="og:description" content="{DESC}">
<meta property="og:url" content="{SITE}/">
<meta property="og:image" content="{SITE}/preview.png">
<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Basketball Done Right">
<meta name="twitter:description" content="{DESC}">
<meta name="twitter:image" content="{SITE}/preview.png">
<meta name="theme-color" content="#3a0a0c">
"""
headmeta=headmeta.replace('<title>Basketball Done Right</title>','<title>Basketball Done Right</title>\n'+OG)
out=headmeta+fonts+theme+extra_css+'\n</head>\n<body>\n'+scene+body_main.strip()+'\n'+extra+'\n</body></html>\n'
open(sys.argv[1],'w').write(out); print('wrote', len(out))
