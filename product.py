"""Product-story photos (owner rule 2026-10-26): a story about a product (action figures, merch, a video game, a book, a DVD,
trading cards, collectibles, a pre-order) shows THE PRODUCT, not the wrestler's current-promotion logo card or a headshot.
The tag is untouched: it stays the product's brand (who makes or licenses it), and the photo ignores which promotion the
wrestler is signed to now ('WWE Xavier Woods and Ilja Dragunov Action Figures Up for Pre-Order' got the AEW logo card).

Lookup order (first hit wins):
  1. store / maker / retailer product pages LINKED in the source article -> that page's og:image (main product photo)
  2. SEARCH the brand's official store and the maker / retailer the story names (Shopify search: AEW Shop, TNAMerch,
     Mattel Creations, Mattel Shop) -> the product whose title names the wrestler(s) and the product kind
     (WWE Shop / Fanatics, Jazwares and Ringside's search block or need JavaScript from a bot: they are used via step 1 / 3)
  3. the source article's og:image / inline images that show the product (email embeds unwrapped; ads, logos, avatars,
     author photos and headshots skipped; needs a product word / maker / name in the file name or alt text, or a vision yes)
Usual checks apply (imgmeta.unusable, blocked list, panorama, file name naming another wrestler / promotion), plus one cheap
cached vision check (detail low) per candidate from the article, max 2 per story, only inside the AI cap (VISION_RESERVE_USD,
llm.pace_ok). No product photo -> None, and the normal rules (vision.choose) pick the photo.
Every result is cached per story (data/image_checks.json 'prod1|...'); misses are retried after 12 h."""
import re, os, json, time, html, hashlib, urllib.request, urllib.parse
import enrich, vision, llm

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124 Safari/537.36", "Accept": "text/html,application/json,*/*"}
MISS_TTL = 12 * 3600
MAX_VISION = 2
# ---------- detection ----------
STRONG = re.compile(r"(?i)\baction[- ]figures?\b|\b(?:elite|ultimate edition|legends|retro|superstars?|main event|unrivaled|unmatched)\b[^|]{0,25}\bfigures?\b"
                    r"|\bfigures?\b[^|]{0,40}\b(?:pre-?orders?|elite|series|wave|exclusive)\b|\bmattel\b|\bjakks\b|\bjazwares\b|\bfunko\b|\bhasbro\b"
                    r"|\bringside ?collectibles\b|\bringsidecollectibles\b|\bwwe ?2k\d*\b|\baew:? fight forever\b|\bvideo ?games?\b|\b(?:dvd|blu-?ray)s?\b"
                    r"|\btrading cards?\b|\btopps\b|\bpanini\b|\bcollectibles?\b|\bpre-?orders?\b|\breplica (?:titles?|belts?|championships?)\b"
                    r"|\b(?:new|upcoming|forthcoming|his|her|their) (?:book|memoir|autobiography|comic)\b|\bmemoir\b|\bautobiography\b|\bbook (?:release|launch|is out|out now)\b")
MERCH = re.compile(r"(?i)\b(?:merch(?:andise)?|t-?shirts?|shirts?|hoodies?|hats?|apparel|collection|jerseys?|posters?)\b")
LAUNCH = re.compile(r"(?i)\b(?:pre-?orders?|launch\w*|releas\w*|unveil\w*|reveal\w*|announc\w*|available|adds?|drops?|debuts?|on sale|first look|"
                    r"offers?|new|now|exclusive|out)\b")
NOT_PRODUCT = re.compile(r"(?i)\b(?:wear\w*|wore|sales? (?:record|numbers|figures)|praise\w*|made|couldn'?t|didn'?t|tickets?|sold out arena|attendance)\b")
def is_product(c):
    """True for a story ABOUT a product. Headline first; the source headline too unless it is a roundup ('... & More')."""
    t = c.get("title") or ""
    raw = c.get("raw_title") or ""
    txts = [t] + ([raw] if raw and not vision.roundup_title(raw) and not re.search(r"(?i)&\s*more\b|\band more\b", raw) else [])
    for x in txts:
        if STRONG.search(x) and not re.search(r"(?i)\bsales? figures?\b|\bviewership figures?\b", x): return True
        if MERCH.search(x) and LAUNCH.search(x) and not NOT_PRODUCT.search(x): return True
    return False
# what kind of product, so a store hit is the same kind of thing (a figure story never gets a t-shirt)
KINDS = [("figure", r"figure|elite|ultimate|action|collector|series"), ("shirt", r"t-?shirt|\btee\b|shirt"), ("hoodie", r"hoodie|sweatshirt"),
         ("hat", r"\bhat\b|cap|snapback"), ("game", r"2k\d*|video ?game|fight forever|dlc|pack"), ("book", r"book|memoir|autobiograph|comic"),
         ("dvd", r"dvd|blu-?ray"), ("cards", r"cards?|topps|panini"), ("belt", r"replica|title belt|championship belt"), ("poster", r"poster|print")]
def kinds(txt):
    k = [k for k, rx in KINDS if re.search(rx, txt, re.I)]
    return [x for x in k if x != "figure"] if "game" in k and not re.search(r"(?i)\bfigures?\b", txt) else k   # 'WWE 2K26 ... Elite Pack' is a game
SERIES = re.compile(r"(?i)\b(elite|series|wave|ultimate edition|legends|retro|2k)\s*(?:collection\s*)?(?:series\s*)?#?\s*(\d{1,3})\b")
def series(txt): return {(a.lower(), b) for a, b in SERIES.findall(txt or "")}
STOP = set("with from that this their have will been into over after about available order orders preorder announced revealed launches launch adds".split())
def words(t): return {w for w in re.findall(r"[a-z0-9]{4,}", (t or "").lower()) if w not in STOP and w not in ("wwe", "tna")}
LOCALE = re.compile(r"(?i)-(?:es|fr|de|it|pt|nl|pl|ja|ko|zh)-(?:mx|es|fr|de|it|br|pt|nl|pl|jp|kr|cn|tw|ca|la)(?:/|$|\?)|/(?:es|fr|de|it|pt|ja)(?:-[a-z]{2})?/products/")
def fresh(img, ts, days=240):
    """Shopify image '?v=<epoch>' within `days` before the story (a 2025 Elite figure is not the new one); unknown -> True."""
    m = re.search(r"[?&]v=(\d{10})\b", img or "")
    return not m or not ts or int(m.group(1)) >= ts - days * 86400
def kind_ok(story_kinds, title):
    return not story_kinds or any(re.search(dict(KINDS)[k], title, re.I) for k in story_kinds)
# ---------- stores ----------
STORE_DOM = re.compile(r"(?i)^(?:www\.)?(?:ringsidecollectibles\.com|wrestlingfigures\.com|shop\.wwe\.com|wweshop\.com|shopaew\.com|tnamerch\.com|"
                       r"(?:creations\.|shop\.)?mattel\.com|jazwares\.com|jakks\.com|(?:wwe\.)?2k\.com|fanatics\.com|funko\.com|amazon\.com|"
                       r"target\.com|walmart\.com|gamestop\.com|entertainmentearth\.com|toploadersandsleeves\.com|topps\.com|paniniamerica\.net|"
                       r"prowrestlingtees\.com|hottopic\.com|boxlunch\.com|ecwpress\.com|simonandschuster\.com|penguinrandomhouse\.com|"
                       r"harpercollins\.com|triumphbooks\.com)$")
SHOPIFY = {"aew": ["https://shopaew.com/en-us"], "tna": ["https://tnamerch.com"],
           "mattel": ["https://creations.mattel.com", "https://shop.mattel.com"]}
SHOP_NAME = {"shopaew.com": "AEW Shop", "tnamerch.com": "TNAMerch", "creations.mattel.com": "Mattel Creations", "shop.mattel.com": "Mattel Shop",
             "ringsidecollectibles.com": "Ringside Collectibles", "shop.wwe.com": "WWE Shop", "jazwares.com": "Jazwares"}
def shop_name(u):
    h = urllib.parse.urlsplit(u).netloc.lower().removeprefix("www.")
    return SHOP_NAME.get(h) or h
def stores_for(c):
    """Shopify stores to search, in order: the brand's official store (the story's tag / promotions), then the maker named."""
    txt = " ".join([c.get("title") or "", c.get("raw_title") or "", c.get("summary") or ""])
    pro = set(enrich.promos((c.get("title") or "") + " | " + (c.get("raw_title") or ""))) | {x.lower() for x in (c.get("categories") or []) if isinstance(x, str)}
    out = []
    for p in ("aew", "tna"):
        if p in pro or p.upper() in pro: out += SHOPIFY[p]
    if re.search(r"(?i)\bmattel\b", txt) or (("wwe" in pro or "WWE" in pro) and re.search(r"(?i)\bfigures?\b", (c.get("title") or "") + " " + (c.get("raw_title") or ""))):
        out += SHOPIFY["mattel"]   # Mattel holds the WWE figure licence
    return list(dict.fromkeys(out))
# ---------- fetch helpers (patchable in tests) ----------
def _get(url, t=10):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=t).read()[:1500000].decode("utf8", "ignore")
def page_image(url):
    """(og:image, page title) of a product page, or (None, '')."""
    try: h = _get(url)
    except Exception: return None, ""
    img = enrich.meta(h, "og:image") or enrich.meta(h, "twitter:image")
    ttl = enrich.meta(h, "og:title") or (re.search(r"(?is)<title>(.*?)</title>", h) or [None, ""])[1]
    if img: img = urllib.parse.urljoin(url, img.strip())
    return img, html.unescape(ttl or "").strip()
def shopify_search(base, q, n=10):
    """[(title, product url, image)] from a Shopify store's public search suggestions."""
    u = base.rstrip("/") + "/search/suggest.json?" + urllib.parse.urlencode({"q": q, "resources[type]": "product", "resources[limit]": n})
    try: d = json.loads(_get(u))
    except Exception: return []
    out = []
    for p in ((d.get("resources") or {}).get("results") or {}).get("products") or []:
        img = p.get("image") or ((p.get("featured_image") or {}).get("url"))
        if not img: continue
        if img.startswith("//"): img = "https:" + img
        pu = urllib.parse.urljoin(base.rstrip("/") + "/", (p.get("url") or "").split("?")[0])
        out.append((p.get("title") or "", pu, img))
    return out
def unwrap(u):
    """Email-embed proxies (googleusercontent ...#https://real) -> the real image URL."""
    if "googleusercontent.com" in u and "#http" in u: return u.split("#", 1)[1]
    return u
BAD_IMG = re.compile(r"(?i)/advert|/ads?/|doubleclick|logo|avatar|icon|sprite|favicon|1x1|pixel|spacer|badge|button|banner|/author|headshot|gravatar|emoji|instagram|facebook|twitter|tiktok|youtube|threads|social|share|\.gif(?:$|\?)|\.svg(?:$|\?)")
PRODUCT_WORD = re.compile(r"(?i)figure|elite|ultimate|mattel|jakks|jazwares|funko|collect|2k\d*|game|cover|box|packag|shirt|tee|hoodie|merch|book|dvd|blu-?ray|card|replica|belt|product|toy")
def article_images(url):
    """[(image url, alt/caption text)] of the source article: og:image first, then inline images (email embeds unwrapped)."""
    try: h = _get(url)
    except Exception: return []
    out = []
    og = enrich.meta(h, "og:image") or enrich.meta(h, "twitter:image")
    if og: out.append((urllib.parse.urljoin(url, og.strip()), enrich.meta(h, "og:image:alt") or ""))
    for m in re.finditer(r"<img[^>]+>", h):
        tag = m.group(0); src = re.search(r'(?:data-src|src)=["\']([^"\']+)', tag)
        if not src or src.group(1).startswith("data:"): continue
        alt = (re.search(r'alt=["\']([^"\']*)', tag) or [None, ""])[1]
        out.append((unwrap(urllib.parse.urljoin(url, html.unescape(src.group(1)))), html.unescape(alt)))
    seen, res = set(), []
    for u, a in out:
        if u not in seen: seen.add(u); res.append((u, a))
    return res
def store_links(url):
    """Product pages on store / maker / retailer sites linked in the article (not their home pages)."""
    try: h = _get(url)
    except Exception: return []
    out = []
    for m in re.finditer(r'href=["\']([^"\']+)["\']', h):
        u = html.unescape(m.group(1)); s = urllib.parse.urlsplit(u)
        if s.scheme in ("http", "https") and STORE_DOM.match(s.netloc) and len(s.path.strip("/")) > 3: out.append(u)
    return list(dict.fromkeys(out))[:4]
# ---------- checks ----------
def usable(u, c):
    import imgmeta, photoguard
    if not u or BAD_IMG.search(urllib.parse.urlsplit(u).path + "?" + (urllib.parse.urlsplit(u).query or "")): return False
    if imgmeta.unusable(u) or vision.blocked(u) or photoguard.pano_url(u): return False
    story_pro = enrich.promos((c.get("title") or "") + " | " + (c.get("raw_title") or "") + " | " + (c.get("summary") or ""))
    return not enrich.img_clash(u, frozenset(), story_pro, (c.get("title") or "") + " | " + (c.get("raw_title") or ""))
def is_product_photo(img, what):
    """Cheap vision check: does the image show the product (not a person photo, logo or poster)? True / False / None (unknown)."""
    k = "prod1v|" + img + "|" + what; C = vision.cache()
    if k in C: return C[k]["ok"]
    key = os.environ.get("AI_API_KEY")
    if not key or llm.budget_left() < vision.VISION_RESERVE_USD or not llm.pace_ok(): return None
    prompt = ("Product photo check. The story is about this product: " + what + ". Answer true ONLY if the image clearly shows a product "
              "(action figure, packaging, merchandise item, video game cover/screenshot art, book cover, DVD, trading card, replica belt) "
              "matching that description. Answer false for a photo of a person/wrestler in action, a promotion logo, an event poster, an ad, "
              "or an unrelated item. Return JSON {\"product\": true|false}.")
    body = {"model": llm.MODEL, "max_tokens": 30, "temperature": 0, "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": img, "detail": "low"}}, {"type": "text", "text": prompt}]}]}
    try:
        r = urllib.request.urlopen(urllib.request.Request(llm.URL, data=json.dumps(body).encode(), headers=llm.HDR(key, "wcn-vision")), timeout=45)
        d = json.load(r)
        with llm._lock: llm.add_cost(d.get("usage", {}).get("cost_in_usd_ticks", 0) / 1e10, "vision")
        ok = bool(json.loads(d["choices"][0]["message"]["content"]).get("product"))
        C[k] = {"ok": ok, "at": int(time.time())}; return ok
    except Exception as e:
        if "400" in str(e)[:100]: C[k] = {"ok": False, "at": int(time.time())}
        print("product vision error:", str(e)[:100], flush=True); return None
# ---------- the pick ----------
def _names(c):
    try: key, names, guessed = vision.key_person(c)
    except Exception: key, names, guessed = None, [], True
    return [n for n in ([key] if key else []) + list(names or []) if n and (not guessed or len(n.split()) >= 2)]
def _lead(c):
    u = c.get("link") or ""
    if "news.google.com" in u:
        try: u = enrich.resolve_google(u)
        except Exception: return None
    return u or None
EMAIL_CDN = re.compile(r"(?i)stripocdn|mcusercontent|mailchimp|klaviyo|sendgrid|cmail|hubspotemail|ctctcdn")
RETAILERS = [(r"(?i)ringside ?collectibles|ringsidecollectibles|wrestlingfigures\.com", "Ringside Collectibles"), (r"(?i)\bmattel\b", "Mattel"),
             (r"(?i)\bjazwares\b", "Jazwares"), (r"(?i)\bwwe ?shop\b", "WWE Shop"), (r"(?i)\baew ?shop\b", "AEW Shop")]
def article_credit(u, c, lead):
    """Credit for an article photo; a retailer's email-newsletter image is credited to the retailer, via the report."""
    src = c.get("source") or urllib.parse.urlsplit(lead or "").netloc.removeprefix("www.")
    if not lead: return None
    if EMAIL_CDN.search(urllib.parse.urlsplit(u).netloc):
        t = " ".join([c.get("title") or "", c.get("raw_title") or "", c.get("summary") or ""])
        for rx, n in RETAILERS:
            if re.search(rx, t): return {"url": lead, "text": "Photo: " + n + " via " + src}
    return {"url": lead, "text": "Photo: " + src}
def find(c, member_images=(), vision_ok=True):
    """(image, credit, status) for a product story, or None (use the normal rules)."""
    names = list(dict.fromkeys(_names(c)))
    txt = (c.get("title") or "") + " | " + (c.get("raw_title") or "")
    sk = kinds(txt)
    ser = series(txt + " " + (c.get("summary") or ""))   # 'Elite 130' in the story -> only an Elite 130 product
    lead = _lead(c)
    def named(t): return not names or any(vision.names_key(t, n) for n in names)
    # 1. store / maker / retailer product pages linked in the article
    for su in store_links(lead) if lead else []:
        img, ttl = page_image(su)
        if img and usable(img, c) and named(ttl + " " + su.replace("-", " ")):
            return img, {"url": su, "text": "Photo: " + shop_name(su)}, "product:store-link"
    # 2. the brand's official store and the maker named in the story
    for base in stores_for(c):
        for q in (names[:2] or [re.sub(r"(?i)\b(?:up for|available|for|pre-?orders?|announced|revealed|new|and)\b", " ", c.get("title") or "")[:60]]):
            hits = [h for h in shopify_search(base, q) if named(h[0]) and kind_ok(sk, h[0]) and not LOCALE.search(h[1])
                    and fresh(h[2], c.get("first_ts") or c.get("ts")) and (not ser or series(h[0]) & ser)
                    and (names or len(words(h[0]) & words(c.get("title"))) >= 2) and usable(h[2], c)]
            if hits:
                t, pu, img = hits[0]
                return img, {"url": pu, "text": "Photo: " + shop_name(base)}, "product:store"
    # 3. the source article's own image(s) of the product
    nv = 0
    cands = article_images(lead) if lead else []
    for u in [m for m in member_images if m]:
        if u not in [x[0] for x in cands]: cands.append((u, ""))
    labelled, other = [], []
    for u, alt in cands:
        if not usable(u, c): continue
        L = vision.label(u) + " | " + alt
        others = [] if not names else vision.others_named(L, names[0], names)
        if others: continue
        (labelled if PRODUCT_WORD.search(L) else other).append(u)
    def score(u):   # the photo naming the most of the story's people first (the figure itself, not the set's promo banner)
        L = vision.label(u) + " | " + dict(cands).get(u, "")
        return -sum(1 for n in names if vision.names_key(L, n) or n.split()[0].lower() in L.lower())
    labelled.sort(key=score)
    for u in labelled + other:
        ok = is_product_photo(u, txt) if (vision_ok and nv < MAX_VISION) else None
        if ok is not None: nv += 1
        if ok is False: continue
        if ok or u in labelled:
            return u, article_credit(u, c, lead), "product:article"
    return None
def pick(c, member_images=(), vision_ok=True, fetch=True):
    """Cached product photo for card c, or None. Non-product stories return None at once (no fetch, no cost)."""
    if not is_product(c): return None
    k = "prod1|" + c["id"] + "|" + hashlib.md5(((c.get("title") or "") + "|" + (c.get("link") or "")).encode()).hexdigest()[:8]; C = vision.cache()
    v = C.get(k)
    if v and v.get("image"):
        import imgmeta
        if not imgmeta.unusable(v["image"]) and not vision.blocked(v["image"]): return v["image"], v.get("credit"), "cached:" + v["st"]
    elif v and time.time() - v.get("at", 0) < MISS_TTL: return None
    if not fetch: return None
    try: r = find(c, member_images, vision_ok)
    except Exception as e:
        print("product photo error:", c.get("id"), str(e)[:120], flush=True); r = None
    C[k] = {"image": r[0], "credit": r[1], "st": r[2], "at": int(time.time())} if r else {"image": None, "at": int(time.time())}
    return r
