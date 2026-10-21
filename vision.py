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
def promotion(key, c):
    """Promotion the key person works for (existing roster brand lists + the story's own promotion/show names), or None for
    free agents, retirees, legends/commentators, celebrities, people who just left or died, and unknown names."""
    import editorial
    k = key.lower(); t = c.get("title") or ""
    if NOT_WITH.search(t): return None
    def hit(n):
        n = n.strip()
        if not n: return False
        try:
            if re.search(r"(?<![a-z])(?:" + n + r")(?![a-z])", key, re.I): return True
        except re.error: pass
        return re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", re.sub(r"\[[^]]*\]", "e", n).lower()) is not None
    brands = [b for b, v in editorial.ROSTER.items() if any(hit(n) for n in v.split("|"))]
    tp = promo_in(t)
    if not brands:   # not on our roster lists (lists lag behind signings): the story itself says they compete/signed there
        if tp and tp in ("wwe", "aew", "tna", "nxt", "roh") and re.search(r"(?i)\b(retains?|wins?|won|beats?|defeats?|debuts?|signs?|signed|captures?|crowned|champions?)\b", t): return tp
        return None
    named = {k_ for k_, rx in PROMO_TXT if re.search(rx, t, re.I)}
    own = {b.lower() for b in brands} | ({"nxt"} if "WWE" in brands else set()) | ({"roh"} if "AEW" in brands else set())
    if tp and not named & own and re.search(r"(?i)\b(results?|card|tag match|show|event|tour|episode|teams? with|appears? (at|in|on))\b", t):
        return tp # the story is about another promotion's show ('CMLL Viernes Espectacular Results', 'AEW Star Teams With X In CMLL')
    if tp in ("wwe", "aew", "tna") and tp.upper() not in brands and re.search(r"(?i)\b(retains?|wins?|won|beats?|defeats?|debuts?|signs?|signed|captures?|crowned)\b", t):
        return tp # roster list is behind: they're competing/signed there now ('Andrade Retains AEW National Title')
    if "WWE" in brands and (tp == "nxt" or (tp is None and re.search(r"\bNXT\b", c.get("summary") or ""))): return "nxt"
    if "AEW" in brands and tp == "roh": return "roh"
    for b in brands:
        if b in ("WWE", "AEW", "TNA") and (tp in (None, b.lower()) or len(brands) == 1): return b.lower()
    if any(b in ("Global", "Indie") for b in brands): return tp
    return brands[0].lower() if brands[0] in ("WWE", "AEW", "TNA") else None
VISION_TOP = 60          # vision confirms only for the top cards on the homepage
def choose(c, member_images, budget_ok=True, rank=0, fetch=True):
    """Photo that shows the story's key person. Order: candidate labelled with the key person (file name/alt/caption) ->
    vision-confirmed (top cards only, ambiguous candidates only, cached per image) -> article photo captioned with them ->
    their free-licence Wikipedia photo -> best unlabelled on-topic photo / show or event art -> none (WCN default card).
    A photo labelled with a DIFFERENT wrestler, or that vision says shows someone else, is never used.
    Returns (image or None, credit dict or None, status)."""
    _tl.n = 0; _tl.bf = False
    key, names, guessed = key_person(c)
    story_pro = enrich.promos((c.get("title") or "") + " | " + (c.get("raw_title") or ""))
    if not key:
        # no person in the headline: never a photo whose file name names a wrestler or another promotion
        # ('WWE Star Signs New Contract' got a Dragon Lee Raw photo from another report in the cluster)
        if c.get("image") and not enrich.subjects(enrich._fname_words(c["image"])) and not enrich.img_clash(c["image"], frozenset(), story_pro):
            return c["image"], None, "no-names"
        pr = promo_in(c.get("title") or "")      # no person, no photo: the story's promotion card instead of the WCN card
        return (PROMO_CARD.format(pr), None, "no-names-promo:" + pr) if pr else (None, None, "no-names")
    cands = list(dict.fromkeys([u for u in [c.get("image")] + member_images if u]))
    k = "choice3|" + c["id"] + "|" + key + "|" + hashlib.md5("|".join(cands).encode()).hexdigest()[:8]; C = cache()
    bf = rank >= VISION_TOP and budget_ok and not guessed and backfill_on() # one-time backlog pass
    if k in C and C[k].get("image") and not str(C[k]["image"]).startswith(PROMO_CARD[:40]):
        _L = label(C[k]["image"])          # cached pick made before the label rules: re-check its file name (free, no fetch)
        if others_named(_L, key, names) or (story_pro and enrich.promos(_L) and not enrich.promos(_L) & story_pro): del C[k]
    if k in C and not (bf and not str(C[k].get("st", "")).startswith("key")):
        if C[k].get("st") == "wcn-card" and not C[k].get("image") and not guessed:   # roster lists updated since: free re-check for the promotion card
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
        if names_key(L, key): labelled.append(u)
        elif others_named(L, key, names): continue   # labelled with a wrestler who isn't in this story (also for names we only guessed)
        elif story_pro and enrich.promos(L) and not enrich.promos(L) & story_pro: continue   # labelled with another promotion
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
    if pr:
        if art and enrich.shows(c.get("title") or ""): return done(art[0], "event-art")
        return done(PROMO_CARD.format(pr), "promo-logo:" + pr, keep=not unknown)
    if neutral: return done(neutral[0], "person-photo-unverified", keep=not unknown)
    if art: return done(art[0], "event-art")
    return done(None, "wcn-card", keep=not unknown)
