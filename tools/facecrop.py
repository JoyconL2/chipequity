"""For each Commons photo: fetch a 960px version, find faces (OpenCV), keep only photos with one clear face,
and work out a headshot crop (1040:760, face about 38% of the width, eyes in the upper part).
Writes wiki_faces.json {nbaId: [url, x0, y0, cw, ch, credit]} with the crop as fractions of the image."""
import json, subprocess, urllib.parse, time, re, html, os, cv2
UA = "chipequity-check/1.0 (github.com/JoyconL2/chipequity)"
M = json.load(open("alt_headshots.json")); W = [(p, v[1:]) for p, v in M.items() if v[0] == "w"]
def api(titles, width):
    q = urllib.parse.urlencode({"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": width, "titles": titles, "redirects": 1})
    for t in range(5):
        r = subprocess.run(["curl", "-s", "-A", UA, "https://commons.wikimedia.org/w/api.php?" + q], capture_output=True, text=True).stdout
        try: return json.loads(r)
        except Exception: time.sleep(5)
info = {}
strip = lambda s: html.unescape(re.sub("<[^>]+>", "", s or "")).strip()
for i in range(0, len(W), 40):
    J = api("|".join("File:" + f for p, f in W[i:i+40]), 500)
    norm = {n["to"]: n["from"] for n in J["query"].get("normalized", [])}; red = {n["to"]: n["from"] for n in J["query"].get("redirects", [])}
    for pg in J["query"]["pages"].values():
        t = pg["title"]; t0 = norm.get(red.get(t, t), red.get(t, t)); ii = (pg.get("imageinfo") or [{}])[0]; md = ii.get("extmetadata", {})
        info[t0[5:]] = {"u": (ii.get("thumburl") or ii.get("url") or "").split("?")[0], "W": ii.get("width"), "a": strip(md.get("Artist", {}).get("value"))[:60], "l": strip(md.get("LicenseShortName", {}).get("value"))}
    time.sleep(1)
fc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
os.makedirs("img", exist_ok=True); os.makedirs("crop", exist_ok=True)
out, why = {}, {}
for j, (p, f) in enumerate(W):
    d = info.get(f)
    if not d or not d["u"]: why[p] = "no info"; continue
    fn = f"img/{p}.jpg"
    for t in range(3):
        code = subprocess.run(["curl", "-sL", "-m", "30", "-o", fn, "-w", "%{http_code}", "-A", UA, d["u"]], capture_output=True, text=True).stdout
        if code == "200": break
        time.sleep(10)
    time.sleep(1.5)
    if j % 25 == 0: print("progress", j, code, flush=True)
    im = cv2.imread(fn)
    if im is None:
        # PNG/other: let ImageMagick convert
        subprocess.run(["convert", fn + "[0]", fn + ".png"]); im = cv2.imread(fn + ".png")
    if im is None: why[p] = "unreadable " + code; continue
    H, Wd = im.shape[:2]; g = cv2.equalizeHist(cv2.cvtColor(im, cv2.COLOR_BGR2GRAY))
    faces = sorted(fc.detectMultiScale(g, 1.1, 6, minSize=(max(24, Wd // 30), max(24, Wd // 30))), key=lambda r: -r[2] * r[3])
    if len(faces) == 0: why[p] = "no face"; continue
    if len(faces) > 1 and faces[0][2] * faces[0][3] < 2.0 * faces[1][2] * faces[1][3]: why[p] = f"{len(faces)} similar faces"; continue
    x, y, w, h = map(int, faces[0])
    if w < 40: why[p] = "face too small"; continue
    cw = w / 0.38; ch = cw * 760 / 1040
    if cw > Wd: cw = Wd; ch = cw * 760 / 1040
    if ch > H: ch = H; cw = ch * 1040 / 760
    cx = x + w / 2; cy = y + h * 0.5
    x0 = min(max(cx - cw / 2, 0), Wd - cw); y0 = min(max(cy - ch * 0.42, 0), H - ch)
    if cw < 120: why[p] = "too low resolution"; continue
    crop = im[int(y0):int(y0 + ch), int(x0):int(x0 + cw)]; cv2.imwrite(f"crop/{j:03d}_{p}.jpg", cv2.resize(crop, (208, 152)))
    cred = ", ".join(x for x in [d["a"], d["l"]] if x)
    out[p] = [d["u"], round(x0 / Wd, 4), round(y0 / H, 4), round(cw / Wd, 4), round(ch / H, 4), cred, f]
print("kept", len(out), "of", len(W)); import collections; print(collections.Counter(v.split(" ")[0] for v in why.values()))
json.dump(out, open("wiki_faces.json", "w"), ensure_ascii=False, separators=(",", ":"))
