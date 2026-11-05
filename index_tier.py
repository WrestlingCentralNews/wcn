"""Index tier (owner 2026-11-05, t620u 'Lets try it'): every story stays published (site, RSS, X, FB) but only strong pieces are
pushed to Google. tier(c) -> ("index"|"noindex", reason). When ENABLED, pages.noindex() adds noindex,follow to 'noindex' stories
and they leave sitemap.xml, es/sitemap.xml and sitemap-news.xml. URLs never change. OFF by default: set WCN_INDEX_TIER=1 (or
ENABLED=True) only after the owner approves the dry-run split (tools/index_tier_dryrun.py)."""
import os, re, json
import breaking, indie_gate

ENABLED = os.environ.get("WCN_INDEX_TIER", "") == "1"
ROOT = os.path.dirname(os.path.abspath(__file__))
MAJOR = {"WWE", "AEW", "TNA"}
# top-tier stars beyond current champions (household names / main-eventers); champions.json holders are added at load
TOP_STARS = ("Roman Reigns|CM Punk|Cody Rhodes|Seth Rollins|John Cena|Randy Orton|Brock Lesnar|The Rock|Rhea Ripley|Becky Lynch|"
    "Charlotte Flair|Bianca Belair|Liv Morgan|Iyo Sky|Tiffany Stratton|Jey Uso|Jimmy Uso|Gunther|Drew McIntyre|LA Knight|Logan Paul|"
    "Bron Breakker|Jacob Fatu|Solo Sikoa|Sami Zayn|Kevin Owens|Dominik Mysterio|Rey Mysterio|AJ Styles|Damian Priest|Penta|Oba Femi|"
    "Jade Cargill|Naomi|Stephanie Vaquer|Nikki Bella|Brie Bella|Triple H|Undertaker|Stone Cold|Steve Austin|Paul Heyman|Goldberg|"
    "Kenny Omega|Will Ospreay|MJF|Jon Moxley|Hangman Page|Adam Page|Darby Allin|Swerve Strickland|Kazuchika Okada|Okada|Young Bucks|"
    "Toni Storm|Mercedes Mone|Mercedes Moné|Mariah May|Kris Statlander|Hikaru Shida|Chris Jericho|Bryan Danielson|Samoa Joe|"
    "Konosuke Takeshita|Ricochet|Christian Cage|Adam Copeland|Edge|Orange Cassidy|Jay White|Tony Khan|"
    "Nic Nemeth|Mike Santana|Moose|Matt Hardy|Jeff Hardy|Masha Slamovich|Joe Hendry|Trick Williams|"
    "Hiroshi Tanahashi|Tetsuya Naito|Zack Sabre Jr|El Hijo del Vikingo|Mistico|M[ií]stico|Rey Fenix|Vince McMahon|Hulk Hogan|Ric Flair")
_STAR_RX = None
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

PLE = re.compile(r"(?i)\b(?:WrestleMania|Royal Rumble|SummerSlam|Survivor Series|Crown Jewel|Wrestlepalooza|Saturday Night'?s Main Event|"
    r"Elimination Chamber|Money in the Bank|Backlash|Bad Blood|Evolution|Night of Champions|Clash in Paris|Halloween Havoc|Deadline|"
    r"Stand & Deliver|Worlds Collide|All In|All Out|Full Gear|Worlds End|Revolution|Double or Nothing|Dynasty|Forbidden Door|"
    r"Grand Slam|WrestleDream|Bound for Glory|Slammiversary|Hard To Kill|Sacrifice|Rebellion|Wrestle Kingdom|Triplemania|Final Battle)\b")
CARD = re.compile(r"(?i)\b(?:match(?:es)?|card|main event|title (?:match|bout)|vs\.?|versus|lineup|announced|official|confirmed|added|set)\b")
BIG = re.compile(r"(?i)\b(?:signs?|signed|signing|inks?|contract|new deal|multi-?year|released|release[sd]? from|retire[sd]?|retirement|"
    r"final match|injur(?:y|ies|ed)|torn|surgery|sidelined|out of action|dies|died|passed away|death|dead at|debuts?|debuted|returns?|returned|"
    r"suspended|arrested|fired|departs?|leaves|leaving|exits?|free agent|hall of fame)\b")
TITLE_MATCH = re.compile(r"(?i)\b(?:title|championship)s?\s+(?:match|bout|defen[cs]e|opportunity|shot)\b|\bdefends?\b.*\b(?:title|championship)\b")
FULLCARD = re.compile(r"(?i)\bresults?\b|\bspoilers?\b|\bfull card\b|\brecap\b")
OUTCOME = re.compile(r"(?i)\b(?:results?|spoilers?|wins?|won|beats?|def(?:eats?|\.)|retains?|crowned|captures?|submits?|pins?|survives?|advances?|classic)\b")
RUMOR = re.compile(r"(?i)\?|\brumou?r\w*|\breportedly\b|\bbackstage\b|\bspeculat\w*|\bcould\b|\bmight\b|\bpossible\b|\bpotential\b|"
    r"\bin talks\b|\bplans? for\b|\bpitched\b|\bconsider\w*|\bupdate on\b|\bnote on\b|\bwhy\b.*\b(?:was|wasn't|didn't)\b")

def _txt(c): return (c.get("title") or "") + " " + (c.get("raw_title") or "")
def tier(c):
    """-> ('index'|'noindex', reason). Pure function of the story dict."""
    k = (c.get("kind") or {}).get("type") or "news"; t = _txt(c); cats = set(c.get("categories") or [])
    if c.get("original") or c.get("analysis"): return "index", "original analysis"
    if c.get("results_page") or c.get("card") or FULLCARD.search(t): return "index", "results/card"
    if k == "results":
        if OUTCOME.search(c.get("title") or ""): return "index", "results/card"
        if not c.get("brk"): return "noindex", "results-side note (promo/segment/ratings)"
    if k != "quote" and PLE.search(t) and CARD.search(t) and not RUMOR.search(c.get("title") or ""): return "index", "PLE card/match"
    if indie_gate.minor(c): return "noindex", "indie/global minor"
    try: b = breaking.kind(c.get("title") or "", k, c.get("raw_title") or "")
    except Exception: b = None
    ttl = c.get("title") or ""
    if k == "quote" and not c.get("brk"): return "noindex", "quote/interview rewrite"
    if b is None and any(rx.search(ttl) for rx in breaking.CHANGE) and not breaking.NOT_CHANGE.search(ttl) and not RUMOR.search(ttl): b = "title-change"
    if b == "title-change" or c.get("brk"): return "index", "breaking" if c.get("brk") else "title change"
    major = bool(cats & MAJOR) or bool(re.search(r"\b(?:NXT|AAA|NJPW|ROH)\b", t))
    spec = bool(RUMOR.search(c.get("title") or ""))
    if major and PLE.search(t) and CARD.search(t) and not spec: return "index", "PLE card/match"
    if major and TITLE_MATCH.search(ttl) and not spec: return "index", "title match announced"
    if re.search(r"(?i)hall of fame", ttl) and not spec: return "index", "Hall of Fame"
    star = star_rx().search(t)
    if BIG.search(c.get("title") or "") and not spec:
        if star: return "index", f"big news, top star ({star.group(0)})"
        if b in ("release", "debut", "return") and major: return "index", f"{b} ({'/'.join(sorted(cats))})"
    if spec: return "noindex", "rumor/speculation"
    if k == "match" and major and int(c.get("imp") or 0) >= 20: return "index", "major match announced"
    if int(c.get("imp") or 0) >= 26 and major: return "index", "high importance (multi-outlet)"
    if not major: return "noindex", "non-major promotion, minor"
    if k == "quote": return "noindex", "quote/interview rewrite" + (f" ({star.group(0)})" if star else "")
    return "noindex", "minor rewrite/roster note"

def noindex(c):
    """Only active when ENABLED; pages.noindex calls this."""
    return ENABLED and tier(c)[0] == "noindex"
