#!/usr/bin/env python3
"""WCN fast-pickup watcher (runs on the box, not in Actions).
Every POLL_S seconds: conditional GET (ETag / If-Modified-Since) on every source the site's aggregator reads (aggregator.FEEDS,
the RSS feeds incl. the Google News site: queries) plus the no-RSS news listing pages (pagesrc.LISTINGS). When an item that
wasn't there before shows up from a trusted source (editorial tier 1-2), it is queued; queued items are coalesced into ONE
`gh workflow run update.yml` (the normal build: aggregator -> Pages deploy -> X -> push -> IndexNow), with safeguards:
  - never dispatch while an update run is already queued (the concurrency group then holds at most 1 running + 1 waiting,
    and only one deploy is ever in flight);
  - if a run is in progress that started AFTER the item was seen, it will pick the item up: no extra dispatch;
  - at most MAX_PER_HOUR dispatches per rolling hour and MIN_GAP_S between dispatches.
It then follows each dispatched item until its link shows up in the live site's news.json and in the X poster state
(data branch posted_x.json, read from GitHub - the X API is never called), logging detection -> site / X latency.
No secrets are read or printed (gh uses its own stored login). State + log: ~/.wcn/ (watcher.json, watcher.log)."""
import json, os, re, sys, time, hashlib, subprocess, urllib.request, urllib.error, email.utils, datetime as dt, html
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
HOME = os.path.expanduser("~/.wcn"); os.makedirs(HOME, exist_ok=True)
STATE = os.path.join(HOME, "watcher.json"); LOGF = os.path.join(HOME, "watcher.log")
REPO_DIR = os.environ.get("WCN_REPO", os.path.join(HOME, "repo"))
GH_REPO = "WrestlingCentralNews/wcn"
SITE_JSON = "https://wrestlingcentralnews.com/news.json"
XSTATE_RAW = "https://raw.githubusercontent.com/WrestlingCentralNews/wcn/data/data/posted_x.json"
POLL_S = 120
TRACK_S = 20               # follow-up checks of the site/X state while dispatched items are pending
MAX_PER_HOUR = 20
MIN_GAP_S = 60
FRESH_H = 6                # items dated older than this never trigger a build
TRACK_MAX_S = 45 * 60
GOOGLE_BACKOFF_S = 15 * 60
EVERY = {"Bleacher Report": 3}   # heavy pages (BR's listing is ~2 MB, no validators): every Nth cycle only (6 min)
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 WCN-watcher/1.0"
sys.path.insert(0, REPO_DIR)
def log(*a):
    line = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + " ".join(str(x) for x in a)
    with open(LOGF, "a") as f: f.write(line + "\n")
    if os.path.getsize(LOGF) > 5_000_000:      # keep the log bounded
        os.replace(LOGF, LOGF + ".1")
def load():
    try: return json.load(open(STATE))
    except Exception: return {}
def save(S):
    tmp = STATE + ".tmp"; json.dump(S, open(tmp, "w")); os.replace(tmp, STATE)
def sources():
    """(name, url, kind) for every feed/page the aggregator reads; reloaded every cycle from the box clone (git pull hourly)."""
    import importlib
    import aggregator, pagesrc, editorial
    for m in (editorial, pagesrc, aggregator): importlib.reload(m)
    out = [(n, u, "rss") for n, u in aggregator.FEEDS.items()]
    out += [(n, v[0], "page") for n, v in pagesrc.LISTINGS.items()]
    return out, editorial, pagesrc
def cget(url, meta):
    """conditional GET -> (status, body or None, new meta)"""
    h = {"User-Agent": UA, "Accept-Encoding": "identity"}
    if meta.get("etag"): h["If-None-Match"] = meta["etag"]
    if meta.get("lm"): h["If-Modified-Since"] = meta["lm"]
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=20)
        b = r.read(4_000_000); m = {"etag": r.headers.get("ETag"), "lm": r.headers.get("Last-Modified")}
        return r.status, b, {k: v for k, v in m.items() if v}
    except urllib.error.HTTPError as e:
        if e.code == 304: return 304, None, meta
        return e.code, None, meta
    except Exception as e:
        return 0, None, meta
def ts_of(d):
    if not d: return None
    try: return email.utils.parsedate_to_datetime(d).timestamp()
    except Exception: pass
    try: return dt.datetime.fromisoformat(d.strip().replace("Z", "+00:00")).timestamp()
    except Exception: return None
def rss_items(b):
    root = ET.fromstring(b); A = "{http://www.w3.org/2005/Atom}"; out = []
    nodes = list(root.iter("item")) or list(root.iter(A + "entry"))
    for it in nodes:
        title = html.unescape(re.sub(r"<[^>]+>", "", it.findtext("title") or it.findtext(A + "title") or "")).strip()
        link = (it.findtext("link") or (it.find(A + "link").get("href") if it.find(A + "link") is not None else "") or "").strip()
        guid = (it.findtext("guid") or it.findtext(A + "id") or link or title).strip()
        src = it.find("source"); src = src.text if src is not None else None
        out.append({"key": guid, "title": re.sub(r"\s+-\s+[^-]+$", "", title) if src else title, "link": link, "src": src,
                    "ts": ts_of(it.findtext("pubDate") or it.findtext(A + "updated") or it.findtext(A + "published"))})
    return out
def gh(*args, t=40):
    return subprocess.run(["gh", *args, "-R", GH_REPO], capture_output=True, text=True, timeout=t)
def active_runs():
    r = gh("run", "list", "--workflow", "update.yml", "--limit", "8", "--json", "databaseId,status,createdAt,event")
    if r.returncode: raise RuntimeError("gh run list failed: " + r.stderr.strip()[:200])
    runs = json.loads(r.stdout)
    for x in runs: x["created"] = dt.datetime.fromisoformat(x["createdAt"].replace("Z", "+00:00")).timestamp()
    return [x for x in runs if x["status"] in ("queued", "in_progress", "pending", "waiting", "requested")]
def poll(S):
    srcs, editorial, pagesrc = sources(); tier = editorial.tier
    F = S.setdefault("feeds", {}); now = time.time(); new = []
    def one(s):
        name, url, kind = s; m = F.get(name, {})
        if "news.google.com" in url and now < S.get("google_backoff_until", 0): return s, "backoff", None, m
        if S.get("cycle", 0) % EVERY.get(name, 1): return s, "backoff", None, m
        code, b, meta = cget(url, m.get("meta", {}))
        return s, code, b, meta
    t0 = time.time()
    with ThreadPoolExecutor(10) as ex: res = list(ex.map(one, srcs))
    stats = {"200": 0, "304": 0, "err": 0}
    for (name, url, kind), code, b, meta in res:
        f = F.setdefault(name, {"seen": {}, "baseline": False})
        if code == "backoff": continue
        f["meta"] = meta; f["last_code"] = code
        if code == 304: stats["304"] += 1; continue
        if code != 200 or not b:
            stats["err"] += 1
            if "news.google.com" in url and code in (429, 503): S["google_backoff_until"] = now + GOOGLE_BACKOFF_S; log("google news rate-limited (HTTP", code, ") - backing off 15 min")
            continue
        stats["200"] += 1
        try:
            if kind == "rss": items = rss_items(b)
            else: items = [{"key": l, "title": l.rsplit("/", 1)[-1], "link": l, "src": None, "ts": None} for l in pagesrc.links(name, b.decode("utf8", "ignore"))]
        except Exception as e:
            log("parse error", name, repr(e)[:120]); continue
        fresh = [i for i in items if i["key"] not in f["seen"]]
        for i in items: f["seen"][i["key"]] = int(now)
        if len(f["seen"]) > 600: f["seen"] = dict(sorted(f["seen"].items(), key=lambda kv: -kv[1])[:600])
        T = S.setdefault("titles", {})
        tid = lambda i: hashlib.md5(re.sub(r"\W", "", i["title"].lower()).encode()).hexdigest()[:12]   # aggregator's article id
        dups = {i["key"] for i in fresh if kind == "rss" and tid(i) in T}   # already seen via another feed (Google re-listing a Fightful post)
        if kind == "rss":
            for i in items: T.setdefault(tid(i), int(now))
        if not f["baseline"]: f["baseline"] = True; continue          # first sight of a source: remember, don't trigger
        for i in fresh:
            if i["key"] in dups: continue
            src = i["src"] or name
            trusted = tier(src) <= 2
            if i["ts"] and i["ts"] < now - FRESH_H * 3600: continue
            if not trusted: continue
            try:
                why = editorial.verdict({"raw_title": i["title"]}) if kind == "rss" else None
            except Exception: why = None
            if why: log("  skip", f"({why})", f"[{src}]", i["title"][:100]); continue    # the site's rules would drop it anyway
            new.append({"feed": name, "source": src, "title": i["title"][:140], "link": i["link"], "ts": i["ts"], "seen_at": int(now)})
    T = S.get("titles", {})
    if len(T) > 5000: S["titles"] = dict(sorted(T.items(), key=lambda kv: -kv[1])[:4000])
    log(f"poll: {len(srcs)} sources in {time.time() - t0:.1f}s - 200:{stats['200']} 304:{stats['304']} err:{stats['err']} new trusted items: {len(new)}")
    for i in new: log("  NEW", f"[{i['source']}]", i["title"], "|", i["link"][:120])
    return new
def maybe_dispatch(S):
    P = S.setdefault("pending", [])
    if not P: return
    now = time.time(); D = S.setdefault("dispatches", []); D[:] = [d for d in D if now - d["at"] < 3600]
    try: act = active_runs()
    except Exception as e: log("dispatch check failed:", e); return
    oldest = min(p["seen_at"] for p in P)
    queued = [r for r in act if r["status"] != "in_progress"]
    running = [r for r in act if r["status"] == "in_progress"]
    covering = [r for r in act if r["created"] >= oldest - 5]    # a run created after the items were seen fetches them itself
    if covering:
        log(f"{len(P)} item(s) covered by run {covering[0]['databaseId']} ({covering[0]['status']}, {covering[0]['event']}) - no dispatch")
        S.setdefault("tracking", []).extend({**p, "run": covering[0]["databaseId"], "dispatched_at": None} for p in P); P.clear(); return
    if queued: log(f"{len(P)} pending - a run is already queued; waiting"); return
    if len(D) >= MAX_PER_HOUR: log(f"{len(P)} pending - hourly cap {MAX_PER_HOUR} reached; the next allowed dispatch picks them up"); return
    if D and now - D[-1]["at"] < MIN_GAP_S: return
    r = gh("workflow", "run", "update.yml")
    if r.returncode: log("dispatch failed:", r.stderr.strip()[:200]); return
    D.append({"at": now, "n": len(P)})
    log(f"DISPATCHED update.yml for {len(P)} new item(s)" + (f" (queued behind running run {running[0]['databaseId']})" if running else ""))
    S.setdefault("tracking", []).extend({**p, "dispatched_at": int(now)} for p in P); P.clear()
def jget(url, meta):
    code, b, meta2 = cget(url, meta)
    return code, (json.loads(b) if code == 200 and b else None), meta2
def track(S):
    T = S.get("tracking") or []
    if not T: return
    now = time.time()
    code, news, S["site_meta"] = jget(SITE_JSON + "?t=" + str(int(now)), {})
    if news:
        S["site_links"] = {l: c["id"] for c in news.get("items", []) for l in [c.get("link")] + [u.get("link") for u in c.get("updates", [])] if l}
        S["site_titles"] = [[c["id"], t] for c in news.get("items", [])[:150] for t in [c.get("raw_title"), c.get("title")] + [u.get("title") for u in c.get("updates", [])] if t]
    links = S.get("site_links") or {}
    def by_title(title):    # Google News items carry news.google.com links; the site stores the resolved article URL
        a = _toks(title)
        for cid, t in S.get("site_titles") or []:
            b = _toks(t)
            if a and b and len(a & b) / len(a | b) >= .6: return cid
        return None
    code, xs, S["x_meta"] = jget(XSTATE_RAW, S.get("x_meta", {}))
    if xs: S["x_posted"] = {k: v.get("at") for k, v in (xs.get("posted") or {}).items()}
    xp = S.get("x_posted") or {}
    keep = []
    for t in T:
        base = t.get("dispatched_at") or t["seen_at"]
        if not t.get("site_at"):
            cid = links.get(t["link"]) or (by_title(t["title"]) if "news.google." in t["link"] or t["feed"] in ("PWInsider", "WWE.com", "TNA Wrestling", "STARDOM", "Bleacher Report") else None)
            if cid:
                t["site_at"] = int(now); t["card"] = cid
                log(f"ON SITE after {t['site_at'] - t['seen_at']}s (detect->dispatch {(t['dispatched_at'] - t['seen_at']) if t.get('dispatched_at') else 'covered by a running build'}): [{t['source']}] {t['title'][:90]}")
        if t.get("card") and not t.get("x_at") and t["card"] in xp:
            t["x_at"] = int(xp[t["card"]]); log(f"ON X after {t['x_at'] - t['seen_at']}s: [{t['source']}] {t['title'][:90]}")
        done = t.get("site_at") and (t.get("x_at") or now - base > 1800)
        if done or now - base > TRACK_MAX_S:
            d = lambda k: f"{t[k] - t['seen_at']}s" if t.get(k) else "n/a"
            log(f"LATENCY [{t['source']}] {t['title'][:80]} | detect->dispatch {d('dispatched_at')} | detect->site {d('site_at')} | "
                f"detect->X {d('x_at')}" + ("" if t.get("site_at") else " (not on site: dropped by editorial rules or merged under another link)"))
            S.setdefault("latency", []).append({k: t.get(k) for k in ("source", "title", "link", "ts", "seen_at", "dispatched_at", "site_at", "x_at")})
            S["latency"] = S["latency"][-300:]
        else: keep.append(t)
    S["tracking"] = keep
def _toks(t): return set(re.findall(r"[a-z0-9]{3,}", (t or "").lower())) - {"the", "and", "for", "with", "from", "after", "wwe", "aew"}
def git_pull(S):
    if time.time() - S.get("pulled_at", 0) < 3600: return
    r = subprocess.run(["git", "-C", REPO_DIR, "pull", "-q", "--ff-only"], capture_output=True, text=True, timeout=120)
    S["pulled_at"] = time.time()
    if r.returncode: log("git pull failed:", r.stderr.strip()[:200])
def main():
    once = "--once" in sys.argv
    log(f"watcher start pid={os.getpid()} poll={POLL_S}s repo={REPO_DIR}")
    S = load(); nxt = 0
    while True:
        try:
            now = time.time()
            if now >= nxt:
                nxt = now + POLL_S
                git_pull(S)
                S.setdefault("pending", []).extend(poll(S)); S["cycle"] = S.get("cycle", 0) + 1
                S["last_poll"] = int(now)
            maybe_dispatch(S)
            track(S)
            save(S)
        except Exception as e:
            log("cycle error:", repr(e)[:300])
        if once: break
        wake = min(nxt, time.time() + (TRACK_S if S.get("tracking") or S.get("pending") else POLL_S))
        while time.time() < wake: time.sleep(2)   # wall-clock steps: a box pause/resume can't stall it
if __name__ == "__main__": main()
