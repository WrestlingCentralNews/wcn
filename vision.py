"""Image relevance: Grok vision check + Wikipedia/Commons fallback. Verdicts cached per (image, names)."""
import os, re, json, html, time, hashlib, urllib.request, urllib.parse
import llm
CACHE_F = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "image_checks.json")
UA = {"User-Agent": "WCN-bot/1.0 (https://wrestlingcentralnews.com/; wcn@mail.grokbot.com)"}
VISION_RESERVE_USD = 1.5   # stop vision checks when less than this remains in the monthly cap
_C = None
MAX_CHECKS_PER_CARD = 4   # cap paid vision calls per card per run (was up to ~9: 4 cluster + 3 inline + wiki)
import threading
_tl = threading.local()
def cache():
    global _C
    if _C is None:
        try: _C = json.load(open(CACHE_F))
        except Exception: _C = {}
    return _C
def save(): json.dump(cache(), open(CACHE_F, "w"))
def _get(url, t=12): return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=t).read()
def check(img, names):
    """True if the image shows at least one of `names` (Grok vision). None if unknown (no key/budget/error)."""
    k = "v2|" + img + "|" + "|".join(sorted(names)); c = cache()
    if k in c: return c[k]["ok"]
    key = os.environ.get("AI_API_KEY")
    if not key or llm.budget_left() < VISION_RESERVE_USD or not llm.pace_ok(): return None
    if getattr(_tl, "n", 0) >= MAX_CHECKS_PER_CARD: return None
    if getattr(_tl, "bf", False) and not backfill_room(): return None
    _tl.n = getattr(_tl, "n", 0) + 1
    prompt = ("Pro-wrestling photo check. Expected people: " + ", ".join(names) +
              ". Answer true ONLY if an expected person is the clear main focus of the photo: shown solo, or dominant/central and largest. "
              "If two people are expected, a photo of either one or both together is fine. Answer false for event posters, logos/graphics, "
              "group shots or lineups with several other wrestlers, crowd shots, or if the focus is a different person. "
              "Return JSON {\"shows_expected\": true|false, \"who\": \"who you believe is shown, or 'unknown'\"}.")
    body = {"model": llm.MODEL, "max_tokens": 60, "temperature": 0, "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": img, "detail": "low"}}, {"type": "text", "text": prompt}]}]}
    try:
        r = urllib.request.urlopen(urllib.request.Request(llm.URL, data=json.dumps(body).encode(),
            headers=llm.HDR(key, "wcn-vision")), timeout=45)
        d = json.load(r)
        with llm._lock:
            cost = d.get("usage", {}).get("cost_in_usd_ticks", 0) / 1e10
            llm._U["usd"] += cost; llm._U["vision"] = llm._U.get("vision", 0) + 1
            if getattr(_tl, "bf", False):
                B = c.setdefault(BACKFILL_KEY, {"usd": 0.0, "calls": 0}); B["usd"] += cost; B["calls"] += 1
        out = json.loads(d["choices"][0]["message"]["content"])
        c[k] = {"ok": bool(out.get("shows_expected")), "who": out.get("who"), "at": int(time.time())}
        return c[k]["ok"]
    except Exception as e:
        msg = str(e)[:100]
        if "400" in msg or "image" in msg.lower(): c[k] = {"ok": False, "who": "unloadable", "at": int(time.time())}
        print("vision error:", msg, flush=True); return None
# ---------- one-time paid backlog check (owner-approved 2026-10-18): vision for EVERY card that fell back to a logo/unverified
# photo, not just the top VISION_TOP. Cheapest path (detail=low, 60 tokens), every verdict cached; stops at BACKFILL_CAP_USD total
# (tracked in the cache across runs) or when the month would pass the $8 pace target. Runs once, then marks itself done.
BACKFILL_KEY = "backfill|2026-10-18-backlog"
BACKFILL_CAP_USD = 0.30
_bf_lock = threading.Lock()
def backfill_on():
    B = cache().get(BACKFILL_KEY) or {}
    return not B.get("done")
def backfill_room():
    with _bf_lock:
        B = cache().setdefault(BACKFILL_KEY, {"usd": 0.0, "calls": 0})
        if B.get("done"): return False
        per = 0.0012 # worst-case cost of one more low-detail check
        if B["usd"] + per > BACKFILL_CAP_USD or llm._U["usd"] + per > llm.PACE_TARGET_USD: B["capped"] = True; return False
        return True
def backfill_finish():
    B = cache().get(BACKFILL_KEY)
    if B is not None and not B.get("done") and B.get("calls"): B["done"] = int(time.time()); return B
    return None
def inline_images(url, names):
    """Article-page images whose alt/caption/filename mentions one of the names."""
    try: h = _get(url, 10)[:900000].decode("utf8", "ignore")
    except Exception: return []
    out = []
    for m in re.finditer(r"<img[^>]+>", h):
        tag = m.group(0); src = re.search(r'(?:data-src|src)=["\']([^"\']+)', tag)
        if not src or src.group(1).startswith("data:"): continue
        u = urllib.parse.urljoin(url, html.unescape(src.group(1)))
        ctx = (tag + h[m.end():m.end() + 400]).lower()
        if any(n.lower() in ctx or n.lower().replace(" ", "-") in u.lower() for n in names) and not re.search(r"logo|avatar|icon|sprite|1x1", u, re.I):
            out.append(u)
    return list(dict.fromkeys(out))[:3]
def wikipedia(name):
    """Freely licensed lead image of a wrestler's Wikipedia article + attribution."""
    c = cache(); k = "wiki|" + name
    if k in c: return c[k]
    res = None
    try:
        q = urllib.parse.urlencode({"action": "query", "list": "search", "srsearch": f"{name} professional wrestler", "srlimit": 1, "format": "json"})
        hits = json.loads(_get("https://en.wikipedia.org/w/api.php?" + q))["query"]["search"]
        if hits and name.lower() in hits[0]["title"].lower() and "wrestl" in (hits[0].get("snippet") or "").lower() + hits[0]["title"].lower():
            q = urllib.parse.urlencode({"action": "query", "titles": hits[0]["title"], "prop": "pageimages", "piprop": "original|name", "format": "json", "redirects": 1})
            p = list(json.loads(_get("https://en.wikipedia.org/w/api.php?" + q))["query"]["pages"].values())[0]
            if p.get("original") and p.get("pageimage"):
                q = urllib.parse.urlencode({"action": "query", "titles": "File:" + p["pageimage"], "prop": "imageinfo", "iiprop": "extmetadata|url", "iiurlwidth": 1200, "format": "json"})
                ii = list(json.loads(_get("https://commons.wikimedia.org/w/api.php?" + q))["query"]["pages"].values())[0]["imageinfo"][0]
                md = ii.get("extmetadata", {}); strip = lambda s: re.sub(r"<[^>]+>", "", (s or {}).get("value", "")).strip()
                lic = strip(md.get("LicenseShortName"))
                if lic and not re.search(r"fair use|non-free", lic, re.I):
                    res = {"url": (ii.get("thumburl") or ii["url"]).split("?")[0], "credit": f"Photo: {strip(md.get('Artist'))[:60] or 'Wikimedia Commons'} / {lic}",
                           "credit_url": ii.get("descriptionurl"), "page": hits[0]["title"]}
    except Exception as e: print("wiki error:", name, str(e)[:80], flush=True)
    c[k] = res; return res

import enrich
from aliases import canon
NOTNAME = re.compile(r"\b(WWE|AEW|TNA|NXT|ROH|NJPW|CMLL|AAA|GCW|MLW|Raw|SmackDown|Dynamite|Collision|Impact|Title|Championship|Match|Event|Show|Report|Results|Review|Night|Main|Event|Card|Crown|Jewel|Full|Gear|Final|Battle|Women|Men|Tag|Team|World|Street|Fight|Medical|Examiner|Officer|Netflix|Halloween|Havoc|Money|Bank|Wrestle\w*|Saudi|Arabia|Books?|Sets?|Says|Reveals?)\b", re.I)
def names_in(title):
    names_in.guessed = False
    seen = []
    for m in enrich._PRX.findall(canon(title)):
        n = canon(m)
        if n.lower() not in [s.lower() for s in seen]: seen.append(n)
    if not seen:   # unknown names: take capitalised 2-3 word person-like names (validated later by Wikipedia + vision)
        for m in re.findall(r"\b([A-Z][a-z'’.]+(?: [A-Z][a-z'’.]+){1,2})\b", canon(title)):
            if not NOTNAME.search(m) and m.lower() not in [s.lower() for s in seen]: seen.append(m)
        names_in.guessed = True
    return seen[:2]
# ---------- key person: who the story's photo must show ----------
VERB_RX = re.compile(r"\b(died|dies|death|passe[sd] away|retire[sd]?|retirement|retiring|injur\w*|hurt|surgery|sidelined|stretchered|"
    r"signs?|signed|re-signs?|inks?|released?|fired|cut|departs?|leaves|leaving|exits?|quits?|suspend\w*|arrest\w*|charged|"
    r"def\.|defeats?|defeated|beats?|beat|wins?|won|retains?|retained|captures?|crowned|dethrones?|pins?|pinned|submits?|tops|outlasts?|"
    r"returns?|debuts?|replaces?|replaced|joins?|named|shares?|explains?|reveals?|confronts?|praises?|promises?|plans?|slams?|blasts?|rips?|criticiz\w*|responds?|fires back|apologi\w*|accused|controvers\w*|backlash|lawsuit|sued|sues|accuses)\b", re.I)
OBJ_RX = re.compile(r"(?i)^(sues|accuses|lawsuit)$")                       # 'Officer sues WWE and Montez Ford' -> the defendant
def _pnames(t):
    """[(name, start, end)] of known wrestlers in t, canonical names, in order."""
    out = []
    for m in enrich._PRX.finditer(t):      # t is already canonicalised: don't canon() again (doubles first names)
        n = m.group(0)
        if n.lower() not in [x[0].lower() for x in out]: out.append((n, m.start(), m.end()))
    return out
def key_person(c):
    """(key person, all named people) for card c. Rules first: the subject of the headline's event verb (winner/champion in a
    result, the person who died/retired/was injured/signed/was released/returned, the one at the centre of a row); 'X loses to Y'
    and 'A sues B' take the person after the verb; no verb -> the most-mentioned wrestler in headline + dek (headline order breaks ties)."""
    t = canon(c.get("title") or ""); P = _pnames(t)
    if not P:
        P = _pnames(canon(c.get("raw_title") or ""))
        if P: t = canon(c.get("raw_title") or "")
    names = [p[0] for p in P]
    if not P:   # only an executive / authority figure is named ('Santino Marella Re-Signs With TNA'): they are the subject
        m = enrich._SRX.search(canon(c.get("title") or "")) or enrich._SRX.search(canon(c.get("raw_title") or ""))
        if m: return m.group(0), [m.group(0)], False
    if not P:
        g = names_in(c["title"]) or names_in(c.get("raw_title", ""))
        g = [x for x in (re.split(VERB_RX, x)[0].strip() for x in g) if len(x.split()) >= 2]   # 'Divine Dominion Beats' -> 'Divine Dominion'
        return (g[0] if g else None), g, True
    m = re.search(r"(?i)\b(loses? to|lost to|falls? to|beaten by|defeated by|pinned by|released by|fired by|signed by)\b", t)
    if m and "by" not in m.group(0).lower():
        after = [p for p in P if p[1] > m.end()]
        if after: return after[0][0], names, False
    v = VERB_RX.search(t)
    if v:
        if OBJ_RX.match(v.group(0)):
            after = [p for p in P if p[1] > v.end()]
            if after: return after[0][0], names, False
        before = [p for p in P if p[2] <= v.start()]
        if before: return before[0][0], names, False      # 'Hangman Page, Bandido & Brody King capture...' -> the first-named
        after = [p for p in P if p[1] >= v.end()]
        if after: return after[0][0], names, False
    if len(P) == 1: return P[0][0], names, False
    body = (c.get("title") or "") + " " + (c.get("summary") or "")
    cnt = {n: len(re.findall(r"(?i)\b" + re.escape(n) + r"(?![a-z])", body)) for n in names}
    return max(names, key=lambda n: (cnt[n], -names.index(n))), names, False
# ---------- what a candidate image is labelled as (caption/alt/filename/nearby text) ----------
_PAGES = {}
def page_labels(url):
    """{photo stem: alt + caption + nearby text} for the images on a source article (fetched once per run)."""
    if url in _PAGES: return _PAGES[url]
    out = {}
    try: h = _get(url, 10)[:900000].decode("utf8", "ignore")
    except Exception: h = ""
    import imgmeta
    for m in re.finditer(r"<img[^>]+>", h):
        tag = m.group(0); src = re.search(r'(?:data-src|src)=["\']([^"\']+)', tag)
        if not src or src.group(1).startswith("data:"): continue
        alt = re.search(r'alt=["\']([^"\']*)', tag)
        nxt = h[m.end():m.end() + 1500]; cap = re.search(r"(?is)^\s*(?:</?(?:a|picture|source|span|div)[^>]*>\s*)*<figcaption[^>]*>(.*?)</figcaption>", nxt)
        txt = " ".join(x for x in [alt.group(1) if alt else "", re.sub(r"<[^>]+>", " ", cap.group(1)) if cap else ""] if x)   # alt + its own caption only
        out.setdefault(imgmeta._stem(urllib.parse.urljoin(url, html.unescape(src.group(1)))), html.unescape(txt))
    _PAGES[url] = out; return out
def label(u, link=None):
    """Words that describe image u: its file name, plus alt/caption text if the source article shows the same photo."""
    import imgmeta
    p = urllib.parse.unquote(urllib.parse.urlsplit(u).path).rsplit("/", 1)[-1]
    words = re.sub(r"[-_.+]+", " ", re.sub(r"\.(jpe?g|png|webp|gif|avif)$", "", p, flags=re.I))
    words = re.sub(r"([a-z])([A-Z])", r"\1 \2", words)
    if link:
        st = imgmeta._stem(u)
        for k, v in page_labels(link).items():
            if k == st or (min(len(k), len(st)) >= 8 and (k in st or st in k)): words += " | " + v; break
    return words
def names_key(txt, key):
    """True if txt names the key person (full name, or the surname of a 2+ word name)."""
    t = canon(txt).lower(); k = key.lower()
    if re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", t): return True
    parts = k.split()
    return len(parts) >= 2 and len(parts[-1]) >= 4 and re.search(r"(?<![a-z])" + re.escape(parts[-1]) + r"(?![a-z])", t) is not None
def others_named(txt, key, allowed):
    """Known wrestlers txt names who are neither the key person nor (for group photos) the story's other named people."""
    al = {a.lower() for a in allowed}
    return [n for n, _, _ in _pnames(canon(txt)) if n.lower() != key.lower() and not names_key(n, key) and n.lower() not in al]
_VI = None
def prior(u, key):
    """Free answer from earlier vision checks of this image (any card): True shows the key person, False shows someone else, None unknown."""
    global _VI
    if _VI is None:
        _VI = {}
        for k, v in list(cache().items()):
            if k.startswith("v2|"):
                img, *nm = k[3:].split("|"); _VI.setdefault(img, []).append((nm, v))
    for nm, v in _VI.get(u, []):
        if key.lower() not in [n.lower() for n in nm]: continue
        who = v.get("who") or ""
        if v.get("ok") and (len(nm) == 1 or names_key(who, key)): return True
        if not v.get("ok") and len(nm) == 1 and who.lower() not in ("unknown", "unloadable", ""): return False
    return None
# ---------- promotion logo cards (public/img/promo/<k>.jpg, 1200x675) ----------
PROMO_CARD = "https://wrestlingcentralnews.com/img/promo/{}.jpg"
PROMO_TXT = [("nxt", r"\bNXT\b"), ("roh", r"\bROH\b|Ring of Honor"), ("njpw", r"\bNJPW\b|New Japan|Wrestle Kingdom|G1\b"), ("stardom", r"\bStardom\b"),
             ("aaa", r"\bAAA\b|Lucha Libre AAA"), ("cmll", r"\bCMLL\b|Arena M[eé]xico"), ("mlw", r"\bMLW\b|Major League Wrestling"), ("gcw", r"\bGCW\b|Game Changer"),
             ("nwa", r"\bNWA\b"), ("tna", r"\bTNA\b|\bi?MPACT\b|Bound for Glory|Destination X"), ("aew", r"\bAEW\b|Dynamite|Collision|WrestleDream|All Elite"),
             ("wwe", r"\bWWE\b|\bRaw\b|SmackDown|WrestleMania|Crown Jewel|Survivor Series|Saturday Night'?s Main Event")]
NOT_WITH = re.compile(r"(?i)\b(died|dies|death|passe[sd] away|retire[sd]?|retirement|released?|fired|firing|departs?|leaves|leaving|exits?|quits?|free agent|former)\b")
def promo_in(text):
    for k, rx in PROMO_TXT:
        if re.search(rx, text or "", re.I): return k
    return None
BIG = ("WWE", "AEW", "TNA")
def promotion(key, c):
    """Promotion the key person works for (existing roster brand lists + the story's own promotion/show names), or None for
    free agents, retirees, legends/commentators, celebrities, people who just left or died, and unknown names."""
    import editorial
    k = key.lower(); t = c.get("title") or ""
    if NOT_WITH.search(t):
        # free agent / between promotions (owner rule 2026-10-23): the LAST promotion they were signed to if they left within
        # ~6 months (departed.py: hand table, official roster drop-offs, story text), else None (WCN card). Died/retired: None.
        if re.search(r"(?i)\b(died|dies|death|passe[sd] away|retire[sd]?|retirement)\b", t): return None
        return free_agent(key, c) or None
    try:   # look-back story about a promotion they've since left ('Chris Sabin Recalls ... TNA'): their current promotion's card
        import current; np_ = current.now_promo(key, c)
        if np_: return np_
    except Exception: pass
    def hit(n):
        n = n.strip()
        if not n: return False
        try:
            if re.search(r"(?<![a-z])(?:" + n + r")(?![a-z])", key, re.I): return True
        except re.error: pass
        return re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", re.sub(r"\[[^]]*\]", "e", n).lower()) is not None
    brands = [b for b, v in editorial.ROSTER.items() if any(hit(n) for n in v.split("|"))]
    if brands:   # the official current rosters (data/rosters.json) beat the hand lists: Joe Hendry is WWE now, not TNA (2026-10-23)
        import current
        on, off = current.official(key)
        if on: brands = [b for b in BIG if b in on] + [b for b in brands if b not in BIG]
    tp = promo_in(t)
    if not brands:   # not on our roster lists (lists lag behind signings): the story itself says they compete/signed there
        if tp and tp in ("wwe", "aew", "tna", "nxt", "roh") and re.search(r"(?i)\b(retains?|wins?|won|beats?|defeats?|debuts?|signs?|signed|captures?|crowned|champions?|deal|contract)\b", t): return tp
        return free_agent(key, c) or None
    return _listed(key, c, brands, t, k)
def free_agent(key, c):
    """Last promotion (lower case) of someone on no current official roster who left it within departed.RECENT; '' if they
    left longer ago; None if unknown or still listed somewhere."""
    try:
        import current, departed
        on, off = current.official(key)
        if on: return None
        return departed.card(key, c)
    except Exception: return None
def _listed(key, c, brands, t, k):
    tp = promo_in(t)
    named = {k_ for k_, rx in PROMO_TXT if re.search(rx, t, re.I)}
    own = {b.lower() for b in brands} | ({"nxt"} if "WWE" in brands else set()) | ({"roh"} if "AEW" in brands else set())
    if tp and not named & own and re.search(r"(?i)\b(results?|card|tag match|show|event|tour|episode|teams? with|appears? (at|in|on))\b", t):
        return tp # the story is about another promotion's show ('CMLL Viernes Espectacular Results', 'AEW Star Teams With X In CMLL')
    if tp in ("wwe", "aew", "tna") and tp.upper() not in brands and re.search(r"(?i)\b(retains?|wins?|won|beats?|defeats?|debuts?|signs?|signed|captures?|crowned)\b", t):
        return tp # roster list is behind: they're competing/signed there now ('Andrade Retains AEW National Title')
    if "WWE" in brands and (tp == "nxt" or (tp is None and re.search(r"\bNXT\b", c.get("summary") or ""))): return "nxt"
    if "AEW" in brands and tp == "roh": return "roh"
    if len(brands) == 1 and brands[0] in BIG and tp in ("wwe", "aew", "tna") and tp != brands[0].lower():
        import current
        on, off = current.official(key)
        if brands[0] not in on and re.search(r"(?i)\b(signs?|signed|deal|contract|joins?|joined|debuts?|wins?|won|retains?|captures?|crowned)\b", t):
            return tp   # hand list is stale (not on that official roster) and the headline places them in another promotion now
    for b in brands:
        if b in ("WWE", "AEW", "TNA") and (tp in (None, b.lower()) or len(brands) == 1): return b.lower()
    if any(b in ("Global", "Indie") for b in brands): return tp
    return brands[0].lower() if brands[0] in ("WWE", "AEW", "TNA") else None
def check_brand(img, promos_, paid=True):
    """True if the image shows logos/branding of any promotion in promos_ (Grok vision, low detail, cached per image+promos).
    Only called for images that already tripped a free signal (enrich.foreign_promo weak). None if unknown."""
    names = sorted({BRAND.get(p, p.upper()) for p in promos_})
    k = "b1|" + img + "|" + "|".join(names); c = cache()
    if k in c: return c[k]["ok"]
    key = os.environ.get("AI_API_KEY")
    if not paid or not key or llm.budget_left() < VISION_RESERVE_USD or not llm.pace_ok(): return None
    if getattr(_tl, "n", 0) >= MAX_CHECKS_PER_CARD: return None
    _tl.n = getattr(_tl, "n", 0) + 1
    prompt = ("Pro-wrestling image check. Does this image show a logo, show name, poster or branding of: " + ", ".join(names) +
              "? Answer true if any of them is visible anywhere (e.g. one half of a split graphic). "
              "Return JSON {\"shows_brand\": true|false}.")
    body = {"model": llm.MODEL, "max_tokens": 20, "temperature": 0, "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": img, "detail": "low"}}, {"type": "text", "text": prompt}]}]}
    try:
        r = urllib.request.urlopen(urllib.request.Request(llm.URL, data=json.dumps(body).encode(),
            headers=llm.HDR(key, "wcn-vision")), timeout=45)
        d = json.load(r)
        with llm._lock:
            llm._U["usd"] += d.get("usage", {}).get("cost_in_usd_ticks", 0) / 1e10; llm._U["vision"] = llm._U.get("vision", 0) + 1
        out = json.loads(d["choices"][0]["message"]["content"])
        c[k] = {"ok": bool(out.get("shows_brand")), "at": int(time.time())}
        return c[k]["ok"]
    except Exception as e:
        print("vision brand error:", str(e)[:100], flush=True); return None
BRAND = {"wwe": "WWE or NXT", "aew": "AEW or ROH", "tna": "TNA", "combat": "UFC/MMA/boxing"}
def other_brand(u, story_pro, L, src, story_txt, vision_ok):
    """True if photo u is tied to a promotion the story isn't about: its file name/alt names one (free), or it comes from a
    'vs'/head-to-head/ratings article naming one and vision confirms (or can't check: then the safe choice is to skip it)."""
    f, strong = enrich.foreign_promo(u, story_pro, L, src, story_txt)
    if not f: return False
    if strong: return True
    return check_brand(u, f, paid=vision_ok) is not False   # an earlier verdict is free; a new paid check only for top cards
VISION_TOP = 60          # vision confirms only for the top cards on the homepage
_PIX = None
KEY_ST = ("key-labelled", "key-verified", "key-verified-cached", "key-inline", "key-verified-earlier")
def person_photo(key, names, story_pro, story_txt, cid=None, vision_ok=False):
    """(image, credit) of the key person that another card's pick already showed (file name/caption named them or vision
    confirmed it), still usable, not tied to a promotion this story isn't about and not labelled with someone else; else None.
    Free (cache only). Newest-looking upload path first (year/month in the URL)."""
    import imgmeta
    global _PIX
    if _PIX is None or _PIX[0] is not cache():     # key person -> their confirmed picks, built once per run (the cache has thousands of entries)
        ix = {}
        for k_, v in list(cache().items()):
            if k_.startswith("choice3|") and v.get("st") in KEY_ST and v.get("key"): ix.setdefault(v["key"], []).append((k_, v))
        _PIX = (cache(), ix)
    seen, out = set(), []
    for k_, v in _PIX[1].get(key, []):
        u = v.get("image")
        if not u or u in seen or str(u).startswith(PROMO_CARD[:40]) or k_.split("|")[1] == cid or not solo_photo(u, key): continue
        if not solo_source(CARD_TITLES.get(k_.split("|")[1]), key): continue   # source card gone, or about more than this person
        seen.add(u)
        try:
            if imgmeta.unusable(u): continue
        except Exception: pass
        L = label(u)
        if others_named(L, key, names) or other_brand(u, story_pro, L, "", story_txt, False): continue
        if story_pro and enrich.label_promos(enrich._fname_words(u) + " | " + L) - set(story_pro): continue   # e.g. a TNA-era photo
        if prior(u, key) is False: continue
        y = re.search(r"/(20\d\d)/(\d\d)/", u)
        out.append(((y.group(1) + y.group(2)) if y else "0", v.get("st") == "key-labelled" or names_key(L, key), u, v.get("credit")))
    if not out: return None
    out.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return out[0][2], out[0][3]
# owner rule 2026-10-23 (Cyndi Lauper story got a Penta photo, a CMLL title change got PAC, a Honolulu house show got Liv Morgan):
# a photo confirmed on ANOTHER story (or an unverified report photo) is only reused when the published headline is about exactly
# that one person: they are its first-named subject (only a promotion / title / 'former' in front of the name), it names no other
# wrestler, and it isn't a results / event / vs / roundup / multi-person story. A key person taken from the SOURCE headline because
# the published one names nobody is never enough. Photos that show more than one wrestler (posters, group shots, screenshots) are
# never reused (reuse_block.json lists the ones found by hand; a file name / caption naming anyone else or 'vs' also blocks).
_PRE_OK = re.compile(r"(?i)^(?:(?:wwe|aew|tna|nxt|roh|njpw|cmll|aaa|stardom|noah|mlw|gcw|nwa|raw|smackdown|impact|collision|dynamite|"
                     r"former|current|new|reigning|interim|undisputed|world|women'?s|men'?s|tbs|tnt|tv|national|continental|international|"
                     r"intercontinental|united states|us|north american|x-division|heavyweight|tag(?: team)?|title|champion|star|"
                     r"legend|veteran|hall of famer|the)\b[\s'’:,-]*)*$")
_ROUND_RX = re.compile(r"(?i)\b(notes?|roundup|round-up|and more|plus|news|report|results?|recap|preview|lineup|live|tonight|show|"
                       r"house show|event|tour|episode|poster|trailer|documentary|card|tournament|league|faction|stable|joins?|unite|"
                       r"tag team|teams?)\b")
def _block():
    try: return {re.sub(r"[?#].*$", "", u) for u in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "reuse_block.json"))).get("images", [])}
    except Exception: return set()
_BLOCK = _block()
def blocked(u): return re.sub(r"[?#].*$", "", str(u or "")) in _BLOCK
def solo_subject(c, key):
    """True if card c's PUBLISHED headline is about the key person alone (see the 2026-10-23 rule above)."""
    if not key: return False
    if ((c.get("kind") or {}).get("type") or "") in ("results", "event", "preview", "card"): return False
    t = canon(c.get("title") or "")
    if not t or not names_key(t, key) or _ONE_RX.search(t) or _ROUND_RX.search(t): return False
    sub = enrich.subjects(t)
    if not sub or not all(names_key(x, key) for x in sub): return False
    P = _pnames(t)
    first = next((p for p in P if names_key(p[0], key)), None)
    if not first or any(not names_key(p[0], key) for p in P): return False
    kw = {w.lower() for w in first[0].split()}       # canon() can leave the source's own first name in front ('Ilja Ilja Dragunov')
    pre = " ".join(w for w in t[:first[1]].split() if w.lower().strip("'’:,") not in kw)
    return bool(_PRE_OK.match(pre.strip()))
def solo_photo(u, key):
    """True if photo u may be reused for the key person: not hand-blocked, its file name / caption names nobody else, no 'vs'."""
    if blocked(u) or re.search(r"(?i)screen[-_ ]?shot|collage|poster|flyer|graphic|instagram", str(u)): return False
    L = enrich._fname_words(u) + " | " + label(u)
    if re.search(r"(?i)(?<![a-z0-9])(vs|versus)(?![a-z0-9])", L) or re.search(r"[a-z]vs ?[A-Z]", L): return False   # 'Nic Nemethvs Leon Slater'
    return all(names_key(x, key) for x in enrich.subjects(L))
CARD_TITLES = {}   # id -> published headline of every card in this run (aggregator sets it before picking photos)
def solo_source(t, key):
    """True if the headline of the card a photo was confirmed on is about the key person and names no other wrestler
    ('Queen Aminata earns TBS title shot vs Persephone' -> its poster shows both; 'Damian Priest Dismisses R-Truth's Injury
    Post' -> a Priest/R-Truth ring photo). Unknown source (card no longer listed) -> False."""
    if not t: return False
    t = canon(t)
    if not names_key(t, key) or re.search(r"(?i)\b(vs\.?|versus|against|teams? with|and|&)\b|&", t): return False
    return all(names_key(x, key) for x in enrich.subjects(t)) and all(names_key(p[0], key) for p in _pnames(t))
_ONE_RX = re.compile(r"(?i)\b(vs\.?|versus|v\.|results?|recap|card|match(?:es)?|battles?|faces?|against|teams? with|and|&)\b")
def report_photo(neutral, msrc, key):
    """A still-unverified photo from a report whose own headline names the key person and no other wrestler, and isn't a
    match/results piece (those show opponents): very likely the subject. None otherwise."""
    for u in neutral:
        h = msrc.get(u) or ""
        if not h or _ONE_RX.search(h) or not solo_photo(u, key): continue
        sub = enrich.subjects(h)
        if sub and all(names_key(x, key) for x in sub) and names_key(h, key): return u
    return None
def choose(c, member_images, budget_ok=True, rank=0, fetch=True):
    """Photo that shows the story's key person. Order: candidate labelled with the key person (file name/alt/caption) ->
    vision-confirmed (top cards only, ambiguous candidates only, cached per image) -> article photo captioned with them ->
    their free-licence Wikipedia photo -> best unlabelled on-topic photo / show or event art -> none (WCN default card).
    A photo labelled with a DIFFERENT wrestler, or that vision says shows someone else, is never used.
    Returns (image or None, credit dict or None, status)."""
    _tl.n = 0; _tl.bf = False
    # photos imgmeta found unusable (broken link / bot-challenge page / not an image / tiny / padded sheet) are never candidates:
    # the next report's photo is tried instead, then the promotion card (cache only, no fetch here)
    import imgmeta
    member_images = [u for u in member_images if not imgmeta.unusable(u)]
    if c.get("image") and imgmeta.unusable(c["image"]): c = {**c, "image": None}
    key, names, guessed = key_person(c)
    story_txt = (c.get("title") or "") + " | " + (c.get("raw_title") or "") + " | " + (c.get("summary") or "")
    story_pro = enrich.promos((c.get("title") or "") + " | " + (c.get("raw_title") or "")) | enrich.promos(c.get("summary") or "")
    msrc = c.get("member_src") or {}
    vis_ok = budget_ok and rank < VISION_TOP
    if key and not guessed:   # a promotion the summary names only as their past ('rose to prominence in TNA') isn't the story's
        try:
            import current; story_pro = frozenset(story_pro) - current.past_promos(c, key)
        except Exception: pass
    if not key:
        # no person in the headline: never a photo whose file name names a wrestler or another promotion
        # ('WWE Star Signs New Contract' got a Dragon Lee Raw photo from another report in the cluster); a photo tied to another
        # promotion (split 'NXT | Blood and Guts' graphic) -> the next report's photo, then the promotion card
        for u in list(dict.fromkeys([x for x in [c.get("image")] + list(member_images) if x])):
            if not enrich.subjects(enrich._fname_words(u)) and not enrich.img_clash(u, frozenset(), story_pro, story_txt) \
                    and not other_brand(u, story_pro, label(u), msrc.get(u, ""), story_txt, vis_ok):
                return u, None, "no-names"
        pr = promo_in(c.get("title") or "")      # no person, no photo: the story's promotion card instead of the WCN card
        return (PROMO_CARD.format(pr), None, "no-names-promo:" + pr) if pr else (None, None, "no-names")
    cands = list(dict.fromkeys([u for u in [c.get("image")] + member_images if u]))
    k = "choice3|" + c["id"] + "|" + key + "|" + hashlib.md5("|".join(cands).encode()).hexdigest()[:8]; C = cache()
    bf = rank >= VISION_TOP and budget_ok and not guessed and backfill_on() # one-time backlog pass
    if k in C and C[k].get("image") and not str(C[k]["image"]).startswith(PROMO_CARD[:40]):
        _L = label(C[k]["image"])          # cached pick made before the label rules: re-check its file name (free, no fetch)
        if others_named(_L, key, names) or enrich.foreign_promo(C[k]["image"], story_pro, _L, msrc.get(C[k]["image"], ""), story_txt)[0]: del C[k]
    solo = solo_subject(c, key)
    if k in C and C[k].get("st") in ("key-other-story", "report-photo") and (not solo or not solo_photo(C[k].get("image"), key)): del C[k]   # picked before the 2026-10-23 rule
    if k in C and C[k].get("st") == "key-other-story" and (person_photo(key, names, story_pro, story_txt, c["id"]) or (None,))[0] != C[k].get("image"): del C[k]   # its source card no longer qualifies
    if k in C and (str(C[k].get("st", "")).startswith("promo-logo:") or C[k].get("st") == "event-art") and guessed and NOT_WITH.search(c.get("title") or "") and free_agent(key, c) == "":
        del C[k]   # departure story, they left that promotion more than ~6 months ago (2026-10-23 rule): no promotion card
    if k in C and str(C[k].get("st", "")).startswith("promo-logo:") and not guessed:
        # placeholder picked earlier: free re-check (official roster says another promotion now, or a photo of them exists now)
        if promotion(key, c) != C[k]["st"].split(":", 1)[1] or (solo and person_photo(key, names, story_pro, story_txt, c["id"])): del C[k]
    if k in C and not (bf and not str(C[k].get("st", "")).startswith("key")):
        if C[k].get("st") == "wcn-card" and not C[k].get("image") and not guessed:   # roster lists updated since: free re-check for the promotion card
            alt = person_photo(key, names, story_pro, story_txt, c["id"]) if solo else None   # photo of them first (2026-10-23)
            if alt:
                C[k] = {"image": alt[0], "credit": alt[1], "st": "key-other-story", "key": key}; return alt[0], alt[1], "key-other-story"
            pr = promotion(key, c)
            if pr:
                C[k] = {"image": PROMO_CARD.format(pr), "credit": None, "st": "promo-logo:" + pr, "key": key}; return C[k]["image"], None, "promo-logo:" + pr
        return C[k]["image"], C[k].get("credit"), "cached:" + str(C[k].get("st", ""))
    if bf: rank = 0; fetch = True; _tl.bf = True # treated like a top card for this pass; checks counted against the backfill cap
    def done(img, st, cr=None, keep=True):
        if keep: C[k] = {"image": img, "credit": cr, "st": st, "key": key}
        return img, cr, st
    link = c.get("link") if fetch else None
    labelled, neutral, art = [], [], []
    for u in cands:
        L = label(u, link)
        if other_brand(u, story_pro, L, msrc.get(u, ""), story_txt, vis_ok and not guessed): continue   # tied to another promotion (even if it names the key person / event)
        if names_key(L, key): labelled.append(u)
        elif others_named(L, key, names): continue   # labelled with a wrestler who isn't in this story (also for names we only guessed)
        elif re.search(r"(?i)poster|logo|graphic|key[-_ ]?art|banner", L): art.append(u)
        else: neutral.append(u)
    # an earlier vision-confirmed pick for this card that showed the key person (incl. a Wikipedia photo)
    for ok_, ov in list(C.items()):
        if not ok_.startswith("choice2|" + c["id"] + "|") or not ov.get("image"): continue
        onames = ok_.split("|")[2:]
        if not any(names_key(n, key) for n in onames): continue
        u = ov["image"]; v = C.get("v2|" + u + "|" + "|".join(sorted(onames))) or C.get("v2|" + u + "|" + key) or {}
        if ov.get("credit") or (u in cands and v.get("ok") and (len(onames) == 1 or names_key(v.get("who") or "", key))):
            if u in cands or ov.get("credit"): return done(u, "key-verified-earlier", ov.get("credit"))
    pri = {u: prior(u, key) for u in neutral}
    neutral = [u for u in neutral if pri[u] is not False]
    good = [u for u in cands if u in labelled or pri.get(u)]      # shows the key person: keep candidate order (the lead report's photo first)
    if good: return done(good[0], "key-labelled" if good[0] in labelled else "key-verified-cached")
    unknown = False
    if rank < VISION_TOP and budget_ok and not guessed:   # guessed (non-roster) names: no paid checks
        for u in neutral[:3]:
            r = check(u, [key])
            if r: return done(u, "key-verified")
            if r is False: neutral = [x for x in neutral if x != u]
            unknown |= r is None
    if fetch:
        for u in inline_images(c["link"], [key]):
            if u in cands: continue
            L = label(u, link)
            if names_key(L, key) and (not guessed or names_key(L.split("|")[0], key)) or (rank < VISION_TOP and budget_ok and not guessed and check(u, [key])): return done(u, "key-inline")
    # nothing clearly shows the key person: (1) the logo card of the promotion they work for (show/event art when the story is
    # about a specific show), (2) people with no promotion: a photo from the story's own reports, (3) the WCN card (None)
    pr = promo_in(c.get("title") or "") if guessed and not neutral else (None if guessed else promotion(key, c)) # unknown name: its report's photo, else the story's promotion
    if guessed and NOT_WITH.search(c.get("title") or "") and free_agent(key, c) == "": pr, art = None, []   # left long ago: no promotion card / logo art -> photo or WCN card
    if not names_key(c.get("title") or "", key):   # key only from the source headline (published one names nobody): the story's own promotion card
        pr = promo_in(c.get("title") or "") or promo_in(c.get("raw_title") or "") or pr
    if pr:
        if art and enrich.shows(c.get("title") or ""): return done(art[0], "event-art")
        # before a placeholder for a person story (owner rule 2026-10-23): a photo of them another story already confirmed,
        # then a photo from one of this story's reports whose headline is about them alone
        alt = person_photo(key, names, story_pro, story_txt, c["id"], vis_ok) if solo else None
        if alt: return done(alt[0], "key-other-story", alt[1])
        rp = report_photo(neutral, msrc, key) if solo else None
        if rp: return done(rp, "report-photo", keep=not unknown)
        return done(PROMO_CARD.format(pr), "promo-logo:" + pr, keep=not unknown)
    if solo and not guessed:   # no promotion (free agent who left long ago, retiree, ...): a confirmed photo of them before the WCN card
        alt = person_photo(key, names, story_pro, story_txt, c["id"], vis_ok)
        if alt: return done(alt[0], "key-other-story", alt[1])
    if neutral: return done(neutral[0], "person-photo-unverified", keep=not unknown)
    if art: return done(art[0], "event-art")
    return done(None, "wcn-card", keep=not unknown)
