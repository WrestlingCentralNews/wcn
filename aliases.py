"""Real name / former ring name -> canonical ring name. Used by clustering and categorization."""
import re
ALIASES = {
 "PAC": ["Ben Satterley", "Ben Satterly", "Neville", "Adrian Neville", "Pac's", "PAC's"],
 "Adam Copeland": ["Edge", "Rated R Superstar"], "Christian Cage": ["Jay Reso", "Christian"],
 "Xavier Woods": ["Austin Creed"], "Big E": ["Ettore Ewen"], "Kofi Kingston": ["Kofi Sarkodie-Mensah"],
 "Roman Reigns": ["Joe Anoa'i", "Leati Joseph Anoa'i"], "The Rock": ["Dwayne Johnson"], "Triple H": ["Paul Levesque", "HHH"],
 "John Cena": ["Cena"], "CM Punk": ["Phil Brooks"], "Cody Rhodes": ["Cody Runnels"], "Seth Rollins": ["Colby Lopez", "Tyler Black"],
 "Jon Moxley": ["Dean Ambrose", "Jonathan Good"], "Rhea Ripley": ["Demi Bennett"], "Becky Lynch": ["Rebecca Quin"],
 "Charlotte Flair": ["Ashley Fliehr"], "Ric Flair": ["Richard Fliehr"], "Bianca Belair": ["Bianca Crawford"], "Liv Morgan": ["Gionna Daddio"],
 "Naomi": ["Trinity Fatu"], "Jade Cargill": ["Jade"], "Mercedes Moné": ["Sasha Banks", "Mercedes Mone", "Mercedes Varnado"],
 "Toni Storm": ["Toni Rossall"], "Kris Statlander": ["Kristen Statlander"], "Jamie Hayter": ["Jamie Hayter"],
 "MJF": ["Maxwell Jacob Friedman", "Max Friedman"], "Swerve Strickland": ["Isaiah Scott", "Shane Strickland"], "Hangman Adam Page": ["Hangman Page", "Adam Page", "Stephen Woltz"],
 "Kenny Omega": ["Tyson Smith"], "Will Ospreay": ["William Peter Charles Ospreay"], "Bryan Danielson": ["Daniel Bryan"],
 "Chris Jericho": ["Y2J", "Christopher Irvine"], "Samoa Joe": ["Nuufolau Joel Seanoa"], "Darby Allin": ["Samuel Ratsch"], "Orange Cassidy": ["James Cipperly"],
 "Kazuchika Okada": ["Okada"], "Young Bucks": ["Matt Jackson", "Nick Jackson", "The Elite"], "Malakai Black": ["Aleister Black", "Tommy End"],
 "Zelina Vega": ["Xelina", "Thea Trinidad"], "Penta": ["Penta El Zero Miedo", "Pentagon Jr", "Penta Zero M"], "Rey Fenix": ["Fenix", "Fénix", "Rey Fénix"],
 "Ricochet": ["Prince Puma", "Trevor Mann"], "Brock Lesnar": ["Lesnar"], "Goldberg": ["Bill Goldberg"], "Undertaker": ["Mark Calaway", "The Undertaker"],
 "Kane": ["Glenn Jacobs"], "Mick Foley": ["Cactus Jack", "Mankind"], "Shawn Michaels": ["HBK"], "Stone Cold Steve Austin": ["Steve Austin", "Stone Cold"],
 "Hulk Hogan": ["Terry Bollea", "Hogan"], "Randy Orton": ["Orton"], "Drew McIntyre": ["Drew Galloway"], "Sami Zayn": ["El Generico", "Rami Sebei"],
 "Kevin Owens": ["Kevin Steen"], "AJ Styles": ["Allen Jones"], "Gunther": ["Walter", "GUNTHER"], "Jey Uso": ["Joshua Fatu", "Main Event Jey"],
 "Jimmy Uso": ["Jonathan Fatu"], "Solo Sikoa": ["Joseph Fatu"], "Jacob Fatu": ["Fatu"], "LA Knight": ["Eli Drake", "Shaun Ricker"],
 "Bron Breakker": ["Bronson Rechsteiner"], "Dominik Mysterio": ["Dirty Dom"], "Rey Mysterio": ["Oscar Gutierrez"], "Damian Priest": ["Punishment Martinez"],
 "Iyo Sky": ["Io Shirai", "IYO SKY"], "Asuka": ["Kana"], "Kairi Sane": ["Kairi Hojo"], "Giulia": ["Giulia"], "Tiffany Stratton": ["Tiffy"],
 "Nia Jax": ["Savelina Fanene"], "Bayley": ["Pamela Martinez"], "Paige": ["Saraya", "Saraya-Jade Bevis"], "Nikki Bella": ["Nikki Garcia", "Stephanie Garcia-Colace"],
 "Montez Ford": ["Kenneth Crawford"], "Trick Williams": ["Matrick Belton"], "Ethan Page": ["Julian Micevski"], "Shotzi Blackheart": ["Shotzi", "Ashley Urbanski"],
 "Joe Hendry": ["Joseph Hendry"], "Nic Nemeth": ["Dolph Ziggler", "Nick Nemeth"], "Mike Santana": ["Santana"], "Moose": ["Quinn Ojinnaka"],
 "Matt Hardy": ["Broken Matt"], "Jeff Hardy": ["Brother Nero"], "Masha Slamovich": ["Masha"], "Jordynne Grace": ["Patricia Parker"],
 "Max Caster": ["Maxwell Caster"], "Ilja Dragunov": ["Dragunov"], "Malik": ["MVP", "Montel Vontavious Porter"], "Bobby Lashley": ["Lashley"],
 "Mark Henry": ["Henry"], "Booker T": ["Booker Huffman"], "Paul Heyman": ["Heyman"], "Vince McMahon": ["Vince"], "Tony Khan": ["TK"],
 "Hiroshi Tanahashi": ["Tanahashi"], "Tetsuya Naito": ["Naito"], "Zack Sabre Jr.": ["ZSJ", "Zack Sabre Jr"], "Mistico": ["Místico"], "Dragon Lee": [],   # Dragon Lee (WWE, Rush's brother) is not today's Místico (CMLL)

 "Hechicero": ["El Hechicero"], "Mayu Iwatani": ["Iwatani"], "Konosuke Takeshita": ["Takeshita"], "Kyle Fletcher": ["Fletcher"],
 "Nick Gage": ["Nicholas Wilson"], "Ludwig Kaiser": ["Marcel Barthel"], "Matt Cardona": ["Zack Ryder"], "Effy": ["Effy"], "Alex Shelley": ["Patrick Martin"],
 "William Regal": ["Darren Matthews", "Lord Steven Regal"], "Michael Cole": ["Sean Coulthard"], "Nick Aldis": ["Magnus"], "Adam Pearce": ["Scrap Iron"],
}
_pairs = sorted(((a, k) for k, v in ALIASES.items() for a in v if a.lower() != k.lower() and len(a) > 3), key=lambda x: -len(x[0]))
_rx = re.compile(r"\b(" + "|".join(re.escape(a) for a, _ in _pairs) + r")\b")
_map = {a: k for a, k in _pairs}
def canon(t):
    """Replace real/former names with the canonical ring name (case-sensitive to avoid 'kane'/'walter' false hits)."""
    return _rx.sub(lambda m: _map[m.group(1)], t or "")

# Same-name / family members: the CHILD must never be resolved to the famous PARENT (2026-10-22: Fightful/Wrestling Inc
# 'Steve(n) Borden Returns' was rewritten 'Sting Returns'). Sting = only 'Sting' or an explicit 'Steve Borden Sr.'.
FAMILY = {   # parent ring name -> names/phrases that mean the child
 "Sting": ["Steve Borden Jr", "Steven Borden Jr", "Steve Borden", "Steven Borden", "Borden Jr", "Sting's son", "Sting’s son", "son of Sting"],
 "Rey Mysterio": ["Dominik Mysterio", "Dominik", "Rey Mysterio's son"],
 "Ric Flair": ["Charlotte Flair", "David Flair", "Reid Flair", "Ric Flair's daughter"],
}
_PARENT_OK = {"Sting": r"\bSting\b(?!['’]s\s+(?i:son|daughter|kid|child))|Steve(?:n)? Borden,? Sr\b"}
def _has_parent(p, t):
    """Text names the parent himself (not 'Sting's son' / 'son of Sting' / 'Sting Jr.')."""
    rx = _PARENT_OK.get(p) or (r"\b" + re.escape(p) + r"\b(?!['’]s\s+(?i:son|daughter|kid|child)|,?\s+Jr\b)")
    t = re.sub(r"(?i)\b(?:son|daughter|child|kid|father|dad)\s+of\s+(?:(?:wrestling|wwe|aew)\s+)?(?:legend|icon|hall of famer\s+)?\s*" + re.escape(p), "", t or "")
    return bool(re.search(rx, t))
def _child_named(p, t):
    t = t or ""
    if any(re.search(r"(?i)\b" + re.escape(c) + r"\b", t) for c in FAMILY.get(p, [])): return True
    return bool(re.search(r"(?i)\b(?:son|daughter)\s+of\s+(?:(?:wrestling|wwe|aew)\s+)?(?:legend\s+|icon\s+)?" + re.escape(p) + r"\b|\b" + re.escape(p) + r"['’]s\s+(?:son|daughter)\b|\b" + re.escape(p) + r",?\s+Jr\b", t))
def family_mixup(headline, src_title, src_text=""):
    """Parent named in the headline although the source headline names only the child (Jr./'son of'/known family) -> parent name."""
    for p in list(FAMILY) + [m for m in re.findall(r"\b((?:[A-Z][a-z]+\s){0,2}[A-Z][a-z]+),?\s+Jr\b", (src_title or "") + " " + (src_text or ""))]:
        if _has_parent(p, headline) and not _has_parent(p, src_title) and _child_named(p, (src_title or "") + "\n" + (src_text or "")):
            return p
    return None
