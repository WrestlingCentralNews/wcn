"""Image dimensions + large-variant finder for Discover (wants >=1200px wide). No AI: probes only the first 64 KB of each
image (Range request) and reads the size from the header. Cache: data/image_sizes.json {feed_url: {best:[url,w,h], v, at}}.

For a feed image that is under 1200px it tries, cheapest first, versions of THE SAME photo:
  1. URL rewrites: WordPress -300x200 / -e1712345678 suffixes removed, CDN resize/crop/fit query params removed or
     bumped (i0.wp.com, Vox/Chorus, wmsports, Static Media l-intro, Wikimedia thumbs, Yahoo embedded originals);
  2. the source article's og:image / twitter:image and the largest <img srcset> entry, only if the file name matches
     (so a vision-verified photo is never swapped for a different picture).
Picks the smallest version that is >=1200px wide (keeps pages light), else the largest found.
apply() then points every card/story at that version and records its real width/height."""
import os, re, json, struct, zlib, urllib.request, urllib.error, urllib.parse, html as _html, time
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.abspath(__file__)); CACHE = os.path.join(ROOT, "data", "image_sizes.json")
V = 7                         # v7: photos under 1200px re-checked once (X 'name=orig', the photo's own report page); v6: Jetpack Photon (i0.wp.com) judged by its origin file (Photon 404s the runner); broken marks re-checked even when no story uses them any more
                              # v5: 401/403/429 no longer count as broken (Jetpack i0.wp.com refused the Actions runner, fine for readers); why kept
V_BROKEN = 6
_WHY = {}
# v3: PNG picks re-checked once for transparent padding (Fightful's 1920px canvas with a small photo)
                              # v4: photos whose size could not be read re-checked once with a browser-like request -> "broken" (404, bot challenge, not an image)
BROKEN_RECHECK_H = 6          # a "broken" photo is tried again after this many hours (publisher fixed the file / challenge lifted)
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
MIN_W = 1200
MIN_SHOW = 400                # narrower than this (logos, 220px thumbs) -> WCN promotion card instead of a tiny photo
PAD_MIN = 0.9                 # a PNG whose visible area is under 90% of its canvas width or height is 'padded' -> never used
WINDOW_D = 60                 # stories first reported within this many days get probed
UA = "Mozilla/5.0 (compatible; WCN-bot/1.0; +https://wrestlingcentralnews.com/)"
def dims(b):
    try:
        if b[:8] == b"\x89PNG\r\n\x1a\n": return struct.unpack(">II", b[16:24])
        if b[:6] in (b"GIF87a", b"GIF89a"): return struct.unpack("<HH", b[6:10])
        if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
            if b[12:16] == b"VP8X": return (int.from_bytes(b[24:27], "little") + 1, int.from_bytes(b[27:30], "little") + 1)
            if b[12:16] == b"VP8 ": w, h = struct.unpack("<HH", b[26:30]); return (w & 0x3fff, h & 0x3fff)
            if b[12:16] == b"VP8L": v = int.from_bytes(b[21:25], "little"); return ((v & 0x3fff) + 1, ((v >> 14) & 0x3fff) + 1)
        if b[4:12] in (b"ftypavif", b"ftypavis"):
            i = b.find(b"ispe")
            if i > 0: return struct.unpack(">II", b[i + 8:i + 16])
        if b[:2] == b"\xff\xd8":
            i = 2
            while i < len(b) - 9:
                if b[i] != 0xFF: i += 1; continue
                m = b[i + 1]
                if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    h, w = struct.unpack(">HH", b[i + 5:i + 9]); return (w, h)
                if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7: i += 2; continue
                i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    except Exception: pass
    return None
def qurl(u):
    """URL as a browser sends it: non-ASCII characters (curly quotes, × in WordPress file names) percent-encoded."""
    return urllib.parse.quote(u, safe=":/?&=%#~+,;@!$'()*[]")
def load_state(u):
    """How a reader's browser fares loading photo u (no referrer, like our <img referrerpolicy=no-referrer>):
    'ok', 'broken:<why>' (HTTP 404/410 and other 4xx except 401/403/429-style IP blocks, bot-challenge page such as SiteGround's 202 sg-captcha or Cloudflare's, HTML/not an image),
    or None when unknown (timeout, 5xx, network) -> never treated as broken."""
    if u.startswith("https://wrestlingcentralnews.com/"): return "ok"
    m = re.match(r"https?://i[0-3]\.wp\.com/([^?#]+)", u)
    if m: return load_state("https://" + m.group(1))   # Jetpack Photon answers the runner 404 for files it serves readers fine
    for rng in (True, False):
        h = {"User-Agent": BROWSER_UA, "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8", "Sec-Fetch-Dest": "image", "Sec-Fetch-Mode": "no-cors", "Sec-Fetch-Site": "cross-site"}
        if rng: h["Range"] = "bytes=0-65535"
        try:
            r = urllib.request.urlopen(urllib.request.Request(qurl(u), headers=h), timeout=10)
            ct = (r.headers.get("Content-Type") or "").lower(); b = r.read(65536)
            if r.status == 202 or r.headers.get("sg-captcha") or r.headers.get("cf-mitigated"): return "broken:challenge"
            if ct.startswith("image") or dims(b): return "ok"
            return "broken:not-image"
        except urllib.error.HTTPError as ex:
            if ex.code in (403, 416) and rng: continue          # some hosts refuse Range requests: retry once without
            if ex.code in (401, 403, 407, 429, 451): return None   # blocks often aimed at the runner's datacenter IP, not readers
            if 400 <= ex.code < 500: return f"broken:http-{ex.code}"
            return None
        except Exception: return None
    return None
_PANO = set()                 # probed files carrying Photo Sphere / equirectangular XMP (photoguard.pano_bytes)
def probe(u):
    if u.startswith("https://wrestlingcentralnews.com/img/promo/"): return (1200, 675) # our own logo cards (may not be deployed yet on the run that first uses them)
    if u.startswith("https://wrestlingcentralnews.com/img/p/"):   # our own hand-made photos (image_overrides.json): read the file in public/
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "public", u.split("wrestlingcentralnews.com/", 1)[1].split("?")[0]), "rb") as f: return dims(f.read(65536))
        except Exception: pass
    try:
        r = urllib.request.urlopen(urllib.request.Request(qurl(u), headers={"User-Agent": UA, "Range": "bytes=0-65535", "Accept": "image/avif,image/webp,image/*,*/*"}), timeout=8)
        if not (r.headers.get("Content-Type") or "image").startswith("image"): return None
        b = r.read(65536)
        import photoguard
        if photoguard.pano_bytes(b): _PANO.add(u)
        return dims(b)
    except Exception: return None
def alpha_box(b):
    """(W, H, x0, y0, x1, y1) of the visible (alpha > 16) area of an 8-bit RGBA / grey+alpha PNG, else None. Stdlib only."""
    if b[:8] != b"\x89PNG\r\n\x1a\n": return None
    i = 8; idat = []; W = H = ct = bd = il = None
    while i + 8 <= len(b):
        n, t = struct.unpack(">I4s", b[i:i + 8]); d = b[i + 8:i + 8 + n]; i += 12 + n
        if t == b"IHDR": W, H, bd, ct, _, _, il = struct.unpack(">IIBBBBB", d[:13])
        elif t == b"IDAT": idat.append(d)
        elif t == b"IEND": break
    if not W or bd != 8 or il or ct not in (4, 6): return None
    bpp = 4 if ct == 6 else 2; st = W * bpp
    try: raw = zlib.decompress(b"".join(idat))
    except Exception: return None
    prev = bytearray(st); x0, y0, x1, y1 = W, H, -1, -1; p = 0
    for y in range(H):
        if p + 1 + st > len(raw): return None
        f = raw[p]; row = bytearray(raw[p + 1:p + 1 + st]); p += 1 + st
        if f == 1:
            for k in range(bpp, st): row[k] = (row[k] + row[k - bpp]) & 255
        elif f == 2: row = bytearray((a + c) & 255 for a, c in zip(row, prev))
        elif f == 3:
            for k in range(st): row[k] = (row[k] + ((row[k - bpp] if k >= bpp else 0) + prev[k]) // 2) & 255
        elif f == 4:
            for k in range(st):
                a = row[k - bpp] if k >= bpp else 0; c = prev[k - bpp] if k >= bpp else 0; u = prev[k]
                q = a + u - c; pa, pb, pc = abs(q - a), abs(q - u), abs(q - c)
                row[k] = (row[k] + (a if pa <= pb and pa <= pc else u if pb <= pc else c)) & 255
        al = row[bpp - 1::bpp]
        if max(al) > 16:
            xs = [k for k, v in enumerate(al) if v > 16]
            x0 = min(x0, xs[0]); x1 = max(x1, xs[-1]); y0 = min(y0, y); y1 = y
        prev = row
    return (W, H, x0, y0, x1 + 1, y1 + 1) if x1 >= 0 else (W, H, 0, 0, 0, 0)
def is_padded(box):
    """True when the visible photo fills under PAD_MIN of the canvas (photo floating on a transparent sheet)."""
    if not box: return False
    W, H, x0, y0, x1, y1 = box
    return (x1 - x0) < PAD_MIN * W or (y1 - y0) < PAD_MIN * H
def padded(u):
    """Full download (PNG only, <=15 MB) -> is the photo a small island on a transparent canvas?"""
    if not re.search(r"\.png$", urllib.parse.urlsplit(u).path, re.I): return False
    try:
        b = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=20).read(15_000_000)
        return is_padded(alpha_box(b))
    except Exception: return False
# ---------- same-photo URL variants ----------
def _stem(u):
    """Normalised file name: no extension, size/edit suffixes, or 'l-' prefixes -> compare two URLs for 'same photo'."""
    p = urllib.parse.unquote(urllib.parse.urlsplit(u).path).rsplit("/", 1)[-1].lower()
    p = re.sub(r"\.(jpe?g|png|webp|gif|avif)$", "", p)
    p = re.sub(r"^\d+px-", "", p)
    for rx in (r"-\d{2,4}x\d{2,4}$", r"-scaled$", r"-e\d{10,13}$", r"-\d{2,4}x\d{2,4}$", r"@\dx$", r"_(large|medium|small|thumb)(_cropped)?$"):
        p = re.sub(rx, "", p)
    return re.sub(r"^l-", "", p)
def same_photo(a, b):
    sa, sb = _stem(a), _stem(b)
    return len(sa) >= 5 and len(sb) >= 5 and (sa == sb or (min(len(sa), len(sb)) >= 8 and (sa in sb or sb in sa)))
def wp_original(u):
    m = re.match(r"^(.*?)-\d{2,4}x\d{2,4}(\.(?:jpe?g|png|webp))(\?.*)?$", u, re.I)
    return m.group(1) + m.group(2) if m else None
RESIZE_Q = {"w", "h", "width", "height", "resize", "fit", "crop", "quality", "strip", "zoom", "lb", "ssl", "x", "y", "dpr", "q", "auto", "format", "fm"}
def variants(u):
    out = []
    def add(x):
        if x and x != u and x not in out: out.append(x)
    s = urllib.parse.urlsplit(u); q = urllib.parse.parse_qsl(s.query, keep_blank_values=True)
    path = s.path
    # X/Twitter media: any size name (small/medium/900x900) or .jpg form -> the original upload
    m = re.match(r"^/media/([A-Za-z0-9_-]{10,})(?:\.(jpe?g|png|webp))?$", path) if s.netloc == "pbs.twimg.com" else None
    if m:
        fmt = (m.group(2) or dict(q).get("format") or "jpg").replace("jpeg", "jpg")
        add(f"https://pbs.twimg.com/media/{m.group(1)}?format={fmt}&name=orig")
    # Yahoo/AOL image proxies carry the original URL at the end of the path
    m = re.search(r"/(https?://[^?#]+)$", urllib.parse.unquote(u)) if re.search(r"yimg\.com|aol\.com", s.netloc) else None
    if m: add(m.group(1))
    # Wikimedia thumbnail -> original file
    m = re.match(r"^(/wikipedia/[^/]+)/thumb(/[0-9a-f]/[0-9a-f]{2}/[^/]+)/\d+px-[^/]+$", path)
    if m: add(f"https://upload.wikimedia.org{m.group(1)}{m.group(2)}")
    # Wix: /media/<id>~mv2.jpg/v1/fill/w_1000,h_563,.../name.jpg -> original upload
    m = re.match(r"^(/media/[^/]+?\.(?:jpe?g|png|webp))/v1/", path, re.I) if "wixstatic.com" in s.netloc else None
    if m: add(urllib.parse.urlunsplit(s._replace(path=m.group(1), query="")))
    # Static Media sites (wrestlinginc.com etc.): /img/gallery/<slug>/intro-123.jpg has a large 'l-intro-123.jpg'
    if re.search(r"/img/gallery/[^/]+/intro-[^/]+$", path): add(urllib.parse.urlunsplit(s._replace(path=re.sub(r"/intro-([^/]+)$", r"/l-intro-\1", path), query="")))
    # WordPress resized copies: -300x200 and edited -e1712345678 suffixes
    base = re.sub(r"-\d{2,4}x\d{2,4}(?=\.(?:jpe?g|png|webp)$)", "", path, flags=re.I)
    base = re.sub(r"-e\d{10,13}(?=\.(?:jpe?g|png|webp)$)", "", base, flags=re.I)
    if base != path: add(urllib.parse.urlunsplit(s._replace(path=base, query="")))
    # CDN resize/crop/fit params: drop them, or ask for a 1600px version
    if any(k.lower() in RESIZE_Q for k, _ in q):
        keep = [(k, v) for k, v in q if k.lower() not in RESIZE_Q]
        add(urllib.parse.urlunsplit(s._replace(query=urllib.parse.urlencode(keep))))
        wk = next((k for k, _ in q if k.lower() in ("w", "width")), None)
        if wk:
            hv = next((v for k, v in q if k.lower() in ("h", "height")), None); wv = next(v for k, v in q if k == wk)
            nq = [(k, "1600" if k == wk else (str(round(int(hv) * 1600 / int(wv))) if k.lower() in ("h", "height") and hv and hv.isdigit() and wv.isdigit() and int(wv) else v)) for k, v in q]
            add(urllib.parse.urlunsplit(s._replace(query=urllib.parse.urlencode(nq))))
        if "wp.com" in s.netloc: add(urllib.parse.urlunsplit(s._replace(query=urllib.parse.urlencode(keep + [("w", "1600")]))))
    elif "wp.com" in s.netloc or "/wp-content/" in path and re.search(r"platform\.|chorus|voxmedia", s.netloc):
        add(urllib.parse.urlunsplit(s._replace(query="w=1600")))
    return out
def page_images(url, img):
    """og:image / twitter:image / largest srcset entry of the source article that show the same photo."""
    try:
        h = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124 Safari/537.36"}), timeout=10).read(700000).decode("utf8", "ignore")
    except Exception: return []
    out = []
    for prop in ("og:image", "og:image:url", "og:image:secure_url", "twitter:image", "twitter:image:src"):
        for m in re.finditer(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]*content=["\']([^"\']+)|<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']%s["\']' % (re.escape(prop), re.escape(prop)), h):
            out.append(urllib.parse.urljoin(url, _html.unescape(m.group(1) or m.group(2))))
    for m in re.finditer(r'srcset=["\']([^"\']+)["\']', h):
        best = None
        for part in _html.unescape(m.group(1)).split(","):
            bits = part.strip().split()
            if len(bits) == 2 and bits[1].endswith("w") and bits[1][:-1].isdigit():
                if not best or int(bits[1][:-1]) > best[1]: best = (urllib.parse.urljoin(url, bits[0]), int(bits[1][:-1]))
        if best: out.append(best[0])
    return [u for u in dict.fromkeys(out) if u != img and u.startswith("https://") and same_photo(u, img)][:6]
def _good(w, h): return w and h and 0.45 <= h / w <= 1.6     # skip banners / tall portraits as 'best'
def pick(found):
    """found: [(url, w, h)] -> smallest version >=1200 wide with a sane shape, else the widest."""
    ok = [f for f in found if f[1] and f[1] >= MIN_W and _good(f[1], f[2])]
    if ok: return min(ok, key=lambda f: f[1])
    ok = [f for f in found if f[1]]
    return max(ok, key=lambda f: f[1]) if ok else None
def find(u, link=None, link2=None):
    """(best_url, w, h) for feed image u; only cheap HTTP. link = the report the photo came from, link2 = the story's lead report."""
    d = probe(u); found = [(u, *d)] if d else []
    import photoguard   # 360 panorama / virtual-tour asset or extreme shape: never shown (2026-10-24 Shodoshima barrel-room thumbnail)
    why = "panorama" if (u in _PANO or photoguard.pano_url(u)) else (photoguard.shape(*d) if d else None)
    if why: _WHY[u] = why; return (u, *(d or (None, None)), why)
    if d and d[0] >= MIN_W and _good(*d) and d[0] <= 2600 and not padded(u): return (u, *d)
    for v in variants(u)[:4]:
        dv = probe(v)
        if dv: found.append((v, *dv))
        if dv and MIN_W <= dv[0] <= 2600 and _good(*dv): break
    b = pick(found)
    for lk in dict.fromkeys(x for x in (link, link2) if x):
        if b and MIN_W <= b[1] <= 2600: break
        for v in page_images(lk, u):
            if any(v == f[0] for f in found): continue
            dv = probe(v)
            if dv: found.append((v, *dv))
        b = pick(found)
    # a 'bigger' PNG can be the same photo floating on a transparent canvas (Fightful: -e edited crop 774px vs 1920px sheet)
    tried = set()
    while b and b[0] not in tried and padded(b[0]):
        tried.add(b[0]); found = [f for f in found if f[0] != b[0]]; b = pick(found)
    if not b and tried: return (u, None, None, "padded")
    st = None if b else load_state(u)
    if st and st.startswith("broken"): _WHY[u] = st; return (u, None, None, "broken")
    if b and (b[0] in _PANO or photoguard.pano_url(b[0]) or photoguard.shape(b[1], b[2])): return (u, *(d or (None, None)), "panorama")   # bigger version found is a panorama
    return b or (u, None, None)
_C = None
def cache():
    global _C
    if _C is None:
        try: _C = json.load(open(CACHE))
        except Exception: _C = {}
    return _C
def best(u):
    """(url, w, h) best-known large version of image u, from cache only."""
    x = cache().get(u)
    if not x: return (u, None, None)
    return tuple(x["best"][:3])
def fill_cls(w, h):
    """' fill' for widescreen photos (16:10 .. 2.1:1): they cover the 16:9 / 2:1 frame edge to edge; other shapes keep the whole photo over the blurred fill."""
    try: return " fill" if w and h and 1.6 <= int(w) / int(h) <= 2.1 else ""
    except Exception: return ""
def unusable(u):
    """Why the photo must not be shown ('padded' / 'too-small' / 'panorama' / 'extreme-shape'), from cache only; None = fine or unknown."""
    import photoguard
    if photoguard.pano_url(u): return "panorama"
    x = cache().get(u)
    if not x: return None
    b = x["best"]
    if len(b) > 3 and b[3]: return b[3]
    if photoguard.pano_url(b[0]): return "panorama"
    return "too-small" if b[1] and b[1] < MIN_SHOW else photoguard.shape(b[1], b[2])
def dims_cached(u):
    """(w, h) of photo u from the size cache, else (None, None). No fetch."""
    x = cache().get(u)
    return tuple(x["best"][1:3]) if x else (None, None)
def _age(c, now): return now - c.get("first_ts", c["ts"])
def stats(clusters, days=7, use_best=True):
    """Share of recent stories whose (displayed) image is >=1200px wide."""
    now = time.time(); r = [c for c in clusters if _age(c, now) < days * 86400]
    w = [c for c in r if (c.get("image") or "").startswith("https://")]
    big = [c for c in w if ((c.get("img_w") or 0) if "img_w" in c else (best(c["image"])[1] or 0)) >= MIN_W]
    return {"stories": len(r), "with_image": len(w), "ge1200": len(big)}
def run(clusters, max_new=150):
    C = cache(); now = time.time()
    seen = set(); todo = []
    for c in sorted(clusters, key=lambda c: _age(c, now)):
        u = c.get("image") or ""
        if not u.startswith("https://") or u in seen or _age(c, now) > WINDOW_D * 86400: continue
        x = C.get(u)
        stale_broken = x and len(x["best"]) > 3 and x["best"][3] == "broken" and (now - x.get("at", 0) > BROKEN_RECHECK_H * 3600 or x.get("v", 1) < V_BROKEN)
        is_broken = x and len(x["best"]) > 3 and x["best"][3] == "broken"   # broken marks follow V_BROKEN / BROKEN_RECHECK_H, not V
        if x and not stale_broken and (is_broken or x.get("v", 1) >= V or (x.get("v", 1) >= 3 and (x["best"][1] or 0) >= MIN_W) or ((x["best"][1] or 0) >= MIN_W and not re.search(r"\.png$", urllib.parse.urlsplit(x["best"][0]).path, re.I))): continue
        seen.add(u); todo.append((u, c.get("image_link") or c.get("link"), c.get("link")))
    for u, x in list(C.items()):   # a broken photo is filtered out before stories pick an image, so it is re-checked here or never
        if u in seen or len(x["best"]) < 4 or x["best"][3] != "broken" or now - x.get("first", x.get("at", 0)) > 7 * 86400: continue
        if now - x.get("at", 0) > BROKEN_RECHECK_H * 3600 or x.get("v", 1) < V_BROKEN: seen.add(u); todo.append((u, x.get("link"), None))
    todo = todo[:max_new]
    l = {a[0]: a[1] for a in todo}
    def job(a): return a[0], find(*a)
    with ThreadPoolExecutor(12) as ex:
        for u, b in ex.map(job, todo):
            old = C.get(u) or {}
            C[u] = {"best": list(b), "v": V, "at": int(now)}
            if u in _WHY:
                C[u].update(why=_WHY.pop(u), first=old.get("first", old.get("at", int(now))), link=l.get(u) or old.get("link"))
    live = {c.get("image") for c in clusters}
    for k in [k for k, v in C.items() if k not in live and now - v.get("at", 0) > 7 * 86400]: C.pop(k)
    json.dump(C, open(CACHE, "w"))
    s = stats(clusters)
    print(f"imgsize: probed {len(todo)}; last 7 days >=1200px {s['ge1200']}/{s['with_image']} stories with photos ({s['stories']} stories)", flush=True)
def apply(clusters):
    """Point each card/story at the best-known version of its photo and record its real size (img_w/img_h)."""
    n = 0
    for c in clusters:
        u = c.get("image") or ""
        if not u.startswith("https://"): continue
        why = unusable(u) if c.get("image_status") != "override" else None
        if why:   # tiny thumb / publisher logo / photo on a transparent sheet -> clean promotion card, never a tiny photo
            c["image_src"] = u; c["image"] = None; c["image_status"] = why; c.pop("img_w", None); c.pop("img_h", None); n += 1; continue
        b, w, h = best(u)
        if b != u: c["image_src"] = u; c["image"] = b; n += 1
        if w and h: c["img_w"], c["img_h"] = int(w), int(h)
    return n
