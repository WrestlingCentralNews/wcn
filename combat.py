"""Non-wrestling combat sports (owner rule 2026-10-21): UFC, MMA, boxing, Bellator, PFL, ONE Championship, Zuffa Boxing,
kickboxing and bare-knuckle news is not wrestling and never appears on WCN, even when a wrestling outlet we follow carries it
(F4W/Wrestling Observer /news/ufc/, Fightful /mma/ and /boxing/, POST Wrestling's MMA coverage).
A report is non-wrestling when its URL sits in a combat-sports section, its headline is about a combat sport, or (headline naming
neither) its own text is mainly about one, AND its headline has no pro-wrestling signal (a promotion, show/event, 'wrestling',
or a named wrestler: 'Brock Lesnar', 'WWE and UFC parent TKO', 'Former UFC fighter signs with AEW' stay)."""
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
def nonwrestling(a):
    """Reason string if report/story a is non-wrestling combat-sports news, else None."""
    head = SITE_SUFFIX.sub("", a.get("raw_title") or "") + " | " + SITE_SUFFIX.sub("", a.get("title") or "")
    if _wrestling_head(head): return None
    if URL_RX.search(a.get("link") or ""): return "non-wrestling: combat-sports section URL"
    if TERM_RX.search(head): return "non-wrestling: headline about UFC/MMA/boxing"
    txt = " ".join(str(a.get(k) or "") for k in ("summary_src", "src_summary", "summary"))[:900] + " " + (a.get("body") or "")[:600]
    if len(TERM_RX.findall(txt)) >= 2 and not WREST_RX.search(txt): return "non-wrestling: text about UFC/MMA/boxing"
    return None
