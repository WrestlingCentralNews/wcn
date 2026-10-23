"""Non-wrestling combat sports (owner rule 2026-10-21): UFC, MMA, boxing, Bellator, PFL, ONE Championship, Zuffa Boxing,
kickboxing and bare-knuckle news is not wrestling and never appears on WCN, even when a wrestling outlet we follow carries it
(F4W/Wrestling Observer /news/ufc/, Fightful /mma/ and /boxing/, POST Wrestling's MMA coverage).
A report is non-wrestling when its URL sits in a combat-sports section, its headline is about a combat sport, or (headline naming
neither) its own text is mainly about one, AND its headline has no pro-wrestling signal (a promotion, show/event, 'wrestling',
or a named wrestler).
2026-10-21 second pass: a headline about a combat sport stays ONLY as a crossover (wrestler -> fight, fighter -> wrestling);
'TKO Reports Record Quarter For WWE And UFC', UFC ticket sales and Zuffa Boxing news go."""
import re
URL_RX = re.compile(r"(?i)^https?://[^/]+(?:/[\w-]+)?/(?:ufc|mma|boxing|bellator|pfl|one-championship|kickboxing|bkfc|bare-knuckle)(?:/|-news/)")
TERM_RX = re.compile(r"\bUFC\b|\bMMA\b|mixed martial arts|\bBellator\b|\bPFL\b|Professional Fighters League|\bONE Championship\b|ONE Fight Night|"
                     r"\b[Bb]oxing\b|\b[Bb]oxers?\b|\bZUFFA\b|\bZuffa\b|\b[Kk]ickboxing\b|\bBKFC\b|[Bb]are[- ][Kk]nuckle|\bDana White's Contender|"
                     r"\b[Oo]ctagon\b|\b(?:[Ff]eather|[Bb]antam|[Ww]elter|[Ff]ly|[Ss]traw)weight\b|\bTKO Boxing\b|\bRizin\b")
WREST_RX = re.compile(r"\bWWE\b|\bAEW\b|\bTNA\b|\bNXT\b|\bROH\b|Ring of Honor|\bNJPW\b|New Japan|\bCMLL\b|\bAAA\b|[Ll]ucha|[Ww]restl(?!e[Tt]ix)|SmackDown|"
                      r"\bRaw\b|\bRAW\b|Dynamite|Collision|Rampage|WrestleMania|Royal Rumble|SummerSlam|Crown Jewel|Survivor Series|Money in the Bank|"
                      r"WrestleDream|Full Gear|Bound for Glory|\bMLW\b|\bGCW\b|\bNWA\b|[Ss]tardom|\bIMPACT\b|iMPACT|Impact Wrestling|Triplemania|"
                      r"H[eé]roes Inmortales|Wrestle Kingdom|\bIWGP\b|\bPLE\b|Halloween Havoc|Saturday Night'?s Main Event")
SITE_SUFFIX = re.compile(r"(?i)\s+[-|–—]\s+(?:Fightful|Wrestling Inc\.?|Ringside News|Cageside Seats|POST Wrestling|Sportskeeda|WON/F4W|F4W Online)\b.*$|\s*\|\s*WWE News, AEW News.*$")
def _wrestling_head(t):
    t = SITE_SUFFIX.sub("", t or "")
    if WREST_RX.search(t or ""): return True
    import enrich
    return bool(enrich.subjects(t or "") - enrich._EXEC)   # a named wrestler (executives alone don't count: 'Dana White')
# Crossovers only (owner rule 2026-10-21, second pass): combat-sports news stays ONLY when it is a crossover: a wrestler going to
# boxing/UFC/MMA (Brock Lesnar UFC return, Logan Paul's boxing match) or a boxer/fighter moving into, appearing in or signing with
# pro wrestling (Jake Paul in WWE, 'Former UFC Fighter Signs With AEW'). Business news that merely covers both (TKO earnings for
# WWE and UFC, UFC ticket sales, Zuffa Boxing) is dropped.
STRONG_RX = re.compile(r"\bUFC\b|\bMMA\b|mixed martial arts|\bBellator\b|\bPFL\b|Professional Fighters League|\bONE Championship\b|ONE Fight Night|"
                       r"\b[Bb]oxing\b|\b[Bb]oxers?\b|\bZUFFA\b|\bZuffa\b|\b[Kk]ickboxing\b|\bBKFC\b|[Bb]are[- ][Kk]nuckle|\bRizin\b|\bTKO Boxing\b|"
                       r"\bprizefight\w*|\bcage ?fight\w*|\b(?:UFC|MMA|cage) fighters?\b", re.I)   # not "Street Fighter" (WWE 2K26 collab)
# wrestlers whose fights count as crossovers even if enrich doesn't know the name
WRESTLERS_EXTRA = re.compile(r"\b(?:Ronda Rousey|Shayna Baszler|Cain Velasquez|Bobby Lashley|Brock Lesnar|Logan Paul|Gable Steveson|Matt Riddle|"
                             r"Marina Shafir|Jessamyn Duke|Ken Shamrock|Dan Severn|Josh Barnett|Kazushi Sakuraba|Bobby Fish|Kyle O'?Reilly|Jon Moxley)\b", re.I)
# a fighter/boxer -> wrestling move, or a wrestler -> fight move
CROSS_RX = re.compile(r"\bsign(?:s|ed|ing)?\b|\bjoin(?:s|ed|ing)?\b|\bdebut\w*|\bappear\w*|\bcameo\b|\bguest\b|\bhost(?:s|ed|ing)?\b|\breturn\w*|"
                      r"\bswitch\w*|\bmov(?:e|es|ed|ing) to\b|\bjump\w*|\btransition\w*|\bcross[- ]?over\b|\bstep(?:s|ped|ping)? into\b|\btrain\w*|"
                      r"\btryout\b|\bPerformance Center\b|\bmatch\b|\bbout\b|\bfight(?:s|ing)?\b|\bvs\.?\b|\bface[sd]?\b|\bchalleng\w*|\bcall(?:s|ed)? out\b|"
                      r"\bwants?\b|\binterest\w*|\bopen to\b|\bin talks\b|\boffer\w*|\beyes?\b|\bteas\w*|\bhint\w*|\bringside\b|\bin the ring\b|"
                      r"\b(?:from|former|ex-)\s*(?:UFC|MMA|boxing|boxer|Bellator|PFL)\b|\bto (?:pro )?wrestling\b|\binto (?:pro )?wrestling\b|\bwrestlers? who\b|"
                      r"\bfrom (?:WWE|AEW|TNA|NXT|wrestling) to\b", re.I)
BIZ_RX = re.compile(r"\bTKO\b(?! Boxing)|\bearnings?\b|\bquarter(?:ly)?\b|\brevenue\b|\bprofits?\b|\bstock\b|\bshares?\b|\binvestors?\b|\bmerger\b|"
                    r"\bmedia rights\b|\brights deal\b|\bTV deal\b|\bbroadcast deal\b|\bstreaming deal\b|\bParamount\b|\bNetflix deal\b|\bticket sales\b|"
                    r"\bWrestleTix\b|\bgate\b|\bviewership\b|\bratings?\b|\bsponsor\w*|\blawsuit\b|\bantitrust\b|\bsettlement\b|\bfinancial\w*|\bfiscal\b", re.I)
def _wrestler_named(t):
    import enrich
    return bool(enrich.subjects(t or "") - enrich._EXEC) or bool(WRESTLERS_EXTRA.search(t or ""))
def crossover(head):
    """Headline is a pro-wrestling <-> boxing/UFC/MMA crossover: a named wrestler in a fight story (not business news),
    or a fighter/boxer moving into / appearing in / signing with wrestling."""
    t = SITE_SUFFIX.sub("", head or "")
    if _wrestler_named(t) and not (BIZ_RX.search(t) and not CROSS_RX.search(t)): return True
    return bool(WREST_RX.search(t) and CROSS_RX.search(t) and not BIZ_RX.search(t))
# Off-topic business / world news (owner rule 2026-10-23): wrestling outlets (POST Wrestling especially) also carry plain
# streaming-industry and world news because it touches WWE ('Netflix faces ... Q3 earnings', 'Netflix's chief content officer
# ... gone', 'Riyadh International Airport remains highly restricted following Houthi attacks'). Their headlines name no
# promotion, show or wrestler, so the combat-sports guard let them through. Corporate news is fine ONLY when the headline is
# clearly about wrestling ('WWE Raw on Netflix Draws 4.5M', 'CM Punk ... Netflix Movie', 'TKO says WWE revenue up').
OFFTOPIC_RX = re.compile(r"\b(?:Netflix|Paramount|Peacock|ESPN|Disney|Comcast|NBCU(?:niversal)?|Warner Bros|WBD|Fox Corp|Amazon|Prime Video|"
                         r"Hulu|HBO Max|Tubi|Roku|Endeavor|Silver Lake|Live Nation|Ticketmaster|Spotify|Apple)\b(?!\s+(?:Raw|SmackDown|NXT))|"
                         r"\b(?:earnings|layoffs?|shareholders?|stock price|share price|Wall Street|chief (?:content|executive|financial|operating) officer|"
                         r"\bCEO\b|subscribers? growth|box office|airports?|airlines?|flights? (?:cancel|suspend|halt)\w*|Houthis?|missiles?|air ?strikes?|"
                         r"drone attacks?|military|ceasefire|invasion|election|government shutdown|tariffs?|hurricane|earthquake|"
                         r"wildfire|NFL|NBA|MLB|NHL|Super Bowl|World Cup|Formula 1|\bF1\b|NASCAR)", re.I)
def offtopic(a):
    """Reason string if report/story a is business/world news whose headline (published and raw) is not about wrestling."""
    head = SITE_SUFFIX.sub("", a.get("raw_title") or "") + " | " + SITE_SUFFIX.sub("", a.get("title") or "")
    import enrich
    if _wrestling_head(head) or WRESTLERS_EXTRA.search(head) or enrich.subjects(head): return None   # executives count here ('Triple H Jacket')
    if re.search(r"(?i)pro[- ]wrestling|\bNJPW\b", a.get("raw_title") or ""): return None              # site suffix 'NEW JAPAN PRO-WRESTLING'
    m = OFFTOPIC_RX.search(head)
    return f"non-wrestling: business/world news headline ({m.group(0)}) with no wrestling subject" if m else None
def nonwrestling(a):
    """Reason string if report/story a is non-wrestling combat-sports news (not a crossover), else None."""
    head = SITE_SUFFIX.sub("", a.get("raw_title") or "") + " | " + SITE_SUFFIX.sub("", a.get("title") or "")
    combat_head = bool(STRONG_RX.search(head))
    if combat_head:
        if crossover(head): return None
        return "non-wrestling: headline about UFC/MMA/boxing (no wrestling crossover)"
    ot = offtopic(a)
    if ot: return ot
    if _wrestling_head(head): return None          # wrestling headline (weight-class words alone: 'MLW Featherweight Championship')
    if URL_RX.search(a.get("link") or ""): return "non-wrestling: combat-sports section URL"
    if TERM_RX.search(head): return "non-wrestling: headline about UFC/MMA/boxing"
    txt = " ".join(str(a.get(k) or "") for k in ("summary_src", "src_summary", "summary"))[:900] + " " + (a.get("body") or "")[:600]
    if len(TERM_RX.findall(txt)) >= 2 and not WREST_RX.search(txt): return "non-wrestling: text about UFC/MMA/boxing"
    return None
