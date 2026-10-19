/** Port of editorial.tier + editorial.verdict (title-only DROP rules). Keep in sync with editorial.py. */
const T1 =
  /^(WWE|WWE\.com|AEW|All Elite Wrestling|TNA Wrestling|TNA|NEW JAPAN PRO-WRESTLING|NJPW|ROH|Ring of Honor|STARDOM|CMLL|Lucha Libre AAA|GCW|MLW|Wrestling Observer|F4W|PWInsider(\.com)?|Fightful|POST Wrestling|Wrestling Inc\.?)$/i;
const T2 =
  /^(Cageside Seats|PWTorch|Pro Wrestling Dot Net|Yahoo Sports|Sports Illustrated|ESPN|CBS Sports|Associated Press|AP News|Reuters|USA Today|BBC|The Guardian|DAZN|Variety|The Hollywood Reporter|Forbes|Wrestlezone|Monthly Puroresu|Bodyslam\.net|411MANIA|Bleacher Report|New York Post|Los Angeles Times|Deadline)$/i;

export function tier(src) {
  if (T1.test(src || "")) return 1;
  if (T2.test(src || "")) return 2;
  return 3;
}

const DROP = [
  [
    "listicle",
    /^\d+\s+(?:\w+\s+){0,4}(reasons|ways|things|times|wrestlers|matches|moments|stars|superstars|questions|takeaways|surprises|ideas|facts|mistakes|best|worst|biggest)|\b(top|best|worst|biggest)\s+\d+\b|\branking(s)?\b|\branked\b|power rankings|\bgreatest\b|\bunderrated\b|\boverrated\b/i,
  ],
  [
    "prediction",
    /predict|picks?\b.*\b(for|ahead)|preview (and|&)|betting odds|\bodds\b|who will win|what to expect|could (win|face|return|happen)|should (win|face|happen|return|book|be)/i,
  ],
  [
    "fantasy/dream",
    /dream match|fantasy book|\bwhat if\b|imagin|would be (perfect|great)|needs to (happen|face|win)|must (face|win|happen)|how (wwe|aew|tna) (should|could|can)/i,
  ],
  [
    "rumor",
    /\brumou?r|\[report\]|\bspeculat|\bteases?\b.*\?|\breportedly\b.*\?|\bhints? at\b.*\?|is (wwe|aew) (planning|teasing)\b.*\?|\bmight\b|\bcould be\b|\bpossibly\b|fans (think|believe|convinced|speculate)|\btheory\b/i,
  ],
  [
    "opinion",
    /\bopinion\b|\bcolumn\b|\bop-ed\b|\bhot take|\bmy (thoughts|take)|\bwe need to talk|\bthe case for\b|\bis wrong\b|\bdeserves? better\b|\bdraws? & duds\b|\bgrades?\b|\bratings? (and|&) review\b|\bstock (up|down)\b|\bwinners? (and|&) losers?\b|\bhits? (and|&) misses\b|\bpodcast\b|\bep(isode)?\.? ?\d+\b|\bmailbag\b|\bdebate\b|\bvs\.? (wwe|aew)\b.*\bwhich\b|\b(roundtable|discussion)\b/i,
  ],
  [
    "podcast/roundup",
    /^(WOL|WOR|POST NEWS|Bryan & Vinny|Rasslin)\s*:|—\s*(WOL|POST NEWS|WOR)\b|wrestling observer (live|radio)|\bpodcast\b|\bradio\b|\bpost news\b|\bnews (and|&) notes\b|\bweekly roundup\b/i,
  ],
  [
    "poll/quiz",
    /\bpoll\b|\bvote\b|\bquiz\b|what do you think|\bsound off\b|\byou decide\b|\bfan reactions?\b|\bfans react\b|twitter reacts|social media reacts|\bmemes?\b/i,
  ],
  [
    "gossip/other",
    /\bon this day\b|\bthrowback\b|\bwhere are they now\b|\blooking back\b|\bhistory of\b|\bdating\b|\bgirlfriend\b|\bboyfriend\b|\bbikini\b|\bphotos?\b.*\b(stuns?|hot)\b|\bnet worth\b|\bhoroscope\b|\bfull list\b.*\bfree agents\b|\brumor roundup\b|\bclickbait\b|\bstreaming guide\b|\bhow to watch\b|\bstart time\b|\bwatch .* live\b/i,
  ],
];

/** Return drop reason or null (keep). Title-only, matching the box watcher's call. */
export function verdict(rawTitle) {
  let t = (rawTitle || "").replace(/["\u201C\u2018'][^"\u201D\u2019']{3,140}["\u201D\u2019']/g, " ");
  const official = /\bresults\b/i.test(t) && !/grades|reaction|discussion|winners/i.test(t);
  if (official) return null;
  if (t.trim().endsWith("?")) return "question headline (speculative)";
  for (const [n, rx] of DROP) {
    if (rx.test(t)) return n;
  }
  return null;
}
