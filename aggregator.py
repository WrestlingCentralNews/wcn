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
 # official promotion feeds read directly (minutes faster than Google News' index); source name = the promotion (tier 1)
 "AEW": "https://www.allelitewrestling.com/blog-feed.xml",
 "MLW": "https://mlw.com/feed/",
 "Google News: AAA": G("\"Lucha Libre AAA\" OR \"AAA Worldwide\" when:7d"),   # AAA's own site is now only a store, no news feed
}
# promotions' own feeds: every item is about that promotion even when the title doesn't say so (e.g. AEW blog posts)
FEED_CAT = {"AEW": "AEW", "MLW": "Indie", "Google News: AAA": "Global"}
# + pagesrc.LISTINGS: PWInsider, WWE.com, TNA Wrestling, STARDOM, Bleacher Report (news listing pages, no RSS)
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
        date = it.findtext("pubDate") or it.findtext(A+"published") or it.findtext(A+"updated")   # published before updated (freshness)
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
        if name in FEED_CAT: cats = cats or [FEED_CAT[name]]
        if not cats: cats = ["Indie"] if re.search(r"wrestl", title + desc, re.I) else []
        if not cats or not title: continue
        items.append({"id": hashlib.md5(re.sub(r"\W", "", title.lower()).encode()).hexdigest()[:12],
            "title": title, "summary": summarize(desc, title), "link": link.strip(), "source": src,
            "ts": int(ts) if ts else None, "image": image_of(it), "categories": cats, "via": name})
    return items
SIG = re.compile(r"wrestl|lucha|luchador|superstar|\bPLE\b|pay-per-view|\bheel\b|babyface|tag team|ring name|\bpromo\b|W\.W\.E|Backlash|Hall of Fame", re.I)
def on_topic(a):
    """Drop off-topic items (cricket, MLB, game codes, celebrity gossip) that leak in via broad feeds."""
    if a["source"] in FEEDS and not a["source"].startswith(("Google", "Sportskeeda")): return True  # dedicated wrestling outlets
    t = a["raw_title"]; b = (a.get("body") or "") + " " + (a.get("summary_src") or "")
    if classify(re.sub(r"\b(Mexico|Japan|Australia)\b", "", t)) or SIG.search(t): return True
    return len(re.findall(r"wrestl|\bWWE\b|\bAEW\b|\bTNA\b|\bNJPW\b|\bCMLL\b|\bring\b", b, re.I)) >= 3
import enrich, editorial, llm, pages, vision, product, breaking, stale, toppick, freshness, pubgate, combat, aliases, framing, indie_gate
STORE = os.path.join(os.path.dirname(OUT), "..", "data", "articles.json")
IMG_CHECK_TOP = 60
LONG_MAX_PER_RUN = 400
LLM_MAX_PER_RUN = 700  # steady state is ~5-30 per run; high cap allows one-time backfill
RETENTION_DAYS = 60  # prune stories older than this each run
DROPPED_CL = set()
MERCH = re.compile(r"(?i)^https?://(?:[\w-]+\.)?(?:shop|euroshop\d*)\.wwe\.com/")   # WWE Shop product pages: merchandise, never news
NOT_NEWS = re.compile(r"(?i)[-|–—]\s*WWE Shop\s*$|\bswimsuit\b|\bbikini\b|\bAI predicts\b")   # shop pages via Google News, photo gossip, AI-guess filler
# raw non-English titles / YouTube highlight clips (owner 2026-10-23: 'Cody Rhodes le propina PUNT a Baron Corbin ...: SmackDown highlights,
# 16 de Oct. 2026' reached the English feed): Spanish-language titles and WWE.com / YouTube highlight clips are not news reports
ES_DATE = re.compile(r"(?i)\b\d{1,2} de (?:ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)[a-z]*\.?(?: de)? \d{4}\b")
ES_WORDS = re.compile(r"(?i)\b(?:el|las|los|del|le|les|frente|una|después|cuando|para|que|sus|contra|aquí|así|qué|cómo|tras|sobre|hacia|desde|pero|muy)\b")
CLIP_LINK = re.compile(r"(?i)^https?://(?:www\.|m\.)?(?:youtube\.com/|youtu\.be/)")   # WWE.com English clips stay (official confirmation)
def foreign_or_clip(a):
    t = a.get("raw_title") or a.get("title") or ""
    if ES_DATE.search(t) or re.search(r"(?i)\bresumen completo\b", t) or len({w.lower() for w in ES_WORDS.findall(t)}) >= 3: return "spanish"
    if CLIP_LINK.search(a.get("link") or "") and re.search(r"(?i)\bhighlights?\b|\bresumen\b|\bmejores momentos\b", t): return "clip"
    return None
def not_news(a):
    """Never a story on its own, never part of one (they used to hide inside wrongly merged stories)."""
    return bool(MERCH.search(a.get("link") or "") or NOT_NEWS.search(a.get("raw_title") or "") or combat.nonwrestling(a) or foreign_or_clip(a))
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
def claim_guard(a):
    """AI rewrite may not ADD a debut / return / title change / release the source doesn't state ('appears' -> 'debuts')."""
    # never let the rewrite ADD a debut / return / title change / release the source doesn't state ('appears' -> 'debuts'):
    # headline: breaking.py's source check; summary: debut / new-champion wording only ('released a video' is too ambiguous)
    src_all = (a.get("raw_title") or "") + "\n" + (a.get("summary_src") or "") + "\n" + (a.get("body") or "")
    hk = breaking._headline_kind(a["title"])
    if hk and not breaking.source_supports(hk, src_all):
        print(f"llm guard: '{a['title']}' claims {hk}, source doesn't -> rule-based headline", flush=True)
        a["title"] = enrich.headline(a["raw_title"], (a.get("kind") or {}).get("type")); a["ai_claim_fixed"] = hk
    for rx, ev in ((r"\b(?:makes?|made|making|marks?|marked) (?:[\w'’-]+\s+){0,3}debut\b|\bdebut(?:s|ed)\b|\bin-ring debut\b",
                    r"\bdebut\w*|\bfirst(?:-ever)?\s+(?:\w+\s+)?appearance\b|\bis all elite\b"),
                   (r"\bnew (?:[\w'’-]+\s+){0,3}champions?\b|\bcrowned\b|\bdethron\w*",
                    r"\bnew (?:\S+\s+){0,4}champions?\b|\bcrowned\b|\bdethron\w*|\bwins?\b|\bwon\b|\bcaptur\w*|\bregain\w*")):
        if re.search(rx, a["summary"], re.I) and not re.search(ev, src_all, re.I):
            print(f"llm guard: summary of '{a['raw_title'][:60]}' adds a claim the source lacks -> rule-based summary", flush=True)
            a["summary"] = enrich.summarize(a); a["ai_claim_fixed"] = a.get("ai_claim_fixed") or "summary"; break
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
    try:   # listing-page sources (no RSS): only links that are new since the last run come back
        import pagesrc
        for i in pagesrc.fetch_all(status):
            cats = classify(i["title"] + " " + i["summary"]) or ([i["cat"]] if i.pop("cat") else [])
            if not cats: continue
            fresh.append({**i, "via": "pagesrc", "id": hashlib.md5(re.sub(r"\W", "", i["title"].lower()).encode()).hexdigest()[:12],
                          "summary": summarize(strip(i["summary"]), i["title"]), "title": strip(i["title"]), "categories": cats})
    except Exception as e: print("pagesrc: error (ignored)", repr(e)[:200], flush=True)
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
    for i in new: i["v"] = enrich.VERSION; i["fresh_v"] = 1      # freshness gate: 48h limit applies to reports first seen from now on
    # freshness backfill: stored reports whose feed date isn't trustworthy (official sites via Google News / listing pages,
    # first-seen guesses) get the page's own publish date once (capped per run)
    bf = [a for a in old.values() if "pubchk" not in a and a["ts"] > time.time() - 8*86400 and freshness.weak_feed_date(a)][:400]
    if bf:
        def _pc(a):
            try: h = enrich._get(a["link"], 10).read()[:900000].decode("utf8", "ignore")
            except Exception: h = ""
            a["pubchk"] = 1; p = freshness.page_published(h)
            if p: a["pub_ts"] = p
        with ThreadPoolExecutor(8) as ex: list(ex.map(_pc, bf))
        print(f"freshness: page dates checked for {len(bf)} stored reports, {sum(1 for a in bf if a.get('pub_ts'))} found", flush=True)
    arts = [a for a in list(old.values()) + new if a["ts"] > cutoff]
    for a in arts:
        if a.get("ev") != editorial.VERSION:
            a["categories"] = editorial.categories(a); a["kind"] = editorial.kind(a)
            r = None if on_topic(a) else "off-topic"
            r = r or editorial.verdict(a)
            if r and a.get("drop") != r: editorial.log_drop(a, r)
            a["drop"] = r; a["title"] = enrich.headline(a["raw_title"], a["kind"]["type"]); a["summary"] = enrich.summarize(a)
            a["ev"] = editorial.VERSION
    for a in arts:   # freshness gate: a report that was already old when we first saw it is never news (real publish date, not 'updated')
        r = None if a.get("drop") else freshness.stale_reason(a)
        if r: editorial.log_drop(a, r); a["drop"] = r; print("old report:", a["raw_title"][:70], "->", r, flush=True)
    for a in arts:   # UFC / MMA / boxing / Bellator / PFL / ONE: not wrestling, never on WCN (owner rule 2026-10-21; checked every run)
        r = None if a.get("drop") else combat.nonwrestling(a)
        if r: editorial.log_drop(a, r); a["drop"] = r; print("off-topic:", a["raw_title"][:70], "->", r, flush=True)
    for a in arts:   # '(LIVESTREAMs)! WWE SmackDown 𝐋𝐈𝐕𝐄 Ｆｒｅｅ 𝐒𝐭𝐑𝐞𝐀𝐦' pages on hijacked sites (2026-10-24): never a source, photo or timeline line
        r = None if a.get("drop") else (editorial.stream_spam(a) or editorial.stream_notice(a) or editorial.video_notice(a) or editorial.filler_notice(a))   # + 'This Week's Edition Of X Is Now Streaming' notices
        if r: editorial.log_drop(a, r); a["drop"] = r; print("spam:", a["raw_title"][:70], "->", r, flush=True)
    for a in arts:   # look-backs / re-published history columns ('10 YEARS AGO - WWE LIVE EVENT REPORT', WON Flashback): fresh date, old news
        r = None if a.get("drop") else editorial.retro(a)
        if r: editorial.log_drop(a, r); a["drop"] = r; print("retro:", a["raw_title"][:70], "->", r, flush=True)
    for a in arts:   # an OLD article a feed re-dated (Google News re-indexing wwe.com/.../2017/...): never published, never on an event page
        r = None if a.get("drop") else stale.reason(a)
        if r: editorial.log_drop(a, r); a["drop"] = r; print("stale:", a["raw_title"][:70], "->", r, flush=True)
    # LLM rewrite pass: only articles without a cached rewrite, trusted/mid-tier, not rule-dropped; newest first
    todo = sorted([a for a in arts if not a.get("drop") and "llm" not in a and editorial.tier(a["source"]) < 3], key=lambda x: -x["ts"])
    _ig = [a for a in todo if indie_gate.skip_rewrite(a)]   # Indie-only + not important: rule-based text, no AI (owner budget rule 2026-10-24)
    if _ig: print(f"indie gate: {len(_ig)} Indie-only reports skip the AI rewrite", flush=True)
    _igs = {id(a) for a in _ig}; todo = [a for a in todo if id(a) not in _igs][:LLM_MAX_PER_RUN]
    if todo and llm.budget_left() > 0:
        with ThreadPoolExecutor(6) as ex:
            for a, out in zip(todo, ex.map(llm.rewrite, todo)):
                if out: a["llm"] = out
        llm.save_usage()
        print(f"llm: rewrote {sum(1 for a in todo if 'llm' in a)}/{len(todo)}, month spend ${llm._U['usd']:.3f}", flush=True)
    try: TEXT_OV = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "text_overrides.json"))).get("items", {})
    except Exception: TEXT_OV = {}
    for a in arts:
        if a["id"] in TEXT_OV and not a.get("llm"):
            o = TEXT_OV[a["id"]]; a["title"] = o.get("headline") or a["title"]; a["summary"] = o.get("summary") or a["summary"]; a["pinned"] = True
            if o.get("categories"): a["categories"] = list(o["categories"])
        L = a.get("llm")
        if not L or a.get("drop") and not str(a["drop"]).startswith("llm:"): continue
        a["title"], a["summary"] = L["headline"].strip(), L["summary"].strip()
        src_txt = (a.get("raw_title") or "") + " " + (a.get("body") or "")
        for y in set(re.findall(r"\b(?:19|20)\d\d\b", a["title"])):   # rewrite added a year the source never says ('Bound For Glory 2024 Results' for 2026): drop it
            if y not in src_txt and y != time.strftime("%Y", time.gmtime(int(a.get("ts") or time.time()))): a["title"] = re.sub(r"\s*\b" + y + r"\b", "", a["title"]).strip(" ,:-")
        claim_guard(a)
        fm = aliases.family_mixup(a["title"], a.get("raw_title"), (a.get("summary_src") or "") + " " + (a.get("body") or ""))
        if fm:   # rewrite named the famous parent (Sting) for the child the source names (Steve Borden): use the source's headline
            print(f"llm guard: '{a['title']}' names {fm}, source names the child -> rule-based headline", flush=True)
            a["title"] = enrich.headline(a["raw_title"], (a.get("kind") or {}).get("type")); a["ai_claim_fixed"] = "family:" + fm
            if aliases._has_parent(fm, a["summary"]) and not aliases._has_parent(fm, a.get("summary_src") or ""): a["summary"] = enrich.summarize(a)
        fsrc = (a.get("raw_title") or "") + " " + (a.get("summary_src") or "") + " " + (a.get("body") or "")
        if framing.choice_inverted(a["title"], fsrc):   # 'Penta Chose AEW Over WWE' when the source says he signed with WWE
            print(f"llm guard: '{a['title']}' inverts the choice the source reports -> rule-based headline", flush=True)
            a["title"] = enrich.headline(a["raw_title"], (a.get("kind") or {}).get("type")); a["ai_claim_fixed"] = "choice"
        pf = framing.past_framing(a["title"], a.get("raw_title"), fsrc, lambda s: bool(enrich.subjects(s)))
        if pf:   # an interview recollection told as if it just happened -> past framing ('X Recalls Pitching ...')
            print(f"llm guard: '{a['title']}' presents a recollection as new -> '{pf}'", flush=True); a["title"] = pf
        if a["id"] in TEXT_OV:   # pinned hand correction (text_overrides.json) beats the cached AI rewrite on every build
            o = TEXT_OV[a["id"]]; a["title"] = o.get("headline") or a["title"]; a["summary"] = o.get("summary") or a["summary"]; a["pinned"] = True
        if L["categories"]: a["categories"] = L["categories"]
        if (TEXT_OV.get(a["id"]) or {}).get("categories"): a["categories"] = list(TEXT_OV[a["id"]]["categories"])   # hand-set tags, primary first
        t = L["type"]
        a["kind"] = {"type": "quote", "who": L.get("speaker") or "", "quote": L.get("quote")} if t == "quote" and L.get("speaker") else {"type": t if t in ("results", "match") else "news"}
        if t != "evergreen" and editorial.evergreen(L["headline"]): t = "evergreen"   # rewrite headline reads as an explainer ('X explained')
        if t in ("opinion", "rumor", "listicle", "evergreen", "off-topic"):
            if a.get("drop") != "llm:" + t: editorial.log_drop(a, "llm:" + t)
            a["drop"] = "llm:" + t
    json.dump(arts, open(STORE, "w"))
    enrich.TIER = editorial.tier
    clusters = []; _BYLINK = {x["link"]: x for x in arts}
    freshness.OWN_FEEDS = {n for n, u in FEEDS.items() if "news.google." not in u and not n.startswith(("Google", "Official:"))}
    freshness.load_url_seen(os.path.join(os.path.dirname(STORE), "url_first_seen.json"), arts)
    for c in enrich.cluster([a for a in arts if not a.get("drop") and not not_news(a)]):
        if c.get("unnamed"):   # only nameless teasers ('WWE Star Signs New Deal'): no report says who -> not a story
            if c["id"] not in DROPPED_CL: editorial.log_drop({"raw_title": c["raw_title"], "source": c["source"], "link": c["link"]}, "vague: no report names the wrestler")
            DROPPED_CL.add(c["id"]); continue
        c.pop("unnamed", None)
        if not freshness.corroborated(c, _BYLINK):
            if c["id"] not in DROPPED_CL: editorial.log_drop({"raw_title": c["raw_title"], "source": c["source"], "link": c["link"]}, "undated: no real publish date and no trusted outlet reports it within 48h")
            DROPPED_CL.add(c["id"]); continue
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
    # a long-form about someone else (copied in from a wrongly merged story, e.g. Santino Marella's TNA re-signing on Dragon Lee's
    # WWE report): drop it so the lead gets its own write-up
    # (only copies: a write-up shared by several reports, or marked as copied; a report's own write-up is never thrown away)
    _lc = {}
    for x in arts:
        if x.get("llm_long"): _lc[json.dumps(x["llm_long"])] = _lc.get(json.dumps(x["llm_long"]), 0) + 1
    for x in arts:
        if x.get("llm_long") and (x.get("llm_long_from") or _lc[json.dumps(x["llm_long"])] > 1) and enrich.long_mismatch(x, x["llm_long"]):
            print("longform: off-subject write-up dropped from", x["id"], x["raw_title"][:60], flush=True)
            x.pop("llm_long", None); x.pop("llm_long_from", None)
    # reuse a long-form already written for another article of the same story (the lead article can change as reports arrive),
    # only from a report about the same wrestler(s)/promotion as the lead
    for c in clusters:
        m = bylink.get(c["link"])
        if m and "llm_long" not in m:
            d = next((bylink[u["link"]] for u in c.get("updates", []) if u["link"] in bylink and bylink[u["link"]].get("llm_long")
                      and enrich.same_story(bylink[u["link"]], m) and not enrich.long_mismatch(m, bylink[u["link"]]["llm_long"])), None)
            if d: m["llm_long"] = d["llm_long"]; m["llm_long_from"] = d["id"]
    indie_gate.remember(clusters, bylink)
    # write-ups (owner 2026-10-25, AI cap $20): every story under longer.TARGET_WORDS words gets one write-up from all its trusted
    # reports, new stories first, then the live back-catalogue; paced per call (llm.pace_ok(prio): Indie/Global cut first)
    import longer
    _lr = longer.run(clusters, bylink)
    if _lr["done"]:
        llm.save_usage(); json.dump(arts, open(STORE, "w"))
    print(f"llm longer: {_lr['kept']} kept / {_lr['done']} written, {_lr['eligible']} short stories eligible, "
          f"today ${llm.day_spend():.3f}, month spend ${llm._U['usd']:.3f}", flush=True)
    for c in clusters:
        m = bylink.get(c["link"]); c["long"] = (m or {}).get("llm_long")
    # image relevance (vision-verified) for top cards and every new card; results cached per card+names
    stats_img = {}
    def _pick(c):
        # only photos of members that are about the same people as the lead (enrich.cluster), never an off-topic neighbour's
        r = rank[c["id"]]
        fetch = r < IMG_CHECK_TOP or c["ts"] > time.time() - 3*86400
        # product stories (figures, merch, games, books, DVDs, cards, pre-orders) show the product itself: official store /
        # retailer first, then the article's product photo (product.py, owner rule 2026-10-26); none found -> the normal rules
        try:
            pr = product.pick(c, [m for m in c.get("member_images", []) if m], vision_ok=fetch, fetch=fetch)
            if pr: return c, pr
        except Exception as e: print("product photo:", c.get("id"), str(e)[:100], flush=True)
        return c, vision.choose(c, [m for m in c.get("member_images", []) if m], rank=r, fetch=r < IMG_CHECK_TOP or c["ts"] > time.time() - 3*86400)
    # every card gets the key-person rule (labels/file names are free); article pages are fetched for top + recent cards,
    # vision confirms only for the top vision.VISION_TOP cards when candidates are ambiguous
    rank = {c["id"]: i for i, c in enumerate(clusters)}
    try:
        import departed; departed.prune()   # drop wrong remembered departures (departures.json 'forget')
    except Exception: pass
    vision.CARD_TITLES = {c["id"]: c.get("title") or "" for c in clusters}   # a reused photo's source card must be about that person alone
    todo = clusters
    with ThreadPoolExecutor(8) as ex:
        for c, (img, cr, st) in ex.map(_pick, todo):
            c["image"] = img; c["image_credit"] = cr; c["image_status"] = st; stats_img[st] = stats_img.get(st, 0) + 1
            ml = (c.get("member_link") or {}).get(img)
            if ml and ml != c.get("link"): c["image_link"] = ml   # the report the photo came from (imgmeta: bigger copy on that page)
            else: c.pop("image_link", None)
    for c in clusters: c.pop("member_images", None); c.pop("member_src", None); c.pop("member_link", None)
    n_ov = image_overrides(clusters)
    if n_ov: print("images: manual overrides applied to", n_ov, flush=True)
    # roster check is on demand only (pubgate.roster_check -> roster.ensure), owner rule 2026-10-21
    # publish-time date gate: stories new to the site need the lead's verified page date under 48h (freshness.publish_check)
    try: live_ids = {p["id"] for p in json.load(open(OUT)).get("items", [])} or None
    except Exception: live_ids = None
    if live_ids is not None:
        rc = [bylink[c["link"]] for c in clusters if c["id"] not in live_ids and freshness.needs_recheck(c, bylink)][:60]
        def _rc(a):
            a["pubchk2"] = int(a.get("pubchk2") or 0) + 1
            try:
                u = a["link"]
                if "news.google.com" in u: u = enrich.resolve_google(u)
                h = enrich._get(u, 10).read()[:900000].decode("utf8", "ignore"); p = freshness.page_published(h)
                if p: a["pub_ts"] = p
            except Exception: pass
        if rc:
            with ThreadPoolExecutor(8) as ex: list(ex.map(_rc, rc))
            print(f"freshness: lead page dates re-checked for {len(rc)} new stories, {sum(1 for a in rc if a.get('pub_ts'))} found", flush=True)
            json.dump(arts, open(STORE, "w"))
    clusters = pubgate.run(clusters, bylink, live_ids=live_ids)   # pre-publish consistency + date gate: held stories never reach pages, feeds, X or push
    try: RM = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "story_removals.json"))).get("ids", {})
    except Exception: RM = {}
    if RM:
        n0 = len(clusters); clusters = [c for c in clusters if c["id"] not in RM]
        if len(clusters) < n0: print(f"removals: {n0 - len(clusters)} hand-removed stories kept off the site", flush=True)
    try:   # 'Full Card' report per show whose official card is announced (template-built, no AI; same id when the card changes)
        import fullcard; fullcard.run(clusters)
    except Exception as ex: print("fullcard: error (ignored)", repr(ex)[:200], flush=True)
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
    toppick.annotate(clusters)   # homepage Top stories: c['imp'] / c['brk'] into news.json (and es/news.json)
    pages.assign_urls(clusters); pages.build(clusters); llm.save_usage()
    try:
        import hubs, live
        lv = [{"key": k, "name": (live.load(k) or {}).get("name", k), "en": v.get("en"), "es": v.get("es")} for k, v in hubs.LIVE_PAGES.items()]
        target = pages.live_target()
        json.dump({"updated": int(time.time()), "live": lv, "target": target}, open(os.path.join(os.path.dirname(OUT), "live.json"), "w"), ensure_ascii=False)
        pages.build_live_redirect(target)
        import conflicts; conflicts.write(7)   # data/live_conflicts.json: upcoming same-night show conflicts for the owner
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
