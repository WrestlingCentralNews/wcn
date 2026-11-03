"""Owner request pt588u (2026-11-02): three data pages built from verified seeds + WCN's own final results.
  /champions/      current champions (WWE Raw/SmackDown/NXT, AEW, TNA, AAA): champion, reign start, days held (at build), source.
  /history/ple/    one row per PLE/PPV edition by year: date, venue, main event, winner, link to WCN's event page.
  /records/2026/   2026 win/loss/draw per wrestler, TV vs big events, only from matches WCN reported (noindex until enough data).
Title changes are applied only when every guard in title_change() passes; anything else goes to data/champ_flags.json (never guessed).
Stateless: everything is recomputed each build from champions.json, ple_history.json, events.json, full_cards.json and data/live/*.json."""
import os, re, json, glob, html, datetime, unicodedata
import chrome, timeline
ROOT = os.path.dirname(os.path.abspath(__file__)); PUB = os.path.join(ROOT, "public"); SITE = "https://wrestlingcentralnews.com/"
LIVE = os.path.join(ROOT, "data", "live"); FLAGS = os.path.join(ROOT, "data", "champ_flags.json")
e = lambda s: html.escape(s or "", quote=True)
PATHS = {"champions": "champions/", "ple": "history/ple/", "records": "records/2026/"}
RECORDS_INDEX_MIN = 300           # matches counted before /records/2026/ becomes indexable
TRUSTED = ("fightful.com", "pwinsider.com", "wwe.com", "allelitewrestling.com", "tnawrestling.com", "luchalibreaaa.com")
BAD_FIN = re.compile(r"disqualif|\bdq\b|count.?out|no contest|draw", re.I)
NOT_TITLE = re.compile(r"eliminator|contender|#\s*1|number one|no\. ?1|\bshot\b|qualif|tournament|briefcase|non.?title", re.I)

def today():
    try:
        from zoneinfo import ZoneInfo; return datetime.datetime.now(ZoneInfo("America/Puerto_Rico")).date()
    except Exception: return datetime.date.today()
def jload(p, d=None):
    try: return json.load(open(p))
    except Exception: return d
def fold(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s.replace("’", "'")).strip()
def lives():
    out = []
    for f in sorted(glob.glob(os.path.join(LIVE, "*.json"))):
        d = jload(f)
        if isinstance(d, dict) and d.get("date") and isinstance(d.get("matches"), list): out.append(d)
    return sorted(out, key=lambda d: (d["date"], d.get("start") or 0))
def good(m): return m.get("confirmed") is True and not m.get("conflict") and (m.get("winner") or "").strip() and (m.get("loser") or "").strip()

# ---------------- people ----------------
def members(side):
    """'The Vision (Bron Breakker & Austin Theory) & X' -> ['Bron Breakker','Austin Theory','X']; a team with no listed members stays one entry."""
    side = (side or "").replace("’", "'").strip()
    out = []
    for grp in re.findall(r"\(([^()]*)\)", side): out += split(grp)
    rest = re.sub(r"[^,&()]*\([^()]*\)", "|", side)          # drop 'Team (a & b)' chunks (members already taken)
    for chunk in rest.split("|"): out += split(chunk)
    seen, res = set(), []
    for n in out:
        k = fold(n)
        if k and k not in seen: seen.add(k); res.append(n)
    return res
def split(s):
    parts = re.split(r"\s*,\s*|\s+&\s+|\s+and\s+|\s*/\s*", s or "")
    return [re.sub(r"^(and|&)\s+", "", p).strip(" .,") for p in parts if p and p.strip(" .,&") and not re.fullmatch(r"\s*(and|&)\s*", p)]

# ---------------- champions ----------------
def title_for(stip, promo, titles):
    s = fold(stip)
    hits = [t for t in titles if t["promo"] == promo and any(re.search(p, s) for p in t["match"]) and not any(re.search(p, s) for p in t.get("not", []))]
    return hits
def headline_ok(winner, date, arts):
    """A trusted outlet's headline within ~2 days that names the winner and says they won a title (not a shot/eliminator)."""
    try: t0 = datetime.datetime.fromisoformat(date).replace(tzinfo=datetime.timezone.utc).timestamp()
    except Exception: return None
    keys = [fold(n).split()[-1] for n in members(winner)] + [fold(winner)]
    keys = [k for k in keys if len(k) >= 3]
    for a in arts or []:
        host = re.sub(r"^https?://(www\.)?", "", a.get("link") or "").split("/")[0]
        if not any(host == h or host.endswith("." + h) for h in TRUSTED): continue
        try: ts = float(a.get("ts") or 0)
        except Exception: continue
        if not (t0 - 86400 <= ts <= t0 + 3 * 86400): continue
        h = fold(a.get("title"))
        if not any(re.search(r"\b" + re.escape(k) + r"\b", h) for k in keys): continue
        if re.search(r"\b(shot|contender|eliminator|retain|retains|defend|defends)\b", h): continue
        if re.search(r"\b(win|wins|won|capture|captures|crowned|new champion|dethrone|dethrones|regain|regains|become|becomes)\b", h) and re.search(r"\b(title|titles|championship|champion|champions)\b", h):
            return a.get("link")
    return None
def title_change(show, m, titles, champ, arts):
    """-> (title, None) when the change is applied, (None, reason) when it is flagged, (None, None) when it is not a change at all."""
    if m.get("title") != "change": return None, None
    if not good(m): return None, "unconfirmed or conflicting result"
    if BAD_FIN.search(m.get("fin_en") or ""): return None, "finish was DQ/count-out/no contest (titles do not change hands)"
    stip = m.get("stip") or ""
    if NOT_TITLE.search(stip): return None, "stipulation is a contender/eliminator match"
    hits = title_for(stip, show.get("brand"), titles)
    if len(hits) != 1: return None, f"stipulation maps to {len(hits)} titles"
    t = hits[0]; cur = champ[t["id"]]
    if show["date"] < cur["since"]: return None, "result predates the current reign"
    if fold(m["winner"]) == fold(cur["champion"]) or set(map(fold, members(m["winner"]))) == set(map(fold, cur.get("members") or [cur["champion"]])):
        return None, (None if show["date"] == cur["since"] else "winner is already the champion")
    src = headline_ok(m["winner"], show["date"], arts)
    if not src: return None, "no trusted headline confirms a new champion"
    return dict(t, _src=src), None
def champions_state(titles, shows, arts):
    champ = {t["id"]: dict(t) for t in titles}; flags = []
    for d in shows:
        for m in sorted(d["matches"], key=lambda m: m.get("order") or 0):
            t, why = title_change(d, m, titles, champ, arts)
            if t:
                mm = members(m["winner"])
                champ[t["id"]] = dict(champ[t["id"]], champion=m["winner"], members=mm if len(mm) > 1 else None, since=d["date"], won_at=d.get("name"),
                                      source=t["_src"], source_name=re.sub(r"^https?://(www\.)?", "", t["_src"]).split("/")[0], wcn=wcn_path(d), note=None, auto=True)
            elif why:
                flags.append({"show": d.get("key") or d["date"], "date": d["date"], "winner": m.get("winner"), "loser": m.get("loser"), "stip": m.get("stip"), "reason": why})
    return champ, flags
def wcn_path(d):
    p = f"events/{d['date']}-{d['slug']}/" if d.get("kind") == "ppv" else f"events/{d['date']}-{re.sub(r'^(wwe|aew|tna)-', '', d.get('slug', ''))}/"
    return p if os.path.isfile(os.path.join(PUB, p, "index.html")) else None
def days(since, now):
    try: return (now - datetime.date.fromisoformat(since)).days
    except Exception: return None
def fmt(dt):
    try: d = datetime.date.fromisoformat(dt); return d.strftime("%b %-d, %Y")
    except Exception: return ""

def page(path, h1, desc, body, robots="index,follow,max-image-preview:large,max-snippet:-1", ld=None):
    h = chrome.head(h1 + " | WCN", desc, SITE + path, "en", ld=ld, robots=robots)
    css = ("<style>.stat{width:100%;border-collapse:collapse;font-size:.95rem;margin:.5rem 0 1.5rem}.stat th,.stat td{text-align:left;padding:.4rem .5rem;border-bottom:1px solid #8883;vertical-align:top}"
           ".stat th{font-size:.8rem;text-transform:uppercase;opacity:.75}.stat td.n{text-align:right;white-space:nowrap}.wrap{overflow-x:auto}.note{opacity:.8;font-size:.9rem}</style>")
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">{h}{css}</head><body>\n{chrome.header("en", "/" + path, "/es/", back=True)}\n'
            f'<main class="layout statpage"><article class="story"><h1>{e(h1)}</h1>{body}</article></main>\n{chrome.footer("en")}\n</body></html>')
def write(path, html_):
    d = os.path.join(PUB, path); os.makedirs(d, exist_ok=True); open(os.path.join(d, "index.html"), "w").write(html_)
def xlinks(cur):
    labs = {"champions": "Current champions", "ple": "PLE &amp; PPV history", "records": "2026 win/loss records"}
    return '<p class="note">' + " · ".join(f'<a href="/{p}">{labs[k]}</a>' for k, p in PATHS.items() if k != cur) + "</p>"

def champions_html(champ, groups, now):
    rows = {}
    for t in champ.values(): rows.setdefault(t["group"], []).append(t)
    body = (f'<p>Every active title in WWE (Raw, SmackDown, NXT), AEW, TNA and AAA, with the date each reign began and how many days it has lasted as of '
            f'{e(now.strftime("%B %-d, %Y"))}. Each reign links to the promotion or a tier-1 report. Title changes are added from WCN\'s own results once a trusted outlet confirms them.</p>')
    body += timeline.html_block(timeline.lineage(champ), now)
    items = []
    for g in groups:
        if g not in rows: continue
        body += f'<h2>{e(g)}</h2><div class="wrap"><table class="stat"><thead><tr><th>Title</th><th>Champion</th><th>Since</th><th>Days</th><th>Source</th></tr></thead><tbody>'
        for t in rows[g]:
            dd = days(t.get("since"), now)
            ch = e(t["champion"]) + (f' <span class="note">({e(" & ".join(t["members"]))})</span>' if t.get("members") and t["champion"] not in ("&".join(t["members"]),) and "&" not in t["champion"] else "")
            won = e(t.get("won_at") or "")
            if t.get("wcn"): won = f'<a href="/{e(t["wcn"])}">{won or "WCN results"}</a>'
            body += (f'<tr><td>{e(t["name"])}</td><td><strong>{ch}</strong>{"<br><span class=note>" + e(t["note"]) + "</span>" if t.get("note") else ""}</td>'
                     f'<td>{e(fmt(t.get("since")))}{"<br><span class=note>" + won + "</span>" if won else ""}</td><td class="n">{dd if dd is not None else ""}</td>'
                     f'<td><a href="{e(t["source"])}" rel="noopener" target="_blank">{e(t.get("source_name") or "Source")}</a></td></tr>')
            items.append({"@type": "ListItem", "position": len(items) + 1, "name": f'{t["name"]}: {t["champion"]}'})
        body += "</tbody></table></div>"
    body += xlinks("champions")
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": "Current wrestling champions", "url": SITE + PATHS["champions"], "itemListElement": items}
    return page(PATHS["champions"], "Current wrestling champions", "Current WWE, NXT, AEW, TNA and AAA champions, the date each reign began and days held.", body, ld=ld)

# ---------------- PLE history ----------------
def series_of(slug): return slug
SERIES_NAME = lambda name: re.sub(r"\s*\b(19|20)\d\d\b\s*$", "", name or "").strip()
def main_event_row(ev, fc, live):
    """(main event text, winner) from WCN's own confirmed results: the match whose participants match full_cards main_event, else the last non-pre-show match."""
    ms = [m for m in (live or {}).get("matches", []) if good(m)]
    if not ms: return "", ""
    want = [fold(n) for n in (fc or {}).get("main_event") or []]
    if not want: return "", ""        # no confirmed main event for this edition: leave blank, never guess from match order
    same = lambda a, b: a == b or a.startswith(b + " ") or b.startswith(a + " ")
    best = None
    for m in ms:
        got = [fold(n) for n in members(m["winner"]) + members(m["loser"])]
        hit = sum(1 for w in want if any(same(w, g) for g in got))
        if hit >= max(2, len(want) - 1): best = m
    if not best: return "", ""
    txt = f'{best["winner"]} def. {best["loser"]}' + (f' ({best["stip"]})' if best.get("stip") else "")
    return txt, best["winner"]
def ple_rows(events, cards, shows, seed):
    lv = {(d.get("slug"), d["date"]): d for d in shows if d.get("kind") == "ppv"}
    rows = {}
    nowd = today().isoformat()
    for ev in events:
        if ev["date"] > nowd: continue
        fc = cards.get(f'{ev["slug"]}/{ev["date"]}') or {}
        me, win = main_event_row(ev, fc, lv.get((ev["slug"], ev["date"])))
        p = f'events/{ev["date"]}-{ev["slug"]}/'
        rows[(ev["slug"], ev["date"])] = {"series": ev["slug"], "series_name": SERIES_NAME(ev["name"]), "name": ev["name"], "date": ev["date"], "brand": ev.get("brand"),
            "venue": ev.get("venue") or "", "city": ev.get("city") or "", "main_event": me, "winner": win,
            "wcn": p if os.path.isfile(os.path.join(PUB, p, "index.html")) else None, "source": None}
    names = {r["series"]: r["series_name"] for r in rows.values()}
    for s in seed:
        k = (s["series"], s["date"]); r = rows.get(k, {"series": s["series"], "series_name": names.get(s["series"], SERIES_NAME(s.get("name"))), "date": s["date"], "wcn": None,
                                                       "brand": s["series"].split("-")[0].upper(), "venue": "", "city": "", "name": s.get("name")})
        for f in ("name", "venue", "city", "main_event", "winner"):
            if s.get(f): r[f] = s[f]
        r["source"], r["source_name"] = s.get("source"), s.get("source_name")
        rows[k] = r
    return sorted(rows.values(), key=lambda r: r["date"], reverse=True)
def ple_html(rows):
    body = ('<p>Every premium live event and pay-per-view edition WCN tracks, newest first: date, venue, main event and winner. 2026 editions link to WCN\'s event page and '
            'results; new editions are added automatically after WCN posts final results. Earlier years are listed only where the result is confirmed by the promotion or a tier-1 outlet.</p>')
    by = {}
    for r in rows: by.setdefault(r["date"][:4], []).append(r)
    for y in sorted(by, reverse=True):
        body += f'<h2>{y}</h2><div class="wrap"><table class="stat"><thead><tr><th>Date</th><th>Event</th><th>Venue</th><th>Main event</th><th>Winner</th></tr></thead><tbody>'
        for r in by[y]:
            nm = e(r.get("name") or r["series_name"])
            if r.get("wcn"): nm = f'<a href="/{e(r["wcn"])}">{nm}</a>'
            src = f' <a class="note" href="{e(r["source"])}" rel="noopener" target="_blank">[{e(r.get("source_name") or "source")}]</a>' if r.get("source") else ""
            ven = ", ".join(x for x in (r.get("venue"), r.get("city")) if x)
            body += (f'<tr><td>{e(fmt(r["date"]))}</td><td>{nm}</td><td>{e(ven)}</td><td>{e(r.get("main_event") or "")}{src}</td><td>{e(r.get("winner") or "")}</td></tr>')
        body += "</tbody></table></div>"
    body += xlinks("ple")
    return page(PATHS["ple"], "WWE, AEW, TNA and AAA PLE & PPV history", "Premium live event and PPV history by year: dates, venues, main events and winners.", body)

# ---------------- records ----------------
def records(shows, year="2026"):
    rec, n = {}, 0
    for d in shows:
        if not d["date"].startswith(year): continue
        big = d.get("kind") == "ppv"
        for m in d["matches"]:
            if not good(m): continue
            col = "big" if big and not m.get("pre") else "tv"
            draw = bool(re.search(r"\bdraw\b|no contest|double (count|dq|disqualif)|time limit", m.get("fin_en") or "", re.I))
            n += 1
            for side, res in ((m["winner"], "d" if draw else "w"), (m["loser"], "d" if draw else "l")):
                for p in members(side):
                    k = fold(p); r = rec.setdefault(k, {"name": p, "tv": {"w": 0, "l": 0, "d": 0}, "big": {"w": 0, "l": 0, "d": 0}})
                    r[col][res] += 1
    return rec, n
def records_html(rec, n):
    rows = sorted(rec.values(), key=lambda r: (-(r["tv"]["w"] + r["big"]["w"]), r["tv"]["l"] + r["big"]["l"], r["name"].lower()))
    body = (f'<p><strong>This page covers only matches WCN reported</strong> in its own final results in 2026 ({n} matches so far), not every match a wrestler had. '
            'It grows automatically as WCN posts results.</p><p class="note">Method: only results WCN marked final (confirmed, no conflicting reports) count. '
            'In a tag, trios or multi-person match every member of the winning side gets a win and every member of the losing side a loss; teams whose members '
            'were not listed are counted under the team name. Draws, no contests and time-limit draws count as a draw for everyone involved. '
            '"Big events" are PLEs and PPVs; weekly TV and pre-show matches count as TV.</p>')
    body += ('<div class="wrap"><table class="stat"><thead><tr><th>Wrestler</th><th>TV W-L-D</th><th>Big events W-L-D</th><th>Total W-L-D</th></tr></thead><tbody>')
    f = lambda x: f'{x["w"]}-{x["l"]}-{x["d"]}'
    for r in rows:
        t = {k: r["tv"][k] + r["big"][k] for k in "wld"}
        body += f'<tr><td>{e(r["name"])}</td><td class="n">{f(r["tv"])}</td><td class="n">{f(r["big"])}</td><td class="n">{f(t)}</td></tr>'
    body += "</tbody></table></div>" + xlinks("records")
    rob = "index,follow" if n >= RECORDS_INDEX_MIN else "noindex,follow"
    return page(PATHS["records"], "2026 wrestling win/loss records", "2026 wins, losses and draws per wrestler from WCN's reported results, TV and big events.", body, robots=rob), rob.startswith("index")

def build():
    """Writes the three pages. Returns (static paths, paths to keep out of sitemaps)."""
    now = today(); shows = lives()
    cfg = jload(os.path.join(ROOT, "champions.json"), {}); arts = jload(os.path.join(ROOT, "data", "articles.json"), [])
    if isinstance(arts, dict): arts = arts.get("items", [])
    champ, flags = champions_state(cfg.get("titles", []), shows, arts)
    os.makedirs(os.path.dirname(FLAGS), exist_ok=True); json.dump(flags, open(FLAGS, "w"), indent=1, ensure_ascii=False)
    write(PATHS["champions"], champions_html(champ, cfg.get("groups", []), now))
    evs = (jload(os.path.join(ROOT, "events.json"), {}) or {}).get("events", [])
    cards = (jload(os.path.join(ROOT, "full_cards.json"), {}) or {}).get("cards", {})
    seed = (jload(os.path.join(ROOT, "ple_history.json"), {}) or {}).get("editions", [])
    write(PATHS["ple"], ple_html(ple_rows(evs, cards, shows, seed)))
    rec, n = records(shows); h, indexable = records_html(rec, n); write(PATHS["records"], h)
    print(f"stats: champions {len(champ)} ({sum(1 for c in champ.values() if c.get('auto'))} auto changes, {len(flags)} flagged), records {len(rec)} wrestlers / {n} matches ({'indexed' if indexable else 'noindex'})", flush=True)
    return list(PATHS.values()), set() if indexable else {PATHS["records"]}
