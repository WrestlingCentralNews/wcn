"""'Full Card' reports (owner rule 2026-10-23): one story per show episode that announces its card in advance, built from
the promotion's OWN card (no AI): every confirmed match/segment, the advertised appearances, and links to WCN's individual
announcement stories (which stay live as their own stories). Same story id per episode, so a changed card updates the
same report instead of posting a new one.

Card sources (fail closed - no verified card, no report; shows that don't announce cards never get one):
 - WWE Raw / SmackDown / NXT: the official preview page https://www.wwe.com/shows/<show>/<YYYY-MM-DD> ('Quick Hits' list),
   fetched only from the day before the show (CHECK_BEFORE_H) and at most every RECHECK_MIN minutes.
 - Any promotion / PLE (AEW, TNA, AAA, WWE PLEs...): repo file full_cards.json, entries keyed '<show-or-event slug>/<date>'
   with the card copied from the promotion's official preview (or trusted outlets) and its source URL. Manual entries can also
   add 'appearances' / 'venue' to an official WWE card.
A card counts as complete once it lists MIN_MATCHES+ items (official/hand list). Reports stay up KEEP_DAYS after the show.
Full-card reports are never auto-posted to X / Facebook / push (regular card previews aren't breaking news)."""
import os, re, json, time, html, hashlib, datetime
ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "data", "fullcards.json")
MANUAL = os.path.join(ROOT, "full_cards.json")
CFG = json.load(open(os.path.join(ROOT, "events.json")))
WWE_PAGES = {"wwe-raw": "raw", "wwe-smackdown": "smackdown", "wwe-nxt": "nxt"}
CHECK_BEFORE_H = 36; RECHECK_MIN = 60; KEEP_DAYS = 3; MIN_MATCHES = 2
SHOW_RX = {"wwe-raw": r"\bRaw\b|\bRAW\b", "wwe-smackdown": r"(?i)smack\s?down", "wwe-nxt": r"\bNXT\b", "aew-dynamite": r"\bDynamite\b",
           "aew-collision": r"\bCollision\b", "tna-impact": r"(?i)\bimpact\b"}
STOP = set("""Women Men WWE AEW TNA AAA NXT ROH NJPW Women's Women’s Men's World Heavyweight Intercontinental United States Tag Team Title Titles
Championship Champion Champions Championships Street Fight Match Matches The A An In On For Against And Vs Once Again Undisputed North American
Cruiserweight Ladder Cage Steel Last Man Standing No Disqualification Falls Count Anywhere Triple Threat Fatal Four Way Battle Royal
Open Challenge Gauntlet Contract Signing Segment Promo SmackDown Raw RAW Dynamite Collision Impact iMPACT Friday Monday Tuesday Wednesday
Thursday Saturday Sunday Plus Also Will Who Find Out Grudge Rematch Non-Title Number One Contender Contenders Tournament Final Semifinal
Qualifying Hardcore Tables Chairs TLC Last Elimination Chamber Iron Mixed Six-Woman Six-Man Eight-Man Handicap Special Guest Referee
Face-to-Face Address Addresses Appearance Appears Returns Return Defends Defend Takes Challenge Challenges Collide Collides Battle Battles""".split())
_MON = "January February March April May June July August September October November December".split()
_DAY = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()

def _load(p, d):
    try:
        with open(p) as f: return json.load(f)
    except Exception: return d
def names(line):
    """Proper-name tokens of a card line ('Chelsea Green defends ... against Roxanne Perez' -> Chelsea, Green, Roxanne, Perez)."""
    out = []
    for w in re.findall(r"[A-Z][\w'’.\-]*[\w]|\b[A-Z]\b", line):
        w = re.sub(r"['’]s$", "", w)
        if w not in STOP and w.rstrip("s") not in STOP and len(w) > 1 and w not in out: out.append(w)
    return out
def parse_wwe(h):
    """WWE.com episode preview -> (card lines, og:image). Lines are the page's 'Quick Hits' (one per match / segment)."""
    lines = []
    for m in re.finditer(r'<a [^>]*contentType=quickHit[^>]*>(.*?)</a>', h, re.S):
        t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", m.group(1)))).strip()
        if t and t not in lines: lines.append(t)
    img = re.search(r'<meta property="og:image" content="([^"]+)"', h)
    return lines, (html.unescape(img.group(1)) if img else None)
def card_id(key): return "c" + hashlib.md5(("fullcard|" + key).encode()).hexdigest()[:12]
def fmt_date(d): return f"{_MON[d.month - 1]} {d.day}, {d.year}"
def upcoming(now):
    """[(key, show_slug, date, info)] for weekly shows / sourced events airing within CHECK_BEFORE_H hours."""
    import hubs
    t0 = datetime.datetime.fromtimestamp(now, datetime.timezone.utc); out = []
    for show in CFG["shows"]:
        for d, inf in hubs.airings(show, t0.date() - datetime.timedelta(days=1), t0.date() + datetime.timedelta(days=2)).items():
            st = hubs.start_dt(d, inf["time"]).timestamp()
            if now - 4 * 3600 <= st <= now + CHECK_BEFORE_H * 3600: out.append((f"{show}/{d.isoformat()}", show, d, inf))
    return out
def link_stories(lines, clusters, show, date, start_ts):
    """card line -> the individual announcement story (show named, reported before the show, the line's wrestlers named)."""
    rx = re.compile(SHOW_RX.get(show, r"(?!x)x")); out = []
    for ln in lines:
        ks = names(ln); need = max(2, -(-len(ks) * 3 // 5)) if len(ks) > 1 else 1; best = None
        for c in clusters:
            if c.get("fullcard") or not (start_ts - 12 * 86400 <= int(c.get("first_ts") or c.get("ts") or 0) <= start_ts): continue
            txt = " ".join([c.get("title", ""), c.get("summary", ""), c.get("raw_title") or ""])
            if not rx.search(txt): continue
            hit = sum(1 for k in ks if re.search(r"(?<![\w-])" + re.escape(k) + r"(?![\w-])", txt))
            score = (hit, bool(rx.search(c.get("title", ""))), int(c.get("first_ts") or 0))   # most wrestlers, then the show in the headline, then newest
            if ks and hit >= need and (not best or score > best[0]): best = (score, c)
        out.append({"line": ln, "sid": best[1]["id"] if best else None})
    return out
def build(key, st, show, date, inf, brand, name):
    lines = st["lines"]; app = st.get("appearances") or []
    when = f"{_DAY[date.weekday()]}, {fmt_date(date)}"
    tm = inf.get("time") or "20:00"; h, m = map(int, tm.split(":")); ampm = f"{(h - 1) % 12 + 1}{':%02d' % m if m else ''} {'p.m.' if h >= 12 else 'a.m.'} ET"
    where = f" from {st['venue']}" if st.get("venue") else ""
    lst = "; ".join(lines[:-1]) + ("; and " if len(lines) > 1 else "") + lines[-1]
    summ = f"{brand} has announced the card for {name.replace(brand + ' ', '')} on {when}{where} ({ampm}, {inf.get('network')}): {lst}."
    if app: summ += f" Also advertised: {', '.join(app)}."
    src = st.get("source_name") or "the promotion"
    long = [summ, f"This is the card as announced by {src} and is subject to change; WCN updates this report if matches are added or changed."]
    return {"id": card_id(key), "title": f"{name} Full Card For {fmt_date(date)}", "summary": summ, "long": long, "link": st["source"],
            "source": st.get("source_name") or brand, "raw_title": f"{name} Full Card For {fmt_date(date)}", "src_summary": summ,
            "first_ts": st["first_ts"], "lead_ts": st["first_ts"], "ts": st["ts"], "added": st["first_ts"], "image": st.get("image"),
            "image_status": "override" if st.get("image") else None, "image_credit": {"text": src, "url": st["source"]} if st.get("image") else None,
            "categories": [brand], "kind": {"type": "news"}, "updates": [], "sources": 1, "trusted": 1, "fullcard": key, "card": st.get("items") or [], "appearances": app, "show_name": name,
            "lead_until": int(st["start"]) if st.get("start") else None}
def run(clusters, now=None, fetch=None, log=print):
    """Add/refresh the Full Card reports in `clusters` (in place). fetch(url)->html (tests inject one). Returns the reports."""
    now = int(now or time.time()); S = _load(STATE, {}); man = _load(MANUAL, {}).get("cards", {}); ch = False
    if fetch is None:
        import enrich
        fetch = lambda u: enrich._get(u, 12).read()[:2000000].decode("utf8", "ignore")
    keys = {k: (show, d, inf) for k, show, d, inf in upcoming(now)}
    for k, v in man.items():   # hand cards (any promotion / PLE) inside the same window
        if k in keys: continue
        slug, ds = k.rsplit("/", 1); d = datetime.date.fromisoformat(ds)
        import hubs
        show = CFG["shows"].get(slug); ev = next((e for e in CFG["events"] if e["slug"] == slug), None)
        inf = {"time": v.get("time") or (show or ev or {}).get("time") or "20:00", "network": v.get("network") or (show or {}).get("network") or "", "name": v.get("name") or (show or ev or {}).get("name")}
        if inf["name"] and now - 4 * 3600 <= hubs.start_dt(d, inf["time"]).timestamp() <= now + CHECK_BEFORE_H * 3600: keys[k] = (slug, d, inf)
    for k, (show, d, inf) in keys.items():
        st = S.get(k) or {}; mv = man.get(k) or {}; lines, img, src, sname = None, None, None, None
        if mv.get("matches"): lines, src, sname, img = list(mv["matches"]), mv.get("source"), mv.get("source_name"), mv.get("image")
        elif show in WWE_PAGES and now - int(st.get("checked") or 0) >= RECHECK_MIN * 60:
            src = f"https://www.wwe.com/shows/{WWE_PAGES[show]}/{d.isoformat()}"; sname = "WWE.com"
            try: lines, img = parse_wwe(fetch(src))
            except Exception as ex: log("fullcard:", k, "official page error", repr(ex)[:120])
            st["checked"] = now; S[k] = st; ch = True
        if not lines or len(lines) < MIN_MATCHES: continue   # no announced / incomplete card -> no report
        new = {"lines": lines, "source": src, "source_name": sname, "image": img or st.get("image"), "appearances": mv.get("appearances") or [],
               "venue": mv.get("venue")}
        if any(st.get(x) != new[x] for x in new):
            if st.get("lines"): log(f"fullcard: {k} card changed -> same report updated")
            st.update(new); st["ts"] = now; st.setdefault("first_ts", now); ch = True
        st["show"], st["date"], st["inf"] = show, d.isoformat(), {"time": inf.get("time"), "network": inf.get("network"), "name": inf.get("name")}
        S[k] = st
    out = []
    for k, st in list(S.items()):
        if not st.get("lines"):
            if now - int(st.get("checked") or 0) > 3 * 86400: S.pop(k); ch = True
            continue
        d = datetime.date.fromisoformat(st["date"])
        if (datetime.datetime.fromtimestamp(now, datetime.timezone.utc).date() - d).days > KEEP_DAYS: S.pop(k); ch = True; continue
        show = CFG["shows"].get(st["show"]) or next((e for e in CFG["events"] if e["slug"] == st["show"]), {}) or {}
        name = (st.get("inf") or {}).get("name") or show.get("name") or st["show"]; brand = show.get("brand") or name.split()[0]
        import hubs
        start = hubs.start_dt(d, (st.get("inf") or {}).get("time") or show.get("time") or "20:00").timestamp()
        st["start"] = int(start)
        st["items"] = link_stories(st["lines"], clusters, st["show"], d, start)
        c = build(k, st, st["show"], d, {**(st.get("inf") or {}), "network": (st.get("inf") or {}).get("network") or show.get("network")}, brand, name)
        clusters[:] = [x for x in clusters if x["id"] != c["id"]]; clusters.append(c); out.append(c)
    if ch:
        os.makedirs(os.path.dirname(STATE), exist_ok=True); tmp = STATE + ".tmp"
        with open(tmp, "w") as f: json.dump(S, f, indent=1)
        os.replace(tmp, STATE)
    if out: log(f"fullcard: {len(out)} full-card report(s): " + ", ".join(f"{c['fullcard']} ({len(c['card'])} items, {sum(1 for i in c['card'] if i['sid'])} linked)" for c in out))
    return out
