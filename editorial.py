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
 ("gossip/other", r"\bon this day\b|\bthrowback\b|\bwhere are they now\b|\blooking back\b|\bhistory of\b|\bdating\b|\bgirlfriend\b|\bboyfriend\b|\bbikini\b|\bphotos?\b.*\b(stuns?|hot)\b|\bnet worth\b|\bhoroscope\b|\bfull list\b.*\bfree agents\b|\brumor roundup\b|\bclickbait\b|\bstreaming guide\b|\bhow to watch\b|\bstart time\b|\bwatch .* live\b"),
]
DROP = [(n, re.compile(p, re.I)) for n, p in DROP]
def verdict(a):
    t = re.sub(r"[\"“‘'][^\"”’]{3,140}[\"”’]", " ", a["raw_title"])
    official = re.search(r"\bresults\b", t, re.I) and not re.search(r"grades|reaction|discussion|winners", t, re.I)
    if official: return None
    if t.strip().endswith("?"): return "question headline (speculative)"
    for n, rx in DROP:
        if rx.search(t): return n
    lead = (a.get("summary_src") or "")[:300] + " " + (a.get("body") or "")[:300]
    if re.search(r"\bin my opinion\b|\bi think\b.*\bshould\b|\bthis writer\b|\bfantasy booking\b|\bwould love to see\b", lead, re.I): return "opinion (text)"
    return None
# ---------- categories: title-first, roster-aware ----------
ROSTER = {
 "WWE": "Chelsea Green|Alexa Bliss|Giulia|Blake Monroe|Michin|B-Fab|Zelina Vega|Paige|Nikki Bella|Brie Bella|R-Truth|Damian Priest|Rey Fenix|Ricky Saints|Montez Ford|Andrade|Carmelo Hayes|Kairi Sane|Asuka|Nia Jax|Raquel Rodriguez|Lyra Valkyria|Stephanie Vaquer|Jordynne Grace|Roxanne Perez|Je'Von Evans|Jacy Jayne|Sol Ruca|Roman Reigns|Cody Rhodes|CM Punk|Seth Rollins|Rhea Ripley|Gunther|John Cena|Randy Orton|Jey Uso|Jimmy Uso|Solo Sikoa|LA Knight|Drew McIntyre|Bianca Belair|Iyo Sky|Tiffany Stratton|Liv Morgan|Becky Lynch|Charlotte Flair|Jade Cargill|Bron Breakker|Dominik Mysterio|Logan Paul|Brock Lesnar|Triple H|Paul Levesque|Nick Khan|Michael Cole|Pat McAfee|Sami Zayn|Kevin Owens|Jacob Fatu|Oba Femi|Penta|Naomi|Nikki Bella|AJ Styles|Goldberg|Undertaker|The Rock|Stephanie McMahon|Adam Pearce|Nick Aldis|Bayley|Damian Priest|Sheamus|Ethan Page|Trick Williams|Tatum Paxley|Shawn Michaels",
 "AEW": "PAC|Persephone|Hyan|Dani Luna|Queen Aminata|Nick Wayne|Megan Bayne|Lena Kross|Thunder Rosa|Hikaru Shida|Britt Baker|Maya World|Daniel Garcia|Wheeler Yuta|Josh Alexander|Mike Bailey|Speedball Mike Bailey|Brian Cage|Ilja Dragunov|Andrade El Idolo|Mark Davis|Kyle O'Reilly|Adam Cole|Willow Nightingale|Harley Cameron|Zayda Steel|Anna Jay|Nigel McGuinness|Tony Khan|Kenny Omega|Will Ospreay|Jon Moxley|MJF|Maxwell Jacob Friedman|Swerve Strickland|Hangman|Adam Page|Samoa Joe|Darby Allin|Toni Storm|Mercedes Mon[eé]|Kris Statlander|Mariah May|Adam Copeland|Christian Cage|Orange Cassidy|Kazuchika Okada|Young Bucks|Jack Perry|Ricochet|Hook|Chris Jericho|Bryan Danielson|Kyle Fletcher|Konosuke Takeshita|Brodido|Bandido|Brody King|Kevin Knight|Jamie Hayter|Athena|Timeless Toni|Hurt Syndicate|MVP|Bobby Lashley|Shelton Benjamin|Death Riders|Claudio Castagnoli|Marina Shafir|Jay White|Mark Briscoe|Powerhouse Hobbs|Wardlow|Max Caster|Thekla|Big Boom AJ|Austin Creed|Xavier Woods|Kofi Kingston|Kofi|New Level",
 "TNA": "Nic Nemeth|Joe Hendry|Mike Santana|Frankie Kazarian|Masha Slamovich|Jordynne Grace|Moose|Trick Williams|Leon Slater|Matt Hardy|Jeff Hardy|Hardys|Santino Marella|Carlos Silva|Scott D'Amore|Steve Maclin|Elijah|Mustafa Ali|Tessa Blanchard|Kelani Jordan|Ash by Elegance",
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
FIG = "|".join([ROSTER[k] for k in ROSTER] + ["William Regal|Austin Creed|Xavier Woods|Paige|Nikki Bella|Brie Bella|Drew McIntyre|Shotzi Blackheart|Tom Lawlor|Eric Bischoff|Jim Ross|Jim Cornette|Bully Ray|Dave Meltzer|Kevin Nash|Booker T|Mick Foley|Paul Heyman|Ric Flair|Hulk Hogan|Vince McMahon|Bruce Prichard|Mark Henry|Taz|Excalibur|Tony Schiavone|Rocky Romero|Gedo|Rob Van Dam|Konnan|Teddy Long|Dutch Mantell|Arn Anderson|Jeff Jarrett|Dixie Carter|Court Bauer|Brett Lauderdale"])
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
VERSION = 6
