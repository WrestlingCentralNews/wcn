"""Official roster snapshot (owner rule 2026-10-21): WWE (wwe.com current superstars), AEW (allelitewrestling.com/aew-roster),
TNA (tnawrestling.com/roster). Fetched on demand only (ensure), at most once per promotion per UTC day, when a contract-type story about it is gated (a handful of plain GETs, no AI,
robots.txt allows these paths). data/rosters.json keeps every name with first-seen / last-seen dates.
Used by pubgate for signing stories:
  * 'released / exits' story while the wrestler is still listed -> held, unless 2+ distinct trusted outlets (tier 1-2) or the
    promotion's own site report it;
  * 'new signing' of a wrestler listed on that roster for more than 14 days -> held (likely a re-signing);
  * support note on the story: 'still on the WWE roster' / 'newly added to the WWE roster'.
Never holds when a roster failed to load, is older than 3 days, or the person isn't a wrestler (executives) / isn't matched."""
import os, re, json, time, html, unicodedata, urllib.request
ROOT = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(ROOT, "data", "rosters.json")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 WCN-roster-check"
OFFICIAL = {"WWE": r"(?:^|\.)wwe\.com$", "AEW": r"(?:^|\.)allelitewrestling\.com$", "TNA": r"(?:^|\.)tnawrestling\.com$"}
LONG_DAYS, MAX_AGE = 14, 3 * 86400
def _get(u):
    req = urllib.request.Request(u, headers={"User-Agent": UA, "X-Requested-With": "XMLHttpRequest" if "views/ajax" in u else ""})
    with urllib.request.urlopen(req, timeout=25) as r: return r.read().decode("utf-8", "ignore")
def _clean(n): return re.sub(r"\s+", " ", html.unescape(n).replace("\xa0", " ")).strip()
def fetch_wwe(get=_get):
    out = set()
    for p in range(15):
        s = get("https://www.wwe.com/views/ajax?_wrapper_format=drupal_ajax&view_name=current_superstar&view_display_id=block_1"
                f"&view_args=&view_path=%2Fnode%2F50000002&pager_element=0&page={p}")
        s = json.loads(s); s = " ".join(x.get("data") for x in (s.values() if isinstance(s, dict) else s) if isinstance(x, dict) and isinstance(x.get("data"), str))
        got = {_clean(n) for n in re.findall(r'<a href="/superstars/[a-z0-9-]+" hreflang="en">([^<]+)</a>', s)}
        if not got - out: break
        out |= got
    return out
def fetch_aew(get=_get):
    s = get("https://www.allelitewrestling.com/aew-roster")
    return {_clean(n) for n in re.findall(r'<div role="listitem"[^>]*>.*?<h2[^>]*>(?:<[^>]+>)*([^<]{2,60})<', s, re.S)}
def fetch_tna(get=_get):
    out = set()
    for p in range(1, 21):
        s = get(f"https://tnawrestling.com/roster/?page={p}")
        got = {_clean(n) for n in re.findall(r'href="https://tnawrestling\.com/roster/[a-z0-9-]+">\s*(?:<img[^>]*>\s*)?<h5[^>]*>([^<]+)</h5>', s)}
        if not got - out: break
        out |= got
    return out
FETCH = {"WWE": fetch_wwe, "AEW": fetch_aew, "TNA": fetch_tna}
MIN = {"WWE": 100, "AEW": 60, "TNA": 30}      # fewer names than this = page changed/broken, keep the old snapshot
def key(n):
    try:
        import aliases; n = aliases.canon(n)
    except Exception: pass
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", re.sub(r"^the\s+", "", n))).strip()
def load():
    try: return json.load(open(PATH))
    except Exception: return {}
def refresh(now=None, fetch=None, log=print, only=None):
    """At most once per UTC day per promotion: fetch roster(s), update first/last seen. A failed or implausibly small fetch changes nothing."""
    now = int(now or time.time()); day = time.strftime("%Y-%m-%d", time.gmtime(now)); db = load(); fetch = fetch or FETCH
    for p, f in fetch.items():
        if only and p not in only: continue
        r = db.setdefault(p, {"names": {}, "baseline": None})
        if r.get("tried_day") == day: continue
        r["tried_day"] = day
        try: names = f()
        except Exception as e: r["ok"] = False; r["error"] = str(e)[:120]; log(f"roster {p}: fetch failed ({e})"); continue
        if len(names) < MIN.get(p, 10): r["ok"] = False; r["error"] = f"only {len(names)} names"; log(f"roster {p}: only {len(names)} names, kept old"); continue
        r["baseline"] = r.get("baseline") or now
        for n in names:
            e = r["names"].setdefault(key(n), {"name": n, "first": now}); e["last"] = now
        r.update(ok=True, fetched=now, count=len(names), error=None)
        log(f"roster {p}: {len(names)} names")
    try: os.makedirs(os.path.dirname(PATH), exist_ok=True); json.dump(db, open(PATH, "w"), indent=0)
    except Exception: pass
    return db
def ensure(promo, now=None, fetch=None, log=print):
    """On demand only (owner rule 2026-10-21 #2): called when a contract-type story (signing, re-signing, release, exit,
    return, retirement) about this promotion is gated. One fetch per promotion per UTC day, reused by later stories;
    nothing is fetched otherwise. Fail-open: any error returns the stored snapshot (status() ignores stale ones).
    Note: first-seen dates now only exist from these on-demand fetches, so the 14-day re-signing rule is weaker."""
    if promo not in (fetch or FETCH): return load()
    try: return refresh(now=now, fetch=fetch, log=log, only={promo})
    except Exception: return load()
def status(name, promo, db=None, now=None):
    """None (no usable roster / not checked) | {'listed': bool, 'days': days listed (lower bound if since baseline), 'new': bool}"""
    db = load() if db is None else db; now = now or time.time(); r = db.get(promo) or {}
    if not r.get("fetched") or now - r["fetched"] > MAX_AGE: return None
    e = r["names"].get(key(name))
    if not e or e.get("last", 0) < r["fetched"]: return {"listed": False, "days": 0, "new": False, "was_listed": bool(e)}
    days = (now - e["first"]) / 86400
    return {"listed": True, "days": days, "new": e["first"] > (r.get("baseline") or 0) + 3600 and days <= LONG_DAYS}
def official(link, promo):
    m = re.match(r"https?://([^/]+)", link or ""); return bool(m and promo in OFFICIAL and re.search(OFFICIAL[promo], m.group(1).lower()))
