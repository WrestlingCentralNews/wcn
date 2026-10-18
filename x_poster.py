"""Auto-post the most important NEW WCN stories to X (@wrestlingWCN).

Posts are link-free (cheap X plan): headline + one line + hashtags + "link in bio".
Runs after the site deploy in the 15-min workflow. Standard library only (OAuth 1.0a user context).
Enable with env X_POST_ENABLED=1 (repo variable); anything else = dry run (logs what it would post).
State: data/posted_x.json (saved to the 'data' branch with the rest of the state).
"""
import os, re, sys, json, time, hmac, base64, hashlib, secrets, ssl, urllib.parse, urllib.request, urllib.error
import xspend, breaking
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
def is_breaking(c): return bool(breaking.kind(c["title"], (c.get("kind") or {}).get("type"), source_text(c)))
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

# --- one-time photo test (owner-approved 2026-10-18): the next regular story post carries the card photo -----------------
# Pending while S["x_photo_test_id"] != PHOTO_TEST_ID; cleared (x_photo_test_pending=False) after one successful photo post.
PHOTO_TEST_ID = "2026-10-18-first-photo"
PHOTO_TEST_MAX_TRIES = 3
PHOTO_OK = re.compile(r"^(?:cached:)?(?:key-|promo-logo:|no-names-promo:|override$)")   # key person confirmed, promotion logo card, or hand-picked
WCN_CARD = re.compile(r"(?i)/img/(?:og|wcn|default)[^/]*\.(?:png|jpe?g)$")
UA_IMG = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36", "Accept": "image/jpeg,image/png,image/webp;q=0.9,image/gif;q=0.8"}
def photo_ok(c):
    u, st = c.get("image") or "", c.get("image_status") or ""
    return bool(u) and bool(PHOTO_OK.match(st)) and not WCN_CARD.search(u)
def fetch_image(u):
    """-> (bytes, mime) of a JPEG/PNG/WEBP/GIF under 5 MB, or raises."""
    req = urllib.request.Request(u, headers=UA_IMG)
    b = urllib.request.urlopen(req, timeout=30).read(5 * 1024 * 1024 + 1)
    if len(b) > 5 * 1024 * 1024: raise ValueError("image over 5 MB")
    if b[:3] == b"\xff\xd8\xff": return b, "image/jpeg"
    if b[:8] == b"\x89PNG\r\n\x1a\n": return b, "image/png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP": return b, "image/webp"
    if b[:6] in (b"GIF87a", b"GIF89a"): return b, "image/gif"
    raise ValueError("not a jpeg/png/webp/gif: " + repr(b[:12]))
def upload_media(u, src="x_poster"):
    """One-shot v2 upload (POST /2/media/upload, JSON body, base64): 1 media request. -> (media_id or None, error or None)."""
    try: b, mime = fetch_image(u)
    except Exception as ex: return None, "image fetch failed: " + repr(ex)[:200]
    url = "https://api.x.com/2/media/upload"
    req = urllib.request.Request(url, data=json.dumps({"media": base64.b64encode(b).decode(), "media_category": "tweet_image", "media_type": mime}).encode(),
                                 method="POST", headers={"Authorization": oauth_header("POST", url), "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=60); code = r.status; body = json.load(r)
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
    _seen = seen
    def seen(c): return _seen(c) or live_seen(c)
    if test_top:
        cands = [c for c in items if not seen(c) and c.get("trusted", 0) >= 1][:1]
        n_allowed = 1
    else:
        recent = [t for t in S["log"] if t.get("ok") and not t.get("deleted") and now - t["at"] < 86400]
        rec_brk = [t for t in recent if t.get("breaking")]; rec_norm = [t for t in recent if not t.get("breaking")]
        allc = [c for c in items if not seen(c) and now - c.get("first_ts", c["ts"]) < FRESH_H * 3600 and score(c) >= MIN_SCORE]
        allc.sort(key=lambda c: -score(c))
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
        text = tweet_text(c)
        if not text or has_url(text):
            log("skipped (URL-like text or too long):", c["title"]); S["links"] += [c["link"]]; continue
        if not (enabled or test_top) or not have_keys:
            log(f"DRY RUN (enabled={enabled}, keys={have_keys}) score={score(c)}:", text.replace("\n", " ⏎ ")); continue
        media, photo_try = None, False
        if not test_top and S.get("x_photo_test_id") != PHOTO_TEST_ID and S.get("x_photo_test_tries", 0) < PHOTO_TEST_MAX_TRIES:
            S["x_photo_test_pending"] = True
            if photo_ok(c):
                photo_try = True; S["x_photo_test_tries"] = S.get("x_photo_test_tries", 0) + 1
                media, merr = upload_media(c["image"])
                if not media:
                    log("photo test: media upload failed, posting text-only:", merr); xspend.event("media_upload_failed", "x_poster", merr)
                    S.setdefault("x_photo_test_log", []).append({"at": int(now), "id": c["id"], "image": c["image"], "err": merr})
            else: log(f"photo test: '{c['title']}' photo not eligible (status={c.get('image_status')}); text-only, test stays pending")
        code, body, hdr = post_tweet(text, [media] if media else None)
        entry = {"id": c["id"], "at": int(now), "code": code, "score": score(c)}
        if is_breaking(c): entry["breaking"] = True     # exempt from DAILY_CAP / MIN_GAP (counted in BREAKING_MAX_24H)
        if media: entry["media"] = media
        if code in (200, 201):
            tid = body["data"]["id"]; entry.update(ok=True, tweet=tid)
            xspend.record("post_url" if has_url(text) else "post", "POST /2/tweets", "x_poster", ref=tid, note="with photo" if media else None)
            if media:
                S["x_photo_test_id"] = PHOTO_TEST_ID; S["x_photo_test_pending"] = False
                S["x_photo_test_result"] = {"at": int(now), "tweet": tid, "url": f"https://x.com/wrestlingWCN/status/{tid}", "media_id": media,
                                            "image": c["image"], "image_status": c.get("image_status"), "media_requests": 1, "tries": S.get("x_photo_test_tries")}
                log(f"photo test done: media {media} attached (1 media request)")
            elif photo_try: S.setdefault("x_photo_test_log", []).append({"at": int(now), "id": c["id"], "posted_text_only": tid})
            S["posted"][c["id"]] = {"tweet": tid, "at": int(now), "title": c["title"]}
            S.pop("paused_until", None); S.pop("pause_reason", None)   # credits/limits are fine again
            S["links"] += [c["link"]] + [u["link"] for u in c.get("updates", [])]
            log(f"posted https://x.com/wrestlingWCN/status/{tid} score={score(c)} {c['title']}")
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
