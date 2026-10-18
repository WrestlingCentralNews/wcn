"""Post confirmed live match results to X (@wrestlingWCN), one post per match, link-free.

- Separate budget from x_poster.py's 10/day story posts: at most CAP_PER_SHOW result posts per show.
- Title matches (changes or retentions) always get their own post; other matches get their own post until
  PRIORITY_RESERVE slots remain, then they are combined into ONE "Also on <show>" post when the window ends.
- Only 'confirmed' results (2 trusted sources, or 1 source unchallenged for 10+ min, no conflicting report).
- NO URLs ever (X bills $0.20 per post with a URL vs $0.015 without): text is checked with x_poster.has_url.
- Same switch as story posts (X_POST_ENABLED=1) and honours x_poster's credit/rate-limit pause.
State: data/posted_live_x.json (data branch). Never fails the workflow.
"""
import os, sys, json, time, glob, re
import x_poster as XP, live
ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "data", "posted_live_x.json")
CAP_PER_SHOW = 12
PRIORITY_RESERVE = 3      # slots kept for title matches / main event
PER_RUN = 4
MAX_AGE_H = 3             # never post a result first seen more than this long ago
POST_WINDOW_H = 6         # stop posting this long after the show starts... plus the combined wrap-up
OUTRO = "Full results: link in bio"
def log(*a): print("[x-live]", *a, flush=True)
def load():
    try: return json.load(open(STATE))
    except Exception: return {"shows": {}, "log": []}
def save(s):
    s["log"] = s["log"][-300:]; os.makedirs(os.path.dirname(STATE), exist_ok=True); json.dump(s, open(STATE, "w"), indent=0)
def brand_tag(st): return {"WWE": "#WWE", "AEW": "#AEW", "TNA": "#TNA"}.get(st.get("brand"), "")
def show_name(st): return re.sub(r"\s+\d{4}$", "", st["name"])
def fits(t): return XP.x_len(t) <= 280 and not XP.has_url(t)
def match_text(st, m):
    tags = " ".join(x for x in dict.fromkeys([st.get("tag"), brand_tag(st)]) if x)
    if m.get("title") == "change": head = f"🏆 TITLE CHANGE at {show_name(st)}!"
    else: head = f"{show_name(st)} result:"
    line = m["en"]
    if m.get("stip") and len(m["stip"]) < 70: line = f"{m['stip']}: {line}"
    for cand in (f"{head}\n\n{line}\n\n{tags}\n{OUTRO}", f"{head}\n\n{m['en']}\n\n{tags}\n{OUTRO}", f"{head}\n\n{m['en']}\n\n{st.get('tag','')}"):
        if fits(cand): return cand
    return None
def combo_text(st, ms):
    tags = " ".join(x for x in dict.fromkeys([st.get("tag"), brand_tag(st)]) if x)
    lines = []
    for m in ms:
        cand = lines + ["• " + m["en"].rstrip(".")]
        if not fits(f"More from {show_name(st)}:\n" + "\n".join(cand) + f"\n\n{tags}\n{OUTRO}"): break
        lines = cand
    if not lines: return None, []
    return f"More from {show_name(st)}:\n" + "\n".join(lines) + f"\n\n{tags}\n{OUTRO}", ms[:len(lines)]
def run():
    enabled = os.environ.get("X_POST_ENABLED", "0") == "1"
    have_keys = all(os.environ.get(k) for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"))
    xs = XP.load_state(); now = time.time()
    if enabled and now < xs.get("paused_until", 0): log("X posting paused:", xs.get("pause_reason")); return
    S = load(); sent = 0
    for f in sorted(glob.glob(os.path.join(live.LIVE_DIR, "*.json"))):
        st = json.load(open(f))
        if not (st["start"] <= now <= st["start"] + POST_WINDOW_H * 3600): continue
        P = S["shows"].setdefault(st["key"], {"posted": {}, "combined": [], "n": 0})
        if "facts" not in P:   # backfill from already-posted ids
            P["facts"] = [{"winner": m["winner"], "loser": m.get("loser", "")} for m in st["matches"] if P["posted"].get(m["id"]) not in (None, "skipped", "dup")]
        ready = [m for m in st["matches"] if m.get("confirmed") and not m.get("conflict") and m["id"] not in P["posted"] and m["id"] not in P["combined"]
                 and now - m["first_seen"] < MAX_AGE_H * 3600]
        P.setdefault("facts", [])
        dup = [m for m in ready if any(live.same(m, f) for f in P["facts"])]
        for m in dup: P["posted"][m["id"]] = "dup"; log("skip duplicate of an already-posted result:", m["en"])
        ready = [m for m in ready if m not in dup]
        jobs = []
        for m in ready:
            left = CAP_PER_SHOW - P["n"] - len(jobs)
            if left <= 0: break
            prio = bool(m.get("title"))
            if prio or left > PRIORITY_RESERVE + (1 if now <= st["end"] else 0): jobs.append(("one", [m]))
        held = [m for m in ready if not any(m in j[1] for j in jobs)]
        if held and now > st["end"] and CAP_PER_SHOW - P["n"] - len(jobs) > 0 and not P.get("combo_done"):
            jobs.append(("combo", held))
        for kind, ms in jobs:
            if sent >= PER_RUN: break
            if kind == "one": text = match_text(st, ms[0]); used = ms
            else: text, used = combo_text(st, ms)
            if not text or XP.has_url(text):
                log("skipped (too long / URL-like):", ms[0]["en"]); P["posted"].update({m["id"]: "skipped" for m in ms}); continue
            if not enabled or not have_keys:
                log(f"DRY RUN (enabled={enabled}, keys={have_keys}):", text.replace("\n", " ⏎ ")); continue
            code, body, hdr = XP.post_tweet(text)
            if code in (200, 201):
                tid = body["data"]["id"]; sent += 1; P["n"] += 1
                XP.xspend.record("post_url" if XP.has_url(text) else "post", "POST /2/tweets", "live_x", ref=tid, note=kind)
                for m in used:
                    P["posted"][m["id"]] = tid; P["facts"].append({"winner": m["winner"], "loser": m.get("loser", "")})
                if kind == "combo": P["combo_done"] = True
                S["log"].append({"key": st["key"], "ids": [m["id"] for m in used], "tweet": tid, "at": int(now), "ok": True})
                log(f"posted https://x.com/wrestlingWCN/status/{tid} :: {text.splitlines()[0]} {used[0]['en']}")
            else:
                msg = json.dumps(body)[:300] if not isinstance(body, str) else body[:300]
                S["log"].append({"key": st["key"], "at": int(now), "ok": False, "code": code, "err": msg}); log(f"post failed HTTP {code}: {msg}")
                if code == 402 or re.search(r"credits.depleted|CreditsDepleted", msg, re.I): XP.xspend.event("credits_depleted", "live_x", f"HTTP {code}: {msg[:200]}")
                elif code in (403, 429): XP.xspend.event(f"http_{code}", "live_x", msg[:200])
                if code in (402, 403, 429) or re.search(r"credit|payment|CreditsDepleted", msg, re.I):
                    xs["paused_until"] = now + (900 if code == 429 else 6 * 3600); xs["pause_reason"] = f"live HTTP {code}: {msg[:150]}"; XP.save_state(xs)
                save(S); return
    save(S)
if __name__ == "__main__":
    try: run()
    except Exception as ex: log("error (ignored):", repr(ex)[:300])
