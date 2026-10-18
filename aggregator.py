#!/usr/bin/env python3
"""Aggregates wrestling RSS feeds -> public/news.json. Run with --loop for 15-min refresh."""
import json, re, sys, time, html, hashlib, urllib.request, urllib.parse, os, email.utils
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public", "news.json")
LOG = os.path.join(os.path.dirname(OUT), "..", "feeds_status.json")
G = lambda q: "https://news.google.com/rss/search?q=" + urllib.parse.quote(q) + "&hl=en-US&gl=US&ceid=US:en"
FEEDS = {
 "Wrestling Inc": "https://www.wrestlinginc.com/feed/",
 "Fightful": "https://www.fightful.com/rss.xml",
 "Google News: PWInsider": G("site:pwinsider.com"),
 "Cageside Seats": "https://www.cagesideseats.com/rss/index.xml",
 "POST Wrestling": "https://www.postwrestling.com/feed/",
 "Wrestling Observer": "https://www.f4wonline.com/feed",
 "Ringside News": "https://www.ringsidenews.com/feed/",
 "Sportskeeda Wrestling": "https://www.sportskeeda.com/feed/wwe",
 "Google News: WWE": G("WWE wrestling"),
 "Google News: AEW": G("AEW wrestling"),
 "Google News: TNA": G("TNA wrestling"),
 "Google News: Indie": G("GCW OR PWG OR MLW OR \"Ring of Honor\" wrestling"),
 "Official: WWE.com": G("site:wwe.com when:7d"),
 "Official: AEW": G("site:allelitewrestling.com when:7d"),
 "Official: TNA": G("site:tnawrestling.com when:7d"),
 "Official: NJPW": G("site:njpw1972.com when:7d"),
 "PWInsider (via Google)": G("site:pwinsider.com when:7d"),
 "Google News: Global": G("NJPW OR Stardom OR CMLL OR \"Lucha Libre AAA\" OR wXw OR RevPro wrestling"),
}
KW = {
 "WWE": r"\bWWE\b|\bRaw\b|SmackDown|\bNXT\b|WrestleMania|Royal Rumble|SummerSlam|Survivor Series|Triple H|Roman Reigns|Cody Rhodes|CM Punk|Rhea Ripley|Seth Rollins|Saturday Night'?s Main Event",
 "AEW": r"\bAEW\b|All Elite|Dynamite|Collision|Rampage|Tony Khan|Double or Nothing|All In\b|Full Gear|Revolution|MJF|Kenny Omega|Jon Moxley|Swerve",
 "TNA": r"\bTNA\b|Impact Wrestling|Bound for Glory|Slammiversary|Joe Hendry|Nic Nemeth|Masha Slamovich|Hard to Kill",
 "Indie": r"\bGCW\b|Game Changer|\bPWG\b|\bROH\b|Ring of Honor|\bMLW\b|Major League Wrestling|\bNWA\b|Beyond Wrestling|\bCZW\b|Black Label Pro|West Coast Pro|\bJCW\b|indie|independent",
 "Global": r"NJPW|New Japan|Stardom|\bCMLL\b|\bAAA\b|Lucha Libre|\bNOAH\b|DDT|AJPW|All Japan|Dragongate|wXw|RevPro|Revolution Pro|\bPROGRESS\b|\bOTT\b|\bPWA\b|Australia|Mexico|Japan|\bIWGP\b|Wrestle Kingdom|G1 Climax|\bTJPW\b|Marigold|\bCMLL\b",
}
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) WrestleWire/1.0"}
def fetch(url, t=20):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=t).read()
def strip(s):
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or "")); return re.sub(r"\s+", " ", html.unescape(s)).strip()
def summarize(text, title):
    text = re.sub(r"The post .* appeared first on .*$", "", text).strip()
    if not text or text.lower().startswith(title.lower()[:30]) and len(text) < len(title) + 40: return ""
    sents = re.split(r"(?<=[.!?])\s+", text); out = ""
    for s in sents:
        if len(out) + len(s) > 300 or out.count(".") >= 3: break
        out += s + " "
    return (out.strip() or text[:280].rsplit(" ", 1)[0] + "…")
def image_of(it):
    for tag in ("{http://search.yahoo.com/mrss/}content", "{http://search.yahoo.com/mrss/}thumbnail", "enclosure"):
        for e in it.iter(tag):
            u = e.get("url")
            if u and (e.get("medium") in (None, "image") or re.search(r"\.(jpe?g|png|webp)", u, re.I)): return u
    m = re.search(r'<img[^>]+src="([^"]+)"', (it.findtext("description") or "") + (it.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or ""))
    return m.group(1) if m else None
def og_image(url):
    try:
        h = fetch(url, 8)[:300000].decode("utf8", "ignore")
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', h) or re.search(r'content=["\']([^"\']+)["\'][^>]+property=["\']og:image', h)
        return html.unescape(m.group(1)) if m else None
    except Exception: return None
import datetime as _dt
def parse_date(d):
    """Feed date -> epoch seconds, honouring timezone offsets (RFC 822 pubDate or ISO 8601/Atom). Naive times are UTC. None if unparseable."""
    d = (d or "").strip()
    if not d: return None
    try:
        x = email.utils.parsedate_to_datetime(d)
        if x is not None:
            if x.tzinfo is None: x = x.replace(tzinfo=_dt.timezone.utc)
            return x.timestamp()
    except Exception: pass
    try:
        x = _dt.datetime.fromisoformat(re.sub(r"Z$", "+00:00", d.replace(" ", "T", 1)))
        if x.tzinfo is None: x = x.replace(tzinfo=_dt.timezone.utc)
        return x.timestamp()
    except Exception: pass
    m = re.match(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)(?:\.\d+)?\s*(Z|[+-]\d{2}:?\d{2})?", d)
    if m:
        tz = (m.group(3) or "+00:00").replace("Z", "+00:00")
        if len(tz) == 5: tz = tz[:3] + ":" + tz[3:]
        try: return _dt.datetime.fromisoformat(f"{m.group(1)}T{m.group(2)}{tz}").timestamp()
        except Exception: pass
    return None
def classify(t):
    return [k for k, r in KW.items() if re.search(r, t, re.I)]
def parse(name, url):
    items = []
    root = ET.fromstring(fetch(url))
    nodes = root.iter("item") if root.find(".//item") is not None else root.iter("{http://www.w3.org/2005/Atom}entry")
    for it in nodes:
        A = "{http://www.w3.org/2005/Atom}"
        title = strip(it.findtext("title") or it.findtext(A+"title"))
        link = it.findtext("link") or (it.find(A+"link").get("href") if it.find(A+"link") is not None else "")
        desc = strip(it.findtext("description") or it.findtext(A+"summary") or it.findtext(A+"content") or "")
        date = it.findtext("pubDate") or it.findtext(A+"updated") or it.findtext(A+"published")
        ts = parse_date(date)   # None if missing/unparseable -> first-seen time is used in run()
        src = name
        if name.startswith("Google News"):
            s = it.find("source"); src = s.text if s is not None else name
            title = re.sub(r"\s+-\s+[^-]+$", "", title); desc = ""
        cats = classify(title + " " + desc)
        if name.endswith(": WWE"): cats = cats or ["WWE"]
        if name.endswith(": AEW"): cats = cats or ["AEW"]
        if name.endswith(": TNA"): cats = cats or ["TNA"]
        if name.endswith(": Indie"): cats = cats or ["Indie"]
        if name.endswith(": Global"): cats = cats or ["Global"]
        if not cats: cats = ["Indie"] if re.search(r"wrestl", title + desc, re.I) else []
        if not cats or not title: continue
        items.append({"id": hashlib.md5(re.sub(r"\W", "", title.lower()).encode()).hexdigest()[:12],
            "title": title, "summary": summarize(desc, title), "link": link.strip(), "source": src,
            "ts": int(ts) if ts else None, "image": image_of(it), "categories": cats})
    return items
SIG = re.compile(r"wrestl|lucha|luchador|superstar|\bPLE\b|pay-per-view|\bheel\b|babyface|tag team|ring name|\bpromo\b|W\.W\.E|Backlash|Hall of Fame", re.I)
def on_topic(a):
    """Drop off-topic items (cricket, MLB, game codes, celebrity gossip) that leak in via broad feeds."""
    if a["source"] in FEEDS and not a["source"].startswith(("Google", "Sportskeeda")): return True  # dedicated wrestling outlets
    t = a["raw_title"]; b = (a.get("body") or "") + " " + (a.get("summary_src") or "")
    if classify(re.sub(r"\b(Mexico|Japan|Australia)\b", "", t)) or SIG.search(t): return True
    return len(re.findall(r"wrestl|\bWWE\b|\bAEW\b|\bTNA\b|\bNJPW\b|\bCMLL\b|\bring\b", b, re.I)) >= 3
import enrich, editorial, llm, pages, vision
STORE = os.path.join(os.path.dirname(OUT), "..", "data", "articles.json")
IMG_CHECK_TOP = 60
LONG_MAX_PER_RUN = 400
LLM_MAX_PER_RUN = 700  # steady state is ~5-30 per run; high cap allows one-time backfill
RETENTION_DAYS = 60  # prune stories older than this each run
DROPPED_CL = set()
OVERRIDES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "image_overrides.json")
def image_overrides(clusters):
    """Hand-picked card photos (repo file image_overrides.json, survives every run): {"items": [{"links": [...], "image": url|null}]}.
    Applied when the card's lead article is one of `links` (so it can't leak onto a different story that later absorbs it).
    image null = WCN default card. Also "block": image URLs never to show on any card."""
    try: ov = json.load(open(OVERRIDES))
    except Exception: return 0
    n = 0; block = set(ov.get("block", []))
    for c in clusters:
        for o in ov.get("items", []):
            if c["link"] in o.get("links", []) or c["id"] in o.get("ids", []):
                c["image"] = o.get("image"); c["image_credit"] = o.get("credit"); c["image_status"] = "override"; n += 1; break
        else:
            if c.get("image") in block: c["image"] = None; c["image_credit"] = None; c["image_status"] = "wcn-card"; n += 1
    return n
def run():
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    old = {i["id"]: i for i in json.load(open(STORE))} if os.path.exists(STORE) else {}
    status, fresh = {}, []
    def job(kv):
        try: r = parse(*kv); return kv[0], r, None
        except Exception as e: return kv[0], [], str(e)[:120]
    with ThreadPoolExecutor(8) as ex:
        for n, r, err in ex.map(job, FEEDS.items()):
            status[n] = {"ok": err is None and len(r) > 0, "items": len(r), "error": err}; fresh += r
    cutoff = time.time() - RETENTION_DAYS*86400
    # items whose feed date was missing/unparseable get the time we FIRST saw them (remembered across runs), never "now" on every run
    fs_path = os.path.join(os.path.dirname(STORE), "first_seen.json")
    try: first_seen = json.load(open(fs_path))
    except Exception: first_seen = {}
    now_i = int(time.time())
    for i in fresh:
        if i["ts"] is None:
            i["ts"] = old[i["id"]]["ts"] if i["id"] in old else first_seen.setdefault(i["id"], now_i); i["ts_guessed"] = True
    first_seen = {k: v for k, v in first_seen.items() if v > cutoff}
    json.dump(first_seen, open(fs_path, "w"))
    new = {}
    for i in fresh:
        if i["id"] not in old and i["ts"] > cutoff: new.setdefault(i["id"], i)
    new = list(new.values())
    for i in new:
        i["raw_title"] = i["title"]; i["summary_src"] = i.pop("summary"); i["added"] = int(time.time())
    with ThreadPoolExecutor(12) as ex: list(ex.map(enrich.fetch_article, new))
    for i in new:
        i["title"] = enrich.headline(i["raw_title"]); i["summary"] = enrich.summarize(i); i["body"] = (i.get("body") or "")[:3000]
    for a in old.values():
        if a.get("v") != enrich.VERSION: a["title"] = enrich.headline(a["raw_title"]); a["summary"] = enrich.summarize(a); a["v"] = enrich.VERSION
    for i in new: i["v"] = enrich.VERSION
    arts = [a for a in list(old.values()) + new if a["ts"] > cutoff]
    for a in arts:
        if a.get("ev") != editorial.VERSION:
            a["categories"] = editorial.categories(a); a["kind"] = editorial.kind(a)
            r = None if on_topic(a) else "off-topic"
            r = r or editorial.verdict(a)
            if r and a.get("drop") != r: editorial.log_drop(a, r)
            a["drop"] = r; a["title"] = enrich.headline(a["raw_title"], a["kind"]["type"]); a["summary"] = enrich.summarize(a)
            a["ev"] = editorial.VERSION
    # LLM rewrite pass: only articles without a cached rewrite, trusted/mid-tier, not rule-dropped; newest first
    todo = sorted([a for a in arts if not a.get("drop") and "llm" not in a and editorial.tier(a["source"]) < 3], key=lambda x: -x["ts"])[:LLM_MAX_PER_RUN]
    if todo and llm.budget_left() > 0:
        with ThreadPoolExecutor(6) as ex:
            for a, out in zip(todo, ex.map(llm.rewrite, todo)):
                if out: a["llm"] = out
        llm.save_usage()
        print(f"llm: rewrote {sum(1 for a in todo if 'llm' in a)}/{len(todo)}, month spend ${llm._U['usd']:.3f}", flush=True)
    for a in arts:
        L = a.get("llm")
        if not L or a.get("drop") and not str(a["drop"]).startswith("llm:"): continue
        a["title"], a["summary"] = L["headline"].strip(), L["summary"].strip()
        if L["categories"]: a["categories"] = L["categories"]
        t = L["type"]
        a["kind"] = {"type": "quote", "who": L.get("speaker") or "", "quote": L.get("quote")} if t == "quote" and L.get("speaker") else {"type": t if t in ("results", "match") else "news"}
        if t in ("opinion", "rumor", "listicle", "off-topic"):
            if a.get("drop") != "llm:" + t: editorial.log_drop(a, "llm:" + t)
            a["drop"] = "llm:" + t
    json.dump(arts, open(STORE, "w"))
    enrich.TIER = editorial.tier
    clusters = []
    for c in enrich.cluster([a for a in arts if not a.get("drop")]):
        srcs = {c["source"]} | {u["source"] for u in c["updates"]}
        tiers = [editorial.tier(s) for s in srcs]
        if min(tiers) == 3:
            if c["id"] not in DROPPED_CL: editorial.log_drop({"raw_title": c["raw_title"], "source": c["source"], "link": c["link"]}, "uncorroborated low-trust source")
            DROPPED_CL.add(c["id"]); continue
        c["sources"] = len({re.sub(r"\.com$|\.$", "", s.lower()) for s in srcs}); c["trusted"] = sum(1 for t in tiers if t == 1)
        clusters.append(c)
    json.dump({"articles": len(arts), "dropped_articles": sum(1 for a in arts if a.get("drop")), "dropped_clusters": len(DROPPED_CL), "clusters": len(clusters)}, open(os.path.join(os.path.dirname(STORE), "stats.json"), "w"))
    clusters = clusters[:3000]
    # long-form write-ups for cards (cached on the card's lead article), then static pages + sitemap
    bylink = {x["link"]: x for x in arts}
    # reuse a long-form already written for another article of the same story (the lead article can change as reports arrive)
    for c in clusters:
        m = bylink.get(c["link"])
        if m and "llm_long" not in m:
            prev = next((bylink[u["link"]]["llm_long"] for u in c.get("updates", []) if u["link"] in bylink and bylink[u["link"]].get("llm_long")), None)
            if prev: m["llm_long"] = prev
    need = [(c, bylink.get(c["link"])) for c in clusters if bylink.get(c["link"]) and "llm_long" not in bylink[c["link"]]]
    need = [(c, m) for c, m in need if m.get("llm")][:LONG_MAX_PER_RUN]
    if need and llm.budget_left() > llm.LONGFORM_RESERVE_USD and llm.pace_ok():
        with ThreadPoolExecutor(6) as ex:
            for (c, m), p in zip(need, ex.map(lambda cm: llm.longform(cm[1], cm[0]["title"]), need)):
                if p: m["llm_long"] = p
        llm.save_usage(); json.dump(arts, open(STORE, "w"))
        print(f"llm longform: {sum(1 for c, m in need if 'llm_long' in m)}/{len(need)}, month spend ${llm._U['usd']:.3f}", flush=True)
    for c in clusters:
        m = bylink.get(c["link"]); c["long"] = (m or {}).get("llm_long")
    # image relevance (vision-verified) for top cards and every new card; results cached per card+names
    stats_img = {}
    def _pick(c):
        # only photos of members that are about the same people as the lead (enrich.cluster), never an off-topic neighbour's
        r = rank[c["id"]]
        return c, vision.choose(c, [m for m in c.get("member_images", []) if m], rank=r, fetch=r < IMG_CHECK_TOP or c["ts"] > time.time() - 3*86400)
    # every card gets the key-person rule (labels/file names are free); article pages are fetched for top + recent cards,
    # vision confirms only for the top vision.VISION_TOP cards when candidates are ambiguous
    rank = {c["id"]: i for i, c in enumerate(clusters)}
    todo = clusters
    with ThreadPoolExecutor(8) as ex:
        for c, (img, cr, st) in ex.map(_pick, todo):
            c["image"] = img; c["image_credit"] = cr; c["image_status"] = st; stats_img[st] = stats_img.get(st, 0) + 1
    for c in clusters: c.pop("member_images", None)
    n_ov = image_overrides(clusters)
    if n_ov: print("images: manual overrides applied to", n_ov, flush=True)
    bf = vision.backfill_finish()
    if bf: print("images: one-time backlog vision pass done:", bf, flush=True)
    vision.save(); llm.save_usage()
    print("images:", stats_img, f"month spend ${llm._U['usd']:.3f}", flush=True)
    try:   # live results for shows on air / just finished (no-op outside show windows; no AI spend)
        import live; ch = live.update(arts)
        if ch: print("live: updated", ch, flush=True)
    except Exception as ex: print("live: error (ignored)", repr(ex)[:200], flush=True)
    # previous run's stories: redirect stubs for URLs that change, and 'resplit' flags. A story whose id is new but whose every
    # report was already on the site (a split/re-cluster, not news) must never trigger an X post or push alert; the flag is sticky.
    try: prev = json.load(open(OUT)).get("items", [])
    except Exception: prev = []
    if prev:
        pl = {l for p in prev for l in pages._members(p)}; pid = {p["id"]: p for p in prev}
        for c in clusters:
            p = pid.get(c["id"])
            if (p and p.get("resplit")) or (not p and all(l in pl for l in pages._members(c))): c["resplit"] = True
    pages.PREV = prev
    pages.assign_urls(clusters); pages.build(clusters); llm.save_usage()
    try:
        import hubs, live
        lv = [{"key": k, "name": (live.load(k) or {}).get("name", k), "en": v.get("en"), "es": v.get("es")} for k, v in hubs.LIVE_PAGES.items()]
        json.dump({"updated": int(time.time()), "live": lv}, open(os.path.join(os.path.dirname(OUT), "live.json"), "w"), ensure_ascii=False)
    except Exception as ex: print("live.json: error (ignored)", repr(ex)[:200], flush=True)   # build() runs the Spanish translations: record their spend
    for c in clusters: c.pop("long", None)
    tmp = OUT + ".tmp"
    json.dump({"updated": int(time.time()), "count": len(clusters), "articles": len(arts), "items": clusters}, open(tmp, "w"))
    os.replace(tmp, OUT)
    json.dump(status, open(LOG, "w"), indent=1)
    print(time.strftime("%F %T"), f"new={len(new)} articles={len(arts)} clusters={len(clusters)}", flush=True)
    return status
if __name__ == "__main__":
    if "--loop" in sys.argv:
        while True:
            try: run()
            except Exception as e: print("error", e, flush=True)
            # Wall-clock wait in short steps so a box pause/restore can't freeze the refresh.
            nxt = time.time() + 900
            while time.time() < nxt: time.sleep(30)
    else: print(json.dumps(run(), indent=1))
