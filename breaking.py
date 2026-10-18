"""'BREAKING🚨🚨🚨' label for X posts: ONLY (1) title changes (new champion / title vacated), (2) a wrestler fired or released,
(3) a wrestler's debut in a promotion, (4) a wrestler's return (after injury / time off TV). Conservative: the HEADLINE must
use clear completed-event wording; any speculative/preview/retrospective word blocks it (a false positive is worse than a miss).
Quotes/interviews never qualify. Not used by push alerts."""
import re
LABEL = "BREAKING🚨🚨🚨"   # exact owner format; followed by a newline, then the post text
PROMOS = r"(?:WWE|AEW|TNA|NXT|ROH|NJPW|AAA|CMLL|MLW|GCW|NWA|Stardom|Raw|SmackDown|Dynamite|Collision|Rampage|Impact)"
# never breaking: speculation, previews, plans, retrospectives, opinion/interview verbs, questions
BLOCK = re.compile(r"(?i)\?|\brumou?r\w*|\bcould\b|(?<!Mariah )\bmay\b|\bmight\b|\bexpect\w*|\breportedly\b|\breport(?:s|ed)?\s*:|\bset (?:to|for)\b|\bpreview\w*|"
                   r"\bpredict\w*|\bpossible\b|\bpotential\b|\bwould\b|\bshould\b|\bplans?\b|\bplanned\b|\bhopes?\b|\bwants?\b|\bteases?\b|\bhints?\b|\bodds\b|"
                   r"\bwill (?:not |never )?(?:be|return|debut|face|win|get|make|challenge|defend|appear|compete|wrestle|have|lose)\b|\bwon'?t\b|\bnear(?:s|ing)?\b|\bclose to\b|"
                   r"\bopen to\b|\brules? out\b|\beyes?\b|\btargets?\b|\binterest\w*|\bin talks\b|\bconsider\w*|\bupdate[sd]?\b|\bbackstage\b|\bcleared\b|\bnot\b|"
                   r"\bif\b|\bwhy\b|\bhow\b|\bwhat\b|\bwhen\b|\bnearly\b|\balmost\b|\brecalls?\b|\bremembers?\b|\breflects?\b|\blooks? back\b|\banniversary\b|\byears ago\b|"
                   r"\bthrowback\b|\bon this day\b|\bdescribes?\b|\bdiscuss\w*|\bexplains?\b|\breveals?\b|\btalks?\b|\bsays\b|\bpraises?\b|\bcriticiz\w*|\bslams?\b|\bresponds?\b|"
                   r"\bdenies\b|\bfake\b|\b2K\d*\b|\bvideo ?game\b|\bdream match\b|\bfantasy\b|\bannounce[sd]?\b|\badvertis\w*|\bbooked\b|\bconfirmed for\b|\bscheduled\b")
TITLE = r"(?:titles?|championships?|belts?|gold)"
CHANGE = [re.compile(r"(?i)\b(?:wins?|won|captures?|captured|claims?|claimed|regains?|regained|reclaims?|reclaimed|lifts?|takes?|took)\b(?:\s+[\w'’.&-]+){0,6}?\s+" + TITLE + r"\b"),
          re.compile(r"(?i)\bnew\s+(?:[\w'’.-]+\s+){0,4}champions?\b|\bcrowned\b|\bdethron\w+|\btitle change\b"),
          re.compile(r"(?i)\b(?:vacates?|vacated|relinquish\w*|stripped of)\b")]
NOT_CHANGE = re.compile(r"(?i)\bretain\w*|\bdefen[ds]\w*|\bshot\b|\bopportunity\b|\bcontender\w*|\bqualif\w*|\beliminator\b|\btournament\b|\bbriefcase\b|"
                        r"\bmoney in the bank\b|\brumble\b|\btitle match\b|\btitle run\b|\btitle win\b|\bvs\.?\b|\bearns?\b|\bchallenge\w*")
RELEASE = [re.compile(r"(?i)\b(?:is|are|been|gets?|got|was|were)\s+released\b|\breleased\s+(?:by|from)\b|\breleased\s*$|\bgranted (?:his|her|their) release\b|\bcut by\b|\blet go by\b"),
           re.compile(r"(?i)\bfired\b(?!\s+(?:up|back|off|shots?))|\bis fired\b"),
           re.compile(r"(?i)\b" + PROMOS + r"\s+(?:releases|cuts|fires)\s+(?:\d+|two|three|four|five|six|seven|eight|nine|ten|several|multiple|more|numerous)\s+(?:wrestlers|talents?|stars|superstars|names)\b")]
NOT_RELEASE = re.compile(r"(?i)\brequest\w*|\basks? for\b|\bwants\b|\bdeni\w*|\brelease date\b|\breleased (?:a|an|the|new|his|her|their|its)\b")
DEBUT = [re.compile(r"(?i)\bdebuts\b|\bdebuted\b|\bmakes? (?:[\w-]+\s+){0,3}debut\b|\bmade (?:[\w-]+\s+){0,3}debut\b|\bwins? (?:[\w-]+\s+){0,2}debut\b|\bin (?:his|her|their) (?:[\w-]+\s+){0,2}debut\b|\bis all elite\b")]
NOT_DEBUT = re.compile(r"(?i)\bto debut\b|\bdebut (?:date|set|match set)\b|\bbefore (?:his|her|their) debut\b|\bahead of\b|\bsince\b|\b" + PROMOS + r"\s+(?:\w+\s+)?debuts?\b(?!\s+(?:at|in|on|for|as))")
RETURN = [re.compile(r"(?i)\breturns\b(?!\s+to\s+(?:the\s+)?(?:city|arena|venue))|\breturned\b|\bmakes? (?:[\w-]+\s+){0,3}return\b|\bmade (?:[\w-]+\s+){0,3}return\b|\bis back\b|\bback in action\b")]
NOT_RETURN = re.compile(r"(?i)^(?:the\s+)?" + PROMOS + r"(?:\s+[\w'’]+){0,3}\s+returns\b|\b(?:show|event|tour|ppv|tournament|series|brand|card|match(?:es)?|stipulation|title)\s+returns\b|"
                        r"\breturns? (?:date|timeline)\b|\bto return\b|\breturns? home\b|\breturns? as (?:a\s+)?(?:guest|commentator|host|analyst|producer|coach)\b|\breturns? to (?:australia|japan|mexico|uk|london|saudi|europe|puerto rico|\w+ city)\b")
def _headline_kind(t):
    if any(rx.search(t) for rx in CHANGE) and not NOT_CHANGE.search(t): return "title-change"
    if any(rx.search(t) for rx in RELEASE) and not NOT_RELEASE.search(t): return "release"
    if any(rx.search(t) for rx in DEBUT) and not NOT_DEBUT.search(t): return "debut"
    if any(rx.search(t) for rx in RETURN) and not NOT_RETURN.search(t): return "return"
    return None
# --- source check: our headline is an AI rewrite, so the label also needs the SOURCE's own title/summary to state the event ---
# (2026-10-18: Fightful 'La Catalina Appears, Tag Title Bout' was rewritten 'La Catalina Debuts in Tag Title Match' and labelled.)
# 'appears' / 'appearance' / 'shows up' is never evidence of a debut; a 'title bout/match' is never evidence of a title change.
SPEC = re.compile(r"(?i)\?|\brumou?r\w*|\bcould\b|\bmight\b|\bwould\b|\bexpect\w*|\bset (?:to|for)\b|\bplans?\b|\bplanned\b|\bpossible\b|\bpotential\b|"
                  r"\bhopes?\b|\bwants?\b|\bteases?\b|\bhints?\b|\bwill\b|\bin talks\b|\bconsider\w*|\bopen to\b|\bahead of\b|\bpreview\w*|\bif\b")
EVID = {
 "title-change": ([re.compile(r"(?i)\b(?:wins?|won|captures?|captured|claims?|claimed|regains?|regained|reclaims?|reclaimed|lifts?|takes?|took|winning|capturing)\b(?:\s+[\w'’.&-]+){0,6}?\s+" + TITLE + r"\b"),
                   re.compile(r"(?i)\bnew\s+(?:[\w'’.-]+\s+){0,4}champions?\b|\bcrowned\b|\bdethron\w+|\btitle change\b|\bvacate[sd]?\b|\brelinquish\w*|\bstripped of\b")],
                  re.compile(r"(?i)\bretain\w*|\bsuccessful(?:ly)? defen\w*|\btitle shot\b|\bcontender\w*|\bqualif\w*|\beliminator\b")),
 "release":      (RELEASE + [re.compile(r"(?i)\b(?:another|latest|more|new)\s+(?:[\w-]+\s+){0,3}releases?\b|\breleased\b|\bfired\b(?!\s+(?:up|back|off|shots?))|\bcut from\b|\bparted ways\b|\bpart ways\b")],
                  NOT_RELEASE),
 "debut":        ([re.compile(r"(?i)\bdebut(?:s|ed|ing)?\b|\bfirst(?:-ever)?\s+(?:\w+\s+)?appearance\b|\bis all elite\b")],
                  re.compile(r"(?i)\bto (?:make (?:\w+\s+){0,3})?debut\b|\bdebut (?:date|set|match set)\b|\bbefore (?:his|her|their) debut\b|\bsince (?:his|her|their) debut\b|\banniversary\b|\byears? ago\b|\brecalls?\b")),
 "return":       ([re.compile(r"(?i)\breturns\b|\breturned\b|\bmakes? (?:[\w-]+\s+){0,3}return\b|\bmade (?:[\w-]+\s+){0,3}return\b|\bis back\b|\bback in action\b|\bfirst (?:\w+\s+){0,2}(?:match|appearance) (?:since|in)\b")],
                  NOT_RETURN),
}
def _segments(src):
    return [x for x in re.split(r"(?<=[.!?])\s+|\s+[|•]\s+|\n+", src or "") if x.strip()]
def source_supports(k, src):
    """True if any sentence of the source title/summary states event k in completed terms (no speculation)."""
    pos, neg = EVID[k]
    for seg in _segments(src):
        if SPEC.search(seg): continue
        if any(rx.search(seg) for rx in pos) and not neg.search(seg): return True
    return False
def kind(title, story_kind=None, source=None):
    """-> 'title-change' | 'release' | 'debut' | 'return' | None.
    title = our (AI-rewritten) headline; source = the source article's OWN title + summary. When source is given (x_poster always
    passes it), the event must also be stated there - the AI headline alone can never earn the label."""
    t = (title or "").replace("🚨", "").strip()
    if not t or (story_kind or "") in ("quote", "rumor", "preview"): return None
    if BLOCK.search(t): return None
    k = _headline_kind(t)
    if k and source is not None and not source_supports(k, source): return None
    return k
