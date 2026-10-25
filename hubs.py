"""Show & event hub pages: /shows/<show>/ (evergreen, latest episode), /events/<date>-<show>/ (per episode),
/events/<date>-<ple>/ (premium live events / PPVs), /upcoming/ (schedule), /shows/ (index) and Spanish mirrors under /es/.
Built every run from the stories the pipeline already has: stories are tagged to a show episode or event by name + date.
Only sourced dates (events.json) and regular weekly slots are shown. Match results come only from live.py (trusted results pages,
facts rewritten in WCN wording, each result credited and linked to its sources)."""
import os, re, json, time, datetime, hashlib
import chrome as C
import live as LIVE
import stale
from chrome import e, SITE, ET
ROOT = os.path.dirname(os.path.abspath(__file__)); PUB = os.path.join(ROOT, "public")
CFG = json.load(open(os.path.join(ROOT, "events.json")))
SHOWS = CFG["shows"]; EVENTS = CFG["events"]
RETENTION_DAYS = 60
CATC = {"WWE": "#f26a14", "AEW": "#7cd618", "TNA": "#4ea8ff", "Indie": "#f05fc1", "Global": "#2fd3b4"}
# show name patterns (case-sensitive where the word is common English) + the brand the story must be tagged with
SHOW_RX = {
 "wwe-raw": re.compile(r"\b(?:Raw|RAW)\b"), "wwe-smackdown": re.compile(r"smack\s?down", re.I), "wwe-nxt": re.compile(r"\bNXT\b(?! (?:Halloween Havoc|Heatwave|Deadline|Stand & Deliver|Battleground|Vengeance|No Mercy|Great American Bash|Roadblock|Level Up|UK|Europe|Women'?s|North American|Tag Team|Champion))"),
 "aew-dynamite": re.compile(r"\bDynamite\b"), "aew-collision": re.compile(r"\bCollision\b"), "tna-impact": re.compile(r"\b(?:iMPACT|Impact|IMPACT)\b(?!\s+(?:Hall|Zone|Plus|Wrestling Hall))"),
}
EP_HINT = re.compile(r"results?|recap|review|preview|tonight|\bcard\b|line-?up|announced for|set for|added to|confirmed for|booked|viewership|ratings?|audience|spoilers?|"
                     r"live (?:blog|coverage|updates|results)|grades|episode|this week|next week|segment|opens|opener|main[- ]event|taping|quarter-hour|dark match|off[- ]air|"
                     r"\d{1,2}/\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2}\b|on (?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday)|"
                     r"(?:appear|appears|appearance|debuts?|returns?|wins?|defeats?|beats?|retains?|crowned|attack(?:s|ed)?|confronts?|challenges?|calls? out|vs\.?|match|this monday|this friday|go(?:es)? home)", re.I)
RES = re.compile(r"results?|recap|review|grades|viewership|ratings?|audience|spoilers?|taping|quarter-hour|off[- ]air|dark match|post-show|after (?:raw|smackdown|nxt|dynamite|collision|impact)|"
                 r"\b(?:won|wins|defeat(?:s|ed)|beat|beats|retain(?:s|ed)|crowned|captur(?:es|ed)|lost)\b", re.I)
PREV = re.compile(r"preview|tonight|\bcard\b|line-?up|announced for|set for|added to|confirmed for|booked|next week|\bwill\b|scheduled|advertised|to face|to battle|lined up|what to expect|how to watch|start time", re.I)
_MON = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
def _hm(s): h, m = (s or "20:00").split(":"); return int(h), int(m)
def _d(s): return datetime.date.fromisoformat(s)
def airings(show, start, end):
    """Regular weekly air dates in [start, end] minus sourced skips, plus sourced extra airings. -> {date: info}"""
    s = SHOWS[show]; out = {}
    skips = {_d(x["date"]): x for x in CFG.get("skips", {}).get(show, [])}
    d = start + datetime.timedelta(days=(s["weekday"] - start.weekday()) % 7)
    while d <= end:
        if d not in skips: out[d] = {"time": s["time"], "network": s["network"], "note": None, "note_es": None}
        d += datetime.timedelta(days=7)
    for x in CFG.get("extra", {}).get(show, []):
        dd = _d(x["date"])
        if start <= dd <= end: out[dd] = {"time": x.get("time", s["time"]), "network": x.get("network", s["network"]), "note": x.get("note"), "note_es": x.get("note_es")}
    return dict(sorted(out.items()))
def start_dt(d, hhmm): h, m = _hm(hhmm); return datetime.datetime(d.year, d.month, d.day, h, m, tzinfo=ET)
def explicit_dates(text, ref, span=10):
    out = []
    for m, d in re.findall(r"\b(1[0-2]|0?[1-9])/([12]\d|3[01]|0?[1-9])(?:/\d{2,4})?\b", text): out.append((int(m), int(d)))
    for mo, d in re.findall(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2})(?:st|nd|rd|th)?\b", text, re.I): out.append((_MON[mo[:3].lower()], int(d)))
    if re.search(r"Halloween Eve", text, re.I): out.append((10, 30))
    elif re.search(r"Halloween", text, re.I): out.append((10, 31))
    if re.search(r"Christmas Eve", text, re.I): out.append((12, 24))
    elif re.search(r"Christmas", text, re.I): out.append((12, 25))
    if re.search(r"New Year'?s Eve", text, re.I): out.append((12, 31))
    res = []
    for m, d in out:
        for y in (ref.year - 1, ref.year, ref.year + 1):
            try: dd = datetime.date(y, m, d)
            except ValueError: continue
            if abs((dd - ref).days) <= span: res.append(dd)
    return res
def text_of(c): return " ".join([c.get("title", ""), c.get("raw_title", "")] + [u.get("title", "") for u in c.get("updates", [])[:3]])
def ref_ts(show, c):
    """When the story about THIS show was first reported: the earliest report whose own headline names the show.
    A cluster's first_ts can be an earlier, looser report folded in (a Tuesday preview on a Friday-night injury story),
    which used to pin the story to the previous week's episode. Falls back to first_ts."""
    rx = SHOW_RX[show]; ts = []
    if rx.search((c.get("raw_title") or "") + " " + (c.get("title") or "")): ts.append(c.get("lead_ts") or c["ts"])
    ts += [u["ts"] for u in c.get("updates", []) if u.get("ts") and rx.search(u.get("title") or "")]
    return min(ts) if ts else c.get("first_ts", c["ts"])
def episode_for(show, c):
    """Which airing of `show` a story is about (date) or None."""
    ts = ref_ts(show, c); t = datetime.datetime.fromtimestamp(ts, ET); txt = text_of(c)
    window = airings(show, t.date() - datetime.timedelta(days=12), t.date() + datetime.timedelta(days=12))
    if not window: return None
    named = explicit_dates(c.get("raw_title", "") + " " + c.get("title", ""), t.date(), span=45)
    for dd in named:
        if dd in window or airings(show, dd, dd): return dd
    for dd in named:   # outlets dating a show by the next day (UK time / upload date): '9/4 Results' for a Thursday 9/3 iMPACT
        for x in (dd - datetime.timedelta(days=1), dd + datetime.timedelta(days=1)):
            if x in window: return x
    if named: return None   # the title names a date that isn't one of these airings ('9/30 Dynamite' on Oct 18, '10/17 NXT live event', 'Direct set for 11/5')
    past = [d for d, i in window.items() if start_dt(d, i["time"]) <= t]
    fut = [d for d, i in window.items() if start_dt(d, i["time"]) > t]
    prev = past[-1] if past else None; nxt = fut[0] if fut else None
    kind = (c.get("kind") or {}).get("type")
    title = c.get("raw_title", "") + " " + c.get("title", "")
    if re.search(r"next week|following week", title, re.I):   # "next week's Raw" = the airing after the coming one
        return next((d for d in fut if d >= t.date() + datetime.timedelta(days=4)), None)
    if re.search(r"ratings?|viewership|audience|viewers|demo\b", title, re.I):   # numbers come out the day after an episode at the earliest
        pr = [d for d in past if start_dt(d, window[d]["time"]) <= t - datetime.timedelta(hours=10)]
        return pr[-1] if pr and (t.date() - pr[-1]).days <= 6 else None
    live = prev and t <= start_dt(prev, window[prev]["time"]) + datetime.timedelta(hours=3, minutes=30)
    if live and not (kind == "match" and not re.search(r"tonight", title, re.I)): return prev
    if live: return next((d for d in fut if d >= t.date() + datetime.timedelta(days=4)), None)
    if kind == "match" and PREV.search(title) and not re.search(r"results?\b", title, re.I):   # 'dark match announced for Monday's Raw' is forward-looking
        return nxt if nxt and (nxt - t.date()).days <= 7 else None
    if kind == "results" or RES.search(txt): return prev if prev and (t.date() - prev).days <= 6 else None
    if kind == "match" or PREV.search(txt): return nxt if nxt and (nxt - t.date()).days <= 7 else None
    if prev and t - start_dt(prev, window[prev]["time"]) <= datetime.timedelta(hours=30): return prev
    return nxt if nxt and (nxt - t.date()).days <= 6 else None
NOT_TV = re.compile(r"house show|live event|\bNXT Live\b|\btour\b|live results from|road to|tickets? (?:on sale|go on sale)|video ?game|\bWWE 2K|merch|podcast", re.I)
def event_for(c):
    ts = c.get("first_ts", c["ts"]); day = datetime.datetime.fromtimestamp(ts, ET).date(); txt = text_of(c)
    title = c.get("raw_title", "") + " " + c.get("title", "")
    for ev in EVENTS:
        d = _d(ev["date"])
        if not (-4 <= (d - day).days <= 35 and re.search(ev["match"], txt, re.I)): continue
        # after the event, a weekly show's episode story that mentions it ("Bound for Glory fallout") belongs to the show
        if day > d and not re.search(ev["match"], title, re.I): continue
        # before the event, results of some OTHER show ('Ospreay Retains ... at All Out' that merely mentions WrestleDream) aren't this event's
        if day < d and (c.get("kind") or {}).get("type") == "results" and not re.search(ev["match"], title, re.I): continue
        if day > d and any(rx.search(title) for sh, rx in SHOW_RX.items() if SHOWS[sh]["brand"] in c.get("categories", [])) and re.search(r"fallout|after|following|go-home", title, re.I): continue
        if not box_fits(c, ev): continue
        return ev
    return None
def box_fits(c, ev):
    """The event coverage box must be about what the HEADLINE is about (owner rule 2026-10-21: 'UFC 333 Start Times' got the AAA
    Heroes Inmortales box because a merged AAA report's title named the event). An event matched only through other reports'
    titles is kept only if the headline/summary don't point to a different promotion than the event's."""
    import enrich
    lead = " ".join([c.get("title") or "", c.get("raw_title") or ""])
    if re.search(ev["match"], lead, re.I): return True
    lp = enrich.promos(lead + " " + (c.get("summary") or "")[:400]); ep = enrich.promos(ev.get("name") or "")
    return not (lp and ep and not lp & ep)
HUB_OV = os.path.join(ROOT, "hub_overrides.json")   # {"exclude": [{"links": [...], "why": "..."}]}: hand-removed from every event/show page
def _excluded():
    try: return {l for x in json.load(open(HUB_OV)).get("exclude", []) for l in x.get("links", [])}
    except Exception: return set()
def tag(clusters):
    """Sets c['hub'] = {'k': 'show'|'event', 'slug', 'date', 'path'} on stories about a specific episode or event."""
    n = 0; ex = _excluded()
    for c in clusters:
        c.pop("hub", None)
        if ex and ({c.get("link")} | {u.get("link") for u in c.get("updates", [])}) & ex: continue
        if stale.reason(c): continue   # an old article re-dated by a feed is never attached to a current episode/event page
        if c.get("kind", {}).get("type") == "quote" and not EP_HINT.search(c.get("raw_title", "")): continue
        ev = event_for(c)
        if ev:
            c["hub"] = {"k": "event", "slug": ev["slug"], "date": ev["date"]}; n += 1; continue
        txt = text_of(c); title = c.get("raw_title", "") + " " + c.get("title", "")
        if c.get("kind", {}).get("type") == "quote" or NOT_TV.search(title): continue
        for show, rx in SHOW_RX.items():
            if SHOWS[show]["brand"] not in c.get("categories", []) or not rx.search(title): continue
            if not ((c.get("kind") or {}).get("type") in ("results", "match") or EP_HINT.search(title)): continue
            d = episode_for(show, c)
            if d: c["hub"] = {"k": "show", "slug": show, "date": d.isoformat()}; n += 1
            break
    return n
# ---------- URLs ----------
def ep_path(show, date, lang): return f"es/eventos/resultados-{show}-{date}/" if lang == "es" else f"events/{date}-{show}/"
def ev_path(ev, lang): return f"es/eventos/{ev['slug']}-{ev['date']}/" if lang == "es" else f"events/{ev['date']}-{ev['slug']}/"
def hub_path(show, lang): return f"es/programas/{show}/" if lang == "es" else f"shows/{show}/"
UP = {"en": "upcoming/", "es": "es/proximos-eventos/"}; SH = {"en": "shows/", "es": "es/programas/"}
def hub_link(c, lang):
    """(label, path) for a story's show/event page, used by story pages."""
    h = c.get("hub")
    if not h: return None
    if h["k"] == "event":
        ev = next((x for x in EVENTS if x["slug"] == h["slug"]), None)
        return (ev["name"], ev_path(ev, lang)) if ev else None
    d = _d(h["date"]); nm = SHOWS[h["slug"]]["name"]
    return (f"{nm} · {C.dlong(d, lang)}", ep_path(h["slug"], h["date"], lang))
# ---------- rendering ----------
L = {
 "en": {"results": "Results", "card": "Card & preview", "card_after": "Card & build-up", "more": "More news from this show", "more_ev": "More news about this event",
        "no_res": "Results will be added here after the show as trusted outlets report them.", "no_card": "No matches announced yet in our coverage. Check back as the card is announced.",
        "slot": "Regular slot", "date": "Date", "time": "Start", "where": "Venue", "watch": "Where to watch", "src": "Schedule source", "read": "Read full story →",
        "next": "Next episode", "latest": "Latest episode", "prev": "Previous episodes", "news": "Latest news", "stories": "stories", "story": "story",
        "all_shows": "All shows & events", "upcoming": "Upcoming events", "weekly": "Weekly shows", "ples": "Premium live events & PPVs", "past": "Recent events",
        "home": "Home", "shows": "Shows", "events": "Events", "aired": "Aired", "upcoming_badge": "Upcoming", "live_badge": "Tonight",
        "disclaimer": "Weekly shows are listed at their regular US broadcast slot; networks occasionally move or pre-empt episodes. Premium live events are listed only once announced by the promotion or a trusted outlet.",
        "ep_page": "Episode page →", "ev_page": "Event page →", "no_stories": "No coverage yet.", "updated": "Updated"},
 "es": {"results": "Resultados", "card": "Cartelera y previa", "card_after": "Cartelera y previa", "more": "Más noticias del programa", "more_ev": "Más noticias del evento",
        "no_res": "Los resultados se publicarán aquí después del programa, a medida que los reporten medios confiables.", "no_card": "Todavía no hay combates anunciados en nuestra cobertura. Vuelve pronto.",
        "slot": "Horario habitual", "date": "Fecha", "time": "Hora", "where": "Sede", "watch": "Dónde verlo", "src": "Fuente del calendario", "read": "Leer la noticia completa →",
        "next": "Próximo episodio", "latest": "Último episodio", "prev": "Episodios anteriores", "news": "Últimas noticias", "stories": "noticias", "story": "noticia",
        "all_shows": "Programas y eventos", "upcoming": "Próximos eventos de lucha libre", "weekly": "Programas semanales", "ples": "Eventos premium y PPV", "past": "Eventos recientes",
        "home": "Inicio", "shows": "Programas", "events": "Eventos", "aired": "Emitido", "upcoming_badge": "Próximamente", "live_badge": "Esta noche",
        "disclaimer": "Los programas semanales aparecen en su horario habitual de EE. UU. (hora del Este); a veces las cadenas los mueven o cancelan. Los eventos premium solo se incluyen cuando la empresa o un medio confiable los anuncia.",
        "ep_page": "Ver episodio →", "ev_page": "Ver evento →", "no_stories": "Aún no hay cobertura.", "updated": "Actualizado"},
}
def loc(c, lang, tr):
    """Localized view of a story: (title, summary, rel url, long paragraphs) or None if no Spanish translation yet."""
    if lang == "en": return {"t": c["title"], "s": c.get("summary") or "", "u": c["url"], "p": c.get("long") or [], "c": c}
    x = tr.get(c["id"]) if tr else None
    if not x or not x.get("url"): return None
    return {"t": x["t"], "s": x["s"], "u": x["url"], "p": x.get("p") or [], "c": c}
def item_html(s, lang, big=False):
    c = s["c"]; col = CATC.get(c["categories"][0], "#7cd618"); img = c.get("image") or ""
    th = f'<a class="hi-img" href="/{e(s["u"])}" style="background-image:url(\'{e(img)}\')" aria-hidden="true" tabindex="-1"></a>' if img else ""
    body = "".join(f"<p>{e(p)}</p>" for p in (s["p"][:2] if big else []))
    return (f'<article class="hi{" big" if big else ""}" style="--c:{col}">{th}<div><h3><a href="/{e(s["u"])}">{e(s["t"])}</a></h3>'
            f'<p class="hs">{e(s["s"])}</p>{body}<p class="hm">{when(c, lang)} · {e(c["source"])}</p></div></article>')
def when(c, lang):
    """First-reported time, plus last-update time when follow-up reports exist (cards sort by latest activity)."""
    f, u = c.get("first_ts", c["ts"]), c["ts"]
    a = f'<time datetime="{C.iso(f)}" data-ts="{int(f)}">{C.stamp(f, lang)}</time>'
    if c.get("updates") and u - f > 300:
        lab = ("Publicado ", " · actualizado ") if lang == "es" else ("First reported ", " · updated ")
        return f'{lab[0]}{a}{lab[1]}<time datetime="{C.iso(u)}" data-ts="{int(u)}">{C.stamp(u, lang)}</time>'
    return a
def classify(s):
    c = s["c"]; k = (c.get("kind") or {}).get("type"); txt = c.get("raw_title", "") + " " + c.get("title", "")
    if k == "results" or re.search(r"results?|recap|review|grades|spoilers?", txt, re.I): return "res"
    if k == "match" or PREV.search(txt): return "card"
    return "more"
def sections(stories, lang, aired, is_event=False):
    t = L[lang]; g = {"res": [], "card": [], "more": []}
    for s in stories: g[classify(s)].append(s)
    out = []
    res = "".join(item_html(s, lang, big=(i == 0)) for i, s in enumerate(g["res"]))
    card = "".join(item_html(s, lang) for s in g["card"])
    more = "".join(item_html(s, lang) for s in g["more"][:20])
    if aired:
        out.append(f'<section class="hsec" id="results"><h2>{t["results"]}</h2>{res or f"<p class=empty-note>{t["no_res"]}</p>"}</section>')
        if card: out.append(f'<section class="hsec" id="card"><h2>{t["card_after"]}</h2>{card}</section>')
    else:
        out.append(f'<section class="hsec" id="card"><h2>{t["card"]}</h2>{card or f"<p class=empty-note>{t["no_card"]}</p>"}</section>')
        if res: out.append(f'<section class="hsec" id="results"><h2>{t["results"]}</h2>{res}</section>')
    if more: out.append(f'<section class="hsec"><h2>{t["more_ev"] if is_event else t["more"]}</h2>{more}</section>')
    return "".join(out)
def facts(rows):
    return '<dl class="facts">' + "".join(f"<div><dt>{e(k)}</dt><dd>{v}</dd></div>" for k, v in rows if v) + "</dl>"
def page(path, lang, title, desc, h1, body, crumbs, ld, alt, active="shows", image=None):
    url = SITE + path; t = C.T[lang]
    en_url = "/" + (alt.get("en") or "").replace(SITE, "") if alt.get("en") else "/"
    es_url = "/" + (alt.get("es") or "").replace(SITE, "") if alt.get("es") else "/es/"
    html_ = (C.head(title, desc, url, lang, alts=alt, ld=ld + [C.breadcrumbs(crumbs)], image=image, ads=True) +
             f'<body class="hub-page"><div class="spot s1"></div><div class="spot s2"></div>{C.header(lang, en_url, es_url, active)}'
             f'<main class="hub">{C.crumbs_html(crumbs)}<h1>{h1}</h1>{body}</main>{C.footer(lang)}{C.SCRIPTS}</body></html>')
    write(path, html_)
    return url
_WRITTEN = {}
def write(path, s):
    full = os.path.join(BUILD, path, "index.html") if path.endswith("/") else os.path.join(BUILD, path)
    os.makedirs(os.path.dirname(full), exist_ok=True); open(full, "w").write(s)
    _WRITTEN[path] = hashlib.md5(re.sub(r'datetime="[^"]*"', "", s).encode()).hexdigest()[:10]
BUILD = PUB
def sports_event(name, d, hhmm, path, brand, status, venue=None, city=None, desc=None, lang="en", show=None):
    ev = {"@context": "https://schema.org", "@type": "SportsEvent", "name": name, "url": SITE + path, "sport": "Professional wrestling",
          "startDate": start_dt(d, hhmm).isoformat() if hhmm else d.isoformat(), "eventStatus": "https://schema.org/EventScheduled",
          "organizer": {"@type": "SportsOrganization", "name": brand if brand != "Global" else name.split()[0]}, "inLanguage": lang}
    if venue: ev["location"] = {"@type": "Place", "name": venue, "address": {"@type": "PostalAddress", "addressLocality": city}}
    else:
        ev["eventAttendanceMode"] = "https://schema.org/OnlineEventAttendanceMode"
        ev["location"] = {"@type": "VirtualLocation", "url": SITE + path}
    if desc: ev["description"] = desc
    return ev
def itemlist(stories, lang):
    return {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "url": SITE + s["u"], "name": s["t"]} for i, s in enumerate(stories[:30])]}
def show_desc(show, lang):
    s = SHOWS[show]; h, m = _hm(s["time"])
    if lang == "es": return f'{s["name"]} se emite {C.DIAS_PL[s["weekday"]]} a las {C.tfmt(h, m, lang)} por {s["network"]} (EE. UU.).'
    return f'{s["name"]} airs {C.DAYS_PL[s["weekday"]]} at {C.tfmt(h, m, lang)} on {s["network"]} (US).'
def _isod(ts): return datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime("%Y-%m-%d")
def _isot(ts): return datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).isoformat(timespec="seconds")
def cite(key, path, title, st, lang, aired=True, extra_src=None):
    """'Cite this page' block for wiki editors + WebPage JSON-LD (datePublished/dateModified/citation). -> (html, [ld]) or ('', []).
    Published = first live result or first story on the page (stable); updated = latest live update or story change.
    Sources = every outlet behind the live results and the stories listed (name + link)."""
    lv = LIVE.page_state(key) if LIVE else None
    if not aired and not (lv and lv.get("shown")): return "", []   # previews aren't results: no citation block yet
    pubs, mods, src = [], [], []
    if lv and lv.get("shown"):
        pubs.append(min(int(m["first_seen"]) for m in lv["shown"])); mods.append(int(lv.get("updated") or lv.get("checked") or lv["start"]))
        for m in lv["shown"]: src += [(x.get("name"), x.get("url")) for x in m.get("sources", [])]
    for x in st:
        c = x["c"]; pubs.append(int(c.get("first_ts", c["ts"]))); mods.append(int(c["ts"]))
        src += [(c.get("source"), c.get("link"))] + [(u.get("source"), u.get("link")) for u in c.get("updates", [])]
    if not pubs: return "", []
    if lv and lv.get("shown"): pubs = [int(lv["start"])]   # results page: published when the show's live coverage began (matches LiveBlogPosting)
    else:
        d0 = datetime.datetime.strptime(key[:10], "%Y-%m-%d").replace(tzinfo=ET).timestamp()
        pubs = [p for p in pubs if p >= d0] or pubs          # results/coverage of the night itself, not earlier preview stories
    if extra_src: src.append(extra_src)
    seen, out = set(), []
    for n, u in src:
        if n and u and u.startswith("http") and u not in seen: seen.add(u); out.append((n, u))
    out = out[:40]; pub, mod = min(pubs), max(mods + pubs); url = SITE + path
    es = lang == "es"; tt = re.sub(r"\s*\|\s*WCN$", "", title)
    tt = re.sub(r"^LIVE:\s*", "", re.sub(r"^EN VIVO: resultados de\s+", "Resultados ", tt))   # stable citation title (no live prefix)
    cw = (f"{{{{cite web |url={url} |title={tt} |website=Wrestling Central News |date={_isod(pub)}"
          + (f" |language=es" if es else "") + "}}")
    lab = {"h": "Citar esta página", "t": "Título", "p": "Publicado", "u": "Actualizado", "l": "Enlace permanente", "s": "Fuentes originales", "w": "Plantilla de wiki"} if es else \
          {"h": "Cite this page", "t": "Title", "p": "Published", "u": "Last updated", "l": "Permanent URL", "s": "Original sources", "w": "Wiki template"}
    by = {}
    for n, u in out: by.setdefault(n, []).append(u)
    srcs = "".join(f'<li><b>{e(n)}</b>: ' + ", ".join(f'<a href="{e(u)}" rel="nofollow noopener" target="_blank">{e(re.sub(r"^https?://(www[.])?", "", u)[:70])}</a>' for u in us) + "</li>" for n, us in by.items())
    h = (f'<section class="cite" id="cite"><h2>{lab["h"]}</h2><dl>'
         f'<div><dt>{lab["t"]}</dt><dd>{e(tt)}</dd></div><div><dt>{"Publicación" if es else "Publisher"}</dt><dd>Wrestling Central News (WCN)</dd></div>'
         f'<div><dt>{lab["p"]}</dt><dd><time datetime="{_isot(pub)}">{_isod(pub)}</time></dd></div>'
         f'<div><dt>{lab["u"]}</dt><dd><time datetime="{_isot(mod)}">{_isod(mod)}</time></dd></div>'
         f'<div><dt>{lab["l"]}</dt><dd><a href="{e(url)}">{e(url)}</a></dd></div></dl>'
         f'<p class="cite-w"><small>{lab["w"]}:</small><code>{e(cw)}</code></p>'
         + (f'<h3>{lab["s"]}</h3><ul class="cite-src">{srcs}</ul>' if srcs else "") + "</section>")
    ld = {"@context": "https://schema.org", "@type": "WebPage", "name": tt, "url": url, "inLanguage": lang, "datePublished": _isot(pub), "dateModified": _isot(mod),
          "publisher": {"@type": "Organization", "name": "Wrestling Central News", "url": SITE, "logo": {"@type": "ImageObject", "url": SITE + "logo.png"}},
          "citation": [{"@type": "CreativeWork", "name": n, "url": u} for n, u in out]}
    return h, [ld]
LIVE_PAGES = {}
def _live_desc(st, nm, dl, lang):
    """Search snippet for a page with live results: the show plus the first reported results (concrete, not 'card and preview')."""
    es = lang == "es"
    lines = [re.sub(r"\s+", " ", (m.get("es") if es else m.get("en")) or "").strip().rstrip(".") for m in st["shown"]]
    lines = [x for x in lines if x]
    if st["is_live"]: lead = f"Resultados en vivo de {nm} ({dl})" if es else f"{nm} live results ({dl})"
    else: lead = f"Resultados de {nm} ({dl})" if es else f"{nm} results ({dl})"
    s = lead + (": " if lines else ". ")
    for x in lines:
        if len(s) + len(x) + 2 > 150: break
        s += x + "; "
    s = s.rstrip("; ").rstrip(":")
    tail = (" y más." if es else " and more.") if lines and len(s) < 150 else "."
    return s + tail if len(s + tail) <= 160 else s
def _live(key, lang, path, nm, dl, title, h1, body, ld, desc=None, img=None):
    """Turn an event/episode page into a live results post (LIVE badge + match list + LiveBlogPosting) when we have live data.
    Returns (title, h1, body, ld, desc): desc names the reported results once there are any."""
    try: r = LIVE.render(key, lang, SITE + path)
    except Exception as ex: print("[live] render failed", key, ex, flush=True); r = None
    if not r: return title, h1, body, ld, desc
    badge, sec, lld = r
    st = LIVE.page_state(key)
    for x in lld:   # Google wants an image on LiveBlogPosting for rich results: the page's story photo, else the 1200x630 site card
        if x.get("@type") == "LiveBlogPosting" and not x.get("image"): x["image"] = [img if (img or "").startswith("https://") else SITE + "og-image.jpg"]
    if st["shown"] or st["is_live"]:
        try: desc = _live_desc(st, nm, dl, lang)
        except Exception as ex: print("[live] desc failed", key, repr(ex)[:120], flush=True)
    if st["is_live"]:
        title = (f"EN VIVO: resultados de {nm} ({dl})" if lang == "es" else f"LIVE: {nm} Results ({dl})")
        LIVE_PAGES.setdefault(key, {})[lang] = path
        sm = re.search(r"<small>.*</small>", h1)
        h1 = (f"Resultados en vivo de {e(nm)}" if lang == "es" else f"{e(nm)} Live Results") + (" " + sm.group(0) if sm else "")
    elif st["shown"]:
        title = (f"Resultados {nm} ({dl})" if lang == "es" else f"{nm} Results ({dl})")
    return title, badge + h1, sec + body, ld + lld, desc
def build(clusters, tr_es=None):
    """Write all hub pages for en + es. Returns {path: content-hash} for sitemaps/IndexNow."""
    import shutil
    global BUILD
    _WRITTEN.clear(); LIVE_PAGES.clear()
    now = datetime.datetime.now(ET); today = now.date(); cutoff = today - datetime.timedelta(days=RETENTION_DAYS)
    by_ep, by_ev = {}, {}
    for c in clusters:
        h = c.get("hub")
        if not h: continue
        (by_ev if h["k"] == "event" else by_ep).setdefault((h["slug"], h["date"]) if h["k"] == "show" else h["slug"], []).append(c)
    for f in (os.listdir(LIVE.LIVE_DIR) if os.path.isdir(LIVE.LIVE_DIR) else []):   # live-results episodes even before any story is tagged
        k = f[:-5]; ds, show = k[:10], k[11:]
        if f.endswith(".json") and show in SHOWS: by_ep.setdefault((show, ds), [])
    stage = os.path.join(ROOT, ".hubs.new"); shutil.rmtree(stage, ignore_errors=True); BUILD = stage
    for lang in ("en", "es"):
        t = L[lang]; T = C.T[lang]
        home = (t["home"], SITE + T["home"].lstrip("/")); shows_c = (T["shows"], SITE + SH[lang])
        def L_(cs): 
            out = [loc(c, lang, tr_es) for c in sorted(cs, key=lambda x: -x.get("first_ts", x["ts"]))]
            return [x for x in out if x]
        # ---- per-episode pages ----
        eps = {}
        for (show, ds), cs in by_ep.items():
            d = _d(ds)
            if d < cutoff: continue
            st = L_(cs)
            if not st and not LIVE.page_state(f"{ds}-{show}"): continue
            info = airings(show, d, d).get(d) or {"time": SHOWS[show]["time"], "network": SHOWS[show]["network"], "note": None, "note_es": None}
            aired = now > start_dt(d, info["time"]) + datetime.timedelta(hours=2, minutes=30)
            nm = SHOWS[show]["name"]; dl = C.dlong(d, lang); h, m = _hm(info["time"])
            if lang == "es":
                title = f"Resultados {nm} ({dl})" if aired else f"{nm} ({dl}): cartelera y previa"
                h1 = f"Resultados de {nm} <small>{C.dfull(d, lang)}</small>" if aired else f"{nm}: cartelera y previa <small>{C.dfull(d, lang)}</small>"
                desc = (f"Resultados de {nm} del {dl}: ganadores, momentos clave y todas las noticias del episodio en Wrestling Central News." if aired
                        else f"Cartelera y previa de {nm} del {dl}: combates anunciados, horario ({C.tfmt(h, m, lang)}) y noticias del episodio.")
            else:
                title = f"{nm} Results ({dl})" if aired else f"{nm} Card & Preview ({dl})"
                h1 = f"{nm} Results <small>{C.dfull(d, lang)}</small>" if aired else f"{nm} Card &amp; Preview <small>{C.dfull(d, lang)}</small>"
                desc = (f"{nm} results for {dl}: winners, key moments and every WCN story from the episode." if aired
                        else f"{nm} card and preview for {dl}: announced matches, start time ({C.tfmt(h, m, lang)}) and the latest news before the show.")
            path = ep_path(show, ds, lang); alt = {"en": SITE + ep_path(show, ds, "en"), "es": SITE + ep_path(show, ds, "es")}
            if lang == "en" and not L_es_has(cs, tr_es): alt.pop("es")
            if lang == "es": pass
            note = info.get("note_es" if lang == "es" else "note")
            fx = facts([(t["date"], e(C.dfull(d, lang))), (t["time"], e(C.tfmt(h, m, lang))), (t["watch"], e(info["network"] + " (US)")), ("", e(note) if note else None)])
            body = (f'<p class="lede">{e(show_desc(show, lang))} <a href="/{hub_path(show, lang)}">{e(nm)} →</a></p>{fx}' + sections(st, lang, aired))
            crumbs = [home, shows_c, (nm, SITE + hub_path(show, lang)), (dl, SITE + path)]
            ld = [sports_event(f"{nm} ({dl})", d, info["time"], path, SHOWS[show]["brand"], aired, desc=desc, lang=lang), itemlist(st, lang)]
            img = next((s["c"].get("image") for s in st if (s["c"].get("image") or "").startswith("https://")), None)
            title, h1, body, ld, desc = _live(f"{ds}-{show}", lang, path, nm, dl, title, h1, body, ld, desc=desc, img=img)
            ch, cl = cite(f"{ds}-{show}", path, title, st, lang, aired); body += ch; ld = ld + cl
            page(path, lang, title + " | WCN", desc, h1, body, crumbs, ld, alt, image=img)
            eps.setdefault(show, []).append((d, path, len(st), aired, st))
        # ---- PLE / PPV event pages ----
        evs = []
        for ev in EVENTS:
            d = _d(ev["date"])
            if d < cutoff: continue
            st = L_(by_ev.get(ev["slug"], []))
            hhmm = ev.get("time"); aired = now > (start_dt(d, hhmm) + datetime.timedelta(hours=4) if hhmm else datetime.datetime(d.year, d.month, d.day, 23, 59, tzinfo=ET) + datetime.timedelta(hours=1))
            nm = ev["name"]; dl = C.dlong(d, lang)
            if lang == "es":
                title = f"Resultados {nm} ({dl})" if aired else f"{nm}: cartelera, fecha y hora ({dl})"
                h1 = (f"Resultados de {e(nm)}" if aired else f"{e(nm)}: cartelera y previa") + f" <small>{C.dfull(d, lang)}</small>"
                desc = (f"Resultados de {nm} ({dl}, {ev['city']}): ganadores y todas las noticias del evento." if aired
                        else f"{nm}: fecha ({dl}), sede ({ev['venue']}, {ev['city']}), cartelera y noticias rumbo al evento.")
            else:
                title = f"{nm} Results ({dl})" if aired else f"{nm} Card, Date & Start Time ({dl})"
                h1 = (f"{e(nm)} Results" if aired else f"{e(nm)} Card &amp; Preview") + f" <small>{C.dfull(d, lang)}</small>"
                desc = (f"{nm} results ({dl}, {ev['city']}): winners and every WCN story from the event." if aired
                        else f"{nm}: date ({dl}), venue ({ev['venue']}, {ev['city']}), announced card and the latest news.")
            path = ev_path(ev, lang); alt = {"en": SITE + ev_path(ev, "en"), "es": SITE + ev_path(ev, "es")}
            tm = None
            if hhmm: h, m = _hm(hhmm); tm = e(C.tfmt(h, m, lang))
            fx = facts([(t["date"], e(C.dfull(d, lang))), (t["time"], tm), (t["where"], e(f"{ev['venue']}, {ev['city']}")), (t["watch"], e(ev.get("network"))),
                        (t["src"], f'<a href="{e(ev["source"])}" rel="nofollow noopener" target="_blank">{e(re.sub(r"^https?://(www\.)?", "", ev["source"]).split("/")[0])}</a>')])
            body = fx + sections(st, lang, aired, is_event=True)
            crumbs = [home, (t["events"], SITE + UP[lang]), (nm, SITE + path)]
            ld = [sports_event(nm, d, hhmm, path, ev["brand"], aired, ev["venue"], ev["city"], desc, lang)] + ([itemlist(st, lang)] if st else [])
            img = next((s["c"].get("image") for s in st if (s["c"].get("image") or "").startswith("https://")), None)
            title, h1, body, ld, desc = _live(f"{ev['date']}-{ev['slug']}", lang, path, nm, dl, title, h1, body, ld, desc=desc, img=img)
            ch, cl = cite(f"{ev['date']}-{ev['slug']}", path, title, st, lang, aired); body += ch; ld = ld + cl
            page(path, lang, title + " | WCN", desc, h1, body, crumbs, ld, alt, active="upcoming", image=img)
            evs.append((ev, d, path, len(st), aired))
        # ---- evergreen show hubs ----
        idx_rows = []
        for show, s in SHOWS.items():
            mine = sorted(eps.get(show, []), key=lambda x: x[0], reverse=True)
            nxt = next(iter(airings(show, today, today + datetime.timedelta(days=13)).items()), None)
            nm = s["name"]; path = hub_path(show, lang)
            latest = next((x for x in mine if x[3]), None) or (mine[0] if mine else None)
            # latest-news list: tagged episodes first, then other recent stories naming the show
            rx = SHOW_RX[show]
            extra = [c for c in clusters if s["brand"] in c.get("categories", []) and rx.search(c.get("raw_title", "") + " " + c.get("title", ""))]
            news = [x for x in (loc(c, lang, tr_es) for c in extra[:40]) if x][:12]
            parts = [f'<p class="lede">{e(show_desc(show, lang))}</p>']
            if nxt:
                d, info = nxt; h, m = _hm(info["time"])
                nlink = next((p for (dd, p, *_r) in mine if dd == d), None)
                parts.append(f'<div class="next"><b>{t["next"]}:</b> {e(C.dfull(d, lang))} · {e(C.tfmt(h, m, lang))} · {e(info["network"])}'
                             + (f' · <a href="/{nlink}">{t["ep_page"]}</a>' if nlink else "") + "</div>")
            if latest:
                d, p, n, aired, st = latest
                lab = (f"Resultados de {nm}" if lang == "es" else f"{nm} Results") if aired else (f"{nm}: cartelera y previa" if lang == "es" else f"{nm} Card & Preview")
                parts.append(f'<section class="latest"><h2>{t["latest"]}: <a href="/{p}">{e(lab)} · {e(C.dlong(d, lang))}</a></h2>{sections(st, lang, aired)}</section>')
            if len(mine) > 1 or (mine and latest is not mine[0]):
                parts.append(f'<section class="hsec"><h2>{t["prev"]}</h2><ul class="eplist">' + "".join(
                    f'<li><a href="/{p}">{e(nm)} · {e(C.dfull(d, lang))}</a> <span>{n} {t["stories"] if n != 1 else t["story"]}</span></li>' for d, p, n, a, _ in mine if (d, p) != (latest[0], latest[1])) + "</ul></section>")
            if news: parts.append(f'<section class="hsec"><h2>{t["news"]}: {e(nm)}</h2>' + "".join(item_html(x, lang) for x in news) + "</section>")
            if lang == "es":
                title = f"{nm}: resultados, cartelera y noticias | WCN"; h1 = f"{e(nm)}: resultados, cartelera y noticias"
                desc = f"Resultados de {nm} cada semana, cartelera del próximo episodio y las últimas noticias. {show_desc(show, lang)}"
            else:
                title = f"{nm} Results, Card & News | WCN"; h1 = f"{e(nm)} Results, Card &amp; News"
                desc = f"Latest {nm} results, the card for the next episode and all the news. {show_desc(show, lang)}"
            alt = {"en": SITE + hub_path(show, "en"), "es": SITE + hub_path(show, "es")}
            crumbs = [home, shows_c, (nm, SITE + path)]
            ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": title.replace(" | WCN", ""), "url": SITE + path, "inLanguage": lang,
                   "about": {"@type": "TVSeries", "name": nm}, "publisher": C.PUBLISHER}]
            if nxt: ld.append(sports_event(f"{nm} ({C.dlong(nxt[0], lang)})", nxt[0], nxt[1]["time"], path, s["brand"], False, lang=lang))
            page(path, lang, title, desc, h1, "".join(parts), crumbs, ld, alt)
            idx_rows.append((show, nm, path, nxt, len(mine)))
        # ---- /shows/ index ----
        rows = "".join(f'<li style="--c:{CATC[SHOWS[sh]["brand"]]}"><a href="/{p}"><b>{e(nm)}</b><span>{e(show_desc(sh, lang))}</span>'
                       + (f'<em>{t["next"]}: {e(C.dfull(n[0], lang))}</em>' if n else "") + "</a></li>" for sh, nm, p, n, k in idx_rows)
        evl = "".join(f'<li style="--c:{CATC.get(ev["brand"], "#7cd618")}"><a href="/{p}"><b>{e(ev["name"])}</b><span>{e(C.dfull(d, lang))} · {e(ev["city"])}</span>'
                      f'<em>{t["aired"] if a else t["upcoming_badge"]}{f" · {n} {t["stories"]}" if n else ""}</em></a></li>' for ev, d, p, n, a in evs)
        path = SH[lang]
        if lang == "es":
            title = "Programas de lucha libre: WWE Raw, SmackDown, NXT, AEW Dynamite, Collision y TNA iMPACT | WCN"; h1 = "Programas y eventos"
            desc = "Resultados y carteleras de WWE Raw, SmackDown, NXT, AEW Dynamite, AEW Collision, TNA iMPACT y de los eventos premium y PPV."
        else:
            title = "Wrestling Shows: WWE Raw, SmackDown, NXT, AEW Dynamite, Collision & TNA iMPACT | WCN"; h1 = "Shows &amp; Events"
            desc = "Results and cards for WWE Raw, SmackDown, NXT, AEW Dynamite, AEW Collision, TNA iMPACT and every premium live event and PPV."
        body = f'<section class="hsec"><h2>{t["weekly"]}</h2><ul class="showgrid">{rows}</ul></section><section class="hsec"><h2>{t["ples"]}</h2><ul class="showgrid">{evl}</ul></section>'
        page(path, lang, title, desc, h1, body, [home, shows_c], [], {"en": SITE + SH["en"], "es": SITE + SH["es"]})
        # ---- /upcoming/ schedule ----
        sched = {}
        for show in SHOWS:
            for d, info in airings(show, today, today + datetime.timedelta(days=13)).items():
                sched.setdefault(d, []).append(("show", show, info))
        for show, lst in CFG.get("skips", {}).items():
            for x in lst:
                d = _d(x["date"])
                if today <= d <= today + datetime.timedelta(days=13): sched.setdefault(d, []).append(("skip", show, x))
        for ev, d, p, n, a in evs:
            if d >= today: sched.setdefault(d, []).append(("event", ev, p))
        rows = []
        lds = []
        for d in sorted(sched):
            lis = []
            for kind, k, info in sorted(sched[d], key=lambda x: (x[0] != "event", (x[2].get("time") if isinstance(x[2], dict) else "") or "")):
                if kind == "event":
                    ev = k; tm = ""
                    if ev.get("time"): h, m = _hm(ev["time"]); tm = C.tfmt(h, m, lang)
                    lis.append(f'<li class="ple" style="--c:{CATC.get(ev["brand"], "#7cd618")}"><span class="tm">{e(tm) or "—"}</span><a href="/{info}"><b>{e(ev["name"])}</b></a>'
                               f'<span class="wh">{e(ev["venue"])}, {e(ev["city"])}{" · " + e(ev["network"]) if ev.get("network") else ""}</span></li>')
                    lds.append(sports_event(ev["name"], d, ev.get("time"), info, ev["brand"], False, ev["venue"], ev["city"], lang=lang))
                elif kind == "skip":
                    lis.append(f'<li class="skip"><span class="tm">—</span><b>{e(SHOWS[k]["name"])}</b><span class="wh">{e(info.get("note_es" if lang == "es" else "note"))}</span></li>')
                else:
                    h, m = _hm(info["time"]); has = next((p for (dd, p, *_r) in eps.get(k, []) if dd == d), None)
                    nm = SHOWS[k]["name"]
                    lab = f'<a href="/{has}"><b>{e(nm)}</b></a>' if has else f'<a href="/{hub_path(k, lang)}"><b>{e(nm)}</b></a>'
                    note = info.get("note_es" if lang == "es" else "note")
                    lis.append(f'<li style="--c:{CATC[SHOWS[k]["brand"]]}"><span class="tm">{e(C.tfmt(h, m, lang))}</span>{lab}<span class="wh">{e(info["network"])}{" · " + e(note) if note else ""}</span></li>')
            rows.append(f'<section class="day"><h2>{e(C.dfull(d, lang))}</h2><ul class="sched">{"".join(lis)}</ul></section>')
        later = [(ev, d, p) for ev, d, p, n, a in evs if d > today + datetime.timedelta(days=13)]
        if later:
            rows.append(f'<section class="day"><h2>{t["ples"]}</h2><ul class="sched">' + "".join(
                f'<li class="ple" style="--c:{CATC.get(ev["brand"], "#7cd618")}"><span class="tm">{e(C.dlong(d, lang))}</span><a href="/{p}"><b>{e(ev["name"])}</b></a><span class="wh">{e(ev["venue"])}, {e(ev["city"])}</span></li>' for ev, d, p in later) + "</ul></section>")
            for ev, d, p in later: lds.append(sports_event(ev["name"], d, ev.get("time"), p, ev["brand"], False, ev["venue"], ev["city"], lang=lang))
        past = [(ev, d, p, n) for ev, d, p, n, a in evs if a]
        if past: rows.append(f'<section class="day"><h2>{t["past"]}</h2><ul class="sched">' + "".join(
            f'<li class="ple" style="--c:{CATC.get(ev["brand"], "#7cd618")}"><span class="tm">{e(C.dlong(d, lang))}</span><a href="/{p}"><b>{e(ev["name"])}</b></a><span class="wh">{t["results"]}{f" · {n} {t["stories"]}" if n else ""}</span></li>' for ev, d, p, n in past) + "</ul></section>")
        path = UP[lang]
        if lang == "es":
            title = "Próximos eventos de lucha libre: calendario WWE, AEW y TNA | WCN"; h1 = "Próximos eventos"
            desc = "Calendario de lucha libre: WWE Raw, SmackDown, NXT, AEW Dynamite, Collision, TNA iMPACT y los próximos eventos premium y PPV, con fecha, hora (ET) y sede."
        else:
            title = "Upcoming Wrestling Events & TV Schedule: WWE, AEW, TNA | WCN"; h1 = "Upcoming Events"
            desc = "Wrestling schedule: WWE Raw, SmackDown, NXT, AEW Dynamite, Collision, TNA iMPACT and upcoming premium live events and PPVs with date, time (ET) and venue."
        body = f'<p class="lede">{t["disclaimer"]}</p>' + "".join(rows)
        page(path, lang, title, desc, h1, body, [home, (t["upcoming"] if lang == "en" else T["upcoming"], SITE + path)], lds[:40],
             {"en": SITE + UP["en"], "es": SITE + UP["es"]}, active="upcoming")
    _gone_stubs(now)
    # swap staged dirs in atomically-ish (old episode pages beyond retention disappear = same pruning as stories)
    for rel in ("shows", "events", "upcoming", "es/programas", "es/eventos", "es/proximos-eventos"):
        src = os.path.join(stage, rel); dst = os.path.join(PUB, rel)
        shutil.rmtree(dst, ignore_errors=True)
        if os.path.exists(src): os.makedirs(os.path.dirname(dst), exist_ok=True); os.replace(src, dst)
    shutil.rmtree(stage, ignore_errors=True); BUILD = PUB
    return dict(_WRITTEN)
HUB_SEEN = os.path.join(ROOT, "data", "hub_paths.json")   # {event/episode path: last ts it was built}
def gone_target(path):
    """Where a vanished event/episode page goes: its weekly show hub, else the upcoming-events page."""
    m = re.fullmatch(r"es/eventos/resultados-(.+)-\d{4}-\d{2}-\d{2}/", path)
    if m: return hub_path(m.group(1), "es") if m.group(1) in SHOWS else UP["es"]
    m = re.fullmatch(r"events/\d{4}-\d{2}-\d{2}-(.+)/", path)
    if m: return hub_path(m.group(1), "en") if m.group(1) in SHOWS else UP["en"]
    return UP["es"] if path.startswith("es/") else UP["en"]
def _gone_stubs(now):
    """Event/episode pages that were published before but are not built this run (no tagged story or live results left)
    get a redirect stub to their show hub for RETENTION_DAYS after they were last built, instead of a 404. Stubs are
    written straight to the stage dir, never through write(), so they never enter sitemaps or IndexNow."""
    try: seen = json.load(open(HUB_SEEN))
    except Exception: seen = {}
    try: seen.update({p: seen.get(p, 0) or int(time.time()) for p in json.load(open(os.path.join(ROOT, "legacy_urls.json"))).get("hub", [])})
    except Exception: pass
    ts = int(time.time()); keep = {}
    for p in _WRITTEN:
        if p.startswith(("events/", "es/eventos/")): keep[p] = ts
    for p, t in seen.items():
        if p in keep or ts - t > RETENTION_DAYS * 86400 or not p.startswith(("events/", "es/eventos/")): continue
        keep[p] = t
        full = os.path.join(BUILD, p, "index.html")
        if not os.path.exists(full):
            os.makedirs(os.path.dirname(full), exist_ok=True); open(full, "w").write(stub_html(gone_target(p)))
    os.makedirs(os.path.dirname(HUB_SEEN), exist_ok=True); json.dump(keep, open(HUB_SEEN, "w"))
def stub_html(to):
    t = SITE + to
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>Moved | Wrestling Central News</title>'
            f'<link rel="canonical" href="{e(t)}"><meta http-equiv="refresh" content="0; url=/{e(to)}">'
            f'<script>location.replace("/{e(to)}")</script></head><body><p>This page moved: <a href="/{e(to)}">{e(t)}</a></p></body></html>')
def L_es_has(cs, tr): return bool(tr) and any(c["id"] in tr and tr[c["id"]].get("url") for c in cs)
