"""Live X thread per show (@wrestlingWCN): one root post when the show starts, then replies IN ORDER for every confirmed match
result and a 1-2 line summary of each major segment between matches (promos, attacks, announcements).

- Shows: every weekly show in events.json (Raw, SmackDown, NXT, Dynamite, Collision, TNA iMPACT) and every PPV/PLE. Overlapping
  shows each get their own thread while the X balance allows (below SEG_MIN_USD only the /live-priority show gets segments).
- Root: "<Show> LIVE results (<date>)" + the WCN results-page URL (+ show photo/card). URL posts cost $0.20, so the link is only
  used while the estimated balance is >= ROOT_LINK_MIN_USD; otherwise the root says "link in bio" ($0.015).
- Results: live.py's 'confirmed' matches only (trusted sources, 2 sources or 1 unchallenged for 10 min). Wording = live.py templates.
- Segments: AI summary (llm.py budget, ~$0.001/call, max 1 call / SEG_EVERY_S, only when source text changed) of the trusted
  results pages live.py already found. Claim guards: the segment must be reported in >=2 AI passes >= 4 min apart or by 2 sources,
  must name people found in the source text, no URLs, and words like debut/return/title change/injury/released/retire/fired are
  only allowed when the source text itself uses them.
- Catch-up: when several items are ready at once (thread started late), they go out as at most 2 compact bullet replies.
- Pinning: the X API v2 has no pin/unpin endpoint, so the root to pin is written to data/x_pin.json (start of show -> 5:00 AM
  Puerto Rico next morning, /live priority via conflicts.choose: WWE PLE > AEW > AAA > NXT > TNA, Collision yields to PPVs).
State: data/live_thread.json (data branch) + live_thread_seed.json (main; roots posted by hand). Never fails the workflow.
"""
import os, re, json, time, glob, hashlib, datetime
import x_poster as XP, live, xspend, conflicts
ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "data", "live_thread.json")
SEED = os.path.join(ROOT, "live_thread_seed.json")
PIN = os.path.join(ROOT, "data", "x_pin.json")
SITE = "https://wrestlingcentralnews.com/"
MAX_REPLIES = 26          # per show (~1 per match/segment on a 2-3h show)
PER_RUN = 3
SEG_EVERY_S = 240
SEG_MIN_USD = 3.0         # below this, segments only for the pinned (/live-priority) show; results always
STOP_USD = 1.0            # below this, nothing but the root (alert fires at $2 via x_poster)
ROOT_LINK_MIN_USD = 5.0
POST_AFTER_END_H = 1.0
GUARD = re.compile(r"(?i)\b(debut\w*|return\w*|title change|new champion\w*|injur\w*|releas\w*|fired|retir\w*|vacat\w*|suspend\w*|arrest\w*|died|death|signs?|signed|stretcher|hospital\w*)")
def log(*a): print("[x-thread]", *a, flush=True)
def load():
    try: s = json.load(open(STATE))
    except Exception: s = {"shows": {}}
    try: seed = json.load(open(SEED)).get("shows", {})
    except Exception: seed = {}
    for k, v in seed.items():
        P = s["shows"].setdefault(k, {})
        if not P.get("root"):
            P.update({"root": v["root"], "last": P.get("last") or v["root"], "root_at": v.get("at"), "items": P.get("items", []), "seeded": True})
            if v.get("charges"):   # bill the hand-posted root once
                for kind in v["charges"]: xspend.record(kind, "POST /2/tweets" if kind.startswith("post") else "POST /2/media/upload", "live_thread", ref=v["root"], note="root (seed)")
    return s
def save(s): os.makedirs(os.path.dirname(STATE), exist_ok=True); json.dump(s, open(STATE, "w"), indent=0)
def balance():
    try: return xspend._summ(xspend.load())["remaining_usd"]
    except Exception: return 0.0
def tags(st): return " ".join(dict.fromkeys(x for x in (st.get("tag"), {"WWE": "#WWE", "AEW": "#AEW", "TNA": "#TNA"}.get(st.get("brand"))) if x))
def show_name(st): return re.sub(r"\s+\d{4}$", "", st["name"])
def page_url(key): return f"{SITE}events/{key}/"
def post(text, reply_to=None, photo=None, src="live_thread"):
    """-> tweet id or None. photo = list of (url, why) candidates (30 s budget, else text-only)."""
    if XP.x_len(text) > 280: log("too long, skipped:", text[:80]); return None
    payload_media = None
    if photo:
        media, img, why, err = XP.attach_photo(photo, src)
        if media: payload_media = [media]
        else: XP.xspend.event("media_upload_failed", src, err or "")
    import urllib.request
    url = "https://api.x.com/2/tweets"; p = {"text": text}
    if payload_media: p["media"] = {"media_ids": payload_media}
    if reply_to: p["reply"] = {"in_reply_to_tweet_id": str(reply_to)}
    req = urllib.request.Request(url, data=json.dumps(p).encode(), method="POST", headers={"Authorization": XP.oauth_header("POST", url), "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=30); body = json.load(r); tid = body["data"]["id"]
        xspend.record("post_url" if XP.has_url(text) else "post", "POST /2/tweets", src, ref=tid, note="reply" if reply_to else "root")
        log(f"posted https://x.com/wrestlingWCN/status/{tid} :: {text.splitlines()[0][:90]}"); return tid
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf8", "ignore")[:300]; log(f"post failed HTTP {e.code}: {msg}")
        if e.code in (402, 403, 429): xspend.event(f"http_{e.code}", src, msg[:200])
        if e.code in (402, 429) or re.search(r"credit|payment|CreditsDepleted", msg, re.I):
            xs = XP.load_state(); xs["paused_until"] = time.time() + (900 if e.code == 429 else 6 * 3600); xs["pause_reason"] = f"thread HTTP {e.code}: {msg[:150]}"; XP.save_state(xs)
            raise RuntimeError("paused")
        return None
    except Exception as ex: log("post error:", repr(ex)[:200]); return None
def show_photo(st):
    import vision
    out = []
    pr = vision.promo_in((st.get("name") or "") + " " + (st.get("brand") or ""))
    if pr: out.append((vision.PROMO_CARD.format(pr), "promo-logo:" + pr))
    out.append((XP.SITE_DEFAULT_IMG, "site-default")); return out
def root_text(st, link):
    d = datetime.date.fromisoformat(st["date"]); ds = d.strftime("%b ") + str(d.day)
    tail = f"Live results: {page_url(st['key'])}" if link else "Live results page: link in bio"
    return f"🔴 {show_name(st)} LIVE results ({ds})\n\nEvery match result and key segment, added to this thread as it happens.\n\n{tail}\n\n{tags(st)}"
def match_line(m):
    t = m["en"]
    if m.get("stip") and len(m["stip"]) < 60: t = f"{m['stip']}: {t}"
    return t
def match_text(st, m):
    head = f"{XP.breaking.LABEL}\nTITLE CHANGE!" if m.get("title") == "change" else "RESULT:"
    for c in (f"{head} {match_line(m)}\n\n{tags(st)}", f"{head} {m['en']}\n\n{tags(st)}", f"{head} {m['en']}"):
        if XP.x_len(c) <= 280: return c
    return None
# ------------------------------------------------------------- segments (AI, guarded)
SEG_SYS = ("You summarize live pro-wrestling TV coverage for Wrestling Central News. You get the text of trusted live-results pages. "
 "List the MAJOR NON-MATCH segments that have already happened and are fully described: promos, in-ring talks, attacks/brawls, "
 "announcements, returns, contract signings, big backstage segments. Skip matches (results are handled elsewhere), recap videos, commentary intros, "
 "short backstage filler, hype packages and anything still in progress. Rules: entirely your own words, never copy phrases; never invent "
 "facts, names or outcomes; only state what the text states; never say debut, return, title change, injury, release or retirement unless the text "
 "says exactly that; present tense; 1-2 short sentences, max 200 characters; no hashtags, no emojis, no links, no quotes longer than 4 words. "
 "Return JSON {\"segments\": [{\"key\": <2-4 main names, lowercase, comma-separated>, \"after\": <the match it came after, or 'opening'>, "
 "\"summary\": <text>, \"sources\": <how many of the given sources describe it>}]} in show order.")
def source_text(st):
    out, n = [], 0
    for url, name in list(st.get("pages", {}).items())[:3]:
        try: L = live.lines_of(live.get(url, 20))
        except Exception: continue
        i0 = next((i for i, l in enumerate(L) if re.search(r"(?i)we are live|we're live|^live! |kicks? off with|show opens|commentary", l)), 0)
        txt = "\n".join(l for l in L[i0:] if len(l) > 25)[-7000:]
        if txt: out.append(f"=== SOURCE {name} ===\n{txt}"); n += 1
    return "\n\n".join(out), n
def segments(st, P):
    import llm
    key = os.environ.get("AI_API_KEY")
    if not key or llm.budget_left() <= 0.3: return []
    now = time.time()
    if now - P.get("seg_at", 0) < SEG_EVERY_S: return []
    txt, n = source_text(st)
    if not txt: return []
    h = hashlib.sha1(txt.encode()).hexdigest()[:12]
    if h == P.get("seg_hash"): return []
    P["seg_at"], P["seg_hash"] = now, h
    llm.budget_left()
    try: out = llm._call(key, "wcn-live-seg", SEG_SYS, f"Show: {st['name']} ({st['date']})\n\n" + txt, 900, "live_seg", llm.MODEL)
    except Exception as ex: log("seg ai error:", str(ex)[:120]); return []
    finally:
        try: llm.save_usage()
        except Exception: pass
    low = txt.lower(); res = []
    for sg in (out.get("segments") or [])[:20]:
        if not isinstance(sg, dict): continue
        s = re.sub(r"\s+", " ", str(sg.get("summary") or "")).strip(); k = str(sg.get("key") or "").lower().strip()
        if not s or not k or len(s) > 230 or XP.has_url(s) or "#" in s: continue
        names = [x.strip() for x in k.split(",") if len(x.strip()) > 2]
        if not names or not all(any(part in low for part in nm.split()) for nm in names): continue      # people must be in the source text
        bad = [w for w in GUARD.findall(s) if w.lower()[:5] not in low]
        if bad: log("seg guard dropped:", s, bad); continue
        res.append({"key": ",".join(sorted(names)), "summary": s, "after": str(sg.get("after") or ""), "src": int(sg.get("sources") or 1), "n_src": n})
    return res
def seg_key_same(a, b):
    A, B = set(a.split(",")), set(b.split(","))
    return bool(A & B) and len(A & B) / min(len(A), len(B)) >= 0.5
# ------------------------------------------------------------- pin state
def pin_update(S, now):
    try: from zoneinfo import ZoneInfo; PR = ZoneInfo("America/Puerto_Rico")
    except Exception: PR = datetime.timezone(datetime.timedelta(hours=-4))
    cands = []
    for key, P in S["shows"].items():
        if not P.get("root"): continue
        st = live.load(key) or {}
        date = st.get("date") or key[:10]
        d = datetime.date.fromisoformat(date) + datetime.timedelta(days=1)
        until = int(datetime.datetime(d.year, d.month, d.day, 5, 0, tzinfo=PR).timestamp())
        start = int(P.get("root_at") or st.get("start") or 0)
        if not (start - 1800 <= now < until): continue
        cands.append({"key": key, "slug": st.get("slug") or key[11:], "name": st.get("name") or key, "brand": st.get("brand"), "kind": st.get("kind"),
                      "date": date, "last": P.get("last_at") or start, "root": P["root"], "from": start, "until": until})
    pr_date = datetime.datetime.fromtimestamp(now - 5 * 3600, PR).date().isoformat()
    c, how = conflicts.choose(cands, pr_date)
    try: old = json.load(open(PIN))
    except Exception: old = {}
    hist = old.get("history", [])
    cur = None
    if c:
        cur = {"root_id": c["root"], "url": f"https://x.com/wrestlingWCN/status/{c['root']}", "show": c["name"], "key": c["key"],
               "pin_from": datetime.datetime.fromtimestamp(c["from"], datetime.timezone.utc).isoformat(timespec="seconds"),
               "pin_until": datetime.datetime.fromtimestamp(c["until"], datetime.timezone.utc).isoformat(timespec="seconds"), "how": how,
               "others": [x["key"] for x in cands if x is not c]}
        if not hist or hist[-1].get("root_id") != cur["root_id"]: hist.append({k: cur[k] for k in ("root_id", "key", "pin_from", "pin_until")})
    out = {"note": "X API v2 has no pin/unpin endpoint: pin 'current' by hand/browser; when current is null, unpin (or leave it for the next show).",
           "current": cur, "pinned_by_hand": old.get("pinned_by_hand"), "updated": int(now), "history": hist[-50:]}
    json.dump(out, open(PIN, "w"), indent=1)
# ------------------------------------------------------------- main
def run():
    enabled = os.environ.get("X_POST_ENABLED", "0") == "1"
    have_keys = all(os.environ.get(k) for k in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"))
    now = time.time(); S = load()
    xs = XP.load_state()
    live_on = [w for w in live.windows(collect=True)]
    try: tgt_key = None; c, _ = conflicts.choose([{"key": w["key"], "slug": w["slug"], "name": w["name"], "brand": w["brand"], "kind": w["kind"], "date": w["date"], "last": 0} for w in live_on]); tgt_key = c and c["key"]
    except Exception: tgt_key = None
    sent = 0
    try:
        for w in live_on:
            key = w["key"]; st = live.load(key)
            if not st: continue
            P = S["shows"].setdefault(key, {"items": []}); P.setdefault("items", [])
            if now > st["end"] + POST_AFTER_END_H * 3600 or now < st["main"] - 300: continue
            if not (enabled and have_keys): log("DRY RUN", key); continue
            if now < xs.get("paused_until", 0): log("X paused:", xs.get("pause_reason")); break
            bal = balance()
            if not P.get("root"):
                if bal < STOP_USD / 2: log("balance too low for a root", bal); continue
                tid = post(root_text(st, bal >= ROOT_LINK_MIN_USD), photo=show_photo(st))
                if not tid: continue
                P.update(root=tid, last=tid, root_at=int(now)); sent += 1; save(S)
            if bal < STOP_USD: log("balance below stop level, no replies", bal); continue
            done = {i["ref"] for i in P["items"]}
            ready = []
            for m in st["matches"]:
                if m.get("confirmed") and not m.get("conflict") and ("m:" + m["id"]) not in done and not any(
                        i.get("kind") == "match" and live.same(m, i.get("fact", {})) for i in P["items"]):
                    if m["first_seen"] >= (P.get("root_at") or 0) - 3 * 3600: ready.append(("match", "m:" + m["id"], m))
            if bal >= SEG_MIN_USD or key == tgt_key:
                for sg in segments(st, P):
                    if any(i.get("kind") == "seg" and seg_key_same(i["key"], sg["key"]) for i in P["items"]): continue
                    cand = P.setdefault("seg_cand", {})
                    ck = next((k for k in cand if seg_key_same(k, sg["key"])), sg["key"])
                    c0 = cand.setdefault(ck, {"first": now, "seen": 0}); c0["seen"] += 1; c0["s"] = sg["summary"]
                    if (sg["src"] >= 2 and sg["n_src"] >= 2) or (c0["seen"] >= 2 and now - c0["first"] >= 240):
                        ready.append(("seg", "s:" + sg["key"], sg))
            if not ready: continue
            if len(P["items"]) >= MAX_REPLIES: log("reply cap reached", key); continue
            order = lambda r: r[2].get("first_seen", now) if r[0] == "match" else now
            ready.sort(key=order)
            def line(r): return match_line(r[2]) if r[0] == "match" else r[2]["summary"]
            groups = []
            if len(ready) > 2 and len(P["items"]) == 0 or len(ready) > 3:     # backlog -> up to 2 compact catch-up replies
                for _ in range(2):
                    head = f"Catch-up from {show_name(st)}:\n"; body, used = [], []
                    for r in ready:
                        if r in sum((g[1] for g in groups), []): continue
                        if XP.x_len(head + "\n".join(body + ["• " + line(r)]) + f"\n\n{tags(st)}") > 280: break
                        body.append("• " + line(r)); used.append(r)
                    if used: groups.append((head + "\n".join(body) + f"\n\n{tags(st)}", used))
            else:
                for r in ready:
                    t = match_text(st, r[2]) if r[0] == "match" else f"{r[2]['summary']}\n\n{tags(st)}"
                    if t: groups.append((t, [r]))
            for text, used in groups:
                if sent >= PER_RUN: break
                ph = None
                if used[0][0] == "match":
                    try: import live_x; ph = live_x.photo_candidates(st, used[0][2])
                    except Exception: ph = show_photo(st)
                else: ph = show_photo(st)
                tid = post(text, reply_to=P["last"], photo=ph)
                if not tid: continue
                sent += 1; P["last"] = tid; P["last_at"] = int(now)
                for kind, ref, obj in used:
                    it = {"kind": kind, "ref": ref, "tweet": tid, "at": int(now)}
                    if kind == "match": it["fact"] = {"winner": obj["winner"], "loser": obj.get("loser", "")}
                    else: it["key"] = obj["key"]
                    P["items"].append(it)
                save(S)
    except RuntimeError: pass
    pin_update(S, now); save(S)
def has_thread(key):
    try: return bool(json.load(open(STATE))["shows"].get(key, {}).get("root"))
    except Exception: pass
    try: return key in json.load(open(SEED)).get("shows", {})
    except Exception: return False
if __name__ == "__main__":
    try: run()
    except Exception as ex: log("error (ignored):", repr(ex)[:300])
