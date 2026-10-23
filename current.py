"""The story subject's CURRENT promotion (owner rule 2026-10-23, Joe Hendry story tagged WWE + TNA with the TNA logo while he is
a WWE star: 'the tag must match the subject's current promotion').
Source of truth: the official roster snapshots in data/rosters.json (roster.py: wwe.com / allelitewrestling.com /
tnawrestling.com current rosters). Used by
  * vision.promotion  -> the placeholder card is the promotion the key person is listed on now (not an old brand list entry);
  * vision.choose     -> a promotion named only as past history ('rose to prominence in TNA') doesn't count as the story's;
  * pubgate.gate      -> tags: a promotion the subject isn't on any more and that the story mentions only as past history is
                         dropped, and the subject's current promotion is the first tag.
Never touches crossovers / partner-show stories: a headline naming another promotion, or a summary sentence about an
appearance / upcoming match / working agreement there, keeps that promotion. Hand-set tags (text_overrides.json) are final."""
import os, re, json, time
import roster
ROOT = os.path.dirname(os.path.abspath(__file__))
BIG = ("WWE", "AEW", "TNA")
TAG_AGE = 14 * 86400        # roster membership changes slowly; snapshots are fetched on demand only (roster.ensure)
PROMO = {"WWE": r"\bWWE\b|\bRaw\b|SmackDown|\bNXT\b|WrestleMania|SummerSlam|Royal Rumble",
         "AEW": r"\bAEW\b|All Elite|Dynamite|Collision|\bROH\b|Ring of Honor",
         "TNA": r"\bTNA\b|\bi?MPACT\b|Impact Wrestling|Bound for Glory|Slammiversary|Hard to Kill|Destination X"}
PAST = re.compile(r"(?i)\b(rose to (?:prominence|fame|stardom)|made (?:his|her|their|a) name|broke out|former(?:ly)?|ex-|previously|"
    r"once (?:held|was|reigned|wrestled)|earlier in (?:his|her|their) career|(?:before|prior to) (?:signing|joining|moving|heading|jumping|"
    r"leaving|his|her|their|arriving)|during (?:his|her|their) (?:time|run|tenure|stint|days|reign)|(?:his|her|their) (?:time|run|tenure|"
    r"stint|days|reign) (?:in|with|at)|spent (?:\w+ )?(?:years?|months?)|left|departed|exited|alum(?:nus|na|ni)?|veteran of|back in|"
    r"in 20(?:0\d|1\d|2[0-5])|during 20(?:0\d|1\d|2[0-5])|years? ago|was (?:a|the) (?:\w+[- ])?(?:time )?(?:TNA|AEW|WWE|Impact))\b")
NOW = re.compile(r"(?i)\b(will (?:appear|face|wrestle|compete|defend|challenge|return)|set to|scheduled|announced for|advertised|"
    r"appear(?:s|ing|ance)? (?:at|on|for|in)|returns? to|returning to|tonight|this week|next week|this weekend|upcoming|crossover|"
    r"working (?:agreement|relationship)|partnership|forbidden door|invades?|invasion|on loan|loaned|guest|"
    r"currently|now (?:on|in|with|wrestles|works|signed))\b")
RECALL = re.compile(r"(?i)\b(recalls?|remembers?|reflects? on|looks? back|reminisces?|recounts?|revisits?|on (?:his|her|their) (?:time|run|days|tenure) in|"
    r"(?:his|her|their) (?:time|run|days|tenure) in|throwback|years? ago|flashback|memories)\b")
def recollection(c):
    """Headline is a look back ('Chris Sabin Recalls MCMG Helping TNA Sign The Young Bucks'): the promotion it names is history."""
    return bool(RECALL.search((c.get("title") or "") + " | " + (c.get("raw_title") or "")))
_OV = None
def _text_ov():
    global _OV
    if _OV is None:
        try: _OV = json.load(open(os.path.join(ROOT, "text_overrides.json"))).get("items", {})
        except Exception: _OV = {}
    return _OV
_DB = [None, None]
def _db():
    try: m = os.path.getmtime(roster.PATH)
    except OSError: return {}
    if _DB[0] != m: _DB[:] = [m, roster.load()]
    return _DB[1]
def official(name, db=None, now=None):
    """(on, off): promotions whose current official roster lists `name`, and promotions with a usable roster that doesn't.
    Both empty when nothing is known (no snapshot / stale / implausibly small)."""
    on, off = set(), set()
    if not name: return on, off
    db = _db() if db is None else db; now = now or time.time(); k = roster.key(name)
    for p in BIG:
        r = db.get(p) or {}
        if not r.get("fetched") or now - r["fetched"] > TAG_AGE or (r.get("count") or 0) < roster.MIN.get(p, 10): continue
        e = (r.get("names") or {}).get(k)
        (on if e and e.get("last", 0) >= r["fetched"] else off).add(p)
    return on, off
def _sentences(t): return [s for s in re.split(r"(?<=[.!?;])\s+|\s+(?:but|while|and now|now)\s+", t or "") if s.strip()]
def past_only(p, text):
    """True if every mention of promotion p in text is past history ('rose to prominence in TNA before signing with WWE'),
    or there is none. False if any sentence about p is about now / an appearance there."""
    rx = re.compile(PROMO[p], re.I if p != "TNA" else 0)
    hits = [s for s in _sentences(text) if rx.search(s)]
    return all(PAST.search(s) and not NOW.search(s) for s in hits)
def _head(c):
    import enrich
    from pubgate import CAT
    t = (c.get("title") or "") + " | " + (c.get("raw_title") or "")
    return {CAT[p] for p in enrich.promos(t) if p in CAT}
def now_promo(key, c, db=None, now=None):
    """Lower-case promotion for a look-back story's placeholder: the key person's only current official roster, when the
    headline names a promotion they are not on (history). None otherwise."""
    on, off = official(key, db, now)
    if len(on) != 1 or not recollection(c): return None
    head = _head(c)
    return next(iter(on)).lower() if head and head - on and not head & on else None
def past_promos(c, key, db=None, now=None):
    """Big promotions (lower case) the story names only as the key person's past: not on their current roster, not in the
    headline, every summary mention past history. Empty unless the key person is on a current official roster."""
    on, off = official(key, db, now)
    if not on: return set()
    head = set() if recollection(c) else _head(c); txt = c.get("summary") or ""
    return {p.lower() for p in BIG if p in off and p not in head and re.search(PROMO[p], txt, re.I if p != "TNA" else 0) and past_only(p, txt)}
def fix_tags(c, db=None, now=None):
    """Tags follow the subject's current promotion. Returns a note when the tags changed, else None."""
    if (_text_ov().get(c.get("id")) or {}).get("categories"): return None     # hand-set tags win
    import vision
    try: key, _names, guessed = vision.key_person(c)
    except Exception: return None
    if not key or guessed: return None
    on, off = official(key, db, now)
    if not on: return None
    head = _head(c); look = recollection(c)
    if head - on and not look: return None   # headline names another promotion: crossover / partner show / 'X vs Y' story, leave it
    cats = list(c.get("categories") or [])
    txt = c.get("summary") or ""
    # a look-back headline keeps the promotion it is about as a secondary tag; the subject's current promotion leads
    drop = [p for p in cats if p in BIG and p in off and p not in head and past_only(p, txt)]
    new = [p for p in cats if p not in drop]
    cur = [p for p in BIG if p in on]
    prim = next((p for p in new if p in on), None)
    if prim: new = [prim] + [p for p in new if p != prim]
    elif drop or not new: new = [cur[0]] + new
    else: return None                  # tags name none of the big three the subject is on, and nothing to drop (e.g. Global/Indie)
    if new == cats: return None
    c["categories"] = new
    return f"tag {cats} -> {new} ({key} is on the current {'/'.join(cur)} roster)"
