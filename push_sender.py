"""Web push via OneSignal (free plan) — ONLY for genuinely big wrestling stories.

Runs after the site deploy in the 15-min workflow (like x_poster.py). No AI calls: uses signals already computed
(sources / trusted-source count per story, the story type from the existing LLM pass, keyword rules).

Big-story types (title/summary rules) and the corroboration each needs (distinct sources / trusted tier-1 sources):
  death 2/2 · title change 2/1 · retirement 2/1 · major signing 3/2 · release/exit 3/2 · return 3/2 · major injury 3/2
  · major-PPV main-event result 2/1 · major-PPV card announcement (main event / world title) 3/2
Brands: WWE/AEW/TNA for all types; Global only for major-PPV results/title changes; deaths from anywhere.
Never: rumors/speculation, quotes/interviews, previews, ratings, live-results threads, opinion.
Limits: max 3 per rolling 24h, >= 2h apart, 1 per run, story first reported < 4h ago (latest report < 3h);
quiet hours 11 PM–8 AM Puerto Rico time (America/Puerto_Rico, UTC-4; OneSignal's per-reader timezone option can only
deliver at a fixed clock time, which would delay breaking news by up to a day). Stories first reported during quiet
hours may go out 8–10 AM. Never the same story twice: by story id, by any report link already pushed (cluster updates
or a re-keyed cluster), and by same type + same wrestler within 72h.
Spanish: subscribers whose browser language is Spanish get the cached Spanish headline and the /es/ page (2nd send
filtered by language); everyone else gets English. Falls back to one English send if no translation is cached.
Every run logs a decision line per fresh candidate. Enable with PUSH_ENABLED=1; anything else = dry run.
State: data/pushed.json (data branch). Never fails the workflow.
"""
import os, re, sys, json, time, uuid, datetime, urllib.request, urllib.error
from zoneinfo import ZoneInfo
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from x_poster import score
NEWS = os.path.join(ROOT, "public", "news.json")
STATE = os.path.join(ROOT, "data", "pushed.json")
TR = os.path.join(ROOT, "data", "translations_es.json")
SITE = "https://wrestlingcentralnews.com/"
API = "https://api.onesignal.com"
TZ = ZoneInfo("America/Puerto_Rico")
DAILY_CAP, MIN_GAP_H = 3, 2
FRESH_H, ACTIVE_H, MORNING_H = 4, 3, 10       # first reported < 4h; latest report < 3h; overnight stories up to 10h at 8–10 AM
QUIET_START, QUIET_END, CATCHUP_END = 23, 8, 10
SEGMENT = "Total Subscriptions"
MAX_LOG = 15

def log(*a): print("[push]", *a, flush=True)
def load_state():
    try: s = json.load(open(STATE))
    except Exception: s = {}
    s.setdefault("pushed", {}); s.setdefault("log", []); return s
def save_state(s):
    now = time.time(); s["pushed"] = {k: v for k, v in s["pushed"].items() if now - v.get("ts", 0) < 120 * 86400}
    s["log"] = s["log"][-200:]; os.makedirs(os.path.dirname(STATE), exist_ok=True); json.dump(s, open(STATE, "w"), indent=0)

# ---------- what counts as big ----------
PPV = (r"WrestleMania|SummerSlam|Royal Rumble|Survivor Series|Money in the Bank|Elimination Chamber|Crown Jewel|Night of Champions|"
       r"Saturday Night'?s Main Event|Clash in Paris|Backlash|Bad Blood|Wrestlepalooza|NXT (?:Stand (?:&|and) Deliver|Halloween Havoc|Deadline|Vengeance Day|Battleground|Heatwave|No Mercy)|"
       r"All In|All Out|Double or Nothing|Full Gear|Revolution|WrestleDream|Worlds? End|Forbidden Door|Dynasty|Grand Slam|"
       r"Bound for Glory|Slammiversary|Hard to Kill|Rebellion|Sacrifice|Wrestle Kingdom|Final Battle|Triplemania|Dominion|G1 Climax Final")
RX = {
    "death": r"\b(died|dies|dead at \d+|death of|has passed|passed away|passes away|rest in peace|RIP)\b|\bmourns?\b",
    "title change": r"\b(new [\w' ]{0,30}champion|crowned|dethrones?|captures?|wins? (?:the )?[\w' ]{0,40}(title|championship)|"
                    r"(?:lose|loses|lost|drops?|dropped) (?:the |his |her |their )?[\w' ]{0,40}(title|championship)|title change|vacate[sd]?)\b",
    "retirement": r"\b(retires?|retired|retirement|hangs? up (?:the|his|her) boots|final match)\b",
    "major signing": r"\b(signs?|signed|signing|inks?|inked|agrees? to (?:a )?(?:new )?(?:deal|contract)|re-signs?|joins) (?:with |a |an |new |multi-year |\w+-year )*(WWE|AEW|TNA|deal|contract|extension)\b",
    "release/exit": r"\b(released (?:from|by)|releases? [A-Z][a-z]+ [A-Z]|granted (?:his |her )?release|requests? (?:his |her )?release|"
                    r"(?:has |have )?(?:left|leaves|departs?|departed|exits?|exited) (WWE|AEW|TNA)|contract (?:has )?expire[sd]?|free agent|parts? ways)\b",
    "return": r"\b(returns?|returned|makes? (?:his |her |a )?(?:shocking |surprise )?return|comeback|is back)\b",
    "major injury": r"\b(injur\w*|surgery|torn|tears? (?:his|her)|broken|fracture\w*|concussion|stretchered|hospitali[sz]ed|out of action|sidelined|halted)\b",
}
INJ_SEVERE = r"\b(surgery|torn|tear|broken|fracture\w*|months?|out of action|sidelined|out indefinitely|stretchered|hospitali[sz]ed|career|halted|stopped|pulled from)\b"
RESULT_VERB = r"\b(def\.|defeats?|defeated|beats?|beat|wins?|won|retains?|retained|captures?|crowned|dethrones?|pins?|submits?)\b"
CARD = r"\b(main event|headline\w*|world (?:heavyweight )?(?:title|championship)|undisputed|title match|championship match|set for|official|announced|confirmed|added to)\b"
NOT_BIG = (r"\b(rumou?rs?|reportedly|report:|could|might|may|plans?|planned|pitched|interested|wants?|hopes?|teases?|hints?|eyes|considering|"
           r"backstage|update on|updates? on|reacts?|comments?|discusses|recalls|reflects|opens up|podcast|interview|video|watch|"
           r"ratings?|viewership|attendance|tickets?|grades?|preview|predictions?|quiz|why|how|what|odds|betting|merch|documentary|"
           r"anniversary|on this day|years? ago|tribute show|death match|deathmatch|statement|teaser|trailer|poster|"
           r"live results|results thread|live coverage|live blog|stream|kickoff|pre-show|house show|live event|dark match|qualif\w*|tournament)\b")
MIN_SRC = {"death": (2, 1), "title change": (2, 1), "retirement": (2, 1), "major signing": (3, 2), "release/exit": (2, 1),
           "return": (3, 2), "major injury": (3, 1), "PPV main-event result": (1, 1), "PPV card announcement": (3, 2)}
TV = r"\b(Raw|SmackDown|NXT|Dynamite|Collision|Rampage|iMPACT|Impact|Thunder|Level Up|Evolve|LFG)\b(?! PPV)"
DEV = r"\b(WWE ID|ID program|Performance Center|developmental|LFG|Evolve|tryout|indie|independent)\b"
WORLD = r"\b(world|main event|undisputed|heavyweight|universal|women's world|headlin\w*)\b"
BIG3 = {"WWE", "AEW", "TNA"}
def classify(c):
    """(type or None, reason)."""
    t = c["title"]; full = t + " " + (c.get("summary") or "")
    kind = (c.get("kind") or {}).get("type", "news"); cats = set(c["categories"])
    ppv = re.search(PPV, t, re.I)
    if re.search(RX["death"], t, re.I) and not re.search(r"\b(death match|deathmatch|anniversary|years? (?:ago|since)|tribute show|on this day|documentary|podcast|medical examiner|cause of death|autopsy|funeral|memorial|celebration of life|remember\w*|honou?r\w*|lawsuit|sues)\b", t, re.I):
        return "death", "death keyword in headline"
    if kind == "quote": return None, "quote/interview story"
    neg = re.search(NOT_BIG, t, re.I)
    if neg and not (ppv and re.search(RESULT_VERB, t, re.I) and neg.group(0).lower() in ("live results", "results thread")): return None, f"not breaking ('{neg.group(0)}' in headline)"
    brand_ok = bool(cats & BIG3)
    if ppv and not re.search(TV, t) and kind in ("results", "news", "match") and re.search(RESULT_VERB, t, re.I) and re.search(WORLD, t, re.I):
        return "PPV main-event result", f"{ppv.group(0)} main-event result"
    if re.search(RX["title change"], t, re.I) and not re.search(r"\b(retains?|retained|defends?|title shot|contender|eliminator|tag team tournament)\b", t, re.I):
        if brand_ok or ppv: return "title change", "title change keyword"
    if not brand_ok: return None, "not a WWE/AEW/TNA story"
    if ppv and not re.search(TV, t) and kind in ("match", "news") and re.search(CARD, t, re.I) and re.search(r"\bvs\b|\b(versus|main event|headline\w*|world|undisputed)\b", t, re.I):
        return "PPV card announcement", f"{ppv.group(0)} card"
    for typ in ("retirement", "release/exit", "major signing", "return", "major injury"):
        if re.search(RX[typ], t, re.I):
            if typ in ("release/exit", "major signing", "return") and re.search(DEV, full, re.I): return None, f"{typ}, but developmental/indie level"
            if typ == "major injury" and re.search(r"\bNXT\b", t): return None, "injury on NXT, not main roster"
            if typ == "major injury" and not re.search(INJ_SEVERE, full, re.I): return None, "injury, but not a major one"
            if typ == "return" and re.search(r"\breturns? to (?:pay-per-view|ppv|tv|television|the [A-Z]\w+ (?:arena|center)|[A-Z]\w+(?:, | in |$)|action on)|\b(event|show|series|brand|tour) returns\b", t, re.I):
                return None, "event/show return, not a wrestler return"
            return typ, f"{typ} keyword"
    return None, "no big-story keyword"
def check(c):
    typ, why = classify(c)
    if not typ: return None, why
    ns, nt = MIN_SRC[typ]; s, tr = c.get("sources", 1), c.get("trusted", 0)
    if s < ns or tr < nt: return None, f"{typ}, but only {s} source(s)/{tr} trusted (needs {ns}/{nt})"
    return typ, f"{typ} ({why}; {s} sources/{tr} trusted)"

# ---------- duplicates ----------
_persons = None
def persons(t):
    global _persons
    if _persons is None:
        try: from enrich import persons as p; _persons = p
        except Exception: _persons = lambda x: frozenset()
    return _persons(t)
def links(c): return {c.get("link")} | {u.get("link") for u in c.get("updates", [])} - {None}
RESULT_TYPES = {"title change", "PPV main-event result"}
def live_candidates(now):
    """Title changes from live results (live.py) as push candidates: same rules, caps, quiet hours and de-dupe as stories.
    Only confirmed results with >= 2 trusted sources and no conflicting report; at most 3h old."""
    import glob
    out = []
    for f in glob.glob(os.path.join(ROOT, "data", "live", "*.json")):
        try: st = json.load(open(f))
        except Exception: continue
        if st.get("brand") not in BIG3 and st.get("kind") != "ppv": continue
        show = re.sub(r"\s+\d{4}$", "", st["name"])
        for m in st.get("matches", []):
            if m.get("title") != "change" or m.get("conflict") or len(m.get("sources", [])) < 2 or now - m["first_seen"] > 3 * 3600: continue
            belt = m.get("stip") if re.search(r"(?i)title|championship", m.get("stip") or "") else "title"
            belt = re.sub(r"(?i)\s*[-–—:]\s*.*match$|\s+match$", "", belt)
            pl = bool(re.search(r"&| and |,", m["winner"]))
            ev_path = (f"events/{st['key']}/" if st.get("kind") == "ppv" else f"events/{st['date']}-{st['slug']}/")
            es_path = (f"es/eventos/{st['slug']}-{st['date']}/" if st.get("kind") == "ppv" else f"es/eventos/resultados-{st['slug']}-{st['date']}/")
            out.append({"id": f"live-{st['key']}-{m['id']}", "title": f"{m['winner']} {'win' if pl else 'wins'} the {belt} at {show}",
                        "summary": m.get("en", ""), "categories": [st.get("brand", "AEW")], "kind": {"type": "results"},
                        "sources": len(m["sources"]), "trusted": len(m["sources"]), "first_ts": m["first_seen"], "ts": m.get("updated", m["first_seen"]),
                        "url": ev_path + "#" + m["id"], "link": m["sources"][0]["url"], "updates": [{"link": x["url"]} for x in m["sources"][1:]],
                        "live_es": {"t": f"{m['winner']} {'ganan' if pl else 'gana'} el título en {show}", "url": es_path + "#" + m["id"]}})
    return out
def duplicate_of(c, typ, s, now):
    if str(c["id"]) in s["pushed"]: return s["pushed"][str(c["id"])].get("title", "same story")
    L = links(c); P = persons(c["title"])
    for v in s["pushed"].values():
        if v.get("url") == c.get("url") or L & set(v.get("links", [])): return v.get("title")
        same_kind = v.get("type") == typ or {v.get("type"), typ} <= RESULT_TYPES   # a live title change and the later story about it are one event
        if now - v.get("ts", 0) < 72 * 3600 and same_kind and P and P & set(v.get("persons", [])): return v.get("title")
    return None

# ---------- timing ----------
def local(ts): return datetime.datetime.fromtimestamp(ts, TZ)
def quiet(ts): h = local(ts).hour; return h >= QUIET_START or h < QUIET_END
def fresh(c, now):
    first, last = c.get("first_ts", c["ts"]), c["ts"]
    if now - last > ACTIVE_H * 3600: return False
    if now - first < FRESH_H * 3600: return True
    # morning catch-up: first reported during last night's quiet hours, sent 8–10 AM
    return catchup(now) and quiet(first) and now - first < MORNING_H * 3600
def catchup(now): return QUIET_END <= local(now).hour < CATCHUP_END

# ---------- OneSignal ----------
def call(method, path, key, body=None, t=20):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Key {key}", "Content-Type": "application/json; charset=utf-8",
                                          "Accept": "application/json", "User-Agent": "WCN-Push/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=t) as r: return r.status, json.loads(r.read() or b"{}"), r.headers
    except urllib.error.HTTPError as ex:
        try: b = json.loads(ex.read() or b"{}")
        except Exception: b = {}
        return ex.code, b, ex.headers
def es_version(c):
    if c.get("live_es"): return c["live_es"]
    try: x = json.load(open(TR)).get(c["id"])
    except Exception: x = None
    if not x or not x.get("t") or not x.get("sl"): return None
    return {"t": x["t"], "url": f"es/noticias/{x['sl']}-{c['id']}.html"}
LABEL = {"en": "BREAKING", "es": "ÚLTIMA HORA"}
SOMBER = {"en": "WCN NEWS", "es": "WCN NOTICIAS"}
def payload(app_id, c, typ, lang="en", es=None, target=None):
    brand = next((k for k in c["categories"] if k in BIG3), c["categories"][0])
    head = (SOMBER if typ == "death" else LABEL)[lang] + f": {brand}"
    title = (es["t"] if lang == "es" else c["title"]).strip()
    url = SITE + (es["url"] if lang == "es" else c["url"])
    p = {"app_id": app_id, "target_channel": "push", "isAnyWeb": True,
         "headings": {"en": head}, "contents": {"en": title[:180]}, "url": url, "name": f"WCN {lang} {typ}: {c['title'][:90]}",
         "chrome_web_icon": SITE + "pwa/icon-192.png", "firefox_icon": SITE + "pwa/icon-192.png", "large_icon": SITE + "pwa/icon-192.png",
         "web_push_topic": ("wcn" + str(c["id"]))[:32], "ttl": 4 * 3600, "priority": 10,
         "idempotency_key": str(uuid.uuid5(uuid.NAMESPACE_URL, url))}
    if lang == "es": p["headings"]["es"], p["contents"]["es"] = head, title[:180]
    if target == "es": p["filters"] = [{"field": "language", "relation": "=", "value": "es"}]
    elif target == "not-es": p["filters"] = [{"field": "language", "relation": "!=", "value": "es"}]
    else: p["included_segments"] = [SEGMENT]
    img = c.get("image") or ""
    if img.startswith("https://"): p["chrome_web_image"] = img
    return p

def main():
    enabled = os.environ.get("PUSH_ENABLED", "").strip() == "1"
    app_id = os.environ.get("ONESIGNAL_APP_ID", "").strip(); key = os.environ.get("ONESIGNAL_REST_API_KEY", "").strip()
    s = load_state(); now = time.time()
    items = json.load(open(NEWS)).get("items", [])
    try: items = live_candidates(now) + items
    except Exception as ex: log(f"live candidates error (ignored): {ex}")
    pool = sorted([c for c in items if c.get("url") and fresh(c, now) and not c.get("resplit") and not c.get("fullcard")], key=score, reverse=True)   # re-clustered, not new
    recent = sorted(v["ts"] for v in s["pushed"].values() if v.get("sent") and now - v["ts"] < 86400)
    lt = local(now)
    gate = None
    if quiet(now): gate = f"quiet hours ({lt:%H:%M} Puerto Rico time; pushes 8 AM–11 PM)"
    elif len(recent) >= DAILY_CAP: gate = f"daily cap reached ({len(recent)}/{DAILY_CAP} in 24h)"
    elif recent and now - recent[-1] < MIN_GAP_H * 3600: gate = f"last push {int((now - recent[-1]) / 60)} min ago (needs {MIN_GAP_H * 60})"
    log(f"{len(pool)} fresh stories; {len(recent)}/{DAILY_CAP} pushes in 24h; {lt:%a %H:%M} PR time; mode={'LIVE' if enabled else 'DRY RUN'}" + (f"; holding: {gate}" if gate else ""))
    chosen = None; shown = 0
    for c in pool:
        typ, why = check(c)
        if typ:
            d = duplicate_of(c, typ, s, now)
            if d: verdict = f"skip: already pushed ({d[:60]})"
            elif gate: verdict = f"hold: {gate} — {why}"
            elif chosen: verdict = f"next: {why} (1 push per run)"
            else: verdict = f"PUSH: {why}"; chosen = (c, typ)
        else: verdict = f"skip: {why}"
        if shown < MAX_LOG: log(f"  [{score(c):>2}] {c['title'][:80]} -> {verdict}"); shown += 1
    if len(pool) > shown: log(f"  ... {len(pool) - shown} more fresh stories not listed")
    if not chosen: log("nothing to push this run"); return
    c, typ = chosen
    if not app_id or not key: log("OneSignal app id / key missing; skipping"); return
    es = es_version(c)
    sends = [("en", "not-es"), ("es", "es")] if es else [("en", None)]
    payloads = [(lang, payload(app_id, c, typ, lang, es, target)) for lang, target in sends]
    st, app, _ = call("GET", f"/apps/{app_id}", key)
    if st != 200: log(f"auth/app check failed: HTTP {st} {app.get('errors')}"); return
    subs = app.get("messageable_players", app.get("players", 0))
    if not enabled or not subs:
        log(f"DRY RUN ({'PUSH_ENABLED!=1' if not enabled else '0 subscribers'}); would send:")
        for lang, p in payloads: log(f"  {lang}:", json.dumps({k: v for k, v in p.items() if k != "app_id"}, ensure_ascii=False))
        return
    nids = {}
    for lang, p in payloads:
        st, r, h = call("POST", "/notifications?c=push", key, p)
        if st == 200 and r.get("id"): nids[lang] = r["id"]; log(f"sent {lang} {r['id']}")
        elif st == 200: log(f"{lang}: no reachable subscribers ({r.get('errors')})")
        elif st == 429: log(f"{lang}: rate limited; retry after {h.get('Retry-After')}s")
        else:
            log(f"{lang}: send failed HTTP {st}: {r.get('errors')}")
            if lang == "en" and p.get("filters"):     # language filter rejected: fall back to one English send to everyone
                st, r, _ = call("POST", "/notifications?c=push", key, payload(app_id, c, typ))
                if st == 200 and r.get("id"): nids["en"] = r["id"]; log(f"sent en (fallback, all subscribers) {r['id']}"); break
    if nids or st == 200:
        s["pushed"][str(c["id"])] = {"ts": now, "url": c["url"], "title": c["title"], "type": typ, "sent": bool(nids), "nids": nids,
                                     "links": sorted(links(c)), "persons": sorted(persons(c["title"])), "score": score(c)}
        s["log"].append({"ts": int(now), "id": str(c["id"]), "type": typ, "nids": nids}); save_state(s)
        log(f"{'pushed' if nids else 'recorded (undelivered)'} [{typ}] to ~{subs} subscribers: {c['title']}")

if __name__ == "__main__":
    try: main()
    except Exception as ex: log(f"error (ignored): {ex}")
    sys.exit(0)
