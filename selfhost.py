"""Self-hosted story photos (2026-10-24). Google Top Stories / Discover want photos >=1200px wide served from the
publisher's own site; 36 of 41 sampled story images were hotlinked. No AI.

Each build, after every photo rule has run (vision.choose subject match, foreign-promotion logo guard, pubgate,
photoguard panoramas, imgmeta's largest-version pick + unusable filter), the chosen hero photo of every live story is
downloaded ONCE, checked again (real image, not a panorama / extreme shape / tiny logo), and re-encoded to a progressive
JPEG at most MAX_W px wide -- never upscaled -- under public/img/s/<sha1(url)[:16]>.jpg (a content-addressed name: a
story whose photo changes gets a new file, so long-lived caches can't show a stale picture).
The page hero, og:image, twitter:image, NewsArticle / LiveBlogPosting JSON-LD, feeds, cards and app.js then use that copy.
Anything that fails (403 to the runner, bot page, not an image) keeps the old hotlink -- never a blank.

Storage: files live in public/img/s (restored each run from the Actions cache, then from the live site for misses),
listed in data/selfhost.json {src: {f, w, h, b, at, used}}. A file no live story has used for KEEP_D days is deleted,
so photos of stories past the 60-day retention go away. ~110 KB a photo -> ~80 MB for ~700 live stories."""
import os, io, re, json, time, hashlib, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = "https://wrestlingcentralnews.com/"
DIR = os.path.join(ROOT, "public", "img", "s"); REL = "img/s/"
MAN = os.path.join(ROOT, "data", "selfhost.json")
MAX_W = 1600          # >=1200 for Discover; wider only costs bytes
Q = 82                # JPEG quality
MAX_NEW = 220         # new downloads per build (first run backfills newest stories first)
MAX_BYTES = 12 * 1024 * 1024
KEEP_D = 3            # unused files kept this long (social cards / cached pages that still point at them)
FAIL_RETRY_H = 12
EV = 2                # bump to retry recorded failures at once (2: Photon origin fallback)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
def fname(u): return hashlib.sha1(u.encode()).hexdigest()[:16] + ".jpg"
def own(u): return (u or "").startswith(SITE)
def _get(u, timeout=20, ref=None):
    h = {"User-Agent": UA, "Accept": "image/avif,image/webp,image/jpeg,image/png,image/*;q=0.8"}
    if ref: h["Referer"] = ref
    u = urllib.parse.quote(u, safe=":/?&=%#+,;@!$'()*~[]")   # curly quotes etc. in WordPress file names
    r = urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=timeout)
    b = r.read(MAX_BYTES + 1)
    if len(b) > MAX_BYTES: raise ValueError("over 12 MB")
    return b
def encode(b):
    """bytes -> (jpeg_bytes, w, h) or raises. Never upscales; flattens transparency on black; EXIF rotation applied, metadata dropped."""
    from PIL import Image, ImageOps
    import photoguard, imgmeta
    if photoguard.pano_bytes(b[:65536]): raise ValueError("panorama (GPano XMP)")
    im = Image.open(io.BytesIO(b)); im.seek(0)
    im = ImageOps.exif_transpose(im)
    w, h = im.size
    if w < imgmeta.MIN_SHOW: raise ValueError(f"too small {w}x{h}")
    if photoguard.shape(w, h): raise ValueError(f"extreme shape {w}x{h}")
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA"); bg = Image.new("RGB", im.size, (0, 0, 0)); bg.paste(im, mask=im.split()[-1]); im = bg
    elif im.mode != "RGB": im = im.convert("RGB")
    if w > MAX_W: im = im.resize((MAX_W, round(h * MAX_W / w)), Image.LANCZOS)
    out = io.BytesIO(); im.save(out, "JPEG", quality=Q, optimize=True, progressive=True)
    return out.getvalue(), im.size[0], im.size[1]
def photon_origin(u):
    m = re.match(r"https://i[0-3]\.wp\.com/([^?#]+)", u or "")
    return "https://" + m.group(1) if m else None
def load():
    try: return json.load(open(MAN))
    except Exception: return {}
def _fetch(job):
    u, f, ref, had = job
    p = os.path.join(DIR, f)
    if had:   # the cache lost it but the live site still has the file: copy it back unchanged (no re-encode)
        try:
            b = _get(SITE + REL + f, timeout=15)
            if b[:3] == b"\xff\xd8\xff":
                from PIL import Image
                w, h = Image.open(io.BytesIO(b)).size; open(p, "wb").write(b); return u, f, w, h, len(b), None
        except Exception: pass
    err = None
    for src in (u, photon_origin(u)):   # Jetpack Photon (i0.wp.com) refuses the Actions runner: same photo from its origin file
        if not src: continue
        try:
            b, w, h = encode(_get(src, ref=ref))
            open(p, "wb").write(b); return u, f, w, h, len(b), None
        except Exception as ex: err = err or repr(ex)[:160]
    return u, f, None, None, 0, err
def run(clusters, max_new=MAX_NEW, fetch=True):
    """Download + record self-hosted copies. Sets c['image_local'], c['local_w'], c['local_h'] on every story whose photo has one."""
    os.makedirs(DIR, exist_ok=True)
    M = load(); now = int(time.time()); todo = []; seen = set()
    for c in sorted(clusters, key=lambda c: -c.get("first_ts", c.get("ts", 0))):
        u = c.get("image") or ""
        if not u.startswith("https://") or own(u): continue
        x = M.get(u); f = (x or {}).get("f") or fname(u)
        if x and x.get("w") and os.path.exists(os.path.join(DIR, f)): continue
        if x and x.get("err") and x.get("ev") == EV and now - x.get("at", 0) < FAIL_RETRY_H * 3600: continue
        if u in seen: continue
        seen.add(u); todo.append((u, f, c.get("link"), bool(x and x.get("w"))))
    todo = todo[:max_new] if fetch else []
    ok = bad = 0
    with ThreadPoolExecutor(10) as ex:
        for u, f, w, h, nb, err in ex.map(_fetch, todo):
            if err: M[u] = {"f": f, "err": err, "at": now, "ev": EV}; bad += 1
            else: M[u] = {"f": f, "w": w, "h": h, "b": nb, "at": now, "used": now}; ok += 1
    n = 0
    for c in clusters:
        for k in ("image_local", "local_w", "local_h"): c.pop(k, None)
        u = c.get("image") or ""; x = M.get(u)
        if x and x.get("w") and os.path.exists(os.path.join(DIR, x["f"])):
            c["image_local"] = SITE + REL + x["f"]; c["local_w"], c["local_h"] = x["w"], x["h"]; x["used"] = now; n += 1
    # prune: files unused for KEEP_D days (stories gone past the 60-day cutoff, or whose photo changed) and stray files
    keep = {}
    for u, x in M.items():
        if x.get("w") and now - x.get("used", x.get("at", 0)) <= KEEP_D * 86400: keep[x["f"]] = u
        elif x.get("err") and now - x.get("at", 0) <= 2 * 86400: pass
    pr = 0
    for f in os.listdir(DIR):
        if f not in keep: os.remove(os.path.join(DIR, f)); pr += 1
    M = {u: x for u, x in M.items() if (x.get("w") and x["f"] in keep and os.path.exists(os.path.join(DIR, x["f"]))) or (x.get("err") and now - x.get("at", 0) <= 2 * 86400)}
    os.makedirs(os.path.dirname(MAN), exist_ok=True); 
    with open(MAN, "w") as fh: json.dump(M, fh)
    tot = sum(os.path.getsize(os.path.join(DIR, f)) for f in os.listdir(DIR))
    ext = sum(1 for c in clusters if (c.get("image") or "").startswith("https://") and not own(c["image"]))
    big = sum(1 for c in clusters if c.get("image_local") and (c.get("local_w") or 0) >= 1200)
    print(f"selfhost: {n}/{ext} story photos on our site ({big} >=1200px), new {ok}, failed {bad}, pruned {pr}, "
          f"{len(os.listdir(DIR))} files {tot / 1e6:.1f} MB", flush=True)
    return {"local": n, "external": ext, "ge1200": big, "new": ok, "failed": bad, "pruned": pr, "mb": round(tot / 1e6, 1)}
class swap:
    """with selfhost.swap(clusters): render with c['image'] = our copy (and its real size); restored afterwards so news.json,
    the photo-rule caches and the X poster keep the source URL."""
    def __init__(self, clusters): self.cl = clusters
    def __enter__(self):
        for c in self.cl:
            if c.get("image_local"):
                c["_hot"] = (c.get("image"), c.get("img_w"), c.get("img_h"))
                c["image"], c["img_w"], c["img_h"] = c["image_local"], c["local_w"], c["local_h"]
        return self.cl
    def __exit__(self, *a):
        for c in self.cl:
            if "_hot" in c:
                c["image"], c["img_w"], c["img_h"] = c.pop("_hot")
                if c["img_w"] is None: c.pop("img_w"); c.pop("img_h", None)
        return False
