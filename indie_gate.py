"""AI budget rule (owner, 2026-10-24; reworked 2026-10-25 for the $20 cap): Indie-only stories are the FIRST to lose the AI
rewrite and the write-up when the budget is tight (llm.pace_ok(prio=2) fails); while the budget has room they get both like
everyone else. Even when tight they keep the AI when they matter: reported by 2+ trusted outlets, a title change, a signing/contract/release, a serious
injury or a death, or an on-record quote from a big name. Everything else keeps the free rule-based headline/summary.
Stories that fell back to 'Indie' only because nothing matched still get the AI pass (it is what tags them correctly)."""
import re, json, os
import editorial
IMPORTANT = re.compile(r"(?i)\b(?:new\s+champions?|crowned|captures?|dethrone[sd]?|title\s+change|vacate[sd]?|stripped|"
    r"(?:wins?|won|winning)\s+(?:the\s+)?(?:[\w'.-]+\s+){0,5}(?:title|championship|belt)s?|"
    r"(?:re-?)?signs?|signed|signing|inks?|contract|(?:new|multi-?year)\s+deal|released|release[sd]?\s+from|departs?|exits?|"
    r"injur(?:y|ies|ed)|torn|surgery|hospitali[sz]ed|collapsed|out\s+of\s+action|sidelined|concussion|broken\s+(?:neck|back|leg|arm)|"
    r"dies|died|passed\s+away|death|dead\s+at|\bRIP\b|in\s+memoriam|killed)\b")
_INDIE_HIT = re.compile(editorial.PROMO["Indie"] + r"|\b(?:" + editorial.ROSTER["Indie"] + r")\b", re.I)
_BIG = "|".join(n for n in editorial.FIG.split("|") if n not in set(editorial.ROSTER["Indie"].split("|")))
BIG_RX = re.compile(r"\b(?:" + _BIG + r")\b", re.I)
FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "indie_important.json")

def _txt(a): return (a.get("raw_title") or "") + " " + (a.get("summary_src") or "") + " " + (a.get("body") or "")[:1500]
def indie_only(a):
    """Rule-based tags say Indie and nothing else, and an Indie promotion/wrestler is actually named (not the fallback)."""
    cats = a.get("categories") or editorial.categories(a)
    return list(cats) == ["Indie"] and bool(_INDIE_HIT.search(_txt(a)))
def important_title(t, lead=""):
    t = t or ""
    if IMPORTANT.search(t): return True
    return bool(editorial._QUOTEISH.search(t) and BIG_RX.search(t))   # 'MJF Says ...', 'Tony Khan Reveals ...'
def important(a):
    return important_title(a.get("raw_title")) or bool(IMPORTANT.search((a.get("summary_src") or "")[:400]))
def multi_trusted(c):
    srcs = {c["source"]} | {u["source"] for u in c.get("updates", [])}
    return sum(1 for s in srcs if editorial.tier(s) <= 2) >= 2

_KEEP = None
def kept():
    global _KEEP
    if _KEEP is None:
        try: _KEEP = set(json.load(open(FILE)))
        except Exception: _KEEP = set()
    return _KEEP
def _tight():
    import llm
    return not llm.pace_ok(prio=2)
def skip_rewrite(a):
    """True = no AI rewrite for this report now (Indie-only, not important, and the budget is tight for Indie/Global work)."""
    return indie_only(a) and not important(a) and a["id"] not in kept() and _tight()
def skip_long(c, lead):
    """True = no long-form write-up for this card now (same rule; longer.prio/llm.pace_ok does this per call)."""
    if list(c.get("categories") or []) != ["Indie"] or not indie_only(lead): return False
    return not (multi_trusted(c) or important(lead) or important_title(c.get("title"))) and _tight()
def remember(clusters, bylink):
    """Indie-only cards reported by 2+ trusted outlets: their reports get the AI rewrite on the next run."""
    ids = set()
    for c in clusters:
        if list(c.get("categories") or []) == ["Indie"] and multi_trusted(c):
            for l in [c["link"]] + [u["link"] for u in c.get("updates", [])]:
                if l in bylink: ids.add(bylink[l]["id"])
    try: json.dump(sorted(ids), open(FILE, "w"))
    except Exception as e: print("indie_gate: could not save", str(e)[:80], flush=True)
