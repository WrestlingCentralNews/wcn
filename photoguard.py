"""Scenery / panorama guard for story photos (2026-10-24). No AI, no extra fetches beyond imgmeta's 64 KB size probe.

Why: Google News carried 'LIVESTREAM ... WWE SmackDown Free Stream' spam pages hijacking a Japanese town's krpano virtual-tour
page (town.shodoshima.lg.jp/section/VR_choseiyoran/...); their 400x200 equirectangular thumbnail of a soy-sauce barrel room
became the hero photo of 'WWE SmackDown Preview For October 23'. A photo is rejected when:
  1. its URL names a 360 / panorama / virtual-tour asset (360, pano, panorama, equirect*, krpano, panotour, vtour, VR_ ...);
  2. its first 64 KB carry Google Photo Sphere XMP (GPano:) or ProjectionType=equirectangular;
  3. its shape is extreme (wider than 3:1 or taller than 1:2.5), or exactly 2:1 equirectangular from a generic source;
  4. it comes from a generic (non-wrestling, low-trust, non-own-feed) source that is an institution / non-news site
     (government, municipal, university host or name, or a non-Latin source name) and its file name has no wrestling /
     promotion / wrestler word ('thumbnail.jpg' from a town website). Ordinary generic news outlets (AOL, Heavy,
     Bleeding Cool ...) are NOT rejected on file name alone -- their wrestler photos often have camera-roll names.
Rejected photos are never candidates: the next report's photo, then show/event art, then the promotion card, then WCN's card."""
import re, unicodedata, urllib.parse
PANO_URL = re.compile(r"(?i)(?:^|[/_\-.=])(?:360(?:deg|vr|°)?|vr360|pano(?:rama|ramic|s)?|panotour|krpano|pano2vr|equirect\w*|photo[-_]?sphere|spherical|virtual[-_]?tours?|visita[-_ ]?virtual|tour[-_ ]?virtual|vtour|vr)(?=[/_\-.=]|$)")
WRESTLE = re.compile(r"(?i)wrestl|lucha|luchador|\bring\b|smack ?down|\braw\b|\bnxt\b|\bwwe\b|\baew\b|\btna\b|\broh\b|\bnjpw\b|\bcmll\b|\baaa\b|\bgcw\b|\bmlw\b|stardom|dynamite|rampage|collision|impact|wrestlemania|summerslam|rumble|survivor series|crown jewel|champion|title|belt|\bmatch\b|\bvs\b|superstar|\bppv\b|\bple\b|\bfaceoff\b|promo|roster")
WRESTLE_SRC = re.compile(r"(?i)wrestl|ringside|slam|sportskeeda|cageside|pwtorch|pwmania|lucha|squared ?circle|411|fightful|pwinsider|f4w|observer|ewrestling|wrestletalk|wwe|aew|tna|njpw|stardom|bodyslam|lastwordonsports|essentially sports|tjr|inside the ropes|voices of wrestling")
def pano_url(u):
    p = urllib.parse.unquote(urllib.parse.urlsplit(u or "").path)
    return bool(PANO_URL.search(p))
def pano_bytes(b):
    """Google Photo Sphere / equirectangular XMP in the first bytes of the file."""
    b = b or b""
    return b"GPano:" in b or bool(re.search(rb"ProjectionType[\"'>=\s]{0,4}equirectangular", b))
def shape(w, h, generic=False):
    """'extreme-shape' / 'panorama' (2:1 equirectangular from a generic source) / None."""
    try: w, h = int(w), int(h)
    except Exception: return None
    if not w or not h: return None
    r = w / h
    if r > 3.0 or r < 0.4: return "extreme-shape"
    if generic and 1.97 <= r <= 2.03: return "panorama"
    return None
def generic_source(a, own_feeds=None):
    """A report from an outlet that isn't a wrestling outlet: low-trust tier, not one of our own feeds, no wrestling word in its name."""
    import editorial
    s = a.get("source") or ""
    if editorial.tier(s) < 3: return False
    if own_feeds is None:
        try: import freshness; own_feeds = freshness.OWN_FEEDS
        except Exception: own_feeds = set()
    if s in own_feeds or (a.get("via") or "") in own_feeds and not str(a.get("via")).startswith("Google"): return False
    host = urllib.parse.urlsplit(a.get("link") or "").netloc
    return not WRESTLE_SRC.search(unicodedata.normalize("NFKC", s) + " " + host)
INSTITUTION_HOST = re.compile(r"(?i)\.(?:gov|mil|edu|int)(?:\.[a-z]{2})?$|\.(?:lg|go|ac|ed|gob|gouv|gv|govt|nic)\.[a-z]{2}$|(?:^|\.)(?:uco|ugr|us|ucm|uab|uam|upm|unam)\.(?:es|mx)$|\.k12\.")
INSTITUTION_NAME = re.compile(r"(?i)universi|college|school|council|municipal|prefecture|ministry|department of|city of|town of|county|[町市村県府庁]")
def institutional(a):
    """A government / municipal / university site (or a source with no Latin letters in its name) -- never a wrestling news outlet."""
    s = unicodedata.normalize("NFKC", a.get("source") or "")
    host = urllib.parse.urlsplit(a.get("link") or "").netloc.lower().split(":")[0]
    return bool(INSTITUTION_HOST.search(host) or INSTITUTION_NAME.search(s) or (s and not re.search(r"[A-Za-z]", s)))
def has_wrestling_words(txt):
    t = unicodedata.normalize("NFKC", txt or "")
    if WRESTLE.search(t): return True
    try:
        import enrich
        return bool(enrich.promos(t) or enrich.subjects(t))
    except Exception: return False
def reject(u, a=None, label="", w=None, h=None):
    """Reason the photo must not be used, or None. a = the report it came from (source/link/via), label = file name/alt/caption."""
    if not u: return None
    if pano_url(u): return "panorama"
    gen = bool(a) and generic_source(a)
    s = shape(w, h, gen)
    if s: return s
    if gen and institutional(a):
        import enrich
        words = enrich._fname_words(u) + " " + (label or "")
        if not has_wrestling_words(words): return "off-topic-generic"
    return None
