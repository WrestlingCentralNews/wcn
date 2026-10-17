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
 "Hiroshi Tanahashi": ["Tanahashi"], "Tetsuya Naito": ["Naito"], "Zack Sabre Jr.": ["ZSJ", "Zack Sabre Jr"], "Mistico": ["Místico", "Dragon Lee"],
 "Hechicero": ["El Hechicero"], "Mayu Iwatani": ["Iwatani"], "Konosuke Takeshita": ["Takeshita"], "Kyle Fletcher": ["Fletcher"],
 "Nick Gage": ["Nicholas Wilson"], "Matt Cardona": ["Zack Ryder"], "Effy": ["Effy"], "Alex Shelley": ["Patrick Martin"],
 "William Regal": ["Darren Matthews", "Lord Steven Regal"], "Michael Cole": ["Sean Coulthard"], "Nick Aldis": ["Magnus"], "Adam Pearce": ["Scrap Iron"],
}
_pairs = sorted(((a, k) for k, v in ALIASES.items() for a in v if a.lower() != k.lower() and len(a) > 3), key=lambda x: -len(x[0]))
_rx = re.compile(r"\b(" + "|".join(re.escape(a) for a, _ in _pairs) + r")\b")
_map = {a: k for a, k in _pairs}
def canon(t):
    """Replace real/former names with the canonical ring name (case-sensitive to avoid 'kane'/'walter' false hits)."""
    return _rx.sub(lambda m: _map[m.group(1)], t or "")
