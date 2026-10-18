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
def kind(title, story_kind=None):
    """-> 'title-change' | 'release' | 'debut' | 'return' | None (headline only)."""
    t = (title or "").replace("🚨", "").strip()
    if not t or (story_kind or "") in ("quote", "rumor", "preview"): return None
    if BLOCK.search(t): return None
    if any(rx.search(t) for rx in CHANGE) and not NOT_CHANGE.search(t): return "title-change"
    if any(rx.search(t) for rx in RELEASE) and not NOT_RELEASE.search(t): return "release"
    if any(rx.search(t) for rx in DEBUT) and not NOT_DEBUT.search(t): return "debut"
    if any(rx.search(t) for rx in RETURN) and not NOT_RETURN.search(t): return "return"
    return None
