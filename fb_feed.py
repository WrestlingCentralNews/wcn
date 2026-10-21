"""Curated Facebook feed: /feed/facebook.xml, read by a Zapier Zap (RSS 'New Item in Feed' -> Facebook Pages 'Create Page Post').
Zapier's free plan = 100 tasks/month, so at most MAX_PER_DAY (3) new items per Puerto Rico day (~90/month).
Picks (owner rules): BREAKING first, then homepage Top stories (toppick.pick), then importance x freshness (toppick.value).
Never: filler/explainer/evergreen (editorial.evergreen), re-splits, stories already in the feed (same cluster, any shared
report, or a near-identical headline), live match-by-match results. A finished show's results page (events/<date>-<show>/)
can be one item. Items are frozen when picked (guid, title, link, description, image, pubDate never change), so Zapier
never reposts. State: data/fb_feed.json (saved to the 'data' branch with the rest of the state)."""
import os, re, json, time, datetime, urllib.parse
import pages, toppick, editorial
ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "data", "fb_feed.json")
LIVE_DIR = os.path.join(ROOT, "data", "live")
OUT = os.path.join(pages.PUB, "feed", "facebook.xml")
SITE = pages.SITE
PR = datetime.timezone(datetime.timedelta(hours=-4))   # America/Puerto_Rico (AST, no DST)
MAX_PER_DAY = 3
SLOTS = {1: 7, 2: 12, 3: 17}   # PR hour from which the 1st/2nd/3rd normal pick of the day may go out (BREAKING ignores slots)
KEEP = 20
MIN_GAP_H = 2                  # hours between normal picks (BREAKING ignores it)
FRESH_H = 12                   # candidate: first reported within the last 12h
MIN_IMP = 14                   # same bar as x_poster.MIN_SCORE
UTM = "utm_source=facebook&utm_medium=social"
RESULT_RX = re.compile(r"\b(retain\w*|beat\w*|def\.|defeat\w*|wins?|won|tops?|topped|outlast\w*|pins?|pinned|submit\w*|crowned|captures?|dethrones?)\b", re.I)
LIVE_RX = re.compile(r"\b(live|ongoing|results?|recap|review\w*|report|grades?|highlights|videos?|viewership|ratings?)\b", re.I)
STOP = set("the a an of to in on at for and with by from is are as his her their after over vs wwe aew tna nxt raw smackdown".split())
PROMO = {"WWE": "wwe", "NXT": "nxt", "AEW": "aew", "TNA": "tna", "AAA": "aaa", "ROH": "roh", "NJPW": "njpw", "CMLL": "cmll"}

def _i(v, d=0):
    try: return int(v)
    except Exception: return d
def log(*a): print("[fb]", *a, flush=True)
def load():
    try: return json.load(open(STATE))
    except Exception: return {"items": []}
def save(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    tmp = STATE + ".tmp"; json.dump(s, open(tmp, "w"), ensure_ascii=False, indent=0); os.replace(tmp, STATE)
def pr_day(ts): return datetime.datetime.fromtimestamp(ts, PR).strftime("%Y-%m-%d")
def _stem(w): return w[:-1] if len(w) > 4 and w.endswith("s") and not w.endswith("ss") else w
def words(t):
    t = re.sub(r"\bring\s+boys?\b", "ringboy", (t or "").lower())
    return {_stem(w) for w in re.findall(r"[a-z0-9']+", t) if w not in STOP and len(w) > 2}
NAME_STOP = {"wwe", "aew", "tna", "nxt", "raw", "smackdown", "the", "dynamite", "collision", "impact", "a", "an", "in", "on", "at", "after", "during", "per", "his", "her", "from", "live", "result", "results", "wrestling", "news", "report", "update", "show", "match", "title", "championship", "world",
             "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december",
             "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "night", "week"}
def names(c):
    """capitalized words (people, places, laws) in title + summary, not at a sentence start: what a story is about"""
    t = re.sub(r"\bRing\s?[Bb]oys?\b", "Ringboy", (c.get("title") or "") + ". " + (c.get("summary") or c.get("desc") or ""))
    out = set()
    for m in re.finditer(r"(?<![.!?]\s)(?<!^)\b([A-Z][a-zA-Z'’-]{2,})", t):
        w = _stem(m.group(1).lower().strip("'’"))
        if w not in NAME_STOP: out.add(w)
    return out
def similar(a, b):
    """same story told twice: near-identical headline, or 4+ shared names covering half of the smaller story (5+ covering a third)"""
    A, B = words(a.get("title")), words(b.get("title"))
    if A and B and len(A & B) / min(len(A), len(B)) >= 0.6: return True
    N, M = names(a), names(b)
    k = len(N & M); r = k / min(len(N), len(M)) if N and M else 0
    return (k >= 4 and r >= 0.5) or (k >= 5 and r >= 0.35)
def utm(url): return url + ("&" if "?" in url else "?") + UTM
def short(text, n=2, cap=300):
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text or "")).strip()
    out = " ".join(re.split(r"(?<=[.!?])\s+(?=[A-Z\"“])", t)[:n])
    if len(out) > cap: out = out[:cap].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return out
def members(c): return [c.get("link")] + [u.get("link") for u in c.get("updates", [])]

def live_result(c):
    """True for match-by-match / live-report results stories (the show's results page is the one results item)."""
    k = (c.get("kind") or {}).get("type")
    t = (c.get("title") or "") + " " + (c.get("raw_title") or "")
    if k == "results": return True
    if k == "match" and RESULT_RX.search(t): return True
    return bool((c.get("hub") or {}).get("k") == "show" and RESULT_RX.search(t))
def blocked(c, S, now):
    if c.get("resplit"): return "resplit"
    if editorial.evergreen(c.get("title")) or editorial.evergreen(c.get("raw_title")): return "evergreen"
    if live_result(c): return "live-result"
    if not (c.get("image") or "").startswith("https://"): return "no-image"
    if now - _i(c.get("first_ts"), _i(c.get("ts"))) > FRESH_H * 3600: return "old"
    have_ids = {x["id"] for x in S["items"]}; have_links = {l for x in S["items"] for l in x.get("members", [])}
    if c["id"] in have_ids or any(l and l in have_links for l in members(c)): return "dup"
    if any(similar(c, x) for x in S["items"][-KEEP:]): return "dup-title"
    return None

def show_results(now, S):
    """Finished shows (ended 30 min-18h ago, 3+ confirmed results) -> results-page candidates."""
    out = []
    if not os.path.isdir(LIVE_DIR): return out
    import hubs
    evs = {f"{e['date']}-{e['slug']}": e for e in hubs.EVENTS} if isinstance(hubs.EVENTS, list) else {}
    for f in sorted(os.listdir(LIVE_DIR)):
        if not f.endswith(".json"): continue
        try: st = json.load(open(os.path.join(LIVE_DIR, f)))
        except Exception: continue
        key = st.get("key") or f[:-5]; end = _i(st.get("end"))
        shown = [m for m in st.get("matches", []) if m.get("sources") and not m.get("conflict") and m.get("en")]
        if not end or not (end + 1800 <= now <= end + 18 * 3600) or len(shown) < 3: continue
        gid = "res-" + key
        if any(x["id"] == gid for x in S["items"]): continue
        ds, slug = key[:10], key[11:]
        path = hubs.ev_path(evs[key], "en") if key in evs else hubs.ep_path(slug, ds, "en")
        if not os.path.exists(os.path.join(pages.PUB, path, "index.html")): continue
        nm = st.get("name") or slug; d = datetime.date.fromisoformat(ds)
        brand = "NXT" if "nxt" in slug else (st.get("brand") or "WWE")
        img = SITE + f"img/promo/{PROMO.get(brand.upper(), 'wwe')}.jpg"
        main = sorted(shown, key=lambda m: -_i(m.get("order")))[0]["en"] if st.get("kind") != "weekly" else ""
        lead = " ".join(m["en"] for m in sorted(shown, key=lambda m: _i(m.get("order")))[:2])
        desc = short(f"All {len(shown)} confirmed results from {nm} on {d.strftime('%B')} {d.day}. " + (main or lead), 2)
        ple = st.get("kind") != "weekly"
        imp = (30 if ple else 16) + min(len(shown), 8)
        out.append({"id": gid, "title": f"{nm} Results ({d.strftime('%b')} {d.day}, {d.year})", "url": SITE + path, "summary": desc,
                    "image": img, "first_ts": end, "ts": end, "imp": imp, "members": [SITE + path], "results_page": True})
    return out

def item_from(c, now, why):
    url = c["url"] if c.get("results_page") else SITE + c["url"]
    return {"id": c["id"], "guid": f"wcn-fb-{c['id']}", "title": c["title"], "link": utm(url), "desc": short(c.get("summary")),
            "image": c["image"], "pub": int(now), "day": pr_day(now), "why": why,
            "members": c.get("members") or [l for l in members(c) if l], "cat": (c.get("categories") or [""])[0]}

def choose(clusters, S, now):
    """-> list of new feed items for this run (0..MAX_PER_DAY - today's)."""
    today = pr_day(now); hour = datetime.datetime.fromtimestamp(now, PR).hour
    n_today = sum(1 for x in S["items"] if x["day"] == today)
    if n_today >= MAX_PER_DAY: return []
    last_normal = max([x["pub"] for x in S["items"] if x.get("why") != "breaking"] or [0])
    gap_ok = now - last_normal >= MIN_GAP_H * 3600
    items = sorted(clusters, key=lambda c: -_i(c.get("first_ts"), _i(c.get("ts"))))
    lead, sec = toppick.pick(items, now)
    top = {c["id"] for c in ([lead] if lead else []) + sec}
    cands, why_not = [], {}
    for c in items:
        r = blocked(c, S, now)
        if r: why_not[r] = why_not.get(r, 0) + 1; continue
        brk = bool(c.get("brk")); imp = _i(c.get("imp"))
        if not brk and imp < MIN_IMP and c["id"] not in top: why_not["low"] = why_not.get("low", 0) + 1; continue
        cands.append((2 if brk else 1 if c["id"] in top else 0, toppick.value(c, now), c, "breaking" if brk else "top" if c["id"] in top else "score"))
    for c in show_results(now, S):
        cands.append((1, toppick.value(c, now), c, "results-page"))
    cands.sort(key=lambda x: (-x[0], -x[1]))
    out = []
    for tier, val, c, why in cands:
        if n_today + len(out) >= MAX_PER_DAY: break
        slot_ok = hour >= SLOTS[n_today + len(out) + 1]
        if why != "breaking" and not (slot_ok and gap_ok): continue
        if any(similar(c, o) for o in out): continue
        if any(l and l in {m for o in out for m in o["members"]} for l in (c.get("members") or members(c))): continue
        out.append(item_from(c, now, why))
        if why != "breaking": break    # at most one normal pick per run: the next one waits for its slot / a later run
    log(f"day {today} {hour}h: {n_today} already, picked {len(out)} of {len(cands)} candidates; skipped {why_not}")
    return out

def rss_item(x):
    xe, t = pages.xe, pages._imgtype(x["image"])
    return (f"<item><title>{xe(x['title'])}</title><link>{xe(x['link'])}</link><guid isPermaLink=\"false\">{xe(x['guid'])}</guid>"
            f"<pubDate>{pages.rfc822(x['pub'])}</pubDate>" + (f"<category>{xe(x['cat'])}</category>" if x.get("cat") else "")
            + f"<description>{xe(x['desc'])}</description>"
            f'<enclosure url="{xe(x["image"])}" length="0" type="{t}"/><media:content url="{xe(x["image"])}" medium="image" type="{t}"/></item>')
def write(S, now):
    its = sorted([x for x in S["items"] if not x.get("hidden")], key=lambda x: -x["pub"])[:KEEP]
    last = its[0]["pub"] if its else int(now)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/"><channel>'
           f"<title>Wrestling Central News: Facebook picks</title><link>{SITE}</link>"
           f"<description>Up to three of the day's biggest wrestling stories from Wrestling Central News.</description><language>en-us</language>"
           f'<atom:link href="{SITE}feed/facebook.xml" rel="self" type="application/rss+xml"/>'
           f"<lastBuildDate>{pages.rfc822(last)}</lastBuildDate><ttl>15</ttl>"
           f"<image><url>{SITE}logo.png</url><title>Wrestling Central News: Facebook picks</title><link>{SITE}</link></image>"
           + "".join(rss_item(x) for x in its) + "</channel></rss>\n")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"; open(tmp, "w").write(xml); os.replace(tmp, OUT)
    return len(its)
def build(clusters, now=None):
    now = now or time.time(); S = load(); S.setdefault("items", [])
    try:
        new = choose(clusters, S, now)
        for x in new: log("pick", x["why"], x["guid"], x["title"])
        S["items"] = sorted(S["items"] + new, key=lambda x: x["pub"])[-60:]   # keep 60 for dedup; feed shows KEEP
        if new: save(S)
    except Exception as ex: log("pick error (feed rebuilt from state)", repr(ex)[:200])
    live = {c["id"] for c in clusters}
    gone = [x for x in S["items"] if x["id"] not in live and not x.get("hidden")]
    if gone:   # a story that was unpublished (held / stale / merged away) leaves the Facebook feed; kept in state so it isn't re-picked
        for x in gone: x["hidden"] = 1
        save(S); log("hidden from feed (no longer published):", [x["guid"] for x in gone])
    n = write(S, now); log(f"facebook.xml: {n} items")
    return n
