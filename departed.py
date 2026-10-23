"""Free agents / wrestlers between promotions (owner rule 2026-10-23, Max Caster after TNA ended his deal at Bound for Glory):
photo of the wrestler first; with no good photo, the placeholder card of the LAST promotion they were signed to, but only if
they left recently (RECENT = ~6 months); after that the WCN card.
Last promotion + departure date per wrestler, newest source wins:
  * departures.json (repo, hand-set, final when newer),
  * official roster snapshots (data/rosters.json): a name that dropped off a roster -> that promotion, date = last seen,
  * story text ('TNA ended his deal', 'released by WWE', 'departure from AEW', 'fired from TNA'): date = when first reported;
    remembered in data/departures.json so later stories about that wrestler know it too."""
import os, re, json, time
import roster
ROOT = os.path.dirname(os.path.abspath(__file__))
HAND = os.path.join(ROOT, "departures.json")
SEEN = os.path.join(ROOT, "data", "departures.json")
RECENT = 183 * 86400
BIG = ("WWE", "AEW", "TNA")
_P = r"(WWE|AEW|TNA|NXT|ROH|Impact Wrestling)"
_PRON = r"(?:his|her|their)"
def _rx(key):
    """Departure phrasings about this person (name, or a pronoun in a story whose headline names them)."""
    n = re.escape(key); who = r"(?:" + n + r"|him|her|them)"; whose = r"(?:" + n + r"'s|" + _PRON + r")"
    return [re.compile(p, re.I) for p in (
        _P + r"(?:'s)? (?:has |had |have )?(?:released|cut|fired|terminated|let go of|parted ways with|cut ties with|severed ties with) " + who + r"\b",
        _P + r"(?:'s)? (?:has |had |have )?(?:ended|terminated|tore up|cancell?ed) " + whose + r" (?:\S+ )?(?:deal|contract)",
        r"\b" + who + r" (?:(?:has been|was|is|gets|got) )?(?:released|cut|fired|let go) (?:by|from)(?: the)? " + _P,
        r"\b" + whose + r" (?:departure|exit|release|firing|split) (?:from|with) (?:the )?" + _P,
        r"\b" + who + r" (?:has |is |was )?(?:departs?|departed|departing|leaves|left|leaving|exits?|exited|exiting|quits?|quit|done with|finished with|parts? ways with|parted ways with|splits? from) (?:the )?" + _P,
        r"\b" + who + r" (?:is |was )?no longer (?:with|under contract (?:with|to)|signed (?:with|to)|working (?:with|for)) " + _P,
        r"\b" + whose + r" (?:\S+ )?" + _P + r" (?:deal|contract) (?:was |has been |is )?(?:ended|terminated|over|done|torn up|cancell?ed)",
        r"\b" + _P + r"(?:'s)? (?:\S+ )?(?:exit|departure|release|firing) of " + n,
        r"\b(?:after|since|following|upon) (?:leaving|departing|exiting|being released (?:by|from)|his release from|her release from) (?:the )?" + _P,
        r"\b(?:" + whose + r" |after |following |since )(?:(?:19|20)\d\d )?" + _P + r" (?:exit|departure|release|firing)\b")]
MON = "jan feb mar apr may jun jul aug sep oct nov dec".split()
def _when(txt, m, ts):
    """Departure date: a 'Month YYYY' / 'YYYY' within the matched phrase or right after it ('left AEW in 2023',
    'his 2021 WWE release') when it's before the story's year, else when the story was first reported."""
    w = txt[max(0, m.start() - 12): m.end() + 30]
    y = re.search(r"(?i)\b(?:(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? )?((?:19|20)\d\d)\b", w)
    if not y or int(y.group(2)) >= time.gmtime(ts).tm_year: return ts
    mo = MON.index(y.group(1).lower()[:3]) + 1 if y.group(1) else 12
    return int(time.mktime((int(y.group(2)), mo, 28, 0, 0, 0, 0, 0, -1)))
NORM = {"NXT": "WWE", "ROH": "AEW", "IMPACT WRESTLING": "TNA"}
def _load(p):
    try: return json.load(open(p))
    except Exception: return {}
def _ts(d):
    if isinstance(d, (int, float)): return int(d)
    try: return int(time.mktime(time.strptime(str(d)[:10], "%Y-%m-%d")))
    except Exception: return 0
def from_text(c, key):
    """(PROMO, ts) when the story says the key person left / was released by a promotion, else None. Only when the headline
    names them (a story about them), and only sentences that name them or follow from the headline."""
    import vision
    t = (c.get("title") or "") + " | " + (c.get("raw_title") or "")
    # the published headline must name them, and a roundup ('..., ERIC YOUNG, ... AND MORE') is no departure story (2026-10-23)
    if not vision.names_key(c.get("title") or "", key) or vision.roundup_title(c.get("title") or ""): return None
    try:
        import current
        if current.recollection(c): return None   # look-back story ('Recalls His 2014 WWE Exit'): not a departure date
    except Exception: pass
    txt = t + ". " + (c.get("summary") or "") + " " + (c.get("src_summary") or "")
    ts = int(c.get("first_ts") or c.get("ts") or time.time()); per = {}
    for rx in _rx(key):
        for m in rx.finditer(txt):
            p = next(g for g in m.groups() if g).upper(); p = NORM.get(p, p); w = _when(txt, m, ts)
            per.setdefault(p, set()).add(w)
    # an explicit year for a promotion beats the undated mention of the same exit ('After WWE Exit' + 'his 2021 WWE release')
    best = [(p, max([w for w in ws if w != ts] or [ts])) for p, ws in per.items()]
    return max(best, key=lambda x: x[1]) if best else None
def from_rosters(key, db=None):
    """(PROMO, last seen) for the newest official roster the name dropped off (snapshot fresh, listed before, not now)."""
    db = roster.load() if db is None else db; k = roster.key(key); best = None
    for p in BIG:
        r = db.get(p) or {}; e = (r.get("names") or {}).get(k)
        if not r.get("fetched") or (r.get("count") or 0) < roster.MIN.get(p, 10) or not e: continue
        if e.get("last", 0) < r["fetched"] and (not best or e["last"] > best[1]): best = (p, int(e["last"]))
    return best
def forget():
    """Keys whose remembered (story-text) departures are wrong; dropped from SEEN on the next write (departures.json 'forget')."""
    return {roster.key(n) for n in (_load(HAND).get("forget") or [])}
def prune(path=None):
    """Drop forgotten keys from the remembered departures (runs each pipeline pass)."""
    path = path or SEEN; d = _load(path); bad = [k for k in d if k in forget()]
    for k in bad: d.pop(k)
    if bad:
        try: json.dump(d, open(path, "w"), indent=0)
        except Exception: pass
    return bad
def record(key, promo, ts, path=None):
    path = path or SEEN; d = _load(path); k = roster.key(key); e = d.get(k) or {}
    if k in forget(): return
    if ts > e.get("ts", 0):
        d[k] = {"name": key, "promo": promo, "ts": int(ts)}
        try: os.makedirs(os.path.dirname(path), exist_ok=True); json.dump(d, open(path, "w"), indent=0)
        except Exception: pass
def last(key, c=None, db=None, now=None, hand=None, seen=None):
    """(PROMO, departure ts) newest known departure for key, else None. Story text found here is remembered."""
    k = roster.key(key); cands = []
    h = _load(HAND).get("items", {}) if hand is None else hand
    for n, v in h.items():
        if roster.key(n) == k and v.get("promo"): cands.append((v["promo"], _ts(v.get("date"))))
    s = (_load(SEEN) if seen is None else seen).get(k)
    if s and k not in forget(): cands.append((s["promo"], int(s["ts"])))
    r = from_rosters(key, db)
    if r: cands.append(r)
    if c is not None:
        tx = from_text(c, key)
        if tx:
            cands.append(tx)
            if seen is None: record(key, *tx)
    return max(cands, key=lambda x: x[1]) if cands else None
def card(key, c=None, db=None, now=None, **kw):
    """Placeholder promotion (lower case) for a free agent: last promotion if they left within RECENT, '' if longer ago
    (-> WCN card), None if no departure is known."""
    lp = last(key, c, db, now, **kw)
    if not lp: return None
    return lp[0].lower() if (now or time.time()) - lp[1] <= RECENT else ""
