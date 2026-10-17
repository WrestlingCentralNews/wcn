"""Auto-post the most important NEW WCN stories to X (@wrestlingWCN).

Runs after the site deploy in the 15-min workflow. Standard library only (OAuth 1.0a user context).
Enable with env X_POST_ENABLED=1 (repo variable); anything else = dry run (logs what it would post).
State: data/posted_x.json (saved to the 'data' branch with the rest of the state).
"""
import os, re, sys, json, time, hmac, base64, hashlib, secrets, ssl, urllib.parse, urllib.request, urllib.error
ROOT = os.path.dirname(os.path.abspath(__file__))
NEWS = os.path.join(ROOT, "public", "news.json")
STATE = os.path.join(ROOT, "data", "posted_x.json")
SITE_HOST = "wrestlingcentralnews.com"
# --- posting rules -------------------------------------------------------------------------------
DAILY_CAP = 14            # max posts in any rolling 24h
PER_RUN = 1               # normal max per 15-min run
PER_RUN_BREAKING = 2      # allowed when the 2nd candidate is also breaking-level
MIN_GAP_MIN = 25          # minutes between posting runs (breaking news may skip the gap)
FRESH_H = 8               # only stories whose first report is younger than this
MIN_SCORE = 14            # importance threshold
BREAKING = 26
PAUSE_ON_PAYMENT_H = 6    # back off after credit/payment errors
CAT_BONUS = {"WWE": 4, "AEW": 4, "TNA": 2, "Global": 1, "Indie": 0}
KIND_BONUS = {"news": 3, "match": 3, "quote": 1, "results": 1}
MAJOR = re.compile(r"\b(champion\w*|title|injur\w*|sign\w*|releas\w*|died|dies|death|passe[sd] away|return\w*|debut\w*|retire\w*|suspend\w*|arrest\w*|leav\w*|departs?|contract|surgery|hall of fame|wrestlemania|all in|bound for glory)\b", re.I)
TAGS = [(r"\bNXT\b", "#WWENXT"), (r"\bROH\b|Ring of Honor", "#ROH"), (r"\bNJPW\b|New Japan", "#NJPW"), (r"\bAAA\b", "#AAA"),
        (r"\bCMLL\b", "#CMLL"), (r"\bRaw\b", "#WWERaw"), (r"\bSmackDown\b", "#SmackDown"), (r"\bDynamite\b", "#AEWDynamite"), (r"\bCollision\b", "#AEWCollision")]
CAT_TAG = {"WWE": "#WWE", "AEW": "#AEW", "TNA": "#TNA", "Indie": "#IndieWrestling", "Global": "#ProWrestling"}

def log(*a): print("[x]", *a, flush=True)
def load_state():
    try: s = json.load(open(STATE))
    except Exception: s = {}
    s.setdefault("posted", {}); s.setdefault("links", []); s.setdefault("log", []); return s
def save_state(s):
    s["links"] = s["links"][-3000:]; s["log"] = s["log"][-200:]
    os.makedirs(os.path.dirname(STATE), exist_ok=True); json.dump(s, open(STATE, "w"), indent=0)

def score(c):
    s = 2 * min(c.get("sources", 1), 8) + 2 * min(c.get("trusted", 0), 4)
    s += max(CAT_BONUS.get(k, 0) for k in c["categories"])
    s += KIND_BONUS.get((c.get("kind") or {}).get("type", "news"), 1)
    s += 1 if c.get("image") else 0
    s += 3 if MAJOR.search(c["title"]) else 0
    if c.get("trusted", 0) == 0: s -= 6                     # never lead with only low-trust sourcing
    if "Indie" in c["categories"] and c.get("sources", 1) < 3: s -= 4
    return s

def base_url():
    """https canonical once GitHub has issued the certificate; plain http until then."""
    try:
        urllib.request.urlopen(urllib.request.Request(f"https://{SITE_HOST}/robots.txt", method="HEAD"), timeout=10, context=ssl.create_default_context())
        return f"https://{SITE_HOST}/"
    except Exception: return f"http://{SITE_HOST}/"

def tweet_text(c, url):
    tags = []
    for k in c["categories"]:
        t = CAT_TAG.get(k)
        if t and t not in tags: tags.append(t)
    blob = c["title"] + " " + c.get("summary", "")
    for rx, t in TAGS:
        if len(tags) >= 3: break
        if re.search(rx, blob) and t not in tags: tags.append(t)
    tags = tags[:3]
    somber = re.search(r"\b(died|dies|death|passed away|passes away|funeral|tribute)\b", c["title"], re.I)
    head = ("🚨 " if score(c) >= BREAKING and not somber else "") + c["title"].strip()
    budget = 280 - 23 - len(head) - len(" ".join(tags)) - 6     # X counts every link as 23 chars
    line = ""
    sents = re.split(r"(?<=[.!?])\s+", (c.get("summary") or "").strip())
    for snt in sents:
        if len(line) + len(snt) + 1 > min(budget, 200): break
        line = (line + " " + snt).strip()
    parts = [head] + ([line] if line else []) + [" ".join(tags) + "\n" + url]
    return "\n\n".join(parts)

# --- OAuth 1.0a ----------------------------------------------------------------------------------
def _q(s): return urllib.parse.quote(str(s), safe="~")
def oauth_header(method, url):
    ck, cs, tk, ts = (os.environ[k] for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"))
    p = {"oauth_consumer_key": ck, "oauth_nonce": secrets.token_hex(16), "oauth_signature_method": "HMAC-SHA1",
         "oauth_timestamp": str(int(time.time())), "oauth_token": tk, "oauth_version": "1.0"}
    base = "&".join([method.upper(), _q(url), _q("&".join(f"{_q(k)}={_q(v)}" for k, v in sorted(p.items())))])
    p["oauth_signature"] = base64.b64encode(hmac.new(f"{_q(cs)}&{_q(ts)}".encode(), base.encode(), hashlib.sha1).digest()).decode()
    return "OAuth " + ", ".join(f'{_q(k)}="{_q(v)}"' for k, v in sorted(p.items()))
def post_tweet(text):
    url = "https://api.x.com/2/tweets"
    req = urllib.request.Request(url, data=json.dumps({"text": text}).encode(), method="POST",
                                 headers={"Authorization": oauth_header("POST", url), "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return r.status, json.load(r), dict(r.headers)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf8", "ignore")[:600]
        try: body = json.loads(body)
        except Exception: pass
        return e.code, body, dict(e.headers)

def run(test_top=False):
    enabled = os.environ.get("X_POST_ENABLED", "0") == "1"
    have_keys = all(os.environ.get(k) for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"))
    S = load_state(); now = time.time()
    if not test_top and now < S.get("paused_until", 0):
        log("paused until", time.strftime("%F %T", time.gmtime(S["paused_until"])), "reason:", S.get("pause_reason")); return
    items = json.load(open(NEWS))["items"]
    posted_links = set(S["links"])
    def seen(c): return c["id"] in S["posted"] or c["link"] in posted_links or any(u["link"] in posted_links for u in c.get("updates", []))
    if test_top:
        cands = [c for c in items if not seen(c) and c.get("trusted", 0) >= 1][:1]
        n_allowed = 1
    else:
        recent = [t for t in S["log"] if t.get("ok") and now - t["at"] < 86400]
        if len(recent) >= DAILY_CAP: log(f"daily cap {DAILY_CAP} reached"); return
        cands = [c for c in items if not seen(c) and now - c.get("first_ts", c["ts"]) < FRESH_H * 3600 and score(c) >= MIN_SCORE]
        cands.sort(key=lambda c: -score(c))
        last = max([t["at"] for t in recent] or [0])
        if cands and now - last < MIN_GAP_MIN * 60 and score(cands[0]) < BREAKING:
            log(f"min gap {MIN_GAP_MIN}m: next post later ({len(cands)} waiting)"); return
        n_allowed = PER_RUN_BREAKING if len(cands) > 1 and score(cands[1]) >= BREAKING else PER_RUN
        n_allowed = min(n_allowed, DAILY_CAP - len(recent))
    if not cands: log("nothing new worth posting"); return
    base = base_url()
    for c in cands[:n_allowed]:
        text = tweet_text(c, base + c["url"])
        if not (enabled or test_top) or not have_keys:
            log(f"DRY RUN (enabled={enabled}, keys={have_keys}) score={score(c)}:", text.replace("\n", " ⏎ ")); continue
        code, body, hdr = post_tweet(text)
        entry = {"id": c["id"], "at": int(now), "code": code, "score": score(c)}
        if code in (200, 201):
            tid = body["data"]["id"]; entry.update(ok=True, tweet=tid)
            S["posted"][c["id"]] = {"tweet": tid, "at": int(now), "title": c["title"]}
            S["links"] += [c["link"]] + [u["link"] for u in c.get("updates", [])]
            log(f"posted https://x.com/wrestlingWCN/status/{tid} score={score(c)} {c['title']}")
        else:
            msg = json.dumps(body)[:400] if not isinstance(body, str) else body[:400]
            entry.update(ok=False, err=msg); log(f"post failed HTTP {code}: {msg}")
            if code in (402, 403) or re.search(r"credit|payment|CreditsDepleted|client-not-enrolled", msg, re.I):
                S["paused_until"] = now + PAUSE_ON_PAYMENT_H * 3600; S["pause_reason"] = f"HTTP {code}: {msg[:200]}"
            elif code == 429:
                reset = int(hdr.get("x-rate-limit-reset") or hdr.get("X-Rate-Limit-Reset") or now + 900)
                S["paused_until"] = max(reset, now + 300); S["pause_reason"] = "HTTP 429 rate limit"
            S["log"].append(entry); break
        S["log"].append(entry)
    save_state(S)

if __name__ == "__main__":
    try: run(test_top="--test-top" in sys.argv)
    except Exception as e: log("error (ignored):", repr(e)[:300])   # never fail the workflow because of X
