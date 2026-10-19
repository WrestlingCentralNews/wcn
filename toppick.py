"""Homepage 'Top stories' block (owner OK 2026-10-19): one large lead story + 4 secondary top stories above the feed.
importance() is written to news.json as c['imp'] (and c['brk'] for BREAKING-level stories, breaking.py rules), so app.js can
pick the block per WWE/AEW/TNA/Indie/Global filter selection. pick() is mirrored in public/app.js (topPick) and is used here
for the server-rendered Spanish home so the first paint matches what app.js renders."""
import re, time, breaking
# same weights as x_poster.score (what we'd post to X first), plus a BREAKING bonus
CAT_BONUS = {"WWE": 4, "AEW": 4, "TNA": 2, "Global": 1, "Indie": 0}
KIND_BONUS = {"news": 3, "match": 3, "quote": 1, "results": 1}
MAJOR = re.compile(r"\b(champion\w*|title|injur\w*|sign\w*|releas\w*|died|dies|death|passe[sd] away|return\w*|debut\w*|retire\w*|suspend\w*|arrest\w*|leav\w*|departs?|contract|surgery|hall of fame|wrestlemania|all in|bound for glory)\b", re.I)
BRK_BONUS = 12
FRESH_H = 24         # candidates: latest activity within 24h (falls back to the newest stories when fewer than N)
DECAY = 0.75         # points lost per hour since the latest activity
OLD = 0.15           # ... plus per hour the story has been running (a 3-day-old live-results thread shouldn't lead forever)
N = 5                # 1 lead + 4 secondary
def _i(v, d=0):
    try: return int(v)
    except Exception: return d
def importance(c):
    k = (c.get("kind") or {}).get("type", "news"); src, tr = _i(c.get("sources"), 1), _i(c.get("trusted"))
    s = 2 * min(src, 8) + 2 * min(tr, 4) + max([CAT_BONUS.get(x, 0) for x in c.get("categories") or []] or [0])
    s += KIND_BONUS.get(k, 1) + (1 if c.get("image") else 0) + (3 if MAJOR.search(c.get("title") or "") else 0)
    if tr == 0: s -= 6
    if "Indie" in (c.get("categories") or []) and src < 3: s -= 4
    try: b = breaking.kind(c.get("title") or "", k, c.get("raw_title") or "")
    except Exception: b = None
    if b and tr >= 1: s += BRK_BONUS
    else: b = None
    return s, b
def annotate(clusters):
    for c in clusters:
        c["imp"], b = importance(c)
        if b: c["brk"] = b
        else: c.pop("brk", None)
def value(c, now):
    ts = _i(c.get("ts")); f = _i(c.get("first_ts"), ts)
    return _i(c.get("imp")) - DECAY * max(0, now - ts) / 3600 - OLD * max(0, ts - f) / 3600
def pick(items, now=None):
    """items: newest-first list (already filtered). -> (lead, [secondary...]) or (None, [])."""
    now = now or time.time()
    if len(items) < N + 3: return None, []
    pool = [c for c in items if now - _i(c.get("ts")) < FRESH_H * 3600]
    if len(pool) < N: pool = items[:40]
    ranked = sorted(pool, key=lambda c: value(c, now), reverse=True)
    quote = lambda c: (c.get("kind") or {}).get("type") == "quote"
    lead = next((c for c in ranked if c.get("image") and not quote(c)), ranked[0])
    rest = [c for c in ranked if c is not lead]
    sec = [c for c in rest if c.get("image")][:N - 1]
    sec += [c for c in rest if c not in sec][:N - 1 - len(sec)]
    sec.sort(key=lambda c: rest.index(c))
    return lead, sec
