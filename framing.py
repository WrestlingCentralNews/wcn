"""Headline framing guards for the AI rewrite (2026-10-22, 'Penta Chose AEW Over WWE With Family Input'):
1. choice_inverted: a 'chose X over Y' headline may not contradict the source ('opted to sign with WWE').
2. past_framing: a recollection told in an interview ('Penta Says His Family Helped Him Choose...', 'McIntyre recalled a pitch')
   must not read as new news ('Drew McIntyre pitched sword idea to Vince McMahon' -> 'Drew McIntyre Recalls Pitching ...')."""
import re
_AL = {"wwe": r"WWE|NXT|Raw|SmackDown", "aew": r"AEW|All Elite|ROH|Ring of Honor", "tna": r"TNA|Impact", "njpw": r"NJPW|New Japan",
       "aaa": r"AAA", "cmll": r"CMLL", "mlw": r"MLW", "gcw": r"GCW", "nwa": r"NWA", "stardom": r"Stardom"}
_PN = r"(WWE|NXT|AEW|ROH|TNA|Impact|NJPW|New Japan|AAA|CMLL|MLW|GCW|NWA|Stardom)"
CHOICE = re.compile(r"(?i)\b(?:chose|chooses|choosing|picked|picks|picking|selected|selects|opted for|opts for|prefers|preferred|went with|goes with)\s+"
                    r"(?:to (?:sign with|join)\s+)?" + _PN + r"\s+over\s+" + _PN)
def _key(p):
    for k, rx in _AL.items():
        if re.fullmatch(r"(?i)" + rx, p): return k
    return p.lower()
def _went(k, src):
    """The source says someone signed with / joined / chose promotion k."""
    return bool(re.search(r"(?i)\b(?:sign(?:s|ed|ing)? (?:with|for)|join(?:s|ed|ing)?|cho(?:se|ose|oses|osing)|pick(?:s|ed|ing)?|"
                          r"opt(?:s|ed|ing)? (?:for|to sign with|to join)|went (?:with|to)|said)\s+(?:the\s+)?['\"“]?(?:" + _AL.get(k, re.escape(k)) + r")\b", src or ""))
def choice_inverted(head, src):
    m = CHOICE.search(head or "")
    if not m: return False
    win, lose = _key(m.group(1)), _key(m.group(2))
    return win != lose and _went(lose, src) and not _went(win, src)
ATTR = re.compile(r"(?i)\b(?:says?|said|recalls?|recalled|reveals?|revealed|explains?|explained|discuss(?:es|ed)?|details?|detailed|reflects?|"
                  r"looks? back|looked back|opens? up|admits?|admitted|addresses|talks?|talked|shares?|shared|remembers?|recounts?|tells?|told|"
                  r"names?|comments?|weighs in|notes?|confirms?|denies|responds?|reacts?|claims?|believes?|thinks?|describes?|credits?|"
                  r"on (?:why|how|his|her|their|the)|why|how)\b")
RAW_ATTR = re.compile(r"(?i)\b(?:says?|said|recalls?|recalled|reveals?|explains?|discusses|details|reflects?|looks? back|opens? up|admits?|"
                      r"talks?|shares?|remembers?|recounts?|tells?|told)\b")
RECALL = re.compile(r"(?i)\b(?:recall(?:ed|s|ing)?|look(?:ed|ing|s) back|reflect(?:ed|s|ing)? on|remember(?:ed|s)?|reminisc\w*|"
                    r"during (?:a|an|his|her|their) (?:recent )?(?:appearance|interview|episode|podcast)|in an interview with|"
                    r"(?:on|during) (?:his|her|the) [\w' ]{0,40}podcast)\b")
_PAST = {"chose": "Choosing", "picked": "Picking", "signed": "Signing", "left": "Leaving", "joined": "Joining", "pitched": "Pitching",
         "turned down": "Turning Down", "rejected": "Rejecting", "refused": "Refusing", "quit": "Quitting", "wanted": "Wanting",
         "changed": "Changing", "dropped": "Dropping", "walked out": "Walking Out", "almost": "Almost", "nearly": "Nearly",
         "was offered": "Being Offered", "missed": "Missing", "lost": "Losing", "nixed": "Nixing", "pushed": "Pushing", "begged": "Begging",
         "convinced": "Convincing", "asked": "Asking", "told": "Telling", "had": "Having", "made": "Making", "got": "Getting", "worked": "Working"}
_PV = re.compile(r"^((?:[A-Z][\w.'’-]*\s+){0,3}[A-Z][\w.'’-]*)\s+(" + "|".join(sorted(map(re.escape, _PAST), key=len, reverse=True)) + r")\b\s*(.*)$", re.I)
_ANCHOR = re.compile(r"(?i)\b(?:in (?:19|20)\d\d|years? ago|back in|early (?:career|days)|once|originally|first|recalls?|remembers?)\b")
def past_framing(head, raw, src, is_person=lambda s: True):
    """New headline in past framing ('X Recalls Pitching ...') when the AI headline states a past career move as if new, the
    source is a recollection (attribution in the source headline or recall wording in the text), and the headline names no
    speaker attribution or time anchor. None when no change is needed."""
    head = (head or "").strip()
    if not head or ATTR.search(head) or _ANCHOR.search(head): return None
    if not (RAW_ATTR.search(raw or "") or RECALL.search(src or "")): return None
    m = _PV.match(head)
    if not m or not is_person(m.group(1)): return None
    subj, verb, rest = m.group(1), m.group(2).lower(), m.group(3)
    return f"{subj} Recalls {_PAST[verb]} {rest}".strip()
