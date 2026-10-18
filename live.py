"""Live results for show/PPV event pages.

During a show window (events.json start time -> +3.5h PPV / +2.5h weekly) the event page becomes a live results post.
Results come ONLY from trusted results pages (Wrestling Observer/F4W, Fightful, Wrestling Inc, PWInsider) found via their RSS
feeds and WCN's own article store. We extract facts only (winner, loser, finish, title status) and write every line in
WCN's own template wording (EN + ES), so no source prose is ever copied. Each result lists its source(s) with links.
A result is shown once >=1 trusted source reports it; 'confirmed' (used for X posts / push) needs 2 sources, or 1 source
once 10 minutes have passed without contradiction.
State: data/live/<date>-<slug>.json (saved to the data branch). No AI needed (cost $0); optional AI hooks are not used.
"""
import os, re, json, time, html, datetime, urllib.request
ROOT = os.path.dirname(os.path.abspath(__file__))
LIVE_DIR = os.path.join(ROOT, "data", "live")
CFG = json.load(open(os.path.join(ROOT, "events.json")))
try:
    from zoneinfo import ZoneInfo; ET = ZoneInfo("America/New_York")
except Exception: ET = datetime.timezone(datetime.timedelta(hours=-4))
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 WCN-results/1.0"}
PPV_H, WEEKLY_H, PRE_MIN = 3.5, 2.5, 15
COLLECT_H = 8          # keep collecting (on the normal 15-min runs) this long after start so the permanent page is complete
FEEDS = {"Wrestling Observer": "https://www.f4wonline.com/feed", "Wrestling Inc": "https://www.wrestlinginc.com/feed/",
         "Fightful": "https://www.fightful.com/rss.xml"}
LISTINGS = ["https://www.fightful.com/wrestling/results/"]
TRUSTED_HOSTS = {"f4wonline.com": "Wrestling Observer", "wrestlinginc.com": "Wrestling Inc", "fightful.com": "Fightful", "pwinsider.com": "PWInsider"}
SHOW_RX = {"wwe-raw": r"\bRaw\b", "wwe-smackdown": r"smack\s?down", "wwe-nxt": r"\bNXT\b", "aew-dynamite": r"\bDynamite\b",
           "aew-collision": r"\bCollision\b", "tna-impact": r"\bimpact\b"}
HASHTAG = {"wwe-raw": "#WWERaw", "wwe-smackdown": "#SmackDown", "wwe-nxt": "#WWENXT", "aew-dynamite": "#AEWDynamite", "aew-collision": "#AEWCollision", "tna-impact": "#TNAiMPACT"}
def log(*a): print("[live]", *a, flush=True)
def _hm(s): h, m = (s or "20:00").split(":"); return int(h), int(m)
def _dt(d, hhmm): h, m = _hm(hhmm); return datetime.datetime(d.year, d.month, d.day, h, m, tzinfo=ET)

# ---------------------------------------------------------------- schedule
def shows_on(day):
    """All shows/PPVs airing on `day` -> list of dicts with key, start, end, kind."""
    out = []
    for ev in CFG["events"]:
        if ev["date"] != day.isoformat(): continue
        st = _dt(day, ev.get("time") or "20:00")
        pre = ev.get("pre_time")
        cs = _dt(day, pre) if pre else st
        out.append({"key": f"{ev['date']}-{ev['slug']}", "kind": "ppv", "slug": ev["slug"], "date": ev["date"], "name": ev["name"], "brand": ev["brand"],
                    "start": cs, "main": st, "end": st + datetime.timedelta(hours=ev.get("hours", PPV_H)), "rx": ev.get("match") or re.escape(ev["name"]),
                    "results_pages": ev.get("results_pages", []), "tag": ev.get("hashtag") or "#" + re.sub(r"[^A-Za-z0-9]", "", re.sub(r"\s*\d{4}$", "", ev["name"]))})
    for show, s in CFG["shows"].items():
        skip = {x["date"] for x in CFG.get("skips", {}).get(show, [])}
        slots = []
        if day.weekday() == s["weekday"] and day.isoformat() not in skip: slots.append(s["time"])
        slots += [x.get("time", s["time"]) for x in CFG.get("extra", {}).get(show, []) if x["date"] == day.isoformat()]
        for t in slots[:1]:
            st = _dt(day, t)
            out.append({"key": f"{day.isoformat()}-{show}", "kind": "weekly", "slug": show, "date": day.isoformat(), "name": s["name"], "brand": s["brand"],
                        "start": st, "main": st, "end": st + datetime.timedelta(hours=WEEKLY_H), "rx": SHOW_RX[show], "tag": HASHTAG.get(show, "#" + s["brand"])})
    return out
def windows(now=None, collect=False):
    now = now or datetime.datetime.now(ET); out = []
    for dd in (-1, 0):
        for w in shows_on(now.date() + datetime.timedelta(days=dd)):
            end = w["start"] + datetime.timedelta(hours=COLLECT_H) if collect else w["end"]
            if w["start"] - datetime.timedelta(minutes=PRE_MIN) <= now <= end: out.append(w)
    return out
def in_window(now=None): return bool(windows(now))

# ---------------------------------------------------------------- fetching + discovery
def get(url, t=20):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=t).read().decode("utf-8", "replace")
def source_of(url):
    h = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
    return next((n for k, n in TRUSTED_HOSTS.items() if h == k or h.endswith("." + k)), None)
def discover(w, store_articles=()):
    """Trusted results pages for this show (title must name the show/event and say results/live)."""
    rx = re.compile(w["rx"], re.I); found = {}
    d = datetime.date.fromisoformat(w["date"]); md = {f"{d.month}/{d.day}", f"{d.month:02d}/{d.day:02d}", f"{d.month}/{d.day}/{d.year % 100}", d.strftime("%B ").lower() + str(d.day)}
    def ok(title, ts=None):
        t = html.unescape(title)
        if not (rx.search(t) and re.search(r"result|live (?:blog|coverage|updates)|recap", t, re.I)): return False
        if re.search(r"preview|predictions?|how to watch|start time|grades only|viewership|ratings", t, re.I): return False
        if ts is not None and abs(ts - w["main"].timestamp()) > 20 * 3600: return False
        if w["kind"] == "weekly" and ts is None and not any(m in t.lower() for m in md): return False
        return True
    for name, url in FEEDS.items():
        try: x = get(url)
        except Exception as ex: log(f"feed {name} failed: {str(ex)[:80]}"); continue
        for it in re.findall(r"<item>(.*?)</item>", x, re.S):
            t = re.search(r"<title>(.*?)</title>", it, re.S); l = re.search(r"<link>(.*?)</link>", it, re.S); p = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
            if not (t and l): continue
            title = re.sub(r"<!\[CDATA\[|\]\]>", "", t.group(1)).strip(); link = re.sub(r"<!\[CDATA\[|\]\]>", "", l.group(1)).strip()
            ts = None
            if p:
                try: import email.utils as eu; ts = eu.parsedate_to_datetime(p.group(1).strip()).timestamp()
                except Exception: ts = None
            if source_of(link) and ok(title, ts): found.setdefault(link, source_of(link))
    for lst in LISTINGS:   # results-section pages whose links carry the show name + date in the URL slug
        try: x = get(lst, 15)
        except Exception: continue
        for link in set(re.findall(r'https://www\.fightful\.com/wrestling/[a-z0-9-]*results[a-z0-9-]*/?', x)):
            slug = link.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
            if rx.search(slug) and (f"{d.month} {d.day} {d.year}" in slug or f"{d.month} {d.day}" in slug): found.setdefault(link, "Fightful")
    for a in store_articles:
        link = a.get("link", "")
        if source_of(link) and ok(a.get("raw_title") or a.get("title", ""), a.get("ts")): found.setdefault(link, source_of(link))
    return found

# ---------------------------------------------------------------- parsing (facts only)
def lines_of(page):
    s = re.sub(r"(?is)<(script|style|noscript|aside|nav|footer|header|form)[^>]*>.*?</\1>", " ", page)
    m = re.search(r"(?is)<article[^>]*>(.*)</article>", s)
    if m: s = m.group(1)
    s = re.sub(r"(?i)<(br|/p|/li|/h\d|/div|/tr|/blockquote)[^>]*>", "\n", s)
    t = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return [re.sub(r"\s+", " ", l).strip() for l in t.split("\n") if l.strip()]
DEF = r"(?:def\.|defeated|defeats|beat|beats|over)"
TITLE_RX = re.compile(r"(?i)\b(champion(?:ship)?s?|title)\b")
CHANGE_RX = re.compile(r"(?i)\b(new (?:\w+ )?champions?|to (?:win|capture|become)|wins? the|captur(?:e|es|ed)|crowned|title change|dethron)")
RETAIN_RX = re.compile(r"(?i)\b(retain(?:s|ed)?|successful(?:ly)? defen[cs]e|still (?:the )?champion)")
NOTE = re.compile(r"(?i)^(?:result|match result|winner|winners)\s*:")
def clean_side(s):
    s = re.sub(r"\s*\((?:w/|with)[^)]*\)", "", s)                     # managers
    s = re.sub(r"\s*\[[^\]]*\]", "", s)
    s = re.sub(r"\s+", " ", s).strip(" .,:;-–—*")
    return s
def split_method(rest):
    """rest = text after the loser -> (loser, method_text)."""
    m = re.search(r"(?i)\s+(?:via|by|with|when|after|following|to (?:retain|win|capture|become|advance|earn)|in\s+\d|\(\d|\d\s*-\s*\d|- |– |— )", rest)
    if not m: return rest, ""
    return rest[:m.start()], rest[m.start():].strip()
def finish(method, line):
    """Short factual finish phrase (our own words): pinfall/submission/DQ/count-out/etc., plus 'X pinned Y'."""
    t = (method + " " + line).lower()
    for rx, en, es in [(r"disqualif|\bdq\b", "by disqualification", "por descalificación"), (r"count-?out", "by count-out", "por cuenta fuera"),
                       (r"no contest", "no contest", "sin resultado"), (r"submi|tap(?:s|ped)? out|\btaps?\b", "by submission", "por rendición"),
                       (r"referee stop|ref stop|tko|ko\b|knockout", "by referee stoppage", "por detención del réferi"),
                       (r"pinfall|pinned|pins\b|three count|3-count|roll-?up|cover", "by pinfall", "por conteo de tres")]:
        if re.search(rx, t): return en, es
    return "", ""
def parse_line(line):
    l = NOTE.sub("", line).strip()
    if len(l) > 330 or len(l) < 8: return None
    m = re.match(rf"(?i)^(?:(?P<stip>[^:]{{3,80}}):\s+)?(?P<w>.+?)\s+{DEF}\s+(?P<rest>.+)$", l)
    if not m: return None
    w = clean_side(m.group("w")); loser, method = split_method(m.group("rest")); loser = clean_side(loser)
    if not w or not loser or len(w) > 140 or len(loser) > 200: return None
    if re.search(r"\b(will|would|could|should|next week|last week|previously|earlier this|on (?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|at (?:all out|all in))\b", l): return None
    if re.search(r"(?i)^(?:the |and |but |after |when |as |in |this |with |following )", w) and not re.match(r"(?i)^the [A-Z]", w): return None
    stip = clean_side(m.group("stip") or "")
    if stip and re.search(r"(?i)\b(?:says|said|note|update)\b", stip): return None
    title = "change" if CHANGE_RX.search(method + " " + l) and TITLE_RX.search(l + " " + stip) else ("retain" if RETAIN_RX.search(l) else None)
    if title is None and stip and TITLE_RX.search(stip) and re.search(r"\(c\)", m.group("w")): title = "retain"
    if title is None and stip and TITLE_RX.search(stip) and re.search(r"\(c\)", m.group("rest")) and not re.search(r"\(c\)", m.group("w")): title = "change"
    fen, fes = finish(method, l)
    mv = re.match(r"(?i)^(?:with|after|via|by|following)\s+(?:a|an|the|his|her|their)\s+([A-Z][\w'’.-]*(?:\s+[A-Z0-9][\w'’.-]*){0,3})", method)
    move = mv.group(1) if mv and not re.search(r"(?i)pinfall|submission|disqualif|count", mv.group(1)) else ""
    pin = re.search(r"\b([A-Z][\w'.-]+(?: [A-Z][\w'.-]+)?) (pinned|submitted|made) ([A-Z][\w'.-]+(?: [A-Z][\w'.-]+)?)", method)
    return {"winner": re.sub(r"\s*\(c\)", "", w).strip(), "loser": re.sub(r"\s*\(c\)", "", loser).strip(), "stip": stip, "title": title,
            "fin_en": fen, "fin_es": fes, "move": move, "who": f"{pin.group(1)} {'pinned' if pin.group(2) == 'pinned' else 'submitted'} {pin.group(3)}" if pin else ""}
PRE_RX = r"(?i:pre-?show|kickoff|kick-off|zero hour|countdown to|tailgate brawl|buy-?in|dark match)"
def card_of(lines):
    """Announced matches from the card lists sources print: '[Stip:] A (c) vs. B vs. C' -> [{stip, sides, champ}]."""
    out = []
    for l in lines:
        if len(l) > 400 or not re.search(r"\bvs\.?\s", l) or re.search(rf"(?i)\b{DEF}\b|def\.", l): continue
        m = re.match(r"^(?:(?P<stip>[^:]{3,120}):\s+)?(?P<rest>.+)$", l)
        stip = clean_side(m.group("stip") or ""); rest = m.group("rest")
        if stip and re.search(r"(?i)\b(?:says|said|update|tonight|watch)\b", stip): continue
        sides = [x.strip() for x in re.split(r"\s+vs\.?\s+", rest) if x.strip()]
        if len(sides) < 2 or any(len(x) > 160 or len(x.split()) > 18 for x in sides): continue
        if re.search(r"(?i)headlined|results are|listed below|will (?:face|take on)|\bcard\b", rest): continue
        if re.search(r"(?i)^(?:video|promo|package|backstage|vignette)|is shown|later tonight", " ".join(sides)): continue
        ft = re.search(r"(?i)\s+(?:for|with) (?:the |his |her |their )?((?:[\w'’.-]+ ){0,6}(?:title|championship)s?)\b.*$", sides[-1])
        if ft:
            sides[-1] = sides[-1][:ft.start()]
            if not stip: stip = clean_side(ft.group(1))
        pre = bool(re.search(PRE_RX, l))
        sides = [re.sub(r"\s*\((?:" + PRE_RX + r")[^)]*\)", "", x, flags=re.I) for x in sides]
        sides = [re.sub(r"\s+[-–—]\s+.*$", "", x) for x in sides]
        champ = next((clean_side(re.sub(r"\s*\(c\.?\)", "", x)) for x in sides if re.search(r"\(c\.?\)", x)), None)
        out.append({"stip": stip, "sides": [clean_side(re.sub(r"\s*\(c\.?\)", "", x)) for x in sides], "champ": champ, "pre": pre})
    return out
def card_match(card, r):
    """Best card entry for result r (winner must overlap one side; loser, if known, another)."""
    best, bs = None, 0
    W, Lo = toks(r["winner"]), toks(r.get("loser"))
    for c in card:
        sc = 0
        for sd in c["sides"]:
            T = toks(sd)
            if W and T and len(W & T) / min(len(W), len(T)) >= 0.5: sc += 2
            elif Lo and T and len(Lo & T) / min(len(Lo), len(T)) >= 0.5: sc += 1
        if sc >= 2: sc += 0.5 if (c["stip"] or c["champ"]) else 0
        if sc >= 2 and sc > bs: best, bs = c, sc
    return best
def apply_card(r, card):
    c = card_match(card, r)
    if not c: return
    r["card"] = True
    if not r.get("loser"):
        W = toks(r["winner"])
        others = [sd for sd in c["sides"] if not (toks(sd) and W and len(toks(sd) & W) / min(len(toks(sd)), len(W)) >= 0.5)]
        if 0 < len(others) <= 2: r["loser"] = " and ".join(others) if len(others) == 2 and len(c["sides"]) == 3 else others[0] if len(others) == 1 else ", ".join(others)
        elif len(others) > 2: r["field"] = len(c["sides"])
    if c["stip"] and not r.get("stip"): r["stip"] = c["stip"]
    if c.get("pre"): r["pre"] = True
    if c["champ"] and TITLE_RX.search(c["stip"] or "Championship") and r.get("title") is None:
        CT = toks(c["champ"]); W = toks(r["winner"])
        r["title"] = "retain" if CT and W and len(CT & W) / min(len(CT), len(W)) >= 0.5 else "change"
CARD = {}
def parse_page(page):
    out, seen = [], set()
    lines = lines_of(page)
    card = card_of(lines); pre_sec = False
    for i, line in enumerate(lines):
        r = None
        if len(line) < 70:
            if re.search(PRE_RX, line) and not re.search(rf"(?i)\b{DEF}\b|def\.|\bvs\b", line): pre_sec = True
            elif re.search(r"(?i)^(?:main (?:card|show)|pay-?per-?view|ppv|main event)\b", line) or \
                    (CARD.get("main_rx") and re.fullmatch(r"(?i)(?:AEW |WWE |TNA |NXT )?(?:" + CARD["main_rx"] + r")(?: \d{4})?(?: results| main card| begins)?", line)): pre_sec = False
        if re.search(rf"(?i)\b{DEF}\b|def\.", line): r = parse_line(line)
        if r is None and len(line) < 220:
            m = re.match(r"^(?:[^:]{3,60}:\s+)?(?P<w>[A-Z][^,:;]{2,70}?) (?:wins|won|retains|retained|captures|captured|is the new|are the new|become the new|becomes the new)\b(?P<rest>.*)$", NOTE.sub("", line).strip())
            if m and not re.search(r"\b(will|would|could|if|last week|previously)\b", line):
                w = clean_side(m.group("w")); rest = m.group("rest")
                if CHANGE_RX.search(line) and TITLE_RX.search(line): ti = "change"
                elif RETAIN_RX.search(line): ti = "retain"
                else: ti = None
                fen, fes = finish(rest, line)
                r = {"winner": w, "loser": "", "stip": "", "title": ti, "fin_en": fen, "fin_es": fes, "who": "", "need_card": True}
        if r is None:
            m = re.match(r"(?i)^winners?\s*:\s*(.{3,120})$", line)                 # Wrestling Inc: "Winner(s): X" after the play-by-play
            if m:
                ctx = " ".join(lines[max(0, i - 3):i])
                w = clean_side(re.split(r"(?i),? (?:and|&) (?:new|still)\b|,\s*(?:new|still)\b", m.group(1))[0])
                fen, fes = finish("", ctx[-400:])
                r = {"winner": re.sub(r"\s*\(c\)", "", w), "loser": "", "stip": "", "title": None, "fin_en": fen, "fin_es": fes, "who": ""}
                if re.search(r"(?i)\b(?:new|and new) (?:\w+ )*champions?\b", m.group(1) + " " + ctx[-300:]): r["title"] = "change"
                elif re.search(r"(?i)\b(?:and still|retain)", m.group(1) + " " + ctx[-200:]): r["title"] = "retain"
        if r:
            if pre_sec: r["pre"] = True
            apply_card(r, card + CARD.get("cur", []))
            if r.pop("need_card", False) and not r.get("card"): continue   # 'X wins…' lines only count for announced matches
            k = norm(r["winner"]) + "|" + norm(r["loser"])
            if k not in seen: seen.add(k); r["pos"] = i; out.append(r)
    return out

# ---------------------------------------------------------------- merging
STOP = set("the and of vs w with team family champion champions c aew wwe tna".split())
def toks(s): return {t for t in re.findall(r"[a-z0-9]+", (s or "").lower().replace("é", "e").replace("í", "i").replace("ó", "o").replace("á", "a")) if t not in STOP and len(t) > 1}
def norm(s): return " ".join(sorted(toks(s)))
def _ov(a, b):
    a, b = toks(a), toks(b)
    return len(a & b) / min(len(a), len(b)) if a and b else 0
def same(a, b):
    if a.get("loser") and b.get("loser") and len(toks(a["loser"])) >= 3 and len(toks(b["loser"])) >= 3 and _ov(a["loser"], b["loser"]) >= 0.6 \
            and _ov(a["winner"], b["loser"]) < 0.34 and _ov(b["winner"], a["loser"]) < 0.34:
        return True                                     # same beaten opponents, winner just named differently (e.g. "DCF" vs "The Don Callis Family")
    if _ov(a["winner"], b["winner"]) < 0.5: return False
    if a.get("loser") and b.get("loser") and toks(a["loser"]) and toks(b["loser"]) and _ov(a["loser"], b["loser"]) < 0.34: return False
    return True
def contradicts(a, b):
    """Two reports where one's winner is the other's loser in the same pairing -> conflicting reports."""
    if not (a.get("loser") and b.get("loser")): return False
    return _ov(a["winner"], b["loser"]) >= 0.5 and _ov(b["winner"], a["loser"]) >= 0.5
def text_en(m):
    w, l = m["winner"], m["loser"]
    s = f"{w} beat {l}" if l else (f"{w} won the {m['field']}-way match" if m.get("field") else f"{w} won")
    if m.get("fin_en"): s += " " + m["fin_en"]
    if m.get("move"): s += f" with the {m['move']}"
    if m.get("who") and m["who"].split()[0].lower() not in (m.get("fin_en") or ""): s += f" ({m['who']})"
    if m.get("title") == "change": s += " — NEW CHAMPION" + ("S" if re.search(r"&| and |,", w) else "")
    elif m.get("title") == "retain": s += " to retain"
    return s if s.endswith("!") else s + "."
def text_es(m):
    w, l = m["winner"], m["loser"]
    pl = bool(re.search(r"&| and | y |,", w))
    s = (f"{w} {'vencieron' if pl else 'venció'} a {l}") if l else (f"{w} {'ganaron' if pl else 'ganó'} el combate a {m['field']} bandas" if m.get("field") else f"{w} {'ganaron' if pl else 'ganó'}")
    if m.get("fin_es"): s += " " + m["fin_es"]
    if m.get("move"): s += f" (remate: {m['move']})"
    if m.get("who"):
        s += " (" + m["who"].replace(" pinned ", " cubrió a ").replace(" submitted ", " rindió a ") + ")"
    if m.get("title") == "change": s += " — ¡CAMBIO DE TÍTULO!"
    elif m.get("title") == "retain": s += (" y retuvieron el título" if re.search(r"&| and | y |,", w) else " y retuvo el título")
    return s if s.endswith("!") else s + "."

def path(key): return os.path.join(LIVE_DIR, key + ".json")
def load(key):
    try: return json.load(open(path(key)))
    except Exception: return None
def update(store_articles=(), now=None):
    """Called from the aggregator every run (cheap no-op outside windows). Returns list of updated keys."""
    now = now or datetime.datetime.now(ET); changed = []
    os.makedirs(LIVE_DIR, exist_ok=True)
    for w in windows(now, collect=True):
        st = load(w["key"]) or {"key": w["key"], "matches": [], "pages": {}}
        st.update({k: w[k] for k in ("kind", "slug", "date", "name", "brand", "tag")})
        st.update(start=int(w["start"].timestamp()), main=int(w["main"].timestamp()), end=int(w["end"].timestamp()))
        try: pages = discover(w, store_articles)
        except Exception as ex: log("discover failed", ex); pages = {}
        st["pages"].update({u: s for u, s in pages.items()})
        for u in w.get("results_pages", []):
            if source_of(u): st["pages"].setdefault(u, source_of(u))
        reports = []; htmls = {}
        for url in st["pages"]:
            try: htmls[url] = get(url)
            except Exception as ex: log(f"fetch {st['pages'][url]} failed: {str(ex)[:80]}")
        CARD["cur"] = [c for h in htmls.values() for c in card_of(lines_of(h))]; CARD["main_rx"] = w["rx"]
        st["card"] = CARD["cur"][:40]
        for url, src in st["pages"].items():
            if url not in htmls: continue
            try: rs = parse_page(htmls[url])
            except Exception as ex: log(f"fetch {src} failed: {str(ex)[:80]}"); continue
            log(f"{w['key']}: {src} -> {len(rs)} results")
            for r in rs: r["src"] = src; r["url"] = url; reports.append(r)
        seen_ids = set()
        for x in sorted(st["matches"], key=lambda q: q["first_seen"]):
            if x["id"] in seen_ids:
                st["next_id"] = max([st.get("next_id", 0)] + [int(q["id"][1:]) for q in st["matches"] if q["id"][1:].isdigit()]) + 1; x["id"] = f"m{st['next_id']}"
            seen_ids.add(x["id"])
        before = json.dumps(st["matches"], sort_keys=True)
        nowi = int(time.time())
        for r in reports:
            m = next((x for x in st["matches"] if same(x, r)), None)
            if m is None and not r.get("loser") and not r.get("field") and any(x.get("loser") for x in reports): continue   # winner-only lines just corroborate
            if m is None:
                m = {k: r.get(k) for k in ("winner", "loser", "stip", "title", "fin_en", "fin_es", "who", "field", "move")}
                st["next_id"] = max([st.get("next_id", 0)] + [int(x["id"][1:]) for x in st["matches"] if x["id"][1:].isdigit()]) + 1
                m.update(id=f"m{st['next_id']}", first_seen=nowi, updated=nowi, sources=[], order=r["pos"] + 10000 * list(st["pages"]).index(r["url"]))
                st["matches"].append(m)
            # enrich with facts another source has (loser, finish, title flag, stipulation)
            m.setdefault("_pre_votes", {})[r["src"]] = bool(r.get("pre"))
            for k in ("loser", "stip", "fin_en", "fin_es", "who", "move"):
                if not m.get(k) and r.get(k): m[k] = r[k]; m["updated"] = nowi
            if r.get("title") and m.get("title") != r["title"] and (m.get("title") is None or r["title"] == "change"): m["title"] = r["title"]; m["updated"] = nowi
            if len(r.get("winner", "")) > len(m["winner"]) and same(r, m): m["winner"] = r["winner"]
            if not any(s["name"] == r["src"] for s in m["sources"]): m["sources"].append({"name": r["src"], "url": r["url"]}); m["updated"] = nowi
        merged = []                                     # fold duplicates that slipped in earlier into the first-seen entry
        for m in sorted(st["matches"], key=lambda x: x["first_seen"]):
            t = next((x for x in merged if same(x, m)), None)
            if t is None: merged.append(m); continue
            for sx in m["sources"]:
                if not any(q["name"] == sx["name"] for q in t["sources"]): t["sources"].append(sx)
            for k in ("loser", "stip", "fin_en", "fin_es", "who", "move", "title", "pre"):
                if not t.get(k) and m.get(k): t[k] = m[k]
        st["matches"] = merged
        for m in st["matches"]:
            v = m.pop("_pre_votes", None)
            if v is not None: m["pre"] = any(v.values()) and sum(v.values()) * 2 >= len(v)
            m["conflict"] = any(contradicts(m, o) for o in st["matches"] if o is not m)
            m["confirmed"] = not m["conflict"] and (len(m["sources"]) >= 2 or nowi - m["first_seen"] >= 600)
            m["en"], m["es"] = text_en(m), text_es(m)
        # order: by position in the source with the most results (show order), new unknowns at the end
        st["matches"].sort(key=lambda m: m.get("order", 0))
        if json.dumps(st["matches"], sort_keys=True) != before: st["updated"] = nowi; changed.append(w["key"])
        st["checked"] = nowi
        json.dump(st, open(path(w["key"]), "w"), indent=0)
    return changed
def live_now(now=None):
    """[{key, name, path_en, path_es}] for the homepage banner (shows on air now)."""
    out = []
    for w in windows(now):
        out.append({"key": w["key"], "name": w["name"], "brand": w["brand"], "kind": w["kind"], "start": int(w["start"].timestamp()), "end": int(w["end"].timestamp())})
    return out
if __name__ == "__main__":
    import sys
    if "--in-window" in sys.argv:
        ws = windows(); print("yes" if ws else "no"); print(" ".join(w["key"] for w in ws), file=sys.stderr); sys.exit(0)
    print(update())

# ---------------------------------------------------------------- rendering (used by hubs.py)
def _e(s): return html.escape(str(s or ""), quote=True)
def _hhmm(ts, lang):
    d = datetime.datetime.fromtimestamp(ts, ET); h = d.hour % 12 or 12
    return f"{h}:{d.minute:02d} {'p. m.' if d.hour >= 12 else 'a. m.'} ET" if lang == "es" else f"{h}:{d.minute:02d} {'PM' if d.hour >= 12 else 'AM'} ET"
def page_state(key, now=None):
    st = load(key)
    if not st: return None
    nowi = time.time() if now is None else now
    st["is_live"] = st["start"] - PRE_MIN * 60 <= nowi <= st["end"]
    st["shown"] = [m for m in st["matches"] if m.get("sources") and not m.get("conflict")]
    return st
def render(key, lang, url):
    """-> (badge_html, section_html, [ld]) or None when we have nothing for this page."""
    st = page_state(key)
    if not st or (not st["shown"] and not st["is_live"]): return None
    es = lang == "es"; live = st["is_live"]
    upd = st.get("updated") or st.get("checked") or st["start"]
    badge = f'<span class="live-badge">{"EN VIVO" if es else "LIVE"}</span> ' if live else ""
    if live: head = "Resultados en vivo" if es else "Live results"
    else: head = "Resultados completos" if es else "Full results"
    rows = []
    for i, m in enumerate(st["shown"], 1):
        srcs = " · ".join(f'<a href="{_e(s["url"])}" rel="nofollow noopener" target="_blank">{_e(s["name"])}</a>' for s in m["sources"])
        flag = ""
        if m.get("title") == "change": flag = f'<span class="tc">{"¡CAMBIO DE TÍTULO!" if es else "TITLE CHANGE"}</span> '
        elif m.get("title") == "retain": flag = f'<span class="tr">{"RETIENE" if es else "RETAINED"}</span> '
        stip = f'<b class="stip">{_e(m["stip"])}:</b> ' if m.get("stip") else ""
        if m.get("pre"): stip = f'<span class="pre">{"PREVIA" if es else "PRE-SHOW"}</span> ' + stip
        rows.append(f'<li id="{m["id"]}"><time datetime="{datetime.datetime.fromtimestamp(m["first_seen"], datetime.timezone.utc).isoformat()}">{_hhmm(m["first_seen"], lang)}</time>'
                    f'<p>{flag}{stip}{_e(m["es"] if es else m["en"])}</p><small>{"Fuente" if es else "Source"}{"s" if len(m["sources"]) > 1 else ""}: {srcs}</small></li>')
    if not rows: rows.append(f'<li class="wait"><p>{"Aún no hay resultados confirmados. Esta página se actualiza cada 5 minutos durante el programa." if es else "No confirmed results yet. This page updates every 5 minutes while the show is on."}</p></li>')
    note = ("Se actualiza cada 5 minutos mientras el programa está al aire. " if live else "") + "Solo publicamos un resultado cuando lo reporta al menos una fuente confiable; los enlaces llevan a cada fuente." if es else \
           ("Updates every 5 minutes while the show is on air. " if live else "") + "We only list a result once a trusted outlet reports it; links go to each source."
    sec = (f'<section class="live-results{" on" if live else ""}" id="live"><h2>{badge}{head}</h2>'
           f'<p class="live-upd">{"Última actualización" if es else "Last updated"}: <time datetime="{datetime.datetime.fromtimestamp(upd, datetime.timezone.utc).isoformat()}">{_hhmm(upd, lang)}</time>'
           f'{" · " + ("se actualiza sola" if es else "auto-refreshing") if live else ""}</p>'
           f'<ol class="live-list">{"".join(reversed(rows)) if live else "".join(rows)}</ol><p class="live-note">{note}</p></section>')
    if live: sec += '<script>setTimeout(function(){if(!document.hidden)location.reload()},180000)</script>'
    iso = lambda ts: datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat(timespec="seconds")
    ld = {"@context": "https://schema.org", "@type": "LiveBlogPosting", "headline": (("Resultados en vivo: " if es else "Live results: ") if live else ("Resultados: " if es else "Results: ")) + st["name"],
          "url": url, "inLanguage": lang, "coverageStartTime": iso(st["start"]), "coverageEndTime": iso(st["end"]), "datePublished": iso(st["start"]), "dateModified": iso(upd),
          "about": {"@type": "Event", "name": st["name"], "startDate": iso(st["main"])},
          "author": {"@type": "Organization", "name": "Wrestling Central News", "url": "https://wrestlingcentralnews.com/"},
          "publisher": {"@type": "Organization", "name": "Wrestling Central News", "logo": {"@type": "ImageObject", "url": "https://wrestlingcentralnews.com/logo.png"}},
          "liveBlogUpdate": [{"@type": "BlogPosting", "headline": (m["es"] if es else m["en"])[:110], "datePublished": iso(m["first_seen"]), "url": url + "#" + m["id"],
                              "author": {"@type": "Organization", "name": "Wrestling Central News"}} for m in st["shown"]][::-1]}
    return badge, sec, [ld]
