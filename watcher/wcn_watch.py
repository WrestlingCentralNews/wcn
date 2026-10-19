#!/usr/bin/env python3
"""WCN fast-pickup watcher (runs on the box, not in Actions).
Every POLL_S seconds: conditional GET (ETag / If-Modified-Since) on every source the site's aggregator reads (aggregator.FEEDS,
the RSS feeds incl. the Google News site: queries) plus the no-RSS news listing pages (pagesrc.LISTINGS). When an item that
wasn't there before shows up from a trusted source (editorial tier 1-2), it is queued; queued items are coalesced into ONE
`gh workflow run update.yml` (the normal build: aggregator -> Pages deploy -> X -> push -> IndexNow), with safeguards:
  - never dispatch while an update run is already queued (the concurrency group then holds at most 1 running + 1 waiting,
    and only one deploy is ever in flight);
  - if a run is in progress that started AFTER the item was seen, it will pick the item up: no extra dispatch;
  - at most MAX_PER_HOUR dispatches per rolling hour and MIN_GAP_S between dispatches (counted from GitHub workflow_dispatch runs so the Cloudflare Worker in cfworker/ shares the same cap);
It then follows each dispatched item until its link shows up in the live site's news.json and in the X poster state
(data branch posted_x.json, read from GitHub - the X API is never called), logging detection -> site / X latency.
No secrets are read or printed (gh uses its own stored login). State + log: ~/.wcn/ (watcher.json, watcher.log).
Liveness: beat() rewrites ~/.wcn/watcher.heartbeat ("<CLOCK_BOOTTIME s> <pid> <phase> <wall s>") at every step and every 2 s
of sleep; supervise.sh kills + restarts the watcher when it goes stale (a hang while alive, not only a crash). Every network
call has a hard TOTAL deadline (not just a per-socket-op timeout), the feed pool is abandoned after POLL_DEADLINE_S, and
SIGUSR1 dumps all thread stacks to ~/.wcn/watcher.stacks (the watchdog does that before killing, so a stall is diagnosable).
CLOCK_BOOTTIME stops while the box VM is paused/snapshotted, so a pause/resume never looks like a hang; beat() logs each
pause it notices (wall clock jumped while the VM was frozen - nothing on the box, cron included, runs then)."""
import json, os, re, sys, time, hashlib, subprocess, signal, faulthandler, urllib.request, urllib.error, email.utils, datetime as dt, html
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, wait as fwait
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
HTTP_TIMEOUT_S = 20        # per socket operation (connect / each read)
HTTP_DEADLINE_S = 45       # whole request incl. a slow-drip body
POLL_DEADLINE_S = 90       # whole feed sweep; sources still running after this count as errors this cycle
HANG_TEST = os.path.join(HOME, "watcher.hang-test")
HBF = os.path.join(HOME, "watcher.heartbeat"); STACKS = os.path.join(HOME, "watcher.stacks")
EVERY = {"Bleacher Report": 3}   # heavy pages (BR's listing is ~2 MB, no validators): every Nth cycle only (6 min)
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 WCN-watcher/1.0"
sys.path.insert(0, REPO_DIR)
def log(*a):
    line = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + " ".join(str(x) for x in a)
    with open(LOGF, "a") as f: f.write(line + "\n")
    if os.path.getsize(LOGF) > 5_000_000:      # keep the log bounded
        os.replace(LOGF, LOGF + ".1")
_hb = {}
def boot_s(): return time.clock_gettime(time.CLOCK_BOOTTIME)
def beat(phase):
    """liveness for the watchdog; also notices box pauses (wall clock advanced far more than the boot clock)"""
    b, w = boot_s(), time.time()
    if _hb and (w - _hb["w"]) - (b - _hb["b"]) > 60:
        log(f"box was paused ~{((w - _hb['w']) - (b - _hb['b'])) / 60:.0f} min (VM suspended: no process on the box ran; resuming now)")
    _hb.update(b=b, w=w)
    try:
        with open(HBF + ".tmp", "w") as f: f.write(f"{b:.1f} {os.getpid()} {phase} {w:.0f}\n")
        os.replace(HBF + ".tmp", HBF)
    except OSError: pass
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
        end = time.monotonic() + HTTP_DEADLINE_S
        r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=HTTP_TIMEOUT_S)
        parts, n = [], 0
        while n < 4_000_000:
            if time.monotonic() > end: r.close(); return 0, None, meta     # slow-drip server: give up, try next cycle
            c = r.read1(min(65536, 4_000_000 - n))   # read1: returns what has arrived (read(n) would wait for n bytes)
            if not c: break
            parts.append(c); n += len(c)
        b = b"".join(parts); m = {"etag": r.headers.get("ETag"), "lm": r.headers.get("Last-Modified")}
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
def recent_dispatches(window_s=3600):
    """workflow_dispatch runs of update.yml in the last window (shared cap with the Cloudflare Worker)."""
    r = gh("run", "list", "--workflow", "update.yml", "--limit", "40", "--json", "databaseId,status,createdAt,event")
    if r.returncode: raise RuntimeError("gh run list failed: " + r.stderr.strip()[:200])
    now = time.time(); out = []
    for x in json.loads(r.stdout):
        if x.get("event") != "workflow_dispatch": continue
        created = dt.datetime.fromisoformat(x["createdAt"].replace("Z", "+00:00")).timestamp()
        if now - created < window_s: out.append({"databaseId": x["databaseId"], "created": created, "status": x["status"]})
    return out
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
    ex = ThreadPoolExecutor(10); futs = [ex.submit(one, s) for s in srcs]
    done, late = fwait(futs, timeout=POLL_DEADLINE_S)
    ex.shutdown(wait=False, cancel_futures=True)        # never block on a stuck source
    res = [f.result() if f in done else (s, 0, None, F.get(s[0], {}).get("meta", {})) for f, s in zip(futs, srcs)]
    if late: log("poll: abandoned", len(late), "source(s) still running after", POLL_DEADLINE_S, "s:", ", ".join(s[0] for f, s in zip(futs, srcs) if f in late)[:200])
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
    try:
        act = active_runs()
        recent = recent_dispatches(3600)   # shared with cfworker via GitHub (not local D alone)
    except Exception as e: log("dispatch check failed:", e); return
    oldest = min(p["seen_at"] for p in P)
    queued = [r for r in act if r["status"] != "in_progress"]
    running = [r for r in act if r["status"] == "in_progress"]
    covering = [r for r in act if r["created"] >= oldest - 5]    # a run created after the items were seen fetches them itself
    if covering:
        log(f"{len(P)} item(s) covered by run {covering[0]['databaseId']} ({covering[0]['status']}, {covering[0]['event']}) - no dispatch")
        S.setdefault("tracking", []).extend({**p, "run": covering[0]["databaseId"], "dispatched_at": None} for p in P); P.clear(); return
    if queued: log(f"{len(P)} pending - a run is already queued; waiting"); return
    n_hour = len(recent)
    if n_hour >= MAX_PER_HOUR: log(f"{len(P)} pending - hourly cap {MAX_PER_HOUR} reached ({n_hour} workflow_dispatch in last hour, shared with cfworker); waiting"); return
    latest = max((r["created"] for r in recent), default=0)
    if latest and now - latest < MIN_GAP_S: return
    if D and now - D[-1]["at"] < MIN_GAP_S: return   # local floor too (gh list can lag a few seconds)
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
        S["site_added"] = {c["id"]: c.get("added") for c in news.get("items", []) if c.get("added")}
        S["site_titles"] = [[c["id"], t] for c in news.get("items", [])[:150] for t in [c.get("raw_title"), c.get("title")] + [u.get("title") for u in c.get("updates", [])] if t]
    links = S.get("site_links") or {}
    def by_title(title):    # Google News items carry news.google.com links; the site stores the resolved article URL
        a = _toks(title)
        for cid, t in S.get("site_titles") or []:
            b = _toks(t)
            if a and b and len(a & b) / len(a | b) >= .6: return cid
        return None
    code, xs, S["x_meta"] = jget(XSTATE_RAW, S.get("x_meta", {}))
    if xs: S["x_posted"] = {k: v.get("at") for k, v in (xs.get("posted") or {}).items() if not v.get("deleted")}
    xp = S.get("x_posted") or {}
    keep = []
    for t in T:
        base = t.get("dispatched_at") or t["seen_at"]
        if not t.get("site_at"):
            cid = links.get(t["link"]) or (by_title(t["title"]) if "news.google." in t["link"] or t["feed"] in ("PWInsider", "WWE.com", "TNA Wrestling", "STARDOM", "Bleacher Report") else None)
            if cid:
                t["site_at"] = int(now); t["card"] = cid
                added = (S.get("site_added") or {}).get(cid)    # when the build actually put it on the site (a box pause delays only our noticing)
                if added and added < t["site_at"]: t["site_at"] = int(max(added, t["seen_at"]))
                pub = f", source published->site {int((added or t['site_at']) - t['ts'])}s" if t.get("ts") and t["ts"] > t["seen_at"] - 6 * 3600 else ""
                log(f"ON SITE after {t['site_at'] - t['seen_at']}s{pub} (detect->dispatch {(t['dispatched_at'] - t['seen_at']) if t.get('dispatched_at') else 'covered by a running build'}): [{t['source']}] {t['title'][:90]}")
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
    try: faulthandler.register(signal.SIGUSR1, file=open(STACKS, "w"), all_threads=True)
    except Exception: pass
    beat("start"); S = load(); nxt = 0
    while True:
        try:
            now = time.time()
            if now >= nxt:
                nxt = now + POLL_S
                beat("git_pull"); git_pull(S)
                if os.path.exists(HANG_TEST):     # watchdog self-test: `touch ~/.wcn/watcher.hang-test` = hang here while alive
                    os.remove(HANG_TEST); log("hang-test: blocking forever in the poll step"); beat("hang-test"); time.sleep(10 ** 7)
                beat("poll"); S.setdefault("pending", []).extend(poll(S)); S["cycle"] = S.get("cycle", 0) + 1
                S["last_poll"] = int(now)
            beat("dispatch"); maybe_dispatch(S)
            beat("track"); track(S)
            beat("save"); save(S)
        except Exception as e:
            log("cycle error:", repr(e)[:300])
        if once: break
        wake = min(nxt, time.time() + (TRACK_S if S.get("tracking") or S.get("pending") else POLL_S))
        while time.time() < wake: beat("sleep"); time.sleep(2)   # wall-clock steps: a box pause/resume can't stall it
if __name__ == "__main__": main()
