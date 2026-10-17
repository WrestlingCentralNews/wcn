"""Image dimensions for structured data / Discover (needs >=1200px wide). Probes only the first bytes of each image;
cached in data/image_sizes.json; tries the full-size WordPress original when the feed gave a resized copy."""
import os, re, json, struct, urllib.request, time
from concurrent.futures import ThreadPoolExecutor
ROOT = os.path.dirname(os.path.abspath(__file__)); CACHE = os.path.join(ROOT, "data", "image_sizes.json")
UA = {"User-Agent": "Mozilla/5.0 (compatible; WCN-bot/1.0; +https://wrestlingcentralnews.com/)", "Range": "bytes=0-65535"}
def dims(b):
    try:
        if b[:8] == b"\x89PNG\r\n\x1a\n": return struct.unpack(">II", b[16:24])
        if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
            if b[12:16] == b"VP8X": return (int.from_bytes(b[24:27], "little") + 1, int.from_bytes(b[27:30], "little") + 1)
            if b[12:16] == b"VP8 ": w, h = struct.unpack("<HH", b[26:30]); return (w & 0x3fff, h & 0x3fff)
            if b[12:16] == b"VP8L": v = int.from_bytes(b[21:25], "little"); return ((v & 0x3fff) + 1, ((v >> 14) & 0x3fff) + 1)
        if b[:2] == b"\xff\xd8":
            i = 2
            while i < len(b) - 9:
                if b[i] != 0xFF: i += 1; continue
                m = b[i + 1]
                if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    h, w = struct.unpack(">HH", b[i + 5:i + 9]); return (w, h)
                i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    except Exception: pass
    return None
def probe(u):
    try: return dims(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=8).read(65536))
    except Exception: return None
def wp_original(u):
    m = re.match(r"^(.*?)-\d{2,4}x\d{2,4}(\.(?:jpe?g|png|webp))(\?.*)?$", u, re.I)
    return m.group(1) + m.group(2) if m else None
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
    return tuple(x["best"])
def run(clusters, max_new=60):
    C = cache(); now = time.time()
    todo = [c["image"] for c in clusters if (c.get("image") or "").startswith("https://") and c["image"] not in C
            and now - c.get("first_ts", c["ts"]) < 4 * 86400][:max_new]
    def job(u):
        d = probe(u); b = (u, *(d or (None, None)))
        if not d or d[0] < 1200:
            o = wp_original(u)
            if o:
                d2 = probe(o)
                if d2 and d2[0] > (d[0] if d else 0): b = (o, *d2)
        return u, b
    with ThreadPoolExecutor(8) as ex:
        for u, b in ex.map(job, todo): C[u] = {"best": list(b), "at": int(now)}
    live = {c.get("image") for c in clusters}
    for k in [k for k, v in C.items() if k not in live and now - v.get("at", 0) > 7 * 86400]: C.pop(k)
    json.dump(C, open(CACHE, "w"))
    big = sum(1 for c in clusters if c.get("image") in C and (C[c["image"]]["best"][1] or 0) >= 1200)
    print(f"imgsize: probed {len(todo)}, >=1200px {big}/{sum(1 for c in clusters if c.get('image') in C)} known", flush=True)
