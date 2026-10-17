"""Image relevance: Grok vision check + Wikipedia/Commons fallback. Verdicts cached per (image, names)."""
import os, re, json, html, time, urllib.request, urllib.parse
import llm
CACHE_F = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "image_checks.json")
UA = {"User-Agent": "WCN-bot/1.0 (https://wrestlingcentralnews.github.io/wcn/; wcn@mail.grokbot.com)"}
VISION_RESERVE_USD = 1.5   # stop vision checks when less than this remains in the monthly cap
_C = None
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
    if not key or llm.budget_left() < VISION_RESERVE_USD: return None
    prompt = ("Pro-wrestling photo check. Expected people: " + ", ".join(names) +
              ". Answer true ONLY if an expected person is the clear main focus of the photo: shown solo, or dominant/central and largest. "
              "If two people are expected, a photo of either one or both together is fine. Answer false for event posters, logos/graphics, "
              "group shots or lineups with several other wrestlers, crowd shots, or if the focus is a different person. "
              "Return JSON {\"shows_expected\": true|false, \"who\": \"who you believe is shown, or 'unknown'\"}.")
    body = {"model": llm.MODEL, "max_tokens": 60, "temperature": 0, "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": img, "detail": "low"}}, {"type": "text", "text": prompt}]}]}
    try:
        r = urllib.request.urlopen(urllib.request.Request(llm.URL, data=json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}), timeout=45)
        d = json.load(r)
        with llm._lock:
            llm._U["usd"] += d.get("usage", {}).get("cost_in_usd_ticks", 0) / 1e10; llm._U["vision"] = llm._U.get("vision", 0) + 1
        out = json.loads(d["choices"][0]["message"]["content"])
        c[k] = {"ok": bool(out.get("shows_expected")), "who": out.get("who"), "at": int(time.time())}
        return c[k]["ok"]
    except Exception as e:
        msg = str(e)[:100]
        if "400" in msg or "image" in msg.lower(): c[k] = {"ok": False, "who": "unloadable", "at": int(time.time())}
        print("vision error:", msg, flush=True); return None
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
def choose(c, member_images, budget_ok=True):
    """Pick a photo that shows the headline's main person(s). Returns (image or None, credit dict or None, status)."""
    names = names_in(c["title"]); guessed = names_in.guessed
    if not names: names = names_in(c.get("raw_title", "")); guessed = names_in.guessed
    if not names: return c.get("image"), None, "no-names"
    k = "choice2|" + c["id"] + "|" + "|".join(names); C = cache()
    if k in C: return C[k]["image"], C[k].get("credit"), "cached"
    cands = list(dict.fromkeys([u for u in [c.get("image")] + member_images if u]))
    unknown = False
    for u in cands[:4]:
        r = check(u, names)
        if r: C[k] = {"image": u}; return u, None, "verified" if u == c.get("image") else "replaced-cluster"
        unknown |= r is None
    for u in inline_images(c["link"], names):
        if check(u, names): C[k] = {"image": u}; return u, None, "replaced-inline"
    for n in names:
        w = wikipedia(n)
        if w and check(w["url"], [n]):
            cr = {"text": w["credit"], "url": w["credit_url"]}; C[k] = {"image": w["url"], "credit": cr}; return w["url"], cr, "replaced-wiki"
    if unknown: return c.get("image"), None, "unknown"
    if guessed: C[k] = {"image": c.get("image")}; return c.get("image"), None, "unverified-name-kept"   # couldn't check (budget/API): don't cache, keep for retry
    C[k] = {"image": None}; return None, None, "placeholder"
