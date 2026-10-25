"""WCN editorial rules: source tiers, news-vs-opinion classifier, category fixes, story kind (quote/match/etc)."""
import re, json, os, time
T1 = r"^(WWE|WWE\.com|AEW|All Elite Wrestling|TNA Wrestling|TNA|NEW JAPAN PRO-WRESTLING|NJPW|ROH|Ring of Honor|STARDOM|CMLL|Lucha Libre AAA|GCW|MLW|Wrestling Observer|F4W|PWInsider(\.com)?|Fightful|POST Wrestling|Wrestling Inc\.?)$"
T2 = r"^(Cageside Seats|PWTorch|Pro Wrestling Dot Net|Yahoo Sports|Sports Illustrated|ESPN|CBS Sports|Associated Press|AP News|Reuters|USA Today|BBC|The Guardian|DAZN|Variety|The Hollywood Reporter|Forbes|Wrestlezone|Monthly Puroresu|Bodyslam\.net|411MANIA|Bleacher Report|New York Post|Los Angeles Times|Deadline)$"
def tier(src):
    if re.match(T1, src or "", re.I): return 1
    if re.match(T2, src or "", re.I): return 2
    return 3   # Sportskeeda, Ringside News, aggregators, blogs: need corroboration
DROP = [
 ("listicle", r"^\d+\s+(?:\w+\s+){0,4}(reasons|ways|things|times|wrestlers|matches|moments|stars|superstars|questions|takeaways|surprises|ideas|facts|mistakes|best|worst|biggest)|\b(top|best|worst|biggest)\s+\d+\b|\branking(s)?\b|\branked\b|power rankings|\bgreatest\b|\bunderrated\b|\boverrated\b"),
 ("prediction", r"predict|picks?\b.*\b(for|ahead)|preview (and|&)|betting odds|\bodds\b|who will win|what to expect|could (win|face|return|happen)|should (win|face|happen|return|book|be)"),
 ("fantasy/dream", r"dream match|fantasy book|\bwhat if\b|imagin|would be (perfect|great)|needs to (happen|face|win)|must (face|win|happen)|how (wwe|aew|tna) (should|could|can)"),
 ("rumor", r"\brumou?r|\[report\]|\bspeculat|\bteases?\b.*\?|\breportedly\b.*\?|\bhints? at\b.*\?|is (wwe|aew) (planning|teasing)\b.*\?|\bmight\b|\bcould be\b|\bpossibly\b|fans (think|believe|convinced|speculate)|\btheory\b"),
 ("opinion", r"\bopinion\b|\bcolumn\b|\bop-ed\b|\bhot take|\bmy (thoughts|take)|\bwe need to talk|\bthe case for\b|\bis wrong\b|\bdeserves? better\b|\bdraws? & duds\b|\bgrades?\b|\bratings? (and|&) review\b|\bstock (up|down)\b|\bwinners? (and|&) losers?\b|\bhits? (and|&) misses\b|\bpodcast\b|\bep(isode)?\.? ?\d+\b|\bmailbag\b|\bdebate\b|\bvs\.? (wwe|aew)\b.*\bwhich\b|\b(roundtable|discussion)\b"),
 ("podcast/roundup", r"^(WOL|WOR|POST NEWS|Bryan & Vinny|Rasslin)\s*:|—\s*(WOL|POST NEWS|WOR)\b|wrestling observer (live|radio)|\bpodcast\b|\bradio\b|\bpost news\b|\bnews (and|&) notes\b|\bweekly roundup\b"),
 ("poll/quiz", r"\bpoll\b|\bvote\b|\bquiz\b|what do you think|\bsound off\b|\byou decide\b|\bfan reactions?\b|\bfans react\b|twitter reacts|social media reacts|\bmemes?\b"),
 ("evergreen/explainer", r"\bexplained\s*(?:$|[:\-–—|,(])|\b(?:rules?|history|meaning|controversy|format|stipulations?|titles?|championships?|belts?|ending|finish|rivalry|feud|storyline|lore|origins?)\s+explained\b|\bexplainer\b|^(?:what|who)\s+(?:is|are|was|were)\b|[:|–—-]\s*(?:what|who)\s+(?:is|are|was|were)\b|\b(?:everything|all|what)\s+you\s+(?:need|want|should)\s+to\s+know\b|\bhow\s+(?:does|do|did)\s+[\w'’ .-]{1,50}\bwork\b|\bhow\s+(?:the\s+|a\s+|an\s+)?[\w'’ .-]{1,50}\bworks\b|\b(?:a|taking a|take a)\s+look\s+back\b|\blooking\s+back\s+(?:at|on)\b|\btimeline\s+of\b|\b(?:full|complete|brief|quick)\s+(?:history|timeline)\b|\bwhy\s+[\w'’ .,-]{1,60}\bmatters?\b|\b(?:best|worst|greatest)\s+(?:[\w'’-]+\s+){0,3}(?:matches|wrestlers|superstars|stars|moments|promos|feuds|rivalries|champions|title reigns|reigns|entrances|finishers|gimmicks|pay-per-views|ppvs|ples|events|shows|storylines|teams|tag teams|factions|heels|babyfaces|debuts|returns|runs)\s+(?:ever|of all[- ]time|in (?:wwe|aew|tna|wrestling) history)\b|\bon this (?:day|date)\b|\byears? ago today\b|\b\d+(?:st|nd|rd|th)?\s+anniversary\s+of\b|\banniversary\s+(?:retrospective|look back|tribute)\b|\bretrospective\b|\bremember when\b|\bflashback\b|\bevery (?:past|previous|former) (?:winner|champion)s?\b|\b(?:full|complete) list of (?:past|all|every|former)\b|\blist of (?:all|every)\b|\b(?:beginner'?s|fan'?s|viewer'?s|complete|ultimate) guide\b|\bthings you (?:didn'?t|might not|may not) know\b|\bfacts about\b|\bhow old is\b|\breal name\b|\bwhat happened to\b|\bwhere are they now\b|\bthrowback\b|(?<!in the )(?<!in )\bhistory of\b"),
 ("gossip/other", r"\bon this day\b|\bthis day in (?:wrestling |pro wrestling )?history\b|\bthrowback\b|\bwhere are they now\b|\blooking back\b|(?<!in the )(?<!in )\bhistory of\b|\bdating\b|\bgirlfriend\b|\bboyfriend\b|\bbikini\b|\bphotos?\b.*\b(stuns?|hot)\b|\bnet worth\b|\bhoroscope\b|\bfull list\b.*\bfree agents\b|\brumor roundup\b|\bclickbait\b|\bstreaming guide\b|\bhow to watch\b|\bstart times?\b|\bwatch .* live\b"),
]
DROP = [(n, re.compile(p, re.I)) for n, p in DROP]
NEWS_EVENT = re.compile(r"\b(?:signs?|signed|signing|released|releases?|returns?|returned|debuts?|debuted|wins?|won|crowned|captures?|arrested|charged|suspended|fired|retires?|retired|announce[sd]?|joins?|joined|hired|injured|injury|vacate[sd]?|stripped|cancel(?:s|ed|led)?|moved|relocated)\b", re.I)
EVERGREEN = next(rx for n, rx in DROP if n == "evergreen/explainer")
def evergreen(title):
    """True for explainer / background / history / anniversary / SEO-definition pieces that report no new event (owner rule 2026-10-20).
    Also run on the AI rewrite's headline (aggregator) so a rewrite that turns 'What is X?' into 'X explained' is caught too."""
    t = re.sub(r"[\"“‘'][^\"”’]{3,140}[\"”’]", " ", title or "")
    m = EVERGREEN.search(t)
    if not m: return False
    # 'Who is Necro Butcher? Hardcore legend signs WWE deal': a 'who/what is' intro on a headline that reports a new event stays
    if re.match(r"\W*(?:what|who)\s", m.group(0), re.I) and NEWS_EVENT.search(t[m.end():] + " " + t[:m.start()]): return False
    return True
# owner rule 2026-10-21 (no filler): podcast-episode listings and generic outlet daily roundups; hand-dropped duplicates
_POD_LINK = re.compile(r"(?i)fightful\.com/podcasts/|f4wonline\.com/news/daily-updates/|/podcasts?/")
_POD_TITLE = re.compile(r"(?i)\bthe hump\b|\bdaily update\b|\bdaily (?:news )?(?:roundup|recap)\b|\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b.*\b(?:show|episode|ep\.?)\b")
_POD_HOST = re.compile(r"\bw/ ?[A-Z]{2,4}\b(?:\s*$|\s*[|,-])")   # '... w/ SRS' episode titles (case-sensitive)
DUP_LINKS = {"https://www.f4wonline.com/news/aew/aew-dynamite-preview-confirmed-matches-segments-10-20-2026/"}   # = official AEW Oct 21 preview
def verdict(a):
    if (a.get("link") or "") in DUP_LINKS: return "duplicate of official preview"
    if _POD_LINK.search(a.get("link") or "") or _POD_TITLE.search(a.get("raw_title") or "") or _POD_HOST.search(a.get("raw_title") or ""): return "podcast/roundup"
    t = re.sub(r"[\"“‘'][^\"”’]{3,140}[\"”’]", " ", a["raw_title"])
    official = re.search(r"\bresults\b", t, re.I) and not re.search(r"grades|reaction|discussion|winners", t, re.I)
    if official: return None
    if t.strip().endswith("?"): return "question headline (speculative)"
    for n, rx in DROP:
        if n == "evergreen/explainer":
            if evergreen(t): return n
        elif rx.search(t): return n
    lead = (a.get("summary_src") or "")[:300] + " " + (a.get("body") or "")[:300]
    if re.search(r"\bin my opinion\b|\bi think\b.*\bshould\b|\bthis writer\b|\bfantasy booking\b|\bwould love to see\b", lead, re.I): return "opinion (text)"
    return None
# ---------- categories: title-first, roster-aware ----------
ROSTER = {
 "WWE": "Chelsea Green|Alexa Bliss|Giulia|Blake Monroe|Michin|B-Fab|Zelina Vega|Paige|Nikki Bella|Brie Bella|R-Truth|Damian Priest|Rey Fenix|Ricky Saints|Montez Ford|Andrade|Carmelo Hayes|Kairi Sane|Asuka|Nia Jax|Raquel Rodriguez|Lyra Valkyria|Stephanie Vaquer|Jordynne Grace|Roxanne Perez|Je'Von Evans|Jacy Jayne|Sol Ruca|Roman Reigns|Cody Rhodes|CM Punk|Seth Rollins|Rhea Ripley|Gunther|John Cena|Randy Orton|Jey Uso|Jimmy Uso|Solo Sikoa|LA Knight|Drew McIntyre|Bianca Belair|Iyo Sky|Tiffany Stratton|Liv Morgan|Becky Lynch|Charlotte Flair|Jade Cargill|Bron Breakker|Dominik Mysterio|Logan Paul|Brock Lesnar|Triple H|Paul Levesque|Nick Khan|Michael Cole|Pat McAfee|Sami Zayn|Kevin Owens|Jacob Fatu|Oba Femi|Penta|Naomi|Nikki Bella|AJ Styles|Goldberg|Undertaker|The Rock|Stephanie McMahon|Adam Pearce|Nick Aldis|Bayley|Damian Priest|Sheamus|Ethan Page|Trick Williams|Tatum Paxley|Shawn Michaels|Joe Hendry|Kelani Jordan",
 "AEW": "PAC|Persephone|Hyan|Dani Luna|Queen Aminata|Nick Wayne|Megan Bayne|Lena Kross|Thunder Rosa|Hikaru Shida|Britt Baker|Maya World|Daniel Garcia|Wheeler Yuta|Josh Alexander|Mike Bailey|Speedball Mike Bailey|Brian Cage|Ilja Dragunov|Andrade El Idolo|Mark Davis|Kyle O'Reilly|Adam Cole|Willow Nightingale|Harley Cameron|Zayda Steel|Anna Jay|Nigel McGuinness|Tony Khan|Kenny Omega|Will Ospreay|Jon Moxley|MJF|Maxwell Jacob Friedman|Swerve Strickland|Hangman|Adam Page|Samoa Joe|Darby Allin|Toni Storm|Mercedes Mon[eé]|Kris Statlander|Mariah May|Adam Copeland|Christian Cage|Orange Cassidy|Kazuchika Okada|Young Bucks|Jack Perry|Ricochet|Hook|Chris Jericho|Bryan Danielson|Kyle Fletcher|Konosuke Takeshita|Brodido|Bandido|Brody King|Kevin Knight|Jamie Hayter|Athena|Timeless Toni|Hurt Syndicate|MVP|Bobby Lashley|Shelton Benjamin|Death Riders|Claudio Castagnoli|Marina Shafir|Jay White|Mark Briscoe|Powerhouse Hobbs|Wardlow|Thekla|Big Boom AJ|Austin Creed|Xavier Woods|Kofi Kingston|Kofi|New Level",
 "TNA": "Nic Nemeth|Mike Santana|Frankie Kazarian|Masha Slamovich|Moose|Leon Slater|Matt Hardy|Jeff Hardy|Hardys|Santino Marella|Carlos Silva|Scott D'Amore|Steve Maclin|Elijah|Mustafa Ali|Tessa Blanchard|Ash by Elegance",
 "Indie": "Effy|Nick Gage|Matt Cardona|Mance Warner|Joey Janela|Alex Shelley|VNDL48|Bear Bronson|Kidd Bandit",
 "Global": "Hiroshi Tanahashi|Tetsuya Naito|Shingo Takagi|Hirooki Goto|Zack Sabre Jr|Yota Tsuji|Shota Umino|El Desperado|Hechicero|Mistico|M[ií]stico|Mesias|Hijo del Vikingo|El Hijo del Vikingo|Mayu Iwatani|Saya Kamitani|Tam Nakano|Momo Watanabe|Kenta Kobashi|Kaito Kiyomiya|Konosuke|Gabe Kidd|Callum Newman",
}
PROMO = {
 "WWE": r"\bWWE\b|\bRaw\b|SmackDown|\bNXT\b|WrestleMania|Royal Rumble|SummerSlam|Survivor Series|Crown Jewel|Wrestlepalooza|Saturday Night'?s Main Event|Evolution\b|Elimination Chamber|Money in the Bank|Backlash|Bad Blood",
 "AEW": r"\bAEW\b|All Elite|Dynamite|Collision|Rampage|Double or Nothing|All In\b|Full Gear|WrestleDream|All Out\b|Worlds End|Grand Slam|Forbidden Door|Dynasty\b|Revolution\b",
 "TNA": r"\bTNA\b|Impact\b|Bound for Glory|\bBFG\b|Slammiversary|Hard to Kill|Destination X|Turning Point|Victory Road",
 "Indie": r"\bGCW\b|Game Changer|\bPWG\b|\bROH\b|Ring of Honor|\bMLW\b|Major League Wrestling|\bNWA\b|Beyond Wrestling|\bCZW\b|Black Label Pro|West Coast Pro|\bJCW\b|Juggalo|DEFY|Prestige Wrestling|Wrestling Revolver|\bSHINE\b|Freelance Wrestling|indie (show|event|scene|circuit)|independent (show|event|scene|circuit|wrestling)",
 "Global": r"NJPW|New Japan|Stardom|\bCMLL\b|\bAAA\b|Lucha Libre|Lucha Kingdom|Pro Wrestling NOAH|\bNOAH\b|\bDDT\b|AJPW|All Japan|Dragon ?Gate|wXw|RevPro|Revolution Pro|\bPROGRESS\b|\bOTT\b|\bIWGP\b|Wrestle Kingdom|G1 Climax|\bTJPW\b|Marigold|\bWWE (Australia|Mexico|Japan)|\bEVE\b|\bICW\b|Over the Top|\bPWA\b",
}
from aliases import canon
def categories(a):
    t = canon(a["raw_title"]); b = canon((a.get("summary_src") or "") + " " + (a.get("body") or "")[:1500])
    cats = [k for k, r in PROMO.items() if re.search(r, t, re.I)]
    if not cats: cats = [k for k, r in ROSTER.items() if re.search(r"\b(" + r + r")\b", t, re.I)]
    if not cats:
        score = {k: len(re.findall(PROMO[k], b, re.I)) * 2 + len(re.findall(r"\b(" + ROSTER[k] + r")\b", b, re.I)) for k in PROMO}
        best = max(score.values())
        cats = [k for k, v in score.items() if v and v >= best * .6]
    big = [c for c in cats if c in ("WWE", "AEW", "TNA")]
    if big and re.search(r"\b(results?|recap|review|live updates)\b", t, re.I): cats = big
    elif "WWE" in cats and "Global" in cats and not re.search(PROMO["Global"].replace(r"|\bAAA\b", "").replace(r"\bAAA\b|", ""), t, re.I): cats.remove("Global")
    # AAA is co-owned by WWE but stays Global; ROH is AEW-owned but listed as Indie per site filters
    return cats or a.get("categories") or ["Indie"]
# ---------- story kind ----------
# Wrestlers the clustering / consistency gate must recognise by name (no brand: categories come from ROSTER/PROMO only).
# A wrestler missing here is invisible to the 'different wrestlers never merge' rule, so add new names as they show up.
NAMES_EXTRA = ("Dragon Lee|Chad Gable|Rey Mysterio|Dominik Mysterio|Big Cass|Ethan Page|Bron Breakker|Bronson Reed|Jacob Fatu|Sheamus|AJ Styles|"
 "Finn Balor|JD McDonagh|Liv Morgan|Becky Lynch|Charlotte Flair|Bayley|Natalya|Ivy Nile|Maxxine Dupri|Akira Tozawa|Kofi Kingston|Grayson Waller|"
 "Austin Theory|Logan Paul|Karrion Kross|Killer Kross|Braun Strowman|Sami Zayn|Kevin Owens|The Miz|Shinsuke Nakamura|Aleister Black|Tama Tonga|"
 "Tonga Loa|Rusev|El Grande Americano|Cruz del Toro|Joaquin Wilde|Wes Lee|Tony D'Angelo|Oba Femi|Tatum Paxley|Jaida Parker|Lash Legend|"
 "Fallon Henley|Naomi|Jade Cargill|Alba Fyre|Isla Dawn|Piper Niven|Candice LeRae|Johnny Gargano|Tommaso Ciampa|Ludwig Kaiser|Pete Dunne|"
 "Tyler Bate|Shayna Baszler|Zoey Stark|Sonya Deville|Myles Borne|Lexis King|Brooks Jensen|Joe Gacy|Nathan Frazer|Charlie Dempsey|Shawn Spears|"
 "Ridge Holland|Brock Lesnar|Goldberg|Angelo Dawkins|Chris Sabin|Santos Escobar|Ilja Dragunov|Kazuchika Okada|Konosuke Takeshita|Claudio Castagnoli|"
 "Marina Shafir|Kris Statlander|Toni Storm|Mariah May|Jamie Hayter|Thekla|Julia Hart|Skye Blue|Kyle Fletcher|Mark Briscoe|Orange Cassidy|"
 "Chris Jericho|Bryan Danielson|Christian Cage|Kip Sabian|Big Bill|Bryan Keith|Bandido|Brody King|Buddy Matthews|Dralistico|Komander|"
 "Mascara Dorada|Lio Rush|Jay White|Juice Robinson|Max Caster|Anthony Bowens|Powerhouse Hobbs|Ricky Starks|Shelton Benjamin|Bobby Lashley|"
 "Lance Archer|Eddie Kingston|Roderick Strong|Matt Taven|Mike Bennett|Jack Perry|Dustin Rhodes|Kevin Knight|Taya Valkyrie|Trey Miguel|"
 "Ryan Nemeth|Eric Young|Xia Brookside|Rosemary|AJ Francis|Jason Hotch|John Skyler|Daria Rae|Indi Hartwell|Lei Ying Lee|Cedric Alexander|"
 "Sami Callihan|Jake Something|KC Navarro|Laredo Kid|Arianna Grace|Lady Frost|Matt Riddle|Satoshi Kojima|Mesias|Brian Pillman Jr|"
 "Okumura|Rina Yamashita|Mike Santana|Ash by Elegance|Daniel Garcia|Hiromu Takahashi|Kenta|Kota Ibushi|Will Ospreay|Ricochet|Darby Allin|"
 "Penta|Rey Fenix|Andrade|Carlito|Mortos|Hijo del Vikingo|Psycho Clown|Pagano|Mr. Iguana|Laredo Kid|Fuego del Sol|Willow Nightingale")
FIG = "|".join([ROSTER[k] for k in ROSTER] + [NAMES_EXTRA, "William Regal|Austin Creed|Xavier Woods|Paige|Nikki Bella|Brie Bella|Drew McIntyre|Shotzi Blackheart|Tom Lawlor|Eric Bischoff|Jim Ross|Jim Cornette|Bully Ray|Dave Meltzer|Kevin Nash|Booker T|Mick Foley|Paul Heyman|Ric Flair|Hulk Hogan|Vince McMahon|Bruce Prichard|Mark Henry|Taz|Excalibur|Tony Schiavone|Rocky Romero|Gedo|Rob Van Dam|Konnan|Teddy Long|Dutch Mantell|Arn Anderson|Jeff Jarrett|Dixie Carter|Court Bauer|Brett Lauderdale"])
FIG_RX = re.compile(r"\b(" + FIG + r")\b", re.I)
def kind(a):
    t = a["raw_title"]
    q = re.search(r"[\"“‘']([^\"”’]{12,140})[\"”’]", t)
    f = FIG_RX.search(t)
    if f and (q or re.search(r"\b(says|said|advises|warns|blasts|slams|praises|recalls|reveals|explains|comments|addresses|responds|admits|confirms|announces|discusses|talks|on why|details|weighs in|opens up|speaks)\b", t, re.I)):
        return {"type": "quote", "who": f.group(1), "quote": q.group(1) if q else None}
    if re.search(r"\b(results?|recap|review|report card|live coverage|live updates|play-by-play)\b", t, re.I): return {"type": "results"}
    if re.search(r"\bvs\.?\b", t, re.I) and re.search(r"\b(set|official|announced|confirmed|added|signed|made|booked|scheduled|locked)\b", t + " " + (a.get("summary_src") or "")[:200], re.I):
        return {"type": "match"}
    if re.search(r"\bresults?\b", t, re.I): return {"type": "results"}
    return {"type": "news"}
LOGF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "dropped.jsonl")
_SEEN = None
def log_drop(a, reason):
    global _SEEN
    if _SEEN is None:
        _SEEN, keep = set(), []
        if os.path.exists(LOGF):
            for l in open(LOGF):
                try: d = json.loads(l)
                except Exception: continue
                if d["at"] > time.time() - 60*86400 and (d["title"], d["reason"]) not in _SEEN:
                    _SEEN.add((d["title"], d["reason"])); keep.append(l)
            open(LOGF, "w").writelines(keep)
    if (a["raw_title"], reason) in _SEEN: return
    _SEEN.add((a["raw_title"], reason))
    with open(LOGF, "a") as f:
        f.write(json.dumps({"at": int(time.time()), "reason": reason, "source": a["source"], "title": a["raw_title"], "link": a["link"]}) + "\n")
VERSION = 9   # v9 2026-10-21: podcast episodes (fightful /podcasts/, The Hump, 'w/ SRS') and '<Outlet> Daily Update' roundups are filler
_V8 = 8   # v8 2026-10-21: 'start times' (plural) and 'This Day In History' are filler
# ---------- re-published / retrospective content (owner rule 2026-10-22: old news is never posted as new) ----------
# PWTorch's '10 YEARS AGO – WWE LIVE EVENT REPORT: AJ Styles vs. Dean Ambrose ...' is a 2016 house-show report re-run on
# 2026-10-22 with a genuinely fresh publish date, so the 48h real-date gate can't catch it, and the AI rewrite dropped
# '10 YEARS AGO' from the headline. These are history pieces, never news: checked on the SOURCE headline and body, every run,
# before the 'results' exemption in verdict().
_RETRO_T = re.compile(r"(?i)^\W*(?:\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|"
                      r"twenty-five|thirty|forty|fifty)\s+years?\s+ago\b|\byears?\s+ago\s+(?:today|tonight|this\s+(?:week|month|weekend))\b|"
                      r"\bflashback\b|\bfrom\s+the\s+(?:vault|archives?)\b|\bthis\s+week\s+in\s+(?:wrestling\s+|wwe\s+|aew\s+)?history\b|"
                      r"\bthrowback\s+thursday\b|\b#?TBT\b|\bretro\s+(?:review|report|recap)\b|\brewind\b|\bdecades?\s+ago\b|"
                      r"\bon\s+this\s+date\b|\btoday\s+in\s+(?:wrestling\s+)?history\b")
_RETRO_ANY = re.compile(r"(?i)\b\d{1,3}\s+years?\s+ago\b")
_RETRO_B = re.compile(r"(?i)\b(?:originally|first)\s+(?:published|posted|ran|appeared|written)\b[^.]{0,60}?\b(?:\d{1,3}\s+years?\s+ago|"
                      r"in\s+(?:19|20)\d\d|on\s+\w+\.?\s+\d{1,2},\s+(?:19|20)\d\d)|\bthe\s+following\s+(?:is|was)\s+(?:a|an|the)\s+"
                      r"(?:\w+\s+){0,3}(?:report|review|recap|column|article)\s+(?:originally|first)\s+(?:published|posted)\b|"
                      r"\bfrom\s+our\s+archives?\b|\breprinted\b")
_ANNIV = re.compile(r"(?i)\banniversary\s+of\b(?!\s+(?:her|his|their)\s+(?:\w+\s+){0,2}(?:signing|debut))")
_QUOTEISH = re.compile(r"(?i)\b(?:reacts?|says|said|reflects?|recalls?|reveals?|comments?|addresses|responds|admits|discusses|talks|opens up|speaks|celebrates? (?:his|her|their))\b")
# results-style report whose opening describes the past ('A live event in Tokyo featured several matches two decades ago')
_RESULTISH = re.compile(r"(?i)\b(?:results?|recap|live event report|house show report|event report)\b")
_PAST_B = re.compile(r"(?i)\b(?:\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten|twenty|thirty)\s+(?:years?|decades?)\s+ago\b|"
                     r"\bon\s+this\s+(?:day|date)\b|\bthrowback\b|\blooking\s+back\b|\blook\s+back\b")
REMOVED_LINKS = {   # hand-removed reports (owner-reported old content), never a story again even if a rule changes
    "https://www.pwtorch.com/site/2026/10/22/10-years-ago-wwe-live-event-report-aj-styles-vs-dean-ambrose-for-wwe-title-plus-ziggler-kane-bray-wyatt-naomi-alexa-bliss-usos-corbin/",
    "https://www.pwtorch.com/site/2026/10/22/20-years-ago-wwe-live-event-report-in-tokyo-japan-cm-punk-randy-orton-tommy-dreamer-triple-h-shawn-michaels-sabu-edge/",
}
# history columns / sections (whole feed sections that only re-run old material)
RETRO_SECTIONS = re.compile(r"(?i)pwtorch\.com/site/\d{4}/\d\d/\d\d/\d+-years?-ago-|/(?:flashback|throwback|this-day-in-history|on-this-day|"
                            r"today-in-wrestling-history|this-week-in-wrestling-history|from-the-vault|rewind)[/-]|[?&]series=flashback")
def _old_year(txt, now=None):
    y = time.gmtime(now or time.time()).tm_year
    yrs = [int(v) for v in re.findall(r"(?<!\d)((?:19|20)\d\d)(?!\d)", txt or "")]
    return bool(yrs) and max(yrs) <= y - 2
def retro(a):
    """'retrospective: ...' when a report re-runs old content (years-ago reprints, flashbacks, archive pieces), else None.
    A quote story where someone talks about the past ('X reveals why he left WWE 5 years ago') is not a retrospective."""
    link = a.get("link") or ""; t = a.get("raw_title") or ""
    if link in REMOVED_LINKS: return "retrospective: hand-removed (old content re-published)"
    if RETRO_SECTIONS.search(link): return "retrospective: history column / look-back URL"
    t0 = re.sub(r"[\"“‘'][^\"”’]{3,140}[\"”’]", " ", t)
    if _RETRO_T.search(t0): return "retrospective: headline says it's a look back"
    quote = kind(a).get("type") == "quote" or _QUOTEISH.search(t0)
    if _RETRO_ANY.search(t0) and not quote: return "retrospective: headline is about something from years ago"
    if _ANNIV.search(t0) and not quote: return "retrospective: anniversary piece"
    lead = (a.get("summary_src") or "")[:400] + " " + (a.get("body") or "")[:600]
    if _RETRO_B.search(lead): return "retrospective: body says it was originally published years ago"
    resultish = (a.get("kind") or {}).get("type") == "results" or kind(a).get("type") == "results" or _RESULTISH.search(t0)
    if resultish and not quote:
        if re.search(r"(?<!\d)(?:19|20)\d\d(?!\d)", t0) and _old_year(t0): return "retrospective: results-style headline about a show 2+ years old"
        opening = ((a.get("summary_src") or "").strip() or (a.get("body") or "").strip())[:250]   # how the source opens
        m = _PAST_B.search(opening)
        dated_now = re.search(r"(?<!\d)\d{1,2}[/.]\d{1,2}(?:[/.](?:%d|%d))?(?![\d/.])|\b%d\b" % (time.gmtime().tm_year % 100, time.gmtime().tm_year, time.gmtime().tm_year), t0 + " " + opening)
        if m and not dated_now: return f"retrospective: results-style report describing the past ('{m.group(0)}')"
        if re.search(r"(?i)\b(?:in|from|during|on\s+\w+\.?\s+\d{1,2},)\s+(?:19|20)\d\d\b", opening) and _old_year(t0 + " " + opening):
            return "retrospective: results-style report that opens on a date 2+ years old"
    return None
# ---------- 'free live stream' spam (2026-10-24) ----------
# Google News carried pages like '(LIVESTREAMs)! WWE SmackDown 𝐋𝐈𝐕𝐄 Ｆｒｅｅ 𝐒𝐭𝐑𝐞𝐀𝐦 Wrestling' planted on hijacked town / university
# sites (town.shodoshima.lg.jp krpano tour '?xml=data:...base64', uco.es). They joined real stories as 'sources' (timeline lines,
# 'confirmed by N sources') and one gave the SmackDown preview a 360 panorama of a barrel room as its photo. Checked every run.
_STREAMY = re.compile(r"(?i)live\s*@?\s*streams?|livestreams?|free\s*streams?|streaming\s+(?:free|online)|\btv\s*channel\b|watch\s+(?:\w+\s+){0,4}(?:online|free)\b|\bfree\s+online\b")
_SPAMMY = re.compile(r"(?i)\bfree\b|\bonline\b|\breddit\b|\bcrackstreams?\b|\btv\s*channel\b|[%*~$+!@\[\]【】()<>]{2,}|\(\s*live")
_HIJACK = re.compile(r"(?i)[?&]xml=data:|base64,|\.(?:lg|go|ac|ed)\.jp/|\.gov(?:\.\w\w)?/|\.edu(?:\.\w\w)?/|\buco\.es/|/VR_[^/]*/")
def stream_spam(a):
    """'stream spam' for illegal free-stream pages dressed up as wrestling news; None otherwise. Trusted (tier 1/2) outlets'
    own 'Buy-In live stream' posts never match."""
    import unicodedata
    if tier(a.get("source")) < 3: return None
    raw = a.get("raw_title") or a.get("title") or ""; t = unicodedata.normalize("NFKC", raw); link = a.get("link") or ""
    if _HIJACK.search(link) and _STREAMY.search(t): return "stream spam"
    if _STREAMY.search(t) and (t != raw or _SPAMMY.search(t)): return "stream spam"   # 𝐋𝐈𝐕𝐄 / Ｆｒｅｅ styled letters, 'free', '%*(((' junk
    return None
# 'This Week's Edition Of Gotham Wrestling Is Now Streaming' (PWInsider, 2026-10-24): a one-line 'episode is up' notice with no
# news in it. These template titles glued unrelated show notices (Gotham, UWN, TNA Xplosion, WWE Main Event, Dynamite, SmackDown
# previews) into one story that carried a WWE logo photo. Any source; checked every run.
_NOTICE = re.compile(r"(?i)^\s*(?:this|last)\s+week'?s\s+(?:edition|episode)\s+of\s+.{2,80}?\s+(?:is|are)\s+(?:now\s+)?(?:streaming|available|online|up)\b")
def stream_notice(a):
    """'streaming notice' for content-free 'this week's edition of X is now streaming' bulletins; None otherwise."""
    return "streaming notice" if _NOTICE.search(a.get("raw_title") or a.get("title") or "") else None
# 2026-10-25 (AdSense 'low value content'): PWInsider-style bulletins whose whole title is '10/23 WWE Smackdown Videos', 'WWE Raw
# Post Game', 'The Smackdown Post Game Show', 'The AEW Wrestledream 2026 Post PPV Scrum Is Now Streaming', 'This Week's MLW Fusion Is
# Now Streaming' carry no news (they only say clips/a show were posted). Only articles dated after VIDEO_NOTICE_FROM are dropped, so
# stories already published keep their ids (the old ones were removed by hand via story_removals.json).
VIDEO_NOTICE_FROM = 1792951200   # 2026-10-25 18:00 UTC
_VNOTICE = re.compile(r"(?i)^\s*(?:results\s+recap:\s*)?(?:\d{1,2}/\d{1,2}(?:/\d{2,4})?\s+)?(?:the\s+)?"
    r"(?:(?:wwe|aew|aaa|tna|nxt|roh|njpw|mlw|cmll|stardom|impact|nwa|gcw)\b[\w!&'. -]{0,40}?\s+(?:highlight\s+)?videos"
    r"|[\w!&'. -]{2,50}?\s+post[- ]?(?:game|ppv)(?:\s+(?:show|scrum))?(?:\s+is\s+now\s+streaming)?"
    r"|this\s+week'?s\s+[\w!&'. -]{2,50}?\s+is\s+now\s+streaming)\s*$")
def video_notice(a):
    """'video notice' for content-free 'X videos' / 'post game show' / 'this week's X is now streaming' bulletins dated after
    VIDEO_NOTICE_FROM; None otherwise."""
    if (a.get("ts") or 0) < VIDEO_NOTICE_FROM: return None
    return "video notice" if _VNOTICE.search(a.get("raw_title") or a.get("title") or "") else None
