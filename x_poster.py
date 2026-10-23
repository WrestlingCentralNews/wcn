"""Auto-post the most important NEW WCN stories to X (@wrestlingWCN).

Posts are link-free (cheap X plan): headline + one line + hashtags + "link in bio".
Full Card reports (fullcard.py) post ONCE as a clean card list (card_text) while the show hasn't started; card updates keep the
same story id, so they never repost.
Runs after the site deploy in the 15-min workflow. Standard library only (OAuth 1.0a user context).
Enable with env X_POST_ENABLED=1 (repo variable); anything else = dry run (logs what it would post).
State: data/posted_x.json (saved to the 'data' branch with the rest of the state).
"""
import os, re, sys, json, time, hmac, base64, hashlib, secrets, ssl, urllib.parse, urllib.request, urllib.error
import xspend, breaking, editorial
ROOT = os.path.dirname(os.path.abspath(__file__))
NEWS = os.path.join(ROOT, "public", "news.json")
STATE = os.path.join(ROOT, "data", "posted_x.json")
SITE_HOST = "wrestlingcentralnews.com"
# --- posting rules -------------------------------------------------------------------------------
DAILY_CAP = 10            # max posts in any rolling 24h (cheap plan: link-free posts only)
PER_RUN = 1               # normal max per 15-min run
PER_RUN_BREAKING = 2      # allowed when the 2nd candidate is also breaking-level
MIN_GAP_MIN = 25          # minutes between posting runs (breaking news may skip the gap)
FRESH_H = 8               # only stories whose first report is younger than this
MIN_SCORE = 14            # importance threshold
BREAKING = 26
# BREAKING-labelled posts (breaking.kind: title change / release / debut / return, owner rule 2026-10-18) skip DAILY_CAP and
# MIN_GAP; only normal posts count toward the cap. Safety limits so a misfire can't drain credits: trusted source required,
# at most BREAKING_PER_RUN per run and BREAKING_MAX_24H per rolling 24h (at $0.015 each that's <= $0.18/day).
BREAKING_PER_RUN = 2
BREAKING_MAX_24H = 12
PAUSE_ON_PAYMENT_H = 6    # back off after credit/payment errors
CAT_BONUS = {"WWE": 4, "AEW": 4, "TNA": 2, "Global": 1, "Indie": 0}
KIND_BONUS = {"news": 3, "match": 3, "quote": 1, "results": 1}
MAJOR = re.compile(r"\b(champion\w*|title|injur\w*|sign\w*|releas\w*|died|dies|death|passe[sd] away|return\w*|debut\w*|retire\w*|suspend\w*|arrest\w*|leav\w*|departs?|contract|surgery|hall of fame|wrestlemania|all in|bound for glory)\b", re.I)
TAGS = [(r"\bNXT\b", "#WWENXT"), (r"\bROH\b|Ring of Honor", "#ROH"), (r"\bNJPW\b|New Japan", "#NJPW"), (r"\bAAA\b", "#AAA"),
        (r"\bCMLL\b", "#CMLL"), (r"\bRaw\b", "#WWERaw"), (r"\bSmackDown\b", "#SmackDown"), (r"\bDynamite\b", "#AEWDynamite"), (r"\bCollision\b", "#AEWCollision")]
CAT_TAG = {"WWE": "#WWE", "AEW": "#AEW", "TNA": "#TNA", "Indie": "#IndieWrestling", "Global": "#ProWrestling"}

def log(*a): print("[x]", *a, flush=True)

# --- don't repeat a match result that live_x.py already posted for the same show -----------------
LIVE_STATE = os.path.join(ROOT, "data", "posted_live_x.json")
LIVE_DIR = os.path.join(ROOT, "data", "live")
RESULT_RX = re.compile(r"\b(retain\w*|beat\w*|def\.|defeat\w*|wins?|won|tops?|topped|over|outlast\w*|pins?|pinned|submit\w*|leads?|crowned|new champion|captures?|dethrones?)\b", re.I)
def _fold(t):
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFKD", t or "") if not unicodedata.combining(ch)).lower()
def _side_names(side):
    """'The Young Bucks (Matt Jackson and Nick Jackson)' -> ['young bucks', 'matt jackson', 'nick jackson']"""
    parts = [re.sub(r"\(.*?\)", "", side)] + re.split(r",|&|\band\b|\bw/", " ".join(re.findall(r"\((.*?)\)", side)))
    out = []
    for p in parts:
        p = _fold(re.sub(r"(?i)^\s*the\s+", "", p.strip()).strip(" .\"“”"))
        if len(p) >= 4: out.append(p)
    return out
def live_posted():
    """[(show_state, [facts already posted by live_x])] for shows with posted results."""
    try: S = json.load(open(LIVE_STATE))
    except Exception: return []
    out = []
    for key, P in S.get("shows", {}).items():
        if not P.get("facts"): continue
        try: st = json.load(open(os.path.join(LIVE_DIR, key + ".json")))
        except Exception: st = {"key": key, "name": key}
        out.append((st, P["facts"]))
    return out
def live_dup(c, L):
    """(show key, fact) if story c is just a match result live_x already posted for that show, else None."""
    if not L: return None
    title = c.get("title", "") + " " + c.get("raw_title", "")
    if (c.get("kind") or {}).get("type") != "results" and not RESULT_RX.search(title): return None
    t = _fold(title); h = c.get("hub") or {}
    for st, facts in L:
        key = st.get("key", "")
        word = _fold(re.sub(r"^(WWE|AEW|TNA|NXT|ROH|NJPW)\s+|\s+\d{4}$", "", st.get("name", ""))).strip()
        on_show = (h.get("date") and f"{h['date']}-{h.get('slug')}" == key) or (len(word) >= 4 and word in t)
        if not on_show: continue
        if st.get("start") and not any(st["start"] - 3 * 3600 <= ts <= st.get("end", st["start"]) + 2 * 86400 for ts in (c.get("first_ts", c["ts"]), c["ts"])): continue
        for f in facts:
            if any(re.search(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", t) for n in _side_names(f.get("winner", ""))): return key, f
    return None
def load_state():
    try: s = json.load(open(STATE))
    except Exception: s = {}
    s.setdefault("posted", {}); s.setdefault("links", []); s.setdefault("log", []); apply_manual(s); return s
MANUAL = os.path.join(ROOT, "x_manual.json")
def apply_manual(s):
    """Tweets deleted by hand (x_manual.json): keep the story marked posted (never re-post it) but flag the tweet deleted so it
    no longer counts as live or toward the daily cap. Idempotent."""
    try: dels = json.load(open(MANUAL)).get("deleted_tweets", [])
    except Exception: return
    for d in dels:
        tid = str(d.get("tweet") or "")
        if not tid: continue
        mark = {"deleted": True, "deleted_at": d.get("at"), "deleted_reason": d.get("reason")}
        hit = [k for k, p in s["posted"].items() if str(p.get("tweet")) == tid]
        if not hit and d.get("card"): s["posted"][d["card"]] = {"tweet": tid, "at": d.get("at"), "title": "(deleted)"}; hit = [d["card"]]
        for k in hit: s["posted"][k].update(mark)
        for e in s["log"]:
            if str(e.get("tweet")) == tid: e.update(mark)
        s.setdefault("deleted", {})[tid] = {"card": hit[0] if hit else d.get("card"), "at": d.get("at"), "reason": d.get("reason")}
def save_state(s):
    s["links"] = s["links"][-3000:]; s["log"] = s["log"][-200:]
    os.makedirs(os.path.dirname(STATE), exist_ok=True); json.dump(s, open(STATE, "w"), indent=0)

def source_text(c):
    """the lead source's OWN title + summary (never our AI rewrite): breaking.kind needs the event stated there too"""
    return ((c.get("raw_title") or "") + "\n" + (c.get("src_summary") or "")).strip()
def is_breaking(c): return not c.get("fullcard") and bool(breaking.kind(c["title"], (c.get("kind") or {}).get("type"), source_text(c)))
def score(c):
    s = 2 * min(c.get("sources", 1), 8) + 2 * min(c.get("trusted", 0), 4)
    s += max(CAT_BONUS.get(k, 0) for k in c["categories"])
    s += KIND_BONUS.get((c.get("kind") or {}).get("type", "news"), 1)
    s += 1 if c.get("image") else 0
    s += 3 if MAJOR.search(c["title"]) else 0
    if c.get("trusted", 0) == 0: s -= 6                     # never lead with only low-trust sourcing
    if "Indie" in c["categories"] and c.get("sources", 1) < 3: s -= 4
    return s

# Posts must contain NO URL (X bills link posts at a much higher rate): no links, no bare domains.
URLISH = re.compile(r"(?i)(https?://|www\.|\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.[a-z]{2,}\b|\b\d{1,3}(?:\.\d{1,3}){3}\b)")
OUTROS = ["Full story: link in bio", "Full story at the link in our bio", "More details: link in bio", "Full report: link in bio"]
def x_len(t):
    """Character count with X's weighting (most Latin text = 1, emoji/CJK etc. = 2)."""
    import unicodedata
    n = 0
    for ch in unicodedata.normalize("NFC", t):
        o = ord(ch)
        n += 1 if (o <= 4351 or 8192 <= o <= 8205 or 8208 <= o <= 8223 or 8242 <= o <= 8247) else 2
    return n
def has_url(t): return bool(URLISH.search(t))
def hashtags(c, text):
    tags = []
    for k in c["categories"]:
        t = CAT_TAG.get(k)
        if t and t not in tags: tags.append(t)
    for rx, t in TAGS:
        if len(tags) >= 3: break
        if re.search(rx, text) and t not in tags: tags.append(t)   # only from what the post actually says
    return tags[:3]
def tweet_text(c):
    # label ONLY for title changes / releases / debuts / returns (breaking.py); nothing else gets a siren
    title = c["title"].replace("🚨", "").strip()
    label = breaking.LABEL + "\n" if breaking.kind(title, (c.get("kind") or {}).get("type"), source_text(c)) else ""
    head = label + title
    outro = OUTROS[int(hashlib.md5(c["id"].encode()).hexdigest(), 16) % len(OUTROS)]
    def build(line): return "\n\n".join([head] + ([line] if line else []) + [" ".join(hashtags(c, title + " " + line)) + "\n" + outro])
    line = ""
    for snt in re.split(r"(?<=[.!?])\s+", (c.get("summary") or "").strip()):
        cand = (line + " " + snt).strip()
        if len(cand) > (230 if not line else 200) or x_len(build(cand)) > 280 or has_url(cand): break
        line = cand
    text = build(line)
    if has_url(text) or x_len(text) > 280:
        text = build("")                                  # drop the summary line and retry
    while x_len(text) > 280 and len(title) > 40:          # still too long: trim the headline, never the label
        title = title[:max(40, len(title) - max(4, x_len(text) - 280))].rsplit(" ", 1)[0].rstrip(",;:-–") + "…"; head = label + title; text = build("")
    if has_url(text) or x_len(text) > 280: return None    # safety: never send anything URL-like or too long
    return text

# --- Full Card reports (owner 2026-10-23): one post per show card, a clean list, regular (never BREAKING), link in bio ----------
def card_due(c, now):
    """unposted Full Card whose show hasn't started (lead_until = show start) and that has at least 2 matches"""
    return bool(c.get("fullcard")) and now < int(c.get("lead_until") or 0) and len(c.get("card") or []) >= 2
_VERB = (r"(?:faces?|takes? on|battles?|meets?|collides? with|clash(?:es)? with|squares? off (?:against|with)|goes one-on-one with|"
         r"goes? head-to-head with|wrestles?|tangles? with|locks? up with|is set to face|will face|vs\.?|versus)")
def match_line(line, short=False):
    """WWE.com card sentence -> 'A (c) vs. B: Title' / 'A vs. B: Street Fight' (falls back to the sentence)."""
    t = re.sub(r"\s+", " ", line.replace("’", "'")).strip().rstrip(".")
    t = re.sub(r"(?i)\b(once again|again|finally|look to|looks to|set to|will)\s+", "", t)
    title = lambda s: re.sub(r"(?i)^(the )?(WWE |AEW |TNA |NXT |AAA )?", "", s.strip()).strip()
    m = re.match(r"(?i)^(.+?) defends? (?:the |their |her |his )?(.+?) against (.+?)$", t)
    if m: a, b, extra = f"{m[1]} (c)", m[3], title(m[2])
    else:
        m = re.match(r"(?i)^(.+?) challenges? (.+?) for (?:the )?(.+?)$", t)
        if m: a, b, extra = f"{m[2]} (c)", m[1], title(m[3])
        else:
            m = re.match(r"(?i)^(.+?) " + _VERB + r" (.+?)(?: in (?:a |an |the )?(.+?)| for (?:the )?(.+?))?$", t)
            if not m: return t
            a, b, extra = m[1], m[2], title(m[3] or m[4] or "")
    a, b = re.sub(r"(?i)^the ", "The ", a.strip()), b.strip()
    return f"{a} vs. {b}" + (f": {extra}" if extra and not short else "")
def card_text(c, now=None):
    import datetime, zoneinfo
    from live_thread import promo_handle
    now = now or time.time(); et = zoneinfo.ZoneInfo("America/New_York")
    key = c["fullcard"]; slug, d = key.split("/")[0], key.split("/")[-1]
    name = c.get("show_name") or c["title"].split(" Full Card")[0]
    show = re.sub(r"^WWE (?=Raw\b|SmackDown\b)", "", name)
    start = datetime.datetime.fromtimestamp(int(c.get("lead_until") or now), et).date(); today = datetime.datetime.fromtimestamp(now, et).date()
    when = "Tonight" if start == today else "Tomorrow" if (start - today).days == 1 else start.strftime("%A")
    head = f"{show} {when}: Full Card"
    handle = promo_handle({"slug": slug, "brand": (c.get("categories") or [""])[0], "name": name, "key": f"{d}-{slug}"})   # same rule as live thread roots
    tags = " ".join(([handle] if handle else []) + sorted(hashtags(c, name), key=lambda h: h in CAT_TAG.values()))   # show tag first
    outro = "Full card: link in bio"
    lines = [i["line"] for i in c.get("card") or []]; app = list(c.get("appearances") or [])
    def build(ms, app, short):
        body = "\n".join("- " + match_line(l, short) for l in ms) + ("\n+ more" if len(ms) < len(lines) else "")
        if app: body += "\nAlso advertised: " + ", ".join(app)
        return f"{head}\n\n{body}\n\n{tags}\n{outro}"
    ms, short = lines, False
    text = build(ms, app, short)
    while x_len(text) > 280 and app: app = app[:-1] if len(app) > 2 else []; text = build(ms, app, short)   # advertised appearances go first (never just one)
    if x_len(text) > 280: short = True; text = build(ms, app, short)                        # then the stipulation/title tails
    while x_len(text) > 280 and len(ms) > 2: ms = ms[:-1]; text = build(ms, app, short)     # then the last matches ('+ more')
    if has_url(text) or x_len(text) > 280: return None
    return text

# --- OAuth 1.0a ----------------------------------------------------------------------------------
def _q(s): return urllib.parse.quote(str(s), safe="~")
def oauth_header(method, url):
    ck, cs, tk, ts = (os.environ[k] for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"))
    p = {"oauth_consumer_key": ck, "oauth_nonce": secrets.token_hex(16), "oauth_signature_method": "HMAC-SHA1",
         "oauth_timestamp": str(int(time.time())), "oauth_token": tk, "oauth_version": "1.0"}
    base = "&".join([method.upper(), _q(url), _q("&".join(f"{_q(k)}={_q(v)}" for k, v in sorted(p.items())))])
    p["oauth_signature"] = base64.b64encode(hmac.new(f"{_q(cs)}&{_q(ts)}".encode(), base.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join(f'{_q(k)}="{_q(v)}"' for k, v in sorted(p.items()))
def post_tweet(text, media_ids=None):
    url = "https://api.x.com/2/tweets"
    payload = {"text": text}
    if media_ids: payload["media"] = {"media_ids": list(media_ids)}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Authorization": oauth_header("POST", url), "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return r.status, json.load(r), dict(r.headers)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf8", "ignore")[:600]
        try: body = json.loads(body)
        except Exception: pass
        return e.code, body, dict(e.headers)

# (the one-time photo test of 2026-10-18 is done: tweet 2111693639889899743; every post now carries a photo, see below)
PHOTO_OK = re.compile(r"^(?:cached:)?(?:key-|promo-logo:|no-names-promo:|override$)")   # key person confirmed, promotion logo card, or hand-picked
WCN_CARD = re.compile(r"(?i)/img/(?:og|wcn|default)[^/]*\.(?:png|jpe?g)$")
UA_IMG = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36", "Accept": "image/jpeg,image/png,image/webp;q=0.9,image/gif;q=0.8"}
# --- photo on EVERY post (owner rule 2026-10-18 06:20 UTC): the image the site shows for that story --------------------------
# Only the site's own image when it is known to match the story (key person confirmed/labelled, the promotion logo card, show
# art, hand-picked, or a no-names story's own report photo). A photo the site could NOT confirm shows the story's key person
# ('person-photo-unverified' - the Austin Creed/Kofi mix-up kind) is never posted: the promotion logo card is used instead,
# else the site's default WCN card. If every download fails, or the upload fails, the post goes out text-only (never skipped).
SITE_IMG_OK = re.compile(r"^(?:cached:)?(?:key-|promo-logo:|no-names-promo|no-names$|override$|event-art$)")
SITE_DEFAULT_IMG = "https://wrestlingcentralnews.com/og-image.jpg"
def photo_candidates(c, extra_text=""):
    """-> [(url, why)] in order of preference for this card (deduped)."""
    import vision
    out = []
    u, st = c.get("image") or "", c.get("image_status") or ""
    if u and SITE_IMG_OK.match(st) and not WCN_CARD.search(u): out.append((u, "site:" + st))
    pr = vision.promo_in(" ".join([c.get("title") or "", c.get("raw_title") or "", extra_text]))
    if pr: out.append((vision.PROMO_CARD.format(pr), "promo-logo:" + pr))
    out.append((SITE_DEFAULT_IMG, "site-default"))
    seen = set(); return [x for x in out if not (x[0] in seen or seen.add(x[0]))]
PHOTO_BUDGET_S = 30   # owner rule: download + upload together get 30 s, then the post goes out text-only (all posts, BREAKING too)
def attach_photo(cands, src="x_poster", budget=None):
    """Download the first candidate that works (downloads are free), upload it once (1 media request, logged in the ledger),
    all within PHOTO_BUDGET_S seconds in total. -> (media_id or None, url, why, error or None)"""
    import threading
    budget = PHOTO_BUDGET_S if budget is None else budget
    deadline = time.time() + budget; res = {}
    def work():
        errs = []
        for u, why in cands:
            left = deadline - time.time()
            if left <= 1: errs.append("time budget used up"); break
            try: data = fetch_image(u, timeout=left)
            except Exception as ex: errs.append(f"{why}: {repr(ex)[:120]}"); continue
            left = deadline - time.time()
            if left <= 1: errs.append("time budget used up before upload"); break
            mid, err = upload_media(u, src, data, timeout=left)
            res["r"] = (mid, u, why, err); return
        res["r"] = (None, None, None, "no image could be downloaded: " + "; ".join(errs)[:300])
    th = threading.Thread(target=work, daemon=True); th.start(); th.join(max(0.0, deadline - time.time()))
    if th.is_alive() or "r" not in res:
        return None, None, None, f"photo download+upload exceeded {budget:.0f}s - text-only"
    if time.time() > deadline + 0.5: return None, None, None, f"photo exceeded {budget:.0f}s - text-only"
    return res["r"]
def photo_ok(c):
    u, st = c.get("image") or "", c.get("image_status") or ""
    return bool(u) and bool(PHOTO_OK.match(st)) and not WCN_CARD.search(u)
def fetch_image(u, timeout=30):
    """-> (bytes, mime) of a JPEG/PNG/WEBP/GIF under 5 MB, or raises."""
    req = urllib.request.Request(u, headers=UA_IMG)
    b = urllib.request.urlopen(req, timeout=timeout).read(5 * 1024 * 1024 + 1)
    if len(b) > 5 * 1024 * 1024: raise ValueError("image over 5 MB")
    if b[:3] == b"\xff\xd8\xff": return b, "image/jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n": return b, "image/png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP": return b, "image/webp"
    if b[:6] in (b"GIF87a", b"GIF89a"): return b, "image/gif"
    raise ValueError("not a jpeg/png/webp/gif: " + repr(b[:12]))
def upload_media(u, src="x_poster", data=None, timeout=60):
    """One-shot v2 upload (POST /2/media/upload, JSON body, base64): 1 media request. -> (media_id or None, error or None)."""
    if data: b, mime = data
    else:
        try: b, mime = fetch_image(u)
        except Exception as ex: return None, "image fetch failed: " + repr(ex)[:200]
    url = "https://api.x.com/2/media/upload"
    req = urllib.request.Request(url, data=json.dumps({"media": base64.b64encode(b).decode(), "media_category": "tweet_image", "media_type": mime}).encode(),
                                 method="POST", headers={"Authorization": oauth_header("POST", url), "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=timeout); code = r.status; body = json.load(r)
    except urllib.error.HTTPError as e:
        code = e.code; body = e.read().decode("utf8", "ignore")[:400]
    except Exception as ex:
        xspend.record("media", "POST /2/media/upload", src, ok=False, note="network error: " + repr(ex)[:150]); return None, "upload error: " + repr(ex)[:200]
    mid = (body.get("data") or {}).get("id") if isinstance(body, dict) else None
    xspend.record("media", "POST /2/media/upload", src, ref=mid, note=f"HTTP {code} {mime} {len(b)}B", ok=True)   # counted even on failure (X may bill the request)
    if code in (200, 201) and mid: return mid, None
    return None, f"upload HTTP {code}: " + (json.dumps(body)[:300] if not isinstance(body, str) else body[:300])
def run(test_top=False):
    enabled = os.environ.get("X_POST_ENABLED", "0") == "1"
    have_keys = all(os.environ.get(k) for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"))
    S = load_state(); now = time.time()
    if enabled and not test_top and now < S.get("paused_until", 0):
        log("paused until", time.strftime("%F %T", time.gmtime(S["paused_until"])), "reason:", S.get("pause_reason")); return
    items = json.load(open(NEWS))["items"]
    posted_links = set(S["links"])
    def seen(c): return c.get("resplit") or c["id"] in S["posted"] or c["link"] in posted_links or any(u["link"] in posted_links for u in c.get("updates", []))
    L = live_posted(); _skipped = []
    def live_seen(c):
        d = live_dup(c, L)
        if d and c["id"] not in _skipped:
            _skipped.append(c["id"]); log(f"skip (result already posted by live_x for {d[0]}: {d[1].get('winner')}):", c["title"])
            S.setdefault("live_dups", {})[c["id"]] = {"show": d[0], "at": int(now), "title": c["title"]}
        return bool(d)
    def evergreen(c):   # never post explainer / history / 'what is' / anniversary pieces (owner rule 2026-10-20); editorial drops them upstream too
        return editorial.evergreen(c.get("title")) or editorial.evergreen(c.get("raw_title"))
    _seen = seen
    def seen(c): return _seen(c) or evergreen(c) or live_seen(c)
    if test_top:
        cands = [c for c in items if not seen(c) and c.get("trusted", 0) >= 1][:1]
        n_allowed = 1
    else:
        recent = [t for t in S["log"] if t.get("ok") and not t.get("deleted") and now - t["at"] < 86400]
        rec_brk = [t for t in recent if t.get("breaking")]; rec_norm = [t for t in recent if not t.get("breaking")]
        allc = [c for c in items if not seen(c) and (card_due(c, now) if c.get("fullcard") else
                now - c.get("first_ts", c["ts"]) < FRESH_H * 3600 and score(c) >= MIN_SCORE)]
        allc.sort(key=lambda c: (not c.get("fullcard"), -score(c)))   # a Full Card has a deadline (showtime): first in line, still under cap/gap
        brk = [c for c in allc if is_breaking(c) and c.get("trusted", 0) >= 1]
        normal = [c for c in allc if c not in brk]
        nb = max(0, min(BREAKING_PER_RUN, BREAKING_MAX_24H - len(rec_brk)))
        if brk and not nb: log(f"breaking safety limit {BREAKING_MAX_24H}/24h reached ({len(brk)} waiting)")
        last = max([t["at"] for t in rec_norm] or [0])
        if not normal: nn = 0
        elif len(rec_norm) >= DAILY_CAP: nn = 0; log(f"daily cap {DAILY_CAP} reached for normal posts ({len(normal)} waiting; BREAKING posts are exempt)")
        elif now - last < MIN_GAP_MIN * 60 and score(normal[0]) < BREAKING:
            nn = 0; log(f"min gap {MIN_GAP_MIN}m: next normal post later ({len(normal)} waiting)")
        else:
            nn = PER_RUN_BREAKING if len(normal) > 1 and score(normal[1]) >= BREAKING else PER_RUN
            nn = min(nn, DAILY_CAP - len(rec_norm))
        cands = brk[:nb] + normal[:nn]
        n_allowed = len(cands)
    if not cands: log("nothing new worth posting (or waiting on cap/gap)"); save_state(S) if _skipped else None; return
    for c in cands[:n_allowed]:
        text = card_text(c, now) if c.get("fullcard") else tweet_text(c)
        if not text or has_url(text):
            log("skipped (URL-like text or too long):", c["title"]); S["links"] += [c["link"]]; continue
        if not (enabled or test_top) or not have_keys:
            log(f"DRY RUN (enabled={enabled}, keys={have_keys}) score={score(c)} photo={photo_candidates(c)[0][1]}:", text.replace("\n", " ⏎ ")); continue
        media, img_url, img_why, merr = attach_photo(photo_candidates(c))
        if not media:
            log("photo: none attached, posting text-only:", merr); xspend.event("media_upload_failed", "x_poster", merr or "")
        code, body, hdr = post_tweet(text, [media] if media else None)
        entry = {"id": c["id"], "at": int(now), "code": code, "score": score(c)}
        if c.get("fullcard"): entry["fullcard"] = c["fullcard"]
        if is_breaking(c): entry["breaking"] = True     # exempt from DAILY_CAP / MIN_GAP (counted in BREAKING_MAX_24H)
        if media: entry.update(media=media, image=img_url, image_why=img_why)
        if code in (200, 201):
            tid = body["data"]["id"]; entry.update(ok=True, tweet=tid)
            xspend.record("post_url" if has_url(text) else "post", "POST /2/tweets", "x_poster", ref=tid, note=f"with photo ({img_why})" if media else "text-only")
            if media and not S.get("first_photo_post"):
                S["first_photo_post"] = {"at": int(now), "tweet": tid, "url": f"https://x.com/wrestlingWCN/status/{tid}", "image": img_url, "why": img_why, "title": c["title"]}
            S["posted"][c["id"]] = {"tweet": tid, "at": int(now), "title": c["title"]}
            S.pop("paused_until", None); S.pop("pause_reason", None)   # credits/limits are fine again
            S["links"] += [c["link"]] + [u["link"] for u in c.get("updates", [])]
            log(f"posted https://x.com/wrestlingWCN/status/{tid} score={score(c)} photo={img_why if media else 'none'} {c['title']}")
        else:
            msg = json.dumps(body)[:400] if not isinstance(body, str) else body[:400]
            entry.update(ok=False, err=msg); log(f"post failed HTTP {code}: {msg}")
            if code == 402 or re.search(r"credits.depleted|CreditsDepleted", msg, re.I): xspend.event("credits_depleted", "x_poster", f"HTTP {code}: {msg[:200]}")
            elif code in (403, 429): xspend.event(f"http_{code}", "x_poster", msg[:200])
            if code in (402, 403) or re.search(r"credit|payment|CreditsDepleted|client-not-enrolled", msg, re.I):
                S["paused_until"] = now + PAUSE_ON_PAYMENT_H * 3600; S["pause_reason"] = f"HTTP {code}: {msg[:200]}"
            elif code == 429:
                reset = int(hdr.get("x-rate-limit-reset") or hdr.get("X-Rate-Limit-Reset") or now + 900)
                S["paused_until"] = max(reset, now + 300); S["pause_reason"] = "HTTP 429 rate limit"
            S["log"].append(entry); break
        S["log"].append(entry)
    save_state(S)

if __name__ == "__main__":
    xspend.ensure()
    try:   # persist manual deletion flags even when this run posts nothing (run() can return before saving)
        _S = load_state(); save_state(_S)
    except Exception as e: log("manual state apply error (ignored):", repr(e)[:200])
    try: run(test_top="--test-top" in sys.argv)
    except Exception as e: log("error (ignored):", repr(e)[:300])   # never fail the workflow because of X
