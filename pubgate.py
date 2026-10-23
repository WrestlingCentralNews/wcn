"""Pre-publish consistency gate (owner rules 2026-10-21). Runs on every story right before pages/feeds/X/push are built, after
clustering (enrich.cluster already keeps different wrestlers/promotions apart and picks a named, fresh lead). Rules only, no AI.
Fixes what it safely can, HOLDS (does not publish) the rest:
  * headline must name who the story is about: a rewritten headline that dropped the name falls back to the source headline;
    a story whose headlines all hide the name ('TNA Signing Confirmed', 'AAA Star Dealing With Injury') is held;
  * headline and summary must be about the same people and promotion;
  * the promotion tag follows the headline's promotion ('Santino Marella Re-Signs With TNA' is tagged TNA, never WWE);
  * signing stories: new signing vs re-signing must agree between the headline and its sources; if the sources disagree
    (several say 'signs with', several say 're-signs') the story is held;
  * long-form body about other people/another promotion -> dropped (the summary shows instead);
  * photo whose file name names another wrestler / promotion -> the promotion's card (or the WCN card).
  * (2026-10-21, UFC 333 / AAA Heroes Inmortales) non-wrestling combat sports (UFC/MMA/boxing...) never publish; a headline whose
    reports are mostly about other promotions/wrestlers is held; an event coverage box the headline isn't about is held; a
    long-form that shares no name/number with the headline is dropped.
Held stories: data/held.json (current holds, for the daily summary) + data/dropped.jsonl."""
import os, json, time, re
import enrich, editorial, combat, roster
ROOT = os.path.dirname(os.path.abspath(__file__))
HELD = os.path.join(ROOT, "data", "held.json")
PROMO_CARD = "https://wrestlingcentralnews.com/img/promo/{}.jpg"
# illustrated / painted header art, not photos: PWTorch's stock caricature headers (artists GG / Joel Tesch, '<Name>_GG_3x2_600.jpg',
# 'CorbinBaronTeschJoel3x2_600.png') that its years-ago reprint columns reuse. Never the story photo -> the promotion card.
ART_IMG = re.compile(r"(?i)pwtorch\.com/.*/uploads/.*(?:_GG_|Tesch|3x2_600\.)")
CAT = {"wwe": "WWE", "aew": "AEW", "tna": "TNA", "njpw": "Global", "cmll": "Global", "aaa": "Global", "stardom": "Global",
       "mlw": "Indie", "gcw": "Indie", "nwa": "Indie"}
def _art(c): return {"raw_title": c.get("raw_title") or "", "title": c.get("title") or ""}
def names_in(t, names):
    low = enrich.canon(t or "").lower()
    def one(n):
        if re.search(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", low): return True
        last = re.sub(r"s$", "", n.split()[-1])                      # 'the hardys' ~ 'Jeff Hardy', 'dragon lee' ~ 'Lee'
        return len(last) >= 3 and re.search(r"(?<![a-z])" + re.escape(last) + r"s?(?![a-z])", low) is not None
    return any(one(n) for n in names)
def kinds(c, bylink):
    out = []
    for l in [c["link"]] + [u["link"] for u in c.get("updates", [])]:
        a = bylink.get(l)
        if a:
            k = enrich.kind_of(a)
            if k: out.append(k)
    return out
_HGEN = set("""start starts times time revealed reveals global audiences audience full card results preview update updates report reports
news live tonight week weekly night show shows match matches title titles championship champion champions tag team women men world event
events big major new latest official set confirmed announced announces date dates ticket tickets sales watch stream streaming how what why
who when where the and for with from into after before vs his her their this that our first last next more says said comments reacts
breaking exclusive backstage injury return returns debut debuts signs signing deal contract star stars legend""".split())
def _proper(t):
    """Distinctive words of a headline: capitalised names/brands and numbers ('UFC', '333', 'Volkanovski'), lower case."""
    w = re.findall(r"[A-Za-z0-9][\w'’.-]*", enrich.canon(t or ""))
    out = set()
    for x in w:
        k = re.sub(r"(?:'s|’s|[.'’])$", "", x).lower()
        if len(k) >= 3 and k not in _HGEN and k not in enrich.STOP and (x[0].isupper() or x[0].isdigit()): out.add(k)
    return out
def off_topic_long(c, paras):
    """The write-up names none of the headline's distinctive words (names, brands, event numbers) but names another
    promotion/event: it was written for a different report."""
    txt = enrich.canon(" ".join(paras or [])).lower()
    hp = _proper(c.get("title") or "") | _proper(c.get("raw_title") or "")
    if len(hp) < 2 or any(re.search(r"(?<![a-z0-9])" + re.escape(k), txt) for k in hp): return False
    return bool(enrich.promos(" ".join(paras or [])))
def promo_clash(a, b):
    """Reports a and b are about different promotions (UFC vs AAA, WWE vs TNA) and don't share a named wrestler."""
    sa, sb = enrich.subj_of(a), enrich.subj_of(b)
    if sa and sb and enrich.same_people(sa, sb): return False
    pa, pb = enrich.promos_of(a), enrich.promos_of(b)
    return bool(pa and pb and not pa & pb)
def box_clash(c):
    """Name of an event whose coverage box this story's reports point to but whose promotion the headline isn't about."""
    try: import hubs
    except Exception: return None
    import datetime
    ts = c.get("first_ts") or c.get("ts") or time.time()
    day = datetime.datetime.fromtimestamp(ts, hubs.ET).date(); txt = hubs.text_of(c)
    for ev in hubs.EVENTS:
        try: d = datetime.date.fromisoformat(ev["date"])
        except Exception: continue
        if -4 <= (d - day).days <= 35 and re.search(ev["match"], txt, re.I) and not hubs.box_fits(c, ev): return ev.get("name") or ev["slug"]
    return None
_RDB = None
# contract stories only (not 'Joins Eight-Man Tag', 'feared release before title win', 'Highspots Virtual Signing')
_R_REL = re.compile(r"(?i)\b(?:releases?|released|parts? ways|let go|departs?|departed|exits?|exited|leaves|leaving|fired|gone from|done with)\b")
_R_NEW = re.compile(r"(?i)\b(?:signs?|signed|signing|inks?|inked)\b|\bjoins? (?:the )?(?:WWE|AEW|TNA|NXT)\b|\bis all elite\b|\bofficially (?:joins|a part of)\b")
_R_RET = re.compile(r"(?i)\b(?:retires|retired|retirement|announces (?:his |her )?retirement|hangs? up (?:the|his|her) boots)\b")
_R_BACK = re.compile(r"(?i)\b(?:returns? to|returned to|back (?:in|with|to) (?:WWE|AEW|TNA)|makes? (?:his |her )?(?:shocking |surprise )?return)\b")
_R_NOT = re.compile(r"(?i)\bfear\w*|\bworr\w*|\brumou?r\w*|\bcould\b|\bwould\b|\bmight\b|\bnearly\b|\balmost\b|\bbefore\b|\breflects?\b|\brecalls?\b|"
                    r"\bdenies\b|\bnot\b|\bnever\b|\?|\bautograph|\bvirtual signing\b|\bsigning (?:session|event)|\bmeet (?:and|&) greet\b|\bif\b|\bwhy\b|\bhow\b")
def roster_check(c, tk, bylink, db=None):
    """(holds, support note). Only for signing/release stories about a named wrestler (not executives) of WWE/AEW/TNA with a
    fresh roster snapshot; a failed/stale roster or an unmatched name never holds."""
    global _RDB
    head = (c.get("title") or "") + " | " + (c.get("raw_title") or "")
    if tk not in ("new", "release", "re-sign"):
        tk = "retire" if _R_RET.search(head) else "return" if _R_BACK.search(head) else None
        if not tk: return [], None
    if _R_NOT.search(head) or not {"release": _R_REL, "new": _R_NEW, "retire": _R_RET, "return": _R_BACK}.get(tk, re.compile(r"(?i)re-?sign|extension|new (?:\w+ ){0,3}(?:deal|contract)")).search(head): return [], None
    fetch_p = db is None
    t = c.get("title") or ""
    ppl = (enrich.subjects(t) | enrich.subjects(c.get("raw_title") or "")) - enrich._EXEC
    pr = {x.lower() for x in enrich.promos(t) | enrich.promos(c.get("raw_title") or "")}
    prom = [p for p in ("WWE", "AEW", "TNA") if p.lower() in pr]
    if len(ppl) != 1 or len(prom) != 1: return [], None
    who, p = next(iter(ppl)), prom[0]
    if fetch_p:   # on-demand: fetch this promotion's roster only now, once per UTC day (cached in data/rosters.json + _RDB)
        day = time.strftime("%Y-%m-%d", time.gmtime())
        if _RDB is None or (_RDB.get(p) or {}).get("tried_day") != day:
            try: _RDB = roster.ensure(p)
            except Exception: _RDB = _RDB or {}
        db = _RDB
    st = roster.status(who, p, db)
    if not st: return [], None
    name = who.title()
    if tk in ("release", "retire"):
        if not st["listed"]: return [], f"no longer on the {p} roster" if st.get("was_listed") else None
        reps = [{"link": c.get("link"), "source": c.get("source")}] + [u for u in c.get("updates", []) if u.get("link") != c.get("link")]
        if any(roster.official(r.get("link"), p) for r in reps): return [], f"still on the {p} roster (official statement)"
        srcs = {(r.get("source") or "").lower() for r in reps if (editorial.tier(r.get("source")) <= 2)
                and enrich.signing_kind((bylink.get(r.get("link")) or {}).get("raw_title") or r.get("title") or "") in ("release", None)}
        if len(srcs) >= 2: return [], f"still on the {p} roster ({len(srcs)} trusted outlets report the exit)"
        if tk == "retire": return [f"retirement story but {name} is still listed on the official {p} roster"], None
        return [f"release/exit story but {name} is still listed on the official {p} roster"], None
    if not st["listed"]: return [], None
    if tk == "new" and st["days"] > roster.LONG_DAYS:
        if neutral_signing(c): return [], f"on the {p} roster {int(st['days'])}+ days; worded neutrally (signs with)"
        return [f"'new signing' but {name} has been on the official {p} roster for {int(st['days'])}+ days (likely a re-signing)"], None
    return [], (f"newly added to the {p} roster" if st["new"] else f"still on the {p} roster")
_NEU = [(re.compile(r"(?i)\bre-?signs?\b|\bsigns? (?:a )?(?:new|fresh) (?:\w+ ){0,3}(?:deal|contract|extension)\b|\bsigns? (?:an )?(?:contract )?extension\b"), "signs a deal"),
        (re.compile(r"(?i)\bre-?signed\b|\bsigned (?:a )?(?:new|fresh) (?:\w+ ){0,3}(?:deal|contract)\b|\bsigned an extension\b"), "signed a deal"),
        (re.compile(r"(?i)\bre-?signing\b|\bnew signing\b"), "signing"),
        (re.compile(r"(?i)\b(?:a )?new ((?:[\w-]+ ){0,2}(?:deal|contract))\b"), r"a \1"),
        (re.compile(r"(?i)\bnewest (?:signing|addition)\b"), "signing"), (re.compile(r"(?i)\bnewly[- ]signed\b"), "signed")]
def neutral_text(x):
    for rx, rep in _NEU: x = rx.sub(rep, x)
    return x
def neutral_signing(c):
    """Owner rule 2026-10-22: new-vs-re-signing unclear -> publish '<Name> Signs With <Promotion>', neutral body, no hold."""
    t = c.get("title") or ""; raw = c.get("raw_title") or ""
    ppl = (enrich.subjects(t) or enrich.subjects(raw)) - enrich._EXEC
    pr = enrich.promos(t) or enrich.promos(raw)
    if not ppl:   # name not in our wrestler list: take the capitalised words before 'Signs'/'Re-Signs' in the headline
        m = re.match(r"^(?:Report:\s*)?((?:[A-Z][\w.'-]*\s+){1,3}?)(?:Officially\s+)?(?:Re-?)?Signs?\b", t) or re.match(r"^(?:Report:\s*)?((?:[A-Z][\w.'-]*\s+){1,3}?)(?:Officially\s+)?(?:Re-?)?Signs?\b", raw)
        if m and not enrich.promos(m.group(1)): ppl = {m.group(1).strip()}
    if len(ppl) != 1 or len(pr) != 1: return False
    who = next(iter(ppl)); p = next(iter(pr)); p = {"wwe": "WWE", "aew": "AEW", "tna": "TNA", "nxt": "NXT", "aaa": "AAA", "roh": "ROH", "njpw": "NJPW", "cmll": "CMLL", "mlw": "MLW"}.get(p.lower(), p)
    nm = next((m.group(0) for m in [re.search(re.escape(who), t + " " + raw, re.I)] if m), who.title())
    nm = nm if nm != nm.lower() else nm.title()
    c["title"] = f"{nm} Signs With {p}"
    for k in ("summary", "long", "dek"):
        if isinstance(c.get(k), str): c[k] = neutral_text(c[k])
    c["signing_neutral"] = True
    return True
# ---- content-staleness guard (owner 2026-10-22): a results-style story whose named wrestlers mostly aren't on ANY current
# official roster (WWE/AEW/TNA snapshot in data/rosters.json, no fetch) describes a past show ('Ziggler retains the IC title,
# the Vaudevillains, the Hype Bros'). Results/live-event reports only; never history/return framing, never interviews/quotes.
_RG_FRAME = re.compile(r"(?i)\b(?:returns?|returned|comeback|reunion|reunite[sd]?|legends?|alumni|history|years ago|decades? ago|flashback|"
                       r"anniversary|tribute|hall of fame|throwback|former|ex-|nostalgia|indie|independent|gcw|mlw|nwa|roh|njpw|cmll|aaa|stardom|evolve|lfg|tryouts?|ovw|dark match|main event)\b")
def _rg_names(txt, cur):
    """Wrestler names in txt: the known-name dictionary (enrich._PRX: editorial roster + figures + aliases) plus any current
    roster name spelled out in full."""
    out = {}
    for m in enrich._PRX.finditer(txt or ""):
        k = roster.key(m.group(1))
        if k: out.setdefault(k, m.group(1))
    N = r"((?:[A-Z][\w'’.-]+)(?:\s+[A-Z][\w'’.-]+){0,2})"
    for m in re.finditer(N + r"\s+(?:defeated|pinned|beat|beats|def\.|vs\.?|over|submitted|retained\s+against)\s+" + N, txt or ""):
        for g in m.groups():
            g = re.sub(r"^(?:The|And|Then|After|Champion|Intercontinental|WWE|Tag)\s+", "", g).strip(" .")
            k = roster.key(g)
            if k and len(g) > 3 and not re.search(r"(?i)\b(?:champion(?:ship)?|title|match|team|tag)\b", g): out.setdefault(k, g)
    low = (txt or "").lower()
    for k, e in cur.items():
        if " " in k and k in low: out.setdefault(k, e)
    return out
def roster_stale(c, bylink, db=None, now=None):
    """Hold reason when a results-style story's named wrestlers are mostly off every current roster, else None."""
    if (c.get("kind") or {}).get("type") != "results" and not re.search(r"(?i)\b(?:results?|live event|house show)\b", c.get("raw_title") or ""): return None
    cats = set(c.get("categories") or [])
    if not cats & {"WWE", "AEW", "TNA"}: return None
    lead = bylink.get(c.get("link")) or {}
    head = (c.get("raw_title") or "") + " " + (c.get("title") or "")
    if _RG_FRAME.search(head): return None
    db = roster.load() if db is None else db; now = now or time.time()
    cur = {}
    for p in ("WWE", "AEW", "TNA"):
        r = db.get(p) or {}
        if not r.get("ok") or not r.get("fetched") or now - r["fetched"] > 30 * 86400 or len(r.get("names", {})) < roster.MIN.get(p, 10): return None
        for k, e in r["names"].items():
            if e.get("last", 0) >= r["fetched"] - 86400: cur[k] = p
    last = {}
    for k in cur:
        parts = k.split()
        if len(parts) > 1: last.setdefault(parts[-1], set()).add(k)
    txt = (lead.get("raw_title") or c.get("raw_title") or "") + ". " + ((lead.get("summary_src") or "") + " " + (lead.get("body") or ""))[:1500]
    on, off = [], []
    for k, n in _rg_names(txt, {k: k for k in cur}).items():
        if k in cur or (" " not in k and len(last.get(k, ())) == 1): on.append(n)
        else: off.append(n)
    if len(on) + len(off) < 4 or len(off) < 3: return None
    if len(off) / (len(on) + len(off)) < 0.6: return None
    return f"results-style story, but {len(off)} of {len(on) + len(off)} named wrestlers aren't on any current roster (e.g. {', '.join(off[:4])}): likely an old show re-run"
def gate(c, bylink):
    fixes, holds = [], []
    # 1. the headline names the person
    T = lambda x: enrich.teaser({"raw_title": x or "", "title": x or ""})
    if T(c.get("title")):
        if enrich.subjects(c.get("raw_title") or ""):          # the rewrite dropped the name the source headline has
            new = enrich.headline(c["raw_title"], (c.get("kind") or {}).get("type"))
            fixes.append(f"nameless headline '{c['title']}' -> '{new}'"); c["title"] = new
        elif T(c.get("raw_title")): holds.append("headline doesn't name who it is about")
    nw = combat.nonwrestling(c)
    if nw: holds.append(nw)
    t = c.get("title") or ""; s = c.get("summary") or ""
    pt = enrich.subjects(t)
    # 2b. the headline must speak for the story's reports: held if it clashes (other promotion / other wrestlers) with at
    # least half of the other reports, or with the event its coverage box would show
    lead = bylink.get(c.get("link")) or {"raw_title": c.get("raw_title") or "", "title": t}
    mem = [bylink[u["link"]] for u in c.get("updates", []) if u.get("link") in bylink and u["link"] != c.get("link")]
    bad = [m for m in mem if promo_clash(lead, m)]
    if mem and len(bad) * 2 >= len(mem):
        holds.append(f"headline is about another promotion than {len(bad)}/{len(mem)} of its reports (e.g. '{(bad[0].get('raw_title') or '')[:60]}')")
    ev = box_clash(c)
    if ev: holds.append(f"event box '{ev}' is about another promotion than the headline")
    # 2. headline vs summary
    if pt and enrich.subjects(s) and not names_in(s, pt): holds.append("headline names " + ", ".join(sorted(pt)) + "; summary is about someone else")
    ft, fs = enrich.promos(t), enrich.promos(s)
    if ft and fs and not ft & fs and not (pt and names_in(s, pt)): holds.append("headline and summary are about different promotions")
    # 3. tag follows the headline
    want = sorted({CAT[p] for p in ft if p in CAT}, key=["WWE", "AEW", "TNA", "Indie", "Global"].index)
    if want and not set(want) & set(c.get("categories") or []):
        fixes.append(f"tag {c.get('categories')} -> {want}"); c["categories"] = want
    # 3b. tags follow the subject's CURRENT promotion (official rosters, current.py): a promotion they've left that the story
    # names only as history ('rose to prominence in TNA') is dropped, their current one leads (owner rule 2026-10-23, Joe Hendry)
    try:
        import current; n = current.fix_tags(c)
        if n: fixes.append(n)
    except Exception as e: print("current-promo tags: error (ignored)", repr(e)[:120], flush=True)
    # 4. new signing vs re-signing
    ks = kinds(c, bylink); tk = enrich.signing_kind(t) or enrich.signing_kind(c.get("raw_title") or "")
    n, r = ks.count("new"), ks.count("re-sign")
    why = None
    if n >= 2 and r >= 2 and min(n, r) >= 0.4 * max(n, r): why = f"sources disagree: {n} say new signing, {r} say re-signing"
    elif tk in ("new", "re-sign"):
        opp = "re-sign" if tk == "new" else "new"
        if ks.count(opp) >= 2 and ks.count(opp) > 2 * ks.count(tk): why = f"headline says {tk} but most sources say {opp}"
    if why and neutral_signing(c): fixes.append("signing unclear (" + why + ") -> neutral '" + c["title"] + "'"); tk = "signs"
    elif why: holds.append(why)
    # 4b. official roster cross-check (WWE/AEW/TNA): released-but-still-listed, 'new' signing listed > 14 days, support note
    rh, note = roster_check(c, tk, bylink)
    holds += rh
    rs = roster_stale(c, bylink)
    if rs: holds.append(rs)
    if note: c["roster_note"] = note; fixes.append("roster: " + note)
    # 5. body
    if c.get("long") and (enrich.long_mismatch(_art(c), c["long"]) or off_topic_long(c, c["long"])):
        c["long"] = None; fixes.append("long-form about another story dropped")
    # 6. photo
    u = c.get("image")
    if u and c.get("image_status") != "override" and ART_IMG.search(u):
        p = sorted(ft)[0] if ft else None
        c["image"] = PROMO_CARD.format(p) if p else None; c["image_status"] = "gate:art:" + (p or "wcn-card"); c["image_credit"] = None
        c.pop("img_w", None); c.pop("img_h", None); fixes.append("illustrated header art, not a photo -> " + (c["image"] or "WCN card")); u = c["image"]
    if u and "wrestlingcentralnews.com/img/" not in u and c.get("image_status") != "override" and enrich.img_clash(u, pt, ft | fs, t + " | " + s + " | " + (c.get("raw_title") or "")):
        p = sorted(ft)[0] if ft else None
        c["image"] = PROMO_CARD.format(p) if p else None; c["image_status"] = "gate:" + (p or "wcn-card"); c["image_credit"] = None
        c.pop("img_w", None); c.pop("img_h", None); fixes.append("photo names another wrestler/promotion -> " + (c["image"] or "WCN card"))
    return not holds, fixes, holds
def run(clusters, bylink, log=print, live_ids=None, now=None):
    """live_ids: story ids already on the site (previous news.json). Every other story must pass freshness.publish_check
    (verified article-page date under 48h, fail closed). None skips the date check (tests / no previous build)."""
    import freshness
    keep, held = [], {}
    for c in clusters:
        ok, fixes, holds = gate(c, bylink)
        if live_ids is not None and c["id"] not in live_ids:
            why = freshness.publish_check(c, bylink, now)
            if why: ok = False; holds = list(holds) + [why]
        if fixes: log(f"gate: fixed {c['id']} '{c['title'][:70]}': " + "; ".join(fixes))
        if ok: keep.append(c); continue
        held[c["id"]] = {"title": c["title"], "link": c["link"], "source": c["source"], "why": holds, "at": int(time.time())}
        editorial.log_drop({"raw_title": c["raw_title"], "source": c["source"], "link": c["link"]}, "consistency hold: " + "; ".join(holds))
        log(f"gate: HOLD {c['id']} '{c['title'][:70]}': " + "; ".join(holds))
    try: os.makedirs(os.path.dirname(HELD), exist_ok=True); json.dump(held, open(HELD, "w"), indent=1)
    except Exception: pass
    return keep
