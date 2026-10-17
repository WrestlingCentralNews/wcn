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
def fetch_article(it):
    url = it["link"]
    if "news.google.com" in url:
        try: url = resolve_google(url); it["link"] = url
        except Exception: return
    try: h = _get(url, 12).read()[:900000].decode("utf8", "ignore")
    except Exception: return
    if not it.get("image"):
        img = meta(h, "og:image") or meta(h, "twitter:image")
        if img and not re.search(r"logo|default|placeholder|favicon", img, re.I): it["image"] = urllib.parse.urljoin(url, img)
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
    return {x for x in e if x not in GENERIC and x not in STOP and x not in ("medical", "late", "former", "report", "breaking") and not x.startswith(("former ", "ex-", "late ")) and not re.match(r"^(former|wwe|aew|tna|nxt)\b", x)}
from aliases import canon as _canon
canon = functools.lru_cache(maxsize=None)(_canon)
EVENT = re.compile(r"\b(died|death|passed away|cause of death|medical examiner|injur\w*|surgery|retire\w*|signs?|signed|released?|departs?|exit|lawsuit|sued|arrest\w*|suspend\w*|returns?|debut\w*|wins?|crowned|vacate\w*|cancel\w*|postpon\w*|crowned)\b", re.I)
EVN = {"died":"death","death":"death","passed":"death","cause":"death","medical":"death","examiner":"death","retire":"retire","retires":"retire","retirement":"retire","retiring":"retire","sued":"lawsuit","lawsuit":"lawsuit"}
import editorial as _ed
from aliases import ALIASES as _AL
_EXEC = {"tony khan","triple h","nick khan","paul levesque","nick aldis","adam pearce","michael cole","pat mcafee","dave meltzer","carlos silva","santino marella","scott d'amore","vince mcmahon","stephanie mcmahon","shawn michaels","eric bischoff","jim ross","jim cornette","bully ray","paul heyman","bruce prichard","tony schiavone","excalibur","taz"}
_PNAMES = sorted({x.strip() for x in ("|".join(_ed.ROSTER.values()) + "|" + _ed.FIG + "|" + "|".join(_AL)).split("|") if len(x.strip()) > 2 and x.strip().lower() not in _EXEC and not re.search(r"[\\\[\]()]", x)}, key=len, reverse=True)
_PRX = re.compile(r"\b(" + "|".join(re.escape(p) for p in _PNAMES) + r")(?![a-z])", re.I)
@functools.lru_cache(maxsize=None)
def persons(t): return frozenset(m.lower() for m in _PRX.findall(t))
@functools.lru_cache(maxsize=None)
def evkeys(t): return {EVN.get(m.lower().split()[0], m.lower()[:5]) for m in EVENT.findall(t)}
@functools.lru_cache(maxsize=None)
def _tk(t): return frozenset(set(toks(t)) - GENERIC)
_MON = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
@functools.lru_cache(maxsize=None)
def dates(t):
    out = {f"{int(m)}/{int(d)}" for m, d in re.findall(r"\b(1[0-2]|0?[1-9])[/-]([12]\d|3[01]|0?[1-9])\b", t)}
    out |= {f"{_MON[m[:3].lower()]}/{int(d)}" for m, d in re.findall(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? (\d{1,2})\b", t, re.I)}
    return frozenset(out)
def similar(a, b):
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
def cluster(articles):
    arts = sorted(articles, key=lambda x: x["ts"]); groups = []
    for a in arts:
        for g in groups:
            if similar(a, g[0]) or any(similar(a, m) for m in g[-3:]): g.append(a); break
        else: groups.append([a])
    merged = True
    while merged:
        merged = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                if any(similar(x, y) for x in (groups[i][0], groups[i][-1]) for y in (groups[j][0], groups[j][-1])):
                    groups[i] = sorted(groups[i] + groups.pop(j), key=lambda x: x["ts"]); merged = True; break
            if merged: break
    out = []
    for g in groups:
        g = sorted(g, key=lambda x: -x["ts"]); main = min(g, key=lambda x: (TIER(x["source"]) if TIER else 0, -x["ts"]))
        best_img = next((m["image"] for m in g if m.get("image")), None)
        cats = sorted({c for m in g for c in m["categories"]}, key=["WWE","AEW","TNA","Indie","Global"].index)
        out.append({"id": "c" + g[-1]["id"], "title": main["title"], "summary": main["summary"], "link": main["link"],
            "source": main["source"], "ts": main["ts"], "first_ts": g[-1]["ts"], "image": best_img, "categories": main["categories"],
            "added": max(m.get("added", 0) for m in g),
            "raw_title": main["raw_title"], "kind": main.get("kind", {"type": "news"}), "ts": g[0]["ts"],
            "updates": [{"ts": m["ts"], "line": update_line(m), "source": m["source"], "link": m["link"], "title": m["title"]} for m in g if m is not main]})
    return sorted(out, key=lambda c: -c["ts"])
VERSION = 7
def img_score(u, src):
    if not u: return -99
    s = 0
    if re.search(r"1920|scaled|1200|large|full|w=1[0-9]{3}", u): s += 3
    if re.search(r"thumb|150x|300x|small|-\d{2,3}x\d{2,3}\.", u): s -= 3
    if re.search(r"logo|graphic|banner|poster", u, re.I): s -= 1
    return s
_old_cluster = cluster
def cluster(articles):
    out = _old_cluster(articles); by = {a["id"]: a for a in articles}
    for c in out:
        members = [by[c["id"][1:]]] + [a for a in articles if a["link"] in {u["link"] for u in c["updates"]}] + [a for a in articles if a["link"] == c["link"]]
        best = max(members, key=lambda a: img_score(a.get("image"), a["source"]))
        if best.get("image"): c["image"] = best["image"]
    return out
