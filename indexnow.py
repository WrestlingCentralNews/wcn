"""Ping IndexNow (Bing, Yandex, Seznam, Naver...) with newly published WCN story URLs.
Runs after deploy. Each URL is submitted once (tracked in data/indexnow_sent.json on the
data branch). Never fails the workflow."""
import os, sys, json, glob, time, ssl, urllib.request, urllib.error
ROOT = os.path.dirname(os.path.abspath(__file__)); PUB = os.path.join(ROOT, "public")
HOST = "wrestlingcentralnews.com"
STATE = os.path.join(ROOT, "data", "indexnow_sent.json")
HTTPS_MARK = os.path.join(ROOT, "data", "indexnow_https_reping.json")  # one-time full re-ping once https is live
ENDPOINT = "https://api.indexnow.org/indexnow"
def log(m): print(f"[indexnow] {m}", flush=True)
def get(url, t=15):
    req = urllib.request.Request(url, headers={"User-Agent": "WCN-IndexNow/1.0"})
    with urllib.request.urlopen(req, timeout=t) as r: return r.status, r.read().decode("utf-8", "replace")
def scheme():
    # Use https once the custom-domain certificate is valid; http until then.
    try: get(f"https://{HOST}/robots.txt", 10); return "https"
    except Exception: return "http"
def main():
    keys = [os.path.basename(p)[:-4] for p in glob.glob(os.path.join(PUB, "*.txt"))
            if len(os.path.basename(p)) == 36 and open(p).read().strip() == os.path.basename(p)[:-4]]
    if not keys: log("no key file in public/; skipping"); return
    key = keys[0]
    news = json.load(open(os.path.join(PUB, "news.json")))
    urls_now = [c["url"] for c in news.get("items", []) if c.get("url")]
    try: sent = json.load(open(STATE))
    except Exception: sent = {}
    base = f"{scheme()}://{HOST}/"
    reping = base.startswith("https") and not os.path.exists(HTTPS_MARK)
    if reping:
        # resubmit homepage + every sitemap-listed story over https, exactly once
        try:
            import re
            locs = re.findall(r"<loc>([^<]+)</loc>", open(os.path.join(PUB, "sitemap.xml")).read())
            rel = [l.split(HOST + "/", 1)[1] for l in locs if HOST + "/" in l]
            urls_now = list(dict.fromkeys([u for u in rel if u] + urls_now))
        except Exception as ex: log(f"sitemap read failed ({ex}); using news.json")
        new = urls_now
        log(f"https is live: one-time re-ping of {len(new)} URLs")
    else:
        new = [u for u in urls_now if u not in sent]
    if not new: log("nothing new"); return
    # key file must be live before IndexNow will accept (it verifies keyLocation)
    for i in range(6):
        try:
            st, body = get(f"{base}{key}.txt?cb={int(time.time())}")
            if body.strip() == key: break
        except Exception as ex: pass
        time.sleep(10)
    else: log("key file not reachable yet; will retry next run"); return
    batch = [base, base + "feed.xml"] + [base + u for u in new[:9999]]
    payload = json.dumps({"host": HOST, "key": key, "keyLocation": f"{base}{key}.txt", "urlList": batch}).encode()
    req = urllib.request.Request(ENDPOINT, data=payload, method="POST",
                                 headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": "WCN-IndexNow/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r: code = r.status
    except urllib.error.HTTPError as ex: code = ex.code
    except Exception as ex: log(f"request failed: {ex}"); return
    log(f"HTTP {code} for {len(batch)} URLs ({base})")
    if code in (200, 202):
        now = int(time.time())
        for u in new[:9999]: sent[u] = now
        if reping:
            os.makedirs(os.path.dirname(HTTPS_MARK), exist_ok=True)
            json.dump({"done": now, "count": len(batch)}, open(HTTPS_MARK, "w"))
        live = set(urls_now); sent = {u: t for u, t in sent.items() if u in live or now - t < 90 * 86400}
        os.makedirs(os.path.dirname(STATE), exist_ok=True); json.dump(sent, open(STATE, "w"))
    else: log("not recorded; will retry next run")
if __name__ == "__main__":
    try: main()
    except Exception as ex: log(f"error (ignored): {ex}")
    sys.exit(0)
