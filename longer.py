"""Longer write-ups (owner 2026-10-25, AdSense 'low value content'; AI cap raised to $20/month).
Every story whose own text is under TARGET_WORDS gets one longer write-up built from ALL its trusted reports about the same
story (llm.longform2): original wording, facts from the reports only, never padded -- if the reports are thin it stays short.
New stories go first, then the live back-catalogue newest first; every call is paced by llm.pace_ok(prio) (monthly pace line +
DAILY_MAX_USD per UTC day), so the back-fill spreads over days. Throttle order: see llm.PRIO_HEADROOM (Indie/Global cut first,
WWE/AEW/TNA and huge news last). The write-up is kept only if it is clearly longer than what the story had; the result (or a
'tried' mark) is cached on the lead article (llm_long / llm_long2) so nothing is paid for twice. Stories that pass
pages.THIN_WORDS lose their noindex automatically (pages.thin is a pure function of the story text)."""
import re, time, hashlib
from concurrent.futures import ThreadPoolExecutor
import llm, editorial, enrich, indie_gate
TARGET_WORDS = 250       # stories below this many words of own text are eligible
MIN_GAIN = 25            # keep the new write-up only if it adds at least this many words
MAX_PER_RUN = 30         # calls per 15-min run at most (the daily $ cap is the real limiter)
NEW_S = 48 * 3600        # 'new' = first published within 48h (back-fill otherwise)
BIG = {"WWE", "AEW", "TNA"}

def words(paras): return sum(len((p or "").split()) for p in paras or [])
def huge(c, lead):
    """Huge news anywhere: title change, death, major signing/release/injury, big-name quote, or 2+ trusted outlets."""
    return bool(indie_gate.multi_trusted(c) or indie_gate.important_title(c.get("title")) or (lead and indie_gate.important(lead)))
def prio(c, lead=None, now=None):
    """0 WWE/AEW/TNA new or huge news, 1 WWE/AEW/TNA back-fill, 2 Indie/Global new, 3 Indie/Global back-fill."""
    now = now or time.time()
    new = now - (c.get("first_ts") or c.get("ts") or now) < NEW_S
    if huge(c, lead): return 0 if new else 1
    big = bool(set(c.get("categories") or []) & BIG) or not c.get("categories")
    return (0 if new else 1) if big else (2 if new else 3)
def reports(c, lead, bylink):
    """Source texts for the write-up: the lead report, then other trusted (tier 1-2) reports about the same people/promotion."""
    txt = lambda a: (a.get("body") or a.get("summary_src") or "")
    out = [txt(lead)]
    for u in c.get("updates", []):
        m = bylink.get(u.get("link"))
        if not m or m is lead or editorial.tier(m.get("source")) > 2: continue
        if not enrich.same_story(m, lead) or enrich.long_mismatch(lead, [m.get("raw_title") or ""]): continue
        if len(txt(m)) >= 150: out.append(txt(m))
        if len(out) >= 4: break
    return out
def sig(rs): return hashlib.md5("|".join(r[:200] for r in rs).encode()).hexdigest()[:10]
def own(c, lead):
    """Words of own text the story has now (write-up or summary + quote + timeline lines), as pages.own_words counts it."""
    import pages
    return pages.own_words({**c, "long": lead.get("llm_long")})
def plan(clusters, bylink, now=None):
    now = now or time.time(); out = []
    for c in clusters:
        m = bylink.get(c.get("link"))
        if not m or not m.get("llm") or c.get("card"): continue
        w = own(c, m)
        if w >= TARGET_WORDS: continue
        rs = reports(c, m, bylink); t = m.get("llm_long2") or {}
        if t.get("sig") == sig(rs) or t.get("n", 0) >= 2: continue      # tried with these same reports (or twice): keep as is
        if t and now - (c.get("first_ts") or c.get("ts") or now) > 3 * 86400: continue   # retry with new reports only while fresh
        out.append((prio(c, m, now), -(c.get("first_ts") or c.get("ts") or 0), c, m, rs, w))
    out.sort(key=lambda x: (x[0], x[1]))
    return out
def run(clusters, bylink, now=None):
    now = now or time.time()
    todo = plan(clusters, bylink, now); n = len(todo)
    if not todo or not llm.pace_ok(prio=todo[0][0]): return {"eligible": n, "done": 0, "kept": 0}
    todo = todo[:MAX_PER_RUN]; kept = done = 0
    def job(x):
        p, _, c, m, rs, w = x
        if not llm.pace_ok(prio=p): return x, "skip"
        paras = llm.longform2(c["title"], rs, prio=p)
        if not paras and not m.get("llm_long"):     # nothing usable from the multi-report pass: the classic short write-up
            short = llm.longform(m, c["title"], prio=p)
            if short: m["llm_long"] = short
        return x, paras
    with ThreadPoolExecutor(4) as ex:
        for (p, _, c, m, rs, w), paras in ex.map(job, todo):
            if paras == "skip": continue
            done += 1; t = m.get("llm_long2") or {}
            rec = {"sig": sig(rs), "n": t.get("n", 0) + 1, "at": int(now), "w0": w, "prio": p}
            if paras and not enrich.long_mismatch(m, paras) and words(paras) >= words(m.get("llm_long") or []) + MIN_GAIN \
                    and own({**c}, {**m, "llm_long": paras}) >= w + MIN_GAIN:
                m["llm_long"] = paras; m.pop("llm_long_from", None); rec["w1"] = own(c, m); kept += 1
            m["llm_long2"] = rec
    return {"eligible": n, "done": done, "kept": kept}
