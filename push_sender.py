"""Web push for BREAKING WCN stories via OneSignal (free plan).

Runs after the site deploy in the 15-min workflow (like x_poster.py). Standard library only.
Rules: score >= 26 (x_poster.score), story first reported < 3h ago, max 3 pushes per rolling 24h,
>= 60 min apart, 1 per run, never the same story twice. State: data/pushed.json (data branch).
Enable with repo variable PUSH_ENABLED=1; anything else = dry run (logs the payload it would send).
Never fails the workflow.
"""
import os, sys, json, time, uuid, urllib.request, urllib.error
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from x_poster import score
NEWS = os.path.join(ROOT, "public", "news.json")
STATE = os.path.join(ROOT, "data", "pushed.json")
SITE = "https://wrestlingcentralnews.com/"
API = "https://api.onesignal.com"
MIN_SCORE, FRESH_H, DAILY_CAP, MIN_GAP_MIN = 26, 3, 3, 60
SEGMENT = "Total Subscriptions"       # OneSignal's default all-subscribers segment (formerly "Subscribed Users")

def log(*a): print("[push]", *a, flush=True)
def load_state():
    try: s = json.load(open(STATE))
    except Exception: s = {}
    s.setdefault("pushed", {}); s.setdefault("log", []); return s
def save_state(s):
    now = time.time(); s["pushed"] = {k: v for k, v in s["pushed"].items() if now - v.get("ts", 0) < 120 * 86400}
    s["log"] = s["log"][-200:]; os.makedirs(os.path.dirname(STATE), exist_ok=True); json.dump(s, open(STATE, "w"), indent=0)

def call(method, path, key, body=None, t=20):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Key {key}", "Content-Type": "application/json; charset=utf-8",
                                          "Accept": "application/json", "User-Agent": "WCN-Push/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=t) as r: return r.status, json.loads(r.read() or b"{}"), r.headers
    except urllib.error.HTTPError as ex:
        try: b = json.loads(ex.read() or b"{}")
        except Exception: b = {}
        return ex.code, b, ex.headers

def payload(app_id, c):
    cat = c["categories"][0]
    title = c["title"].strip()
    p = {"app_id": app_id, "target_channel": "push", "included_segments": [SEGMENT], "isAnyWeb": True,
         "headings": {"en": f"WCN Breaking · {cat}"}, "contents": {"en": title[:180]},
         "url": SITE + c["url"], "name": f"WCN breaking: {title[:100]}",
         "chrome_web_icon": SITE + "pwa/icon-192.png", "firefox_icon": SITE + "pwa/icon-192.png",
         "large_icon": SITE + "pwa/icon-192.png",
         "web_push_topic": ("wcn" + str(c["id"]))[:32], "ttl": 6 * 3600, "priority": 10,
         "idempotency_key": str(uuid.uuid5(uuid.NAMESPACE_URL, SITE + c["url"]))}
    img = c.get("image") or ""
    if img.startswith("https://"): p["chrome_web_image"] = img
    return p

def main():
    enabled = os.environ.get("PUSH_ENABLED", "").strip() == "1"
    app_id = os.environ.get("ONESIGNAL_APP_ID", "").strip(); key = os.environ.get("ONESIGNAL_REST_API_KEY", "").strip()
    if not app_id or not key: log("OneSignal app id / key missing; skipping"); return
    s = load_state(); now = time.time()
    items = json.load(open(NEWS)).get("items", [])
    sent_urls = {v.get("url") for v in s["pushed"].values()}
    recent = sorted(v["ts"] for v in s["pushed"].values() if v.get("sent") and now - v["ts"] < 86400)
    cands = sorted([c for c in items if c.get("url") and str(c["id"]) not in s["pushed"] and c["url"] not in sent_urls
                    and now - c.get("first_ts", c["ts"]) < FRESH_H * 3600 and score(c) >= MIN_SCORE], key=score, reverse=True)
    if not cands: log("no new breaking stories"); return
    c = cands[0]; p = payload(app_id, c)
    if len(recent) >= DAILY_CAP: log(f"daily cap reached ({len(recent)}/{DAILY_CAP}); holding: {c['title']}"); return
    if recent and now - recent[-1] < MIN_GAP_MIN * 60: log(f"last push {int((now - recent[-1]) / 60)} min ago (< {MIN_GAP_MIN}); holding: {c['title']}"); return
    st, app, _ = call("GET", f"/apps/{app_id}", key)
    if st != 200: log(f"auth/app check failed: HTTP {st} {app.get('errors')}"); return
    subs = app.get("messageable_players", app.get("players", 0))
    if not enabled or not subs:
        why = "PUSH_ENABLED!=1" if not enabled else "0 subscribers"
        log(f"DRY RUN ({why}); app '{app.get('name')}' auth OK; would send score={score(c)}:",
            json.dumps({k: v for k, v in p.items() if k != "app_id"}, ensure_ascii=False))
        return
    st, r, h = call("POST", "/notifications?c=push", key, p)
    if st == 200 and r.get("id"):
        s["pushed"][str(c["id"])] = {"ts": now, "url": c["url"], "title": c["title"], "sent": True, "nid": r["id"], "score": score(c)}
        s["log"].append({"ts": int(now), "id": str(c["id"]), "nid": r["id"]}); save_state(s)
        log(f"sent {r['id']} to ~{subs} subscribers score={score(c)}: {c['title']}")
    elif st == 200:
        s["pushed"][str(c["id"])] = {"ts": now, "url": c["url"], "title": c["title"], "sent": False, "errors": r.get("errors")}
        save_state(s); log(f"not delivered (no reachable subscribers): {r.get('errors')}")
    elif st == 429: log(f"rate limited; retry after {h.get('Retry-After')}s")
    else: log(f"send failed HTTP {st}: {r.get('errors')}")

if __name__ == "__main__":
    try: main()
    except Exception as ex: log(f"error (ignored): {ex}")
    sys.exit(0)
