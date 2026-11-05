"""Index tier (owner 2026-11-05, t620u + t620 answers + steering): every story stays published (site, RSS, X, FB) but only
strong pieces are pushed to Google. tier(c) -> ("index"|"noindex", reason). When ENABLED, pages.noindex() adds noindex,follow
to 'noindex' stories and they leave sitemap.xml, es/sitemap.xml and sitemap-news.xml. URLs never change. Owner approved the
expanded split (business/ratings, weekly/PLE non-title matches, newsworthy top-star quotes, controversy quotes from industry
figures); set WCN_INDEX_TIER=1 in the update workflow to enable."""
import os, re, json
import breaking, indie_gate

ENABLED = os.environ.get("WCN_INDEX_TIER", "") == "1"
ROOT = os.path.dirname(os.path.abspath(__file__))
MAJOR = {"WWE", "AEW", "TNA"}
# top-tier stars beyond current champions (household names / main-eventers); champions.json holders are added at load
TOP_STARS = ("Roman Reigns|CM Punk|Cody Rhodes|Seth Rollins|John Cena|Randy Orton|Brock Lesnar|The Rock|Rhea Ripley|Becky Lynch|"
    "Charlotte Flair|Bianca Belair|Liv Morgan|Iyo Sky|Tiffany Stratton|Jey Uso|Jimmy Uso|Gunther|GUNTHER|Drew McIntyre|LA Knight|Logan Paul|"
    "Bron Breakker|Jacob Fatu|Solo Sikoa|Sami Zayn|Kevin Owens|Dominik Mysterio|Rey Mysterio|AJ Styles|Damian Priest|Penta|Oba Femi|"
    "Jade Cargill|Naomi|Stephanie Vaquer|Nikki Bella|Brie Bella|Triple H|Paul Levesque|Undertaker|Stone Cold|Steve Austin|Paul Heyman|Goldberg|"
    "Kenny Omega|Will Ospreay|MJF|Jon Moxley|Hangman Page|Adam Page|Darby Allin|Swerve Strickland|Kazuchika Okada|Okada|Young Bucks|"
    "Toni Storm|Mercedes Mone|Mercedes Moné|Mariah May|Kris Statlander|Hikaru Shida|Chris Jericho|Bryan Danielson|Samoa Joe|"
    "Konosuke Takeshita|Ricochet|Christian Cage|Adam Copeland|Edge|Orange Cassidy|Jay White|Tony Khan|"
    "Nic Nemeth|Mike Santana|Moose|Matt Hardy|Jeff Hardy|Masha Slamovich|Joe Hendry|Trick Williams|"
    "Hiroshi Tanahashi|Tetsuya Naito|Zack Sabre Jr|El Hijo del Vikingo|Mistico|M[ií]stico|Rey Fenix|Vince McMahon|Hulk Hogan|Ric Flair|"
    "Sting|Steven Borden|Shawn Michaels")
# executives, legends, journalists and other industry voices for controversy-quote indexing (unioned with TOP_STARS)
INDUSTRY = ("Nick Khan|Dana White|Jim Cornette|Eric Bischoff|Dave Meltzer|Bruce Prichard|Stephanie McMahon|Ari Emanuel|Mark Shapiro|"
    "Kevin Nash|Bret Hart|Jim Ross|Conrad Thompson|RVD|Rob Van Dam|Bully Ray|Booker T|The Miz|Pat McAfee|John Laurinaitis|"
    "Ariel Helwani|Sean Ross Sapp|Wade Keller")
_STAR_RX = None
_INDUSTRY_RX = None
def star_rx():
    global _STAR_RX
    if _STAR_RX is None:
        names = TOP_STARS.split("|")
        try:
            for t in json.load(open(os.path.join(ROOT, "champions.json")))["titles"]:
                if t.get("promo") in MAJOR and t.get("champion"):
                    names += [re.escape(n.strip()) for n in re.split(r"\s*(?:&|,| and )\s*", t["champion"]) if len(n.strip()) > 3]
        except Exception: pass
        _STAR_RX = re.compile(r"\b(?:" + "|".join(sorted(set(names), key=len, reverse=True)) + r")\b", re.I)
    return _STAR_RX
def industry_rx():
    """Top stars + execs/legends/journalists for controversy quotes."""
    global _INDUSTRY_RX
    if _INDUSTRY_RX is None:
        names = TOP_STARS.split("|") + INDUSTRY.split("|")
        try:
            for t in json.load(open(os.path.join(ROOT, "champions.json")))["titles"]:
                if t.get("promo") in MAJOR and t.get("champion"):
                    names += [re.escape(n.strip()) for n in re.split(r"\s*(?:&|,| and )\s*", t["champion"]) if len(n.strip()) > 3]
        except Exception: pass
        _INDUSTRY_RX = re.compile(r"\b(?:" + "|".join(sorted(set(names), key=len, reverse=True)) + r")\b", re.I)
    return _INDUSTRY_RX

PLE = re.compile(r"(?i)\b(?:WrestleMania|Royal Rumble|SummerSlam|Survivor Series|Crown Jewel|Wrestlepalooza|Saturday Night'?s Main Event|"
    r"Elimination Chamber|Money in the Bank|Backlash|Bad Blood|Evolution|Night of Champions|Clash in Paris|Halloween Havoc|Deadline|"
    r"Stand & Deliver|Worlds Collide|All In|All Out|Full Gear|Worlds End|Revolution|Double or Nothing|Dynasty|Forbidden Door|"
    r"Grand Slam|WrestleDream|Bound for Glory|Slammiversary|Hard To Kill|Sacrifice|Rebellion|Wrestle Kingdom|Triplemania|Final Battle|"
    r"Destination X|Bound For Unbound)\b")
WEEKLY = re.compile(r"(?i)\b(?:Monday Night )?Raw\b|\bSmackDown\b|\bNXT\b|\bDynamite\b|\bCollision\b|\b(?:TNA\s+)?Impact\b")
# non-title match announced for a weekly show or PLE (vs / match added|set|booked)
MATCH_SET = re.compile(
    r"(?i)\bvs\.?\b|\bversus\b|"
    r"\b(?:tag\s+)?match(?:es)?\s+(?:added|set|announced|booked|made official|confirmed)\b|"
    r"\b(?:added|booked|announced|confirmed)\s+(?:for\s+)?(?:a\s+)?(?:tag\s+)?match\b|"
    r"\bmatch(?:es)?\s+(?:added|set|booked)\s+(?:to|for|on)\b|"
    r"\bbooked for match\b|"
    r"\b(?:six|eight|ten|12|12-person|multi)-?(?:\s*man|\s*woman|\s*person)?\s+tag\s+match\b|"
    r"\bset for\b.{0,60}\b(?:vs\.?|versus|match)\b|"
    r"\b(?:vs\.?|versus|match).{0,60}\bset for\b"
)
CARD = re.compile(r"(?i)\b(?:match(?:es)?|card|main event|title (?:match|bout)|vs\.?|versus|lineup|announced|official|confirmed|added|set)\b")
BIG = re.compile(r"(?i)\b(?:signs?|signed|signing|inks?|contract|new deal|multi-?year|released|release[sd]? from|retire[sd]?|retirement|"
    r"final match|injur(?:y|ies|ed)|torn|surgery|sidelined|out of action|dies|died|passed away|death|dead at|debuts?|debuted|returns?|returned|"
    r"suspended|arrested|fired|departs?|leaves|leaving|exits?|free agent|hall of fame)\b")
TITLE_MATCH = re.compile(r"(?i)\b(?:title|championship)s?\s+(?:match|bout|defen[cs]e|opportunity|shot)\b|\bdefends?\b.*\b(?:title|championship)\b")
FULLCARD = re.compile(r"(?i)\bresults?\b|\bspoilers?\b|\bfull card\b|\brecap\b")
OUTCOME = re.compile(r"(?i)\b(?:results?|spoilers?|wins?|won|beats?|def(?:eats?|\.)|retains?|crowned|captures?|submits?|pins?|survives?|advances?|classic)\b")
RUMOR = re.compile(r"(?i)\?|\brumou?r\w*|\breportedly\b|\bbackstage\b|\bspeculat\w*|\bcould\b|\bmight\b|\bpossible\b|\bpotential\b|"
    r"\bin talks\b|\bplans? for\b|\bpitched\b|\bconsider\w*|\bupdate on\b|\bnote on\b|\bwhy\b.*\b(?:was|wasn't|didn't)\b")
# viewership, TKO/WWE earnings, guidance, TV/streaming deals (owner 2026-11-05)
BUSINESS = re.compile(
    r"(?i)\b(?:viewership|viewers|ratings?|nielsen|audience)\b|"
    r"\b(?:revenue|earnings|guidance|quarterly|Q[1-4]\b)|"
    r"\b\$[\d.,]+\s*(?:million|billion|m|b)\b|"
    r"\b(?:TV|streaming|media|rights?)\s+deals?\b|"
    r"\b(?:Netflix|Disney|ESPN|Peacock|Fox|USA Network|CW)\b.{0,40}\b(?:deal|partnership|rights|viewership|ratings|subscribers|success)\b|"
    r"\b(?:deal|partnership|rights).{0,40}\b(?:Netflix|Disney|ESPN|Peacock|Fox|USA Network|CW)\b|"
    r"\bTKO\b.{0,40}\b(?:guidance|revenue|earnings|raises?|cuts?)\b|"
    r"\b(?:raises?|cuts?|updates?|reaffirms?)\s+(?:20\d\d\s+)?guidance\b|"
    r"\bexpand(?:s|ed)?\s+partnership\b"
)
# newsworthy (not filler) quote signals from a top star
NEWSWORTHY_QUOTE = re.compile(
    r"(?i)\b(?:injur(?:y|ies|ed)|concussion|surgery|torn|sidelined|out of action|diagnosed)\b|"
    r"\b(?:leav(?:es|ing)|departs?|quit(?:s|ting)?|retir(?:es|ed|ing|ement)|released?|fired|suspended|arrested)\b|"
    r"\b(?:contract|extension|free agent|renew(?:s|ed|al)?|salary|earnings|pay(?: ?cut| ?rise)?)\b|"
    r"\b(?:rules? out|won'?t (?:wrestle|return)|declines?|demands?|sets? terms|wants out|walked out|refuses?)\b|"
    r"\b(?:creative control|lawsuit|sues|sued|pregnant|pregnancy)\b|"
    r"\b(?:hesitant on|open to).{0,40}\b(?:return|extension|deal|leaving)\b"
)
# controversy / heated remarks (criticism, feud, accusation, backlash)
CONTROVERSY = re.compile(
    r"(?i)\b(?:criticiz\w*|criticism|blasts?|blasted|slams?|slammed|rips?(?:\s+into)?|ripped|lambast\w*|condemn\w*)\b|"
    r"\b(?:accus(?:es|ed|ation)s?|backlash|feud|war of words|fired (?:a )?shots?|takes? shots?|shots at|calls? out|called out)\b|"
    r"\b(?:trash(?:es|ed)?|attacks?|attacked|heated|controversy|controversial|toxic|corrupt)\b|"
    r"\b(?:inmates|dysfunctional|disaster|embarrass\w*|worst ever|lied|liar)\b|"
    r"\b(?:refutes?|denies|denied|dismisses|fires back|clap ?back)\b|"
    r"\bresponds? to\b.{0,30}\bcritic"
)
# multi-outlet signal for controversy quotes (below the general high-imp bar of 26)
CONTROVERSY_IMP = 14

def _txt(c): return (c.get("title") or "") + " " + (c.get("raw_title") or "")
def tier(c):
    """-> ('index'|'noindex', reason). Pure function of the story dict."""
    k = (c.get("kind") or {}).get("type") or "news"; t = _txt(c); cats = set(c.get("categories") or [])
    if c.get("original") or c.get("analysis"): return "index", "original analysis"
    if c.get("results_page") or c.get("card") or FULLCARD.search(t): return "index", "results/card"
    if BUSINESS.search(t): return "index", "business/ratings"
    if k == "results":
        if OUTCOME.search(c.get("title") or ""): return "index", "results/card"
        if not c.get("brk"): return "noindex", "results-side note (promo/segment)"
    if k != "quote" and PLE.search(t) and CARD.search(t) and not RUMOR.search(c.get("title") or ""): return "index", "PLE card/match"
    if indie_gate.minor(c): return "noindex", "indie/global minor"
    try: b = breaking.kind(c.get("title") or "", k, c.get("raw_title") or "")
    except Exception: b = None
    ttl = c.get("title") or ""
    if b is None and k != "quote" and any(rx.search(ttl) for rx in breaking.CHANGE) and not breaking.NOT_CHANGE.search(ttl) and not RUMOR.search(ttl): b = "title-change"
    if b == "title-change" or c.get("brk"): return "index", "breaking" if c.get("brk") else "title change"
    major = bool(cats & MAJOR) or bool(re.search(r"\b(?:NXT|AAA|NJPW|ROH)\b", t))
    spec = bool(RUMOR.search(c.get("title") or ""))
    if major and PLE.search(t) and CARD.search(t) and not spec: return "index", "PLE card/match"
    if major and TITLE_MATCH.search(ttl) and not spec: return "index", "title match announced"
    # non-title matches announced for Raw/SmackDown/NXT/Dynamite/Collision/Impact or a PLE
    if not spec and (WEEKLY.search(t) or PLE.search(t)) and MATCH_SET.search(ttl) and (major or PLE.search(t)):
        return "index", "weekly/PLE match announced"
    if re.search(r"(?i)hall of fame", ttl) and not spec: return "index", "Hall of Fame"
    star = star_rx().search(t)
    if BIG.search(c.get("title") or "") and not spec:
        if star: return "index", f"big news, top star ({star.group(0)})"
        if b in ("release", "debut", "return") and major: return "index", f"{b} ({'/'.join(sorted(cats))})"
    if spec: return "noindex", "rumor/speculation"
    if k == "match" and major and int(c.get("imp") or 0) >= 20: return "index", "major match announced"
    if int(c.get("imp") or 0) >= 26 and major: return "index", "high importance (multi-outlet)"
    if k == "quote":
        fig = industry_rx().search(t)
        if fig and CONTROVERSY.search(ttl) and int(c.get("imp") or 0) >= CONTROVERSY_IMP:
            return "index", f"controversy quote ({fig.group(0)})"
        if star and NEWSWORTHY_QUOTE.search(ttl):
            return "index", f"newsworthy quote ({star.group(0)})"
        return "noindex", "quote/interview rewrite" + (f" ({star.group(0)})" if star else "")
    if not major: return "noindex", "non-major promotion, minor"
    return "noindex", "minor rewrite/roster note"

def noindex(c):
    """Only active when ENABLED; pages.noindex calls this."""
    return ENABLED and tier(c)[0] == "noindex"
