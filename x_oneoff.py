"""One-time, owner-approved X posts (run after x_poster/live_x in the 15-min workflow). Each id posts at most once, ever.
Not part of x_poster's story log, so it never counts toward the daily cap / min gap and is never re-posted or deduped against.
State: data/posted_x.json -> "oneoff": {id: {...}}. Spend: logged to data/x_spend.json (URL posts at $0.20)."""
import os, json, time, urllib.request
import x_poster as XP, xspend
ONEOFF = [
    {"id": "live-link-pin-2026-10", "check": "https://wrestlingcentralnews.com/live/",
     "text": "📌 Live results every show night, match by match: WWE, AEW, TNA and more.\n\nwrestlingcentralnews.com/live"},
]
MAX_TRIES = 2
def log(*a): print("[x-oneoff]", *a, flush=True)
def run():
    if os.environ.get("X_POST_ENABLED", "0") != "1" or not all(os.environ.get(k) for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")):
        log("disabled / no keys"); return
    S = XP.load_state(); O = S.setdefault("oneoff", {}); now = time.time()
    if now < S.get("paused_until", 0): log("X posting paused:", S.get("pause_reason")); return
    for job in ONEOFF:
        r = O.get(job["id"], {})
        if r.get("tweet") or r.get("tries", 0) >= MAX_TRIES: continue
        try:
            code = urllib.request.urlopen(urllib.request.Request(job["check"], headers={"User-Agent": "WCN-bot"}), timeout=20).status
        except Exception as ex: code = repr(ex)[:80]
        if code != 200: log(job["id"], "link not live yet:", code); continue
        r["tries"] = r.get("tries", 0) + 1
        code, body, hdr = XP.post_tweet(job["text"])
        if code in (200, 201):
            tid = body["data"]["id"]; r.update(tweet=tid, at=int(now), url=f"https://x.com/wrestlingWCN/status/{tid}")
            xspend.record("post_url" if XP.has_url(job["text"]) else "post", "POST /2/tweets", "x_oneoff", ref=tid, note=job["id"])
            log("posted", r["url"])
        else:
            msg = json.dumps(body)[:300] if not isinstance(body, str) else body[:300]; r["err"] = f"HTTP {code}: {msg}"; log("failed", r["err"])
            if code == 402 or "credits" in msg.lower(): xspend.event("credits_depleted", "x_oneoff", r["err"])
        O[job["id"]] = r
    XP.save_state(S)
if __name__ == "__main__":
    try: run()
    except Exception as ex: log("error (ignored):", repr(ex)[:300])
