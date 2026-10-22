"""Article enrichment (link resolve, page text, og:image), original summary/headline writing, story clustering."""
TIER = None
import re, json, html, urllib.request, urllib.parse, random, hashlib
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124 Safari/537.36"}
def _get(url, t=12, data=None, hdr=None):
    return urllib.request.urlopen(urllib.request.Request(url, data=data, headers={**UA, **(hdr or {})}), timeout=t)
def resolve_google(url):
    gid = url.split("/articles/")[1].split("?")[0]
    h = _get(f"https://news.google.com/rss/articles/{gid}").read().decode()
    sg = re.search(r'data-n-a-sg="([^"]+)"', h).group(1); ts = re.search(r'data-n-a-ts="([^"]+)"', h).group(1)
    inner = ["garturlreq", [["X","X",["X","X"],None,None,1,1,"US:en",None,1,None,None,None,None,None,0,1],"X","X",1,[1,1,1],1,1,None,0,0,None,0], gid, int(ts), sg]
    body = "f.req=" + urllib.parse.quote(json.dumps([[["Fbv4je", json.dumps(inner), None, "generic"]]]))
    r = _get("https://news.google.com/_/DotsSplashUi/data/batchexecute", data=body.encode(),
             hdr={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}).read().decode()
    return json.loads(json.loads(r.split("\n\n")[1])[0][2])[1]
def clean(s): return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()
def meta(h, prop):
    m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]*content=["\']([^"\']+)' % prop, h) or \
        re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']%s["\']' % prop, h)
    return html.unescape(m.group(1)) if m else None
JUNK = re.compile(r"subscribe|newsletter|cookie|click here|sign up|follow us|advertis|copyright|all rights|©|share this|related:|read more|you can (?:watch|listen)|podcast|patreon|share facebook|whatsapp|linkedin|watch [\w ]+ live on|preferred source|add [\w. ]+ on google|google discover|stale|my throat|lol\b|loading…|comment|connect with us|bluesky|ugh|this article|photo credit|getty|discord|affiliate", re.I)
PAYWALL = re.compile(r"(?i)class=[\"'][^\"']*\b(paywall|premium-content|members?-only|subscriber-only|pmpro_content_message|mepr-unauthorized|piano-offer|tp-container)\b|"
                     r"this (content|article|post) is (only )?(available )?(for|to) (subscribers|members)|subscribe to (read|continue|unlock)")
def fetch_article(it):
    url = it["link"]
    if "news.google.com" in url:
        try: url = resolve_google(url); it["link"] = url
        except Exception: return
    try: h = _get(url, 12).read()[:900000].decode("utf8", "ignore")
    except Exception: return
    import freshness
    it["pubchk"] = 1; p = freshness.page_published(h)   # the page's own publish time (never 'modified'): freshness gate
    if p: it["pub_ts"] = p
    if not it.get("image"):
        img = meta(h, "og:image") or meta(h, "twitter:image")
        if img and not re.search(r"logo|default|placeholder|favicon", img, re.I): it["image"] = urllib.parse.urljoin(url, img)
    if PAYWALL.search(h) or re.search(r"fightful\.com/(select|premium)", url):
        # subscriber content (Fightful Select, F4W/Observer members, any paywall): never copy it - public description only
        it["paywalled"] = True; it["body"] = clean(meta(h, "og:description") or ""); return
    body = re.sub(r"(?is)<(script|style|nav|footer|header|aside|figure|form)[^>]*>.*?</\1>", " ", h)
    paras = [clean(p) for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", body)]
    paras = [p for p in paras if len(p) > 60 and not JUNK.search(p)]
    it["body"] = " ".join(paras)[:6000] or clean(meta(h, "og:description") or "")
# ---------- original summary writing (rule-based extractive + paraphrase; no LLM available on box) ----------
SYN = [(r"\bannounced\b","revealed"),(r"\breportedly\b","by most accounts"),(r"\bconfirmed\b","made official"),(r"\bwill face\b","is set to meet"),
 (r"\bdefeated\b","got the win over"),(r"\bbeat\b","got past"),(r"\breturned\b","made a comeback"),(r"\bsigned\b","inked a deal"),(r"\bstated\b","said"),
 (r"\bnoted\b","pointed out"),(r"\brevealed\b","disclosed"),(r"\bupcoming\b","forthcoming"),(r"\binjury\b","injury setback"),
 (r"\bhowever\b","that said"),(r"\balso\b","additionally"),(r"\bcurrently\b","right now"),(r"\bfollowing\b","after"),(r"\bseveral\b","a number of"),
 (r"\bplans\b","the plan"),(r"\bexpected to\b","likely to"),(r"\bset to\b","slated to"),(r"\baccording to\b","per"),(r"\bfans\b","the audience"),
 
 (r"\bhuge\b","massive"),(r"\bsaid\b","explained"),(r"\bwants\b","is hoping"),(r"\bstarted\b","kicked off")]
STOP = set("a an the of to in on for and or but is are was were be been with at by from as that this it its his her their they he she we you i not no new will has have had after over into about than then just more most".split())
def spam(s):
    w = s.split(); caps = sum(1 for x in w if x[:1].isupper())
    return len(w) < 7 or caps / len(w) > .45 or re.search(r"\bGame\b.*\bGame\b|\bBet\b|\bBDG\b|By [A-Z][a-z]+ [A-Z][a-z]+ on \d", s)
def sents(t):
    t = re.sub(r"[^\x00-\u024F\u2018-\u201D\u2026—–]+", " ", t)
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"'])", t) if 40 < len(s.strip()) < 400 and not spam(s.strip()) and not JUNK.search(s)]
def toks(t): return [w for w in re.findall(r"[a-z0-9']+", t.lower()) if w not in STOP and len(w) > 2]
def restructure(s):
    m = re.match(r"^([A-Z][\w.' ]{2,40}?) (said|says|revealed|reveals|noted|explained|stated|admitted|confirmed|told [\w ]+?) (?:that )?(.{30,})$", s)
    if m: s = f"{m.group(3).rstrip('.')}, {m.group(1)} {m.group(2) if not m.group(2).endswith('s') or m.group(2) in ('says',) else m.group(2)}."; s = s[0].upper() + s[1:]
    s = re.sub(r"(?i)during (?:\w+ night'?s|this week'?s|the latest|last night'?s) (?:episode|edition) of ", "on ", s)
    s = re.sub(r"(?i)\bit (?:has been|was) (?:announced|confirmed|revealed) that ", "Officially, ", s)
    s = re.sub(r"(?i)\bin an interview with ([^,]+), ", r"Speaking with \1, ", s)
    s = re.sub(r"(?i)\bis going to\b", "will", s); s = re.sub(r"(?i)\bdid not\b", "didn't", s); s = re.sub(r"(?i)\bwill not\b", "won't", s)
    s = re.sub(r"(?i)\bin order to\b", "to", s); s = re.sub(r"(?i)\bat this time\b", "for now", s); s = re.sub(r"(?i)\bthe fact that\b", "how", s)
    return s
def rephrase(s):
    s = restructure(s)
    s = re.sub(r"\s*\([^)]*\)", "", s); s = re.sub(r"[\"“”]", "", s)
    used = set()
    for a, b in SYN:
        if b in used or a.strip("\\b") in used: continue
        if re.search(a, s, re.I): s = re.sub(a, b, s, count=1, flags=re.I); used.add(b); used.add(a.strip("\\b"))
    s = re.sub(r"^(On|In|During|At) [^,]{3,60}, ", "", s)
    w = s.split()
    if len(w) > 30:
        cut = s.find(", ", 90); s = s[:cut] if 0 < cut < 220 else " ".join(w[:30])
    # move a trailing attribution / "according to" clause to the front
    m = re.match(r"(.+?),\s*(per [^,]+|by most accounts)[,.]?\s*(.*)$", s)
    if m and m.group(3): s = f"{m.group(2)[0].upper()+m.group(2)[1:]}, {m.group(1)[0].lower()+m.group(1)[1:]} {m.group(3)}"
    s = re.sub(r"^(However|Also|Meanwhile|Additionally),?\s*", "", s); s = s[0].upper() + s[1:]
    return s.rstrip(".") + "."
def summarize(it):
    text = it.get("body") or it.get("summary_src") or ""
    title = it["raw_title"]; tt = set(toks(title))
    ss = sents(text)
    if not ss:
        return f"New details are emerging on this story from {it['source']}: {headline_topic(enrich_hl(title)).rstrip('.')}. Tap through for the full breakdown."
    scored = sorted(enumerate(ss), key=lambda x: -(len(tt & set(toks(x[1]))) * 2 + (3 if x[0] < 3 else 0) - x[0] * .1))
    pick = sorted(scored[:2], key=lambda x: x[0])
    out = " ".join(rephrase(s) for _, s in pick)
    lead = random.Random(it["id"]).choice(["", f"Per {it['source']}: ", "", "The latest: "])
    if out.startswith("Per ") or out.lower().startswith("the latest") or lead.strip(": ").lower() in out[:60].lower(): lead = ""
    out = lead + out if lead and re.match(r"(I|[A-Z][a-z]+ [A-Z])", out) else out
    out = lead + out[0].lower() + out[1:] if lead and not re.match(r"[A-Z]{2}|[A-Z][a-z]+ [A-Z]", out) else lead + out
    return (out[:420].rsplit(" ", 1)[0] + "…") if len(out) > 430 else out
def headline_topic(t): return re.sub(r"[:|].*$", "", t).strip()
HL = [(r"^Report:?\s*", ""),(r"\bReveals?\b","Opens Up On"),(r"\bAnnounced\b","Set"),(r"\bConfirmed\b","Locked In"),(r"\bComments On\b","Weighs In On"),
 (r"\bTalks\b","Discusses"),(r"\bDiscusses\b","Breaks Down"),(r"\bUpdate On\b","Latest On"),(r"\bReacts To\b","Responds To"),(r"\bResults\b","Recap"),
 (r"\bBackstage News On\b","Inside Word On"),(r"\bNote On\b","Word On"),(r"\bDetails On\b","What We Know About"),(r"\bAddresses\b","Speaks On")]
def tcase(h):
    if h.upper() == h: h = " ".join(w if w in ("WWE","AEW","TNA","NXT","ROH","NJPW","PPV","GCW","MLW") else w.capitalize() for w in h.split())
    return h
HOOKS = [(r"injur|hurt|surgery|punctured|broken", "Injury Update"),(r"\bvs\.?\b", "Match Made"),(r"return|comeback|back in", "Comeback Watch"),
 (r"\\bsign(s|ed|ing)?\\b|contract|free agent|\\breleased?\\b|departure|\\bleaves?\\b|\\bleaving\\b|\\bexits?\\b", "Contract News"),
 (r"results|recap|review|grades", "Results Recap"),(r"retire|final match|farewell|last match", "End of an Era"),(r"\\bnew champion|\\bwins? the\\b.*\\b(title|championship)|\\bretains?\\b|\\btitle change", "Title Picture"),
 (r"backstage|plans|unhappy|heat|creative", "Backstage Buzz"),(r"ratings|viewership|ticket|sales|attendance", "By the Numbers"),
 (r"died|passed away|death|rip\b", "In Memoriam"),(r"lawsuit|sued|court|arrest", "Legal Watch")]
def enrich_hl(t): return tcase(re.sub(r"\s+[-|]\s+[^-|]+$", "", t))
def headline(t, kind=None):
    h = headline_old(enrich_hl(t))
    if kind == 'results': h = re.sub(r'^(Match Made|Results Recap):\s*', '', h); return h if re.match(r'(?i)results recap', h) else 'Results Recap: ' + re.sub(r'(?i)\s*\b(results|recap)\b\s*', ' ', h).strip()
    if kind == 'match': return 'Match Made: ' + re.sub(r'^(Match Made:\s*)', '', h)
    if kind == 'quote' and not re.search(r'injur|retire|died|passed away', t, re.I): return 'On the Record: ' + h; h = re.sub(r"\b(\w+) \1\b", r"\1", h)
    h = re.sub(r"^(Backstage|Report|Breaking|Exclusive)\s*[:\-–—]?\s*", "", h)
    for pat, hook in HOOKS:
        if re.search(pat, t, re.I) and hook.split()[-1].lower() not in h.lower():
            for w in hook.split()[-1:]: h = re.sub(r"\s*\b%s\b\s*$" % w, "", h, flags=re.I)
            return f"{hook}: {h}"
    return h
def headline_old(t):
    h = re.sub(r"\s+[-|]\s+[^-|]+$", "", t)
    for a, b in HL:
        if re.search(a, h, re.I): h = re.sub(a, b, h, count=1, flags=re.I); break
    else:
        m = re.match(r"(.+?):\s*(.+)$", h)
        if m and len(m.group(1)) < 40: h = f"{m.group(2)} — {m.group(1)}"
    return h.strip()
def update_line(it):
    s = (it.get("summary") or "").split(". ")[0].rstrip(".")
    return (s[:160].rsplit(" ", 1)[0] + "…") if len(s) > 160 else s + "."
# ---------- clustering ----------
GENERIC = set("wwe aew tna raw smackdown nxt dynamite collision wrestling pro news report update results star stars match title champion championship".split())
import functools
@functools.lru_cache(maxsize=None)
def entities(t):
    e = set(m.lower() for m in re.findall(r"\b[A-Z][a-zA-Z'’]+(?:\s+[A-Z][a-zA-Z'’]+)+\b", t))
    e |= set(w.lower() for w in re.findall(r"\b[A-Z][a-zA-Z]{3,}\b", t))
    from aliases import ALIASES
    e |= {k.lower() for k in ALIASES if re.search(r"\b" + re.escape(k) + r"(?![a-z])", t, re.I)}
    return {x for x in e if x not in GENERIC and x not in CGEN and x not in STOP and x not in ("medical", "late", "former", "report", "breaking") and not x.startswith(("former ", "ex-", "late ")) and not re.match(r"^(former|wwe|aew|tna|nxt)\b", x)}
from aliases import canon as _canon
canon = functools.lru_cache(maxsize=None)(_canon)
EVENT = re.compile(r"\b(died|death|passed away|cause of death|medical examiner|injur\w*|surgery|retire\w*|signs?|signed|released?|departs?|exit|lawsuit|sued|arrest\w*|suspend\w*|returns?|debut\w*|wins?|crowned|vacate\w*|cancel\w*|postpon\w*|crowned)\b", re.I)
EVN = {"died":"death","death":"death","passed":"death","cause":"death","medical":"death","examiner":"death","retire":"retire","retires":"retire","retirement":"retire","retiring":"retire","sued":"lawsuit","lawsuit":"lawsuit"}
import editorial as _ed
# two different matches from the same show must not merge (e.g. "Persephone retains TBS title" vs "Nick Wayne beats Jericho",
# or a multi-match card preview bridging them): see _different_match() used by similar()
from aliases import ALIASES as _AL
_EXEC = {"tony khan","triple h","nick khan","paul levesque","nick aldis","adam pearce","michael cole","pat mcafee","dave meltzer","carlos silva","santino marella","scott d'amore","vince mcmahon","stephanie mcmahon","shawn michaels","eric bischoff","jim ross","jim cornette","bully ray","paul heyman","bruce prichard","tony schiavone","excalibur","taz"}
_PNAMES = sorted({x.strip() for x in ("|".join(_ed.ROSTER.values()) + "|" + _ed.FIG + "|" + "|".join(_AL)).split("|") if len(x.strip()) > 2 and x.strip().lower() not in _EXEC and not re.search(r"[\\\[\]()]", x)}, key=len, reverse=True)
_PRX = re.compile(r"\b(" + "|".join(re.escape(p) for p in _PNAMES) + r")(?![a-z])", re.I)
@functools.lru_cache(maxsize=None)
def persons(t): return frozenset(m.lower() for m in _PRX.findall(t))
@functools.lru_cache(maxsize=None)
def evkeys(t): return {EVN.get(m.lower().split()[0], m.lower()[:5]) for m in EVENT.findall(t)}
@functools.lru_cache(maxsize=None)
def _tk(t): return frozenset(set(toks(t)) - GENERIC - CGEN)
_MON = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
@functools.lru_cache(maxsize=None)
def dates(t):
    out = {f"{int(m)}/{int(d)}" for m, d in re.findall(r"\b(1[0-2]|0?[1-9])[/-]([12]\d|3[01]|0?[1-9])\b", t)}
    out |= {f"{_MON[m[:3].lower()]}/{int(d)}" for m, d in re.findall(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2})\b", t, re.I)}
    return frozenset(out)
_SHOW_RECAP = re.compile(r"(?i)^(?=.*\b(raw|smackdown|nxt|dynamite|collision|impact|rampage)\b)(?=.*\b(results?|recap|review|live updates|report|preview)\b)")
def _different_match(a, b):
    """A results report vs. an article naming none of its wrestlers (checked on the source titles AND our rewritten headlines,
    which can drop first names: 'Jericho-Wayne 3')."""
    if "results" not in ((a.get("kind") or {}).get("type"), (b.get("kind") or {}).get("type")): return False
    if _recap(a["raw_title"]) or _recap(b["raw_title"]): return False   # weekly-show recaps ('SmackDown Results 10/16') keep the old rules
    pa = _pp(a["raw_title"], a.get("title") or ""); pb = _pp(b["raw_title"], b.get("title") or "")
    return bool(pa and pb and not pa & pb)
@functools.lru_cache(maxsize=None)
def _recap(t): return bool(_SHOW_RECAP.search(t))
@functools.lru_cache(maxsize=None)
def _pp(raw, title): return persons(canon(raw)) | persons(canon(title))
def similar(a, b):
    if _different_match(a, b): return False
    sa, sb = shows(a["raw_title"]), shows(b["raw_title"])
    if sa and sb and not sa & sb: return False   # different shows/events ('TNA Destination X' vs 'NJPW Power Struggle')
    j = _teaser_join(a, b)                       # a headline naming nobody: only via its own text (see _teaser_join)
    if j is not None: return j and not conflict(a, b)
    hit = _sim(a, b) or _same_signing(a, b) or bool(a.get('llm') and b.get('llm') and _sim({**a, 'raw_title': a['title']}, {**b, 'raw_title': b['title']}))
    return hit and not conflict(a, b)            # never different promotions or different named wrestlers (see conflict())
def _sim(a, b):
    if abs(a["ts"] - b["ts"]) > 72*3600: return False
    A, B = canon(a["raw_title"]), canon(b["raw_title"])
    da, db = dates(A), dates(B)
    if da and db and not da & db: return False
    SH = r"\b(raw|smackdown|nxt|dynamite|collision|impact|rampage)\b"
    RS = r"\b(results?|recap|review|live updates|report)\b"
    sa, sb = set(re.findall(SH, A.lower())), set(re.findall(SH, B.lower()))
    if da & db and sa & sb and re.search(RS, A, re.I) and re.search(RS, B, re.I): return True
    ea, eb = entities(A), entities(B)
    if persons(A) & persons(B) and evkeys(A) & evkeys(B) - {"wins", "retur", "debut", "signs"}: return True
    ta, tb = _tk(A), _tk(B)
    if not ta or not tb: return False
    j = len(ta & tb) / len(ta | tb)
    shared = ea & eb
    return j >= .5 or (len(shared) >= 2 and j >= .3) or (len(shared) >= 1 and j >= .42)
_WIN = 72*3600   # similar() is always False for reports more than 72h apart (_sim's first check) - used to skip pairs safely
GSIM_MAX = 12   # members per group compared when merging groups (oldest + newest first); was only the first and last report
def _reps(g): return g if len(g) <= GSIM_MAX else g[:GSIM_MAX // 2] + g[-(GSIM_MAX // 2):]
def _gsim(gi, gj):
    """Two groups are one story if ANY of their reports match (not just the oldest/newest pair: the two Shotzi Blackheart
    'keeps indie dates' reports sat in separate stories because their first/last reports didn't match each other)."""
    if _gclash(gi, gj): return False
    if any(similar(x, y) for x in (gi[0], gi[-1]) for y in (gj[0], gj[-1])): return True
    # beyond the oldest/newest pair, only when both groups are mainly about the same named wrestler (otherwise 'any member
    # matches any member' chains unrelated stories: a Gowen retirement joining a Copeland retirement)
    ti, tj = _top_subj(gi), _top_subj(gj)
    # and at least two cross pairs agree, so one loose match can't chain two angles (Dragunov on Japan / Dragunov on Bandido)
    return bool(ti) and ti == tj and sum(similar(x, y) for x in _reps(gi) for y in _reps(gj)) >= 2
def _top_subj(g):
    from collections import Counter
    c = Counter(p for m in g for p in subj_of(m))
    if not c: return None
    p, n = c.most_common(1)[0]
    return p if n * 2 >= len(g) else None
def _gclash(gi, gj):
    """Groups (or a report and a group) are different stories if at least half of their cross pairs clash (different promotion
    or different wrestlers). Half, not any: one tangential report inside a group ('Tony Khan on Steven Borden' among Toni Storm
    reports) must not keep the rest of the same story apart."""
    n = bad = 0
    for x in gi:
        for y in gj:
            n += 1; bad += conflict(x, y)
    return bad * 2 >= n
def cluster(articles):
    """Same result as the original greedy pass + restart-from-the-top merge loop, without the O(merges x groups^2) rescans:
    groups stay ordered by their oldest report, so a scan for group i stops once group j starts >72h after i's newest report,
    and after a merge only the pairs involving the changed group are re-checked, in the order the full restart would reach them."""
    arts = sorted(articles, key=lambda x: x["ts"]); groups = []
    for a in arts:
        for g in groups:
            if g[-1]["ts"] < a["ts"] - _WIN: continue    # every candidate in g is older than the window
            if (similar(a, g[0]) or any(similar(a, m) for m in g[-3:])) and not _gclash([a], g): g.append(a); break
        else: groups.append([a])
    def merge(i, j): groups[i] = sorted(groups[i] + groups.pop(j), key=lambda x: x["ts"])
    def first_j(i, start):
        lim = groups[i][-1]["ts"] + _WIN
        for j in range(start, len(groups)):
            if groups[j][0]["ts"] > lim: return None
            if _gsim(groups[i], groups[j]): return j
        return None
    i = 0
    while i < len(groups):
        j = first_j(i, i + 1)
        if j is None: i += 1; continue
        merge(i, j)
        # a full restart would now re-check (k, i) for k < i first (only pairs with the changed group i can be new)
        while True:
            k = next((k for k in range(i) if groups[i][0]["ts"] - groups[k][-1]["ts"] <= _WIN and _gsim(groups[k], groups[i])), None)
            if k is None: break
            merge(k, i); i = k
    out = []
    for g in groups:
        g = sorted(g, key=lambda x: -x["ts"]); import freshness as _fr
        newest = max((_fr.real_ts(x) or 0) for x in g); kinds = [kind_of(x) for x in g if kind_of(x)]
        dom = max(set(kinds), key=kinds.count) if kinds and kinds.count(max(set(kinds), key=kinds.count)) * 2 >= len(g) else None
        # lead: names the wrestler > not an old report > says what most reports say (a signing story leads with the signing) > tier > newest
        toks_ = {id(x): _tk(canon(x["raw_title"])) for x in g}
        def central(x):   # how typical x's headline is of the story (a signing story leads with 'X Signs With TNA', not a side angle)
            if len(g) < 6: return 0
            a = toks_[id(x)]
            return round(sum(len(a & toks_[id(y)]) / len(a | toks_[id(y)]) for y in g if y is not x and a | toks_[id(y)]) / (len(g) - 1), 1)
        main = min(g, key=lambda x: (teaser(x), _fr.older_than(x, newest, 48*3600), bool(dom) and kind_of(x) != dom,
                                     TIER(x["source"]) if TIER else 0, -central(x), -x["ts"]))
        best_img = next((m["image"] for m in g if m.get("image")), None)
        cats = sorted({c for m in g for c in m["categories"]}, key=["WWE","AEW","TNA","Indie","Global"].index)
        out.append({"id": "c" + g[-1]["id"], "title": main["title"], "summary": main["summary"], "link": main["link"],
            "source": main["source"], "first_ts": g[-1]["ts"], "lead_ts": main["ts"], "image": best_img, "categories": main["categories"],
            "added": max(m.get("added", 0) for m in g),
            "raw_title": main["raw_title"], "src_summary": (main.get("summary_src") or "")[:500], "kind": main.get("kind", {"type": "news"}),
            "ts": g[0]["ts"],   # latest activity (newest report) -> feed sort order; first_ts = when the story was first reported
            "updates": [{"ts": m["ts"], "line": update_line(m), "source": m["source"], "link": m["link"], "title": m["title"]} for m in g if m is not main]})
        if all(teaser(m) for m in g): out[-1]["unnamed"] = True   # no headline names who it's about: not a story (owner rule)
    return sorted(out, key=lambda c: -feed_ts(c))
FRESH_BUMP = 48 * 3600
def feed_ts(c):
    """Feed position of a story: its latest activity, but never more than 48h after it was first reported, so a story first
    reported > 48h ago is never bumped back to the top as new by a late report (owner rule 2026-10-21; 'Updated' still shows)."""
    f = c.get("first_ts") or c["ts"]
    return min(c["ts"], f + FRESH_BUMP)
VERSION = 7
def img_score(u, src):
    if not u: return -99
    s = 0
    if re.search(r"1920|scaled|1200|large|full|w=1[0-9]{3}", u): s += 3
    if re.search(r"thumb|150x|300x|small|-\d{2,3}x\d{2,3}\.", u): s -= 3
    if re.search(r"logo|graphic|banner|poster", u, re.I): s -= 1
    return s
_old_cluster = cluster
JUNK_IMG = re.compile(r"(?i)click[-_]?to[-_]?unlock|placeholder|default[-_](image|thumb|og)|no[-_]image|fallback")
_SHOWS = [("raw", r"\braw\b"), ("smackdown", r"smackdown"), ("nxt", r"\bnxt\b"), ("dynamite", r"dynamite"), ("collision", r"collision"),
          ("rampage", r"rampage"), ("impact", r"\bimpact\b|\btna\b"), ("roh", r"\broh\b|ring of honor"), ("wrestledream", r"wrestledream"),
          ("crownjewel", r"crown jewel"), ("mitb", r"money in the bank|\bmitb\b"), ("survivor", r"survivor series"), ("fullgear", r"full gear"),
          ("njpw", r"\bnjpw\b|new japan"), ("cmll", r"\bcmll\b"), ("aaa", r"\baaa\b"), ("mlw", r"\bmlw\b"), ("nwa", r"\bnwa\b")]
@functools.lru_cache(maxsize=None)
def shows(t): return frozenset(k for k, rx in _SHOWS if re.search(rx, t, re.I))
def about_same(m, main):
    """True if cluster member m is really about the lead article's story (not just a same-show/same-night neighbour)."""
    if m is main: return True
    if conflict(m, main): return False
    sm, sM = shows(m["raw_title"]), shows(main["raw_title"])
    if sm and sM and not sm & sM: return False      # 'TNA Impact taping spoiler' photo on a 'next week's SmackDown' card
    pm, pM = persons(canon(m["raw_title"])), persons(canon(main["raw_title"]))
    if pm and pM: return bool(pm & pM)
    if sM and not sm & sM: return False             # lead is about a show; member names neither that show nor the lead's people
    return True                                     # otherwise it's in the cluster: trust the clustering
def cluster(articles):
    """Card image: the LEAD article's own photo first; another member's photo only if that member is about the same people/story
    and its photo scores better (bigger/non-thumbnail). Before this, ties went to the OLDEST member (max() keeps the first), so a
    WrestleDream card preview's Jericho photo became the image of the Persephone TBS-title result. c['member_images'] (lead first,
    on-topic members only) feeds the vision check; aggregator pops it before writing news.json."""
    _F.clear()
    out = _old_cluster(articles); bylink = {}
    for a in articles: bylink.setdefault(a["link"], a)
    # stock/promo photos an outlet puts on many unrelated articles (podcast 'click to unlock' art, show logos, file photos)
    use = {}; cl_of = {}
    for c in out:
        for l in [c["link"]] + [u["link"] for u in c["updates"]]: cl_of[l] = c["id"]
    for a in bylink.values():
        if a.get("image"): use.setdefault(a["image"].split("?")[0], set()).add(cl_of.get(a["link"], a["link"]))
    generic = {u for u, cs in use.items() if len(cs) >= 3}   # same photo on 3+ different stories (an event poster on 3 reports of ONE story is fine)
    def sc(m):
        u = m.get("image") or ""
        return img_score(u, m["source"]) - (6 if u.split("?")[0] in generic or JUNK_IMG.search(u) else 0)
    for c in out:
        main = bylink.get(c["link"])
        if not main: continue
        others = [bylink[u["link"]] for u in sorted(c["updates"], key=lambda u: -u["ts"]) if u["link"] in bylink]
        pool = [main] + [m for m in others if m is not main and about_same(m, main)]
        pool = list({id(m): m for m in pool}.values())
        csub = frozenset().union(*(subj_of(m) for m in pool)); cpro = promos_of(main)
        ctxt = (main.get("raw_title") or "") + " | " + (main.get("title") or "") + " | " + (main.get("summary") or "")
        withimg = [m for m in pool if m.get("image") and not JUNK_IMG.search(m["image"]) and not img_clash(m["image"], csub, cpro, ctxt)
                   and not foreign_promo(m["image"], cpro, src=m.get("raw_title") or "", story_text=ctxt)[0]]   # e.g. a head-to-head piece's split graphic
        best = max(withimg, key=sc) if withimg else None
        if best and main in withimg and sc(main) >= sc(best) - (0 if re.search(r"(?i)logo|graphic|poster", main["image"]) else 2): best = main
        c["image"] = best["image"] if best else None
        c["member_images"] = list(dict.fromkeys(m["image"] for m in ([best] if best else []) + withimg if m.get("image")))
        c["member_src"] = {m["image"]: m.get("raw_title") or "" for m in pool if m.get("image")}   # image -> its report's headline (vision.choose)
    return out

# ---------- subject / promotion guards ----------
# 2026-10-21: 'WWE Star Signs New Contract' (PWInsider teaser naming nobody) matched 'Santino Marella Signs New TNA Deal' on the
# words 'signs new deal' alone, so Dragon Lee's WWE re-signing, Santino Marella's TNA re-signing and Shotzi Blackheart's TNA signing
# ended up in one story with a WWE headline, a Dragon Lee photo and a Santino/Shotzi body. Rules now:
#  - contract boilerplate (signs/re-signs/new deal/contract/extension/exclusive/star...) never counts as a topic match;
#  - two reports (or two groups of reports) are never merged if they name different promotions or different wrestlers;
#  - a headline that names nobody ('WWE Re-Signs Former Tag Team Champion') joins a story only if its own text names that story's
#    wrestler, never becomes the lead when a named report exists, and a story made only of such teasers is not published;
#  - the card photo may not be a file named after a different wrestler or promotion.
CGEN = set("sign signs signed signing re-signs resigns resign resigned ink inks inked deal deals contract contracts extension extensions extend extends extended agreement new exclusive reportedly officially star stars superstar talent legend wrestler former multi year years long-term term".split())
_SNAMES = sorted(set(_PNAMES) | {x for x in _EXEC if len(x) > 3}, key=len, reverse=True)
_SRX = re.compile(r"\b(" + "|".join(re.escape(p) for p in _SNAMES) + r")(?![a-z])", re.I)
@functools.lru_cache(maxsize=None)
def subjects(t):
    """Every named wrestler/on-air figure in t (canonical, lower case), executives and authority figures included.
    A nickname match doesn't hide the name inside it ('Timeless Toni Storm' -> 'timeless toni' and 'toni storm')."""
    t = canon(t or ""); out = set()
    for m in _SRX.finditer(t):
        out.add(m.group(0).lower())
        for w in re.finditer(r"\S+", m.group(0)):
            if w.start() == 0: continue
            mm = _SRX.match(t, m.start() + w.start())
            if mm and mm.end() > m.end(): out.add(mm.group(0).lower())
    return frozenset(out)
_HEAD = re.compile(r"^(?:[A-Z][\w'’]*:\s*)?([A-Z][a-z'’]+ [A-Z][a-z'’]+)\b")
_NOTHEAD = re.compile(r"(?i)\b(wwe|aew|tna|nxt|raw|smackdown|dynamite|collision|impact|report|reports|breaking|exclusive|latest|update|backstage|former|major|new|big|top|the|this|why|how|what|who|results?|review|watch|live|night|world|title|tag|team|women|men)\b")
def _head(a):
    """Unknown subject named at the start of the source headline ('Billy Gunn sides with...' / 'Billy Gunn Takes A Shot...')."""
    def f(a):
        m = _HEAD.match(a.get("raw_title") or "")
        return m.group(1).lower() if m and not _NOTHEAD.search(m.group(1)) and m.group(1).lower() not in _EXEC else ""
    return _fc("h", a, f) or None
def _keys(names): return {re.sub(r"s$", "", n.split()[-1]) for n in names}   # 'the hardys' ~ 'matt hardy'; 'dragon lee' -> 'lee'
def same_people(a, b):
    """Shared wrestler (or surname). Executives/authority figures only count when one side names nobody else:
    'Tony Khan on Toni Storm' vs 'Tony Khan on Kairi Sane' are different stories."""
    na, nb = a - _EXEC, b - _EXEC
    if na and nb: a, b = na, nb
    return bool(a & b) or bool(_keys(a) & _keys(b))
_PROMOS = [("wwe", r"\bWWE\b|\bNXT\b|\bRAW\b|SmackDown|WrestleMania|Survivor Series|Crown Jewel|Royal Rumble|SummerSlam|Saturday Night'?s Main Event|Halloween Havoc"),
           ("aew", r"\bAEW\b|\bROH\b|Ring of Honor|Dynamite|Collision|Rampage|All Elite|WrestleDream|Full Gear|Double or Nothing|Forbidden Door"),
           ("tna", r"\bTNA\b|\biMPACT\b|\bIMPACT\b|Impact Wrestling|Bound for Glory|Destination X|Hard to Kill|Knockouts"),
           ("njpw", r"\bNJPW\b|New Japan|Wrestle Kingdom"), ("cmll", r"\bCMLL\b|Arena M[eé]xico"), ("aaa", r"\bAAA\b|Lucha Libre AAA|Triplemania"),
           ("mlw", r"\bMLW\b|Major League Wrestling"), ("gcw", r"\bGCW\b"), ("nwa", r"\bNWA\b"), ("stardom", r"\bStardom\b"),
           # non-wrestling combat sports count as their own 'promotion' so a UFC report can never merge with, lead, or lend its
           # poster/write-up to a wrestling story ('UFC 333 Start Times' + 'AAA Heroes Inmortales Start Times', 2026-10-21)
           ("combat", r"\bUFC\b|\bMMA\b|\bBellator\b|\bPFL\b|ONE Championship|\bZuffa Boxing\b|\bboxing\b|\bkickboxing\b|\bBKFC\b")]
_PRO_RX = [(k, re.compile(rx, re.I if k not in ("wwe", "tna") else 0)) for k, rx in _PROMOS]
_PN = r"(?:WWE|AEW|TNA|NXT|ROH|MLW|NJPW|CMLL|AAA|Impact|IMPACT|GCW|NWA)"
_FORMER = re.compile(r"(?i)\b(?:former|ex-|ex|one-time|onetime|longtime|then-)\s*(?:" + _PN + r"\s*(?:(?:,|/|&|and)\s*)?)+"
                     r"|\b" + _PN + r"\s+(?:legend|hall of famer|veteran|alum\w*|icon|original)s?\b"
                     r"|\b(?:formerly (?:of|with|in)|leaves?|leaving|left|exits?|exited|departs?|departed|quits?|released by|from|after|before) " + _PN + r"\b(?:\s+(?:exit|departure|release|run|contract))?")
@functools.lru_cache(maxsize=None)
def promos(t):
    """Promotions a headline is about now ('Former WWE Star X Signs With TNA' -> {'tna'}; WWE/NXT and AEW/ROH count as one)."""
    t = _FORMER.sub(" ", t or "")
    t = re.sub(r"\bRaw\b", "RAW", t)
    return frozenset(k for k, rx in _PRO_RX if rx.search(t))
_F = {}   # per-cluster()-call cache of per-report features, keyed by (id(report), titles)
def _fc(kind, a, fn):
    k = (kind, id(a), a.get("raw_title"), a.get("title"))
    v = _F.get(k)
    if v is None: v = _F[k] = fn(a)
    return v
def subj_of(a): return _fc("s", a, lambda a: subjects(a.get("raw_title") or "") | subjects(a.get("title") or ""))
def promos_of(a): return _fc("p", a, lambda a: promos(a.get("raw_title") or "") | promos(a.get("title") or ""))
_CONTRACT = re.compile(r"(?i)\bre-?sign(?:s|ed|ing)?\b|\bsign(?:s|ed|ing|ee)\b|\binks?\b|\binked\b|\bnew (?:[\w-]+ ){0,2}(?:deal|contract)\b|\bcontract extension\b|\bextends? (?:\w+ )?(?:deal|contract)\b")
_NOTNAME_W = set("""wwe aew tna nxt roh mlw njpw cmll aaa gcw nwa raw smackdown dynamite collision impact wrestling pro news report update
 results star stars superstar superstars talent legend legends veteran wrestler wrestlers champion champions championship title titles tag team
 former new major big top latest exclusive breaking official officially reportedly signs signed sign signing re-signs re-signed re resigns
 deal deals contract contracts extension agreement inks inked announces announced confirms confirmed adds added another two three hall fame
 famer world women's women men's men director authority on-air air fan fans favorite favorites spoiler id performance center rookie
 spotted seen sighted talents teases tease end era injury injured announces announcement retirement retires
 joins joined join dealing deals injury injuries injured surgery netflix series cast show shows exit exits additional dark match matches taping
 status future health return returns returning debut debuts debuted released release releases arrested suspended provides gives update
 updates major minor key backstage reported reports say says after before amid following during heading expected set lands landed
 knockout knockouts luchador free agent personality figure athlete competitor gets got makes made announcement announcements""".split())
@functools.lru_cache(maxsize=None)
def _named(t):
    """Headline names someone, even a wrestler not on our lists ('Necro Butcher'): two capitalised non-generic words in a row."""
    w = re.findall(r"[A-Za-z][\w'’.-]*", t or "")
    ok = [x[0].isupper() and x.lower().strip("'’.") not in _NOTNAME_W and x.lower() not in STOP for x in w]
    if any(ok[i] and ok[i + 1] for i in range(len(ok) - 1)): return True
    if any(ok[i] and ok[i + 2] and w[i + 1].lower() in ("and", "&") for i in range(len(ok) - 2)): return True   # 'Borden and Ford'
    # a lone surname/ring name leading an event verb: 'Gowen Retires After 24-Year Career', 'Danhausen Signs ...'
    return bool(len(w) > 1 and ok[0] and re.match(r"(?i)(re-?signs?|signs?|signed|retires?|retired|released|injured|returns?|debuts?|joins?|exits?|leaves|wins?|beats?|defeats?|says|reveals?)$", w[1]))
def _contractish(a): return _fc("c", a, lambda a: bool(_CONTRACT.search((a.get("raw_title") or "") + " | " + (a.get("title") or ""))))
# nameless person-news (owner rule 2026-10-21): signings, re-signings, injuries, releases, exits, debuts, returns, arrests...
_VAGUE_EVT = re.compile(r"(?i)\b(injur\w*|surgery|sidelined|health|released?|fired|let go|cut|exits?|departs?|departure|leaves|leaving|"
                        r"debuts?|debuted|returns?|returning|arrest\w*|charged|suspend\w*|retire\w*|dies|died|passes away|passed away|joins?|joined|"
                        r"hired|quits?|absent|pulled|replaced|status|future|spoiler|deal|contract|signing|signs?|signed|update)\b")
_VAGUE_NOUN = re.compile(r"(?i)\b(star|superstar|wrestler|talent|legend|veteran|champion|titleholder|name|performer|knockout|luchador|luchadora|"
                         r"newcomer|signing|free agent|hall of famer|competitor|fan favou?rite|personality|figure|athlete|grappler)s?\b")
_SEGMENT = re.compile(r"(?i)contract signing|signing ceremony|autograph|signing session|meet (?:and|&) greet")
def teaser(a):
    """A person-news headline that names nobody: 'WWE Star Signs New Deal', 'TNA Announces New Signing', 'TNA Signing Confirmed',
    'AAA Star Dealing With Injury', 'WWE Signs New ID Talent', 'Exclusive: ...'. Such a report may support a story that names the
    person (consistency of its own text is checked by _teaser_join) but never leads one or becomes one."""
    def f(a):
        rt, tt = a.get("raw_title") or "", a.get("title") or ""
        if subj_of(a) or _named(rt) or _named(tt): return False
        t = rt + " | " + tt
        if _SEGMENT.search(t): return False
        if _CONTRACT.search(t): return True
        if _VAGUE_NOUN.search(t) and _VAGUE_EVT.search(t): return True
        return bool(re.match(r"(?i)\s*exclusive\b", rt) and not shows(rt) and not _SHOWLEVEL.search(rt))
    return _fc("t", a, f)
# ---------- signing kind: new signing / re-signing / contract expiring / release ----------
_K_RE = re.compile(r"(?i)\bre-?sign(?:s|ed|ing)?\b|\bresign(?:s|ed|ing)\b|\bextension\b|\bextends?\b|\bextended\b|\brenew\w*|"
                   r"\bstay(?:s|ing)? (?:with|in|at)\b|\bremains? with\b|\bnew (?:[\w-]+ ){0,3}(?:deal|contract)\b|\bcontract (?:renewal|extension)")
_K_EXP = re.compile(r"(?i)contract (?:expires?|expired|expiring|is up|ends|ended|ending|set to expire|has expired|coming up)|\bfree agent\b|\bexpir(?:es|ed|ing)\b")
_K_REL = re.compile(r"(?i)\breleased?\b|\bdeparts?\b|\bdeparted\b|\bleaves\b|\bleaving\b|\bexits?\b|\bexited\b|\bparts? ways\b|\bpart ways\b|\blet go\b|\bfired\b|\bgets cut\b")
_K_NEW = re.compile(r"(?i)\bsigns?\b|\bsigned\b|\bsigning\b|\bsignee\b|\bjoins?\b|\bjoined\b|\binks?\b|\binked\b|\bacquires?\b|\bhired\b|\bis all elite\b|\bheading to\b|\bcoming to\b")
@functools.lru_cache(maxsize=None)
def signing_kind(t):
    """'re-sign' | 'expiring' | 'release' | 'new' | None, from a headline's own wording. 'Signs new deal/contract' = re-signing."""
    t = t or ""
    if _K_RE.search(t): return "re-sign"
    if _K_EXP.search(t): return "expiring"
    if _K_REL.search(t): return "release"
    if _K_NEW.search(t): return "new"
    return None
def kind_of(a): return _fc("k", a, lambda a: signing_kind(a.get("raw_title") or "") or signing_kind(a.get("title") or ""))
def body_subj(a): return subjects(((a.get("summary_src") or "")[:500] + " " + (a.get("body") or "")[:800]))
def body_lead(a):
    """First wrestler the report's own text names (who a nameless headline is about)."""
    t = canon((a.get("summary_src") or "")[:500] + " " + (a.get("body") or "")[:800])
    m = _SRX.search(t)
    return m.group(0).lower() if m else None
def conflict(a, b):
    """True if a and b can't be one story: different promotions, or both name wrestlers and none of them is shared
    (a weekly-show recap naming several people is exempt from the people rule, not from the promotion rule)."""
    sa, sb = subj_of(a), subj_of(b)
    ha = _head(a)
    if ha and ha == _head(b): return False             # same (possibly unlisted) person leads both headlines
    if sa and sb and same_people(sa, sb): return False # same wrestler: outlets' promotion labels differ ('AEW star PAC' / 'WWE wrestler Pac')
    pa, pb = promos_of(a), promos_of(b)
    if pa and pb and not pa & pb: return True
    if _recap(a.get("raw_title") or "") or _recap(b.get("raw_title") or ""): return False
    if _SHOWLEVEL.search(a.get("raw_title") or "") or _SHOWLEVEL.search(b.get("raw_title") or ""): return False   # show results/preview names many people
    if sa and sb: return True
    # a wrestler not on our lists leads one headline ('Anya Rune Steps Away From Wrestling') and someone else the other
    # ('Max Caster Steps Away From Wrestling'): same words, different people
    na, nb = sa | ({ha} if ha else set()), sb | ({_head(b)} if _head(b) else set())
    return bool(na and nb and (ha or _head(b)) and not same_people(frozenset(na), frozenset(nb)))
_SHOWLEVEL = re.compile(r"(?i)\b(results?|recap|review|preview|report|card|line-?up)\b")
def _teaser_join(a, b):
    """None = no opinion. A nameless contract teaser joins a named contract report only if its own text names that wrestler."""
    ta, tb = teaser(a), teaser(b)
    if not (ta or tb): return None
    if not (_contractish(a) or _contractish(b)):      # nameless injury / release / debut teaser: own text must name the wrestler
        if ta and tb: return False
        T, O = (a, b) if ta else (b, a)
        lead = body_lead(T)
        return bool(abs(T["ts"] - O["ts"]) <= 72*3600 and lead and same_people(frozenset([lead]), subj_of(O))
                    and evkeys(canon(T["raw_title"])) & evkeys(canon(O["raw_title"])))
    if ta and tb: return False                         # two nameless teasers: nothing says they're about the same person
    T, O = (a, b) if ta else (b, a)
    if abs(T["ts"] - O["ts"]) > 72*3600 or not _contractish(O): return False
    kt, ko = kind_of(T), kind_of(O)
    if {kt, ko} == {"new", "re-sign"}: return False    # 'TNA Re-Signs Wrestling Legend' is not 'TNA Signs Shotzi Blackheart'
    lead = body_lead(T)
    return bool(lead and same_people(frozenset([lead]), subj_of(O)))
def _fname_words(u):
    p = urllib.parse.unquote(urllib.parse.urlsplit(u or "").path).rsplit("/", 1)[-1]
    w = re.sub(r"[-_.+]+", " ", re.sub(r"\.(jpe?g|png|webp|gif|avif)$", "", p, flags=re.I))
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", w)
def img_clash(u, story_people, story_promos, story_text=""):
    """The photo's file name names a wrestler who isn't in the story, or a promotion the story isn't about."""
    w = _fname_words(u)
    n = subjects(w)
    if n and story_people and not same_people(n, story_people): return True
    return bool(_foreign(label_promos(w), story_promos, story_text))
# ---------- other-promotion branding on a photo (2026-10-22) ----------
# 'AEW Blood And Guts 2026 Match Set' showed Ringside News' split 'NXT logo | Dynamite Blood and Guts poster' graphic
# (file 'wwe-nxt-expected-to-go-head-to-head-with-aew-blood-amp-guts...jpg', from a head-to-head ratings article). The old rule
# only asked that the photo share ONE promotion with the story; now every promotion a photo is tied to must be one the story's
# own text (headline + summary) names. WWE/NXT and AEW/ROH still count as one (enrich.promos).
SPLIT_RX = re.compile(r"(?i)\bvs\.?(?![a-z])|\bversus\b|head[- ]to[- ]head|ratings? (?:war|battle|fight)|\bopposite\b|counter-?program\w*|"
                      r"\bgo(?:es|ing)? (?:up )?against\b|\bcompet\w* (?:with|against) \w+ (?:for )?(?:viewers|ratings|viewership)|\bviewership\b|\bratings?\b")
_ABBR = re.compile(r"(?i)\b(wwe|nxt|tna|aew|roh|njpw|cmll|aaa|mlw|gcw|nwa|ufc|mma|pfl|bkfc)\b")
def label_promos(t):
    """promos() for file names / alt text, where 'wwe-nxt-...' is lower case (promos() is case-sensitive for WWE/TNA)."""
    return promos(_ABBR.sub(lambda m: m.group(1).upper(), t or ""))
_CROSS = re.compile(r"(?i)\bbox(?:er|ers|ing)\b|\bfighter\b|\bUFC\b|\bMMA\b|\bPFL\b|\bBKFC\b")
def mentioned(t):
    """Every promotion a text names, 'former X' included (promos() drops those)."""
    t = re.sub(r"\bRaw\b", "RAW", t or "")
    return frozenset(k for k, rx in _PRO_RX if rx.search(t)) if t else frozenset()
def _foreign(p, sp, story_text=""):
    """Promotions in p that the story (promotions sp) isn't about. A combat-sports tag next to the story's own promotion is
    fine for crossover stories ('wwe-star-boxing-debut.jpg')."""
    if not p or not sp: return frozenset()
    f = p - sp - mentioned(story_text)   # any mention counts, 'former AEW champion' too (Max Caster's old Dynamite photo)
    if f == {"combat"} and (p & sp or _CROSS.search(story_text or "")): return frozenset()
    return f
def foreign_promo(u, story_promos, label="", src="", story_text=""):
    """(other promotions the image is tied to, strong?) for a story about `story_promos`.
    strong: the image's own file name / alt / caption names a promotion the story isn't about (free, certain enough to drop).
    weak:   the image names no promotion, but the article it came from is a 'vs' / head-to-head / ratings piece whose headline
            names another promotion (a split graphic is likely; vision may confirm)."""
    sp = frozenset(story_promos or ())
    if not sp: return frozenset(), False
    lp = label_promos(_fname_words(u) + " | " + (label or ""))
    if lp: return _foreign(lp, sp, story_text), True
    if src and SPLIT_RX.search(src + " | " + (label or "") + " | " + _fname_words(u)):
        return _foreign(promos(src), sp, story_text), False
    return frozenset(), False
def _same_signing(a, b):
    """Both headlines are about a contract/signing of the same named wrestler with the same promotion, within 72h."""
    if not (_contractish(a) and _contractish(b)) or abs(a["ts"] - b["ts"]) > 72*3600: return False
    sa, sb = subj_of(a) - _EXEC or subj_of(a), subj_of(b) - _EXEC or subj_of(b)
    pa, pb = promos_of(a), promos_of(b)
    return bool(sa and sb and same_people(sa, sb) and pa and pb and pa & pb)
def same_story(a, b):
    """Donor check for sharing a write-up: no promotion/people clash, and if both name people they share one."""
    if conflict(a, b): return False
    sa, sb = subj_of(a), subj_of(b)
    return not (sa and sb) or same_people(sa, sb)
def long_mismatch(a, paras):
    """A write-up (list of paragraphs) that is about other people or another promotion than report a's headline."""
    t = " ".join(paras or [])
    sa, st = subj_of(a), subjects(t)
    if sa and st and not same_people(sa, st): return True
    pa, pt = promos_of(a), promos(t)
    return bool(pa and pt and not pa & pt)
