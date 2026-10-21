"""Estimated X API pay-per-use spend ledger (X has no balance API, so we count every billable call ourselves).

Ledger: data/x_spend.json on the 'data' branch (saved with the rest of the state every run). Top-level fields first:
  remaining_usd, spent_usd, loaded_total_usd, low_balance (True at <= LOW_USD), counts {kind: n}, top_ups, events, entries.
Top-ups: add {"date": "YYYY-MM-DD", "usd": 5.00, "note": "..."} to x_topups.json in the repo (main branch); every run merges it in.
Rebase: x_topups.json "rebase" {at, total_usd, paid_usd, free_usd} pins the real console balance at a moment; from then on
remaining = total_usd + later top-ups - estimated spend logged after 'at' (free credits are drawn first).
Prices are X's published pay-per-use rates (estimates; the developer console is the source of truth).
"""
import os, json, time
ROOT = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(ROOT, "data", "x_spend.json")
TOPUPS = os.path.join(ROOT, "x_topups.json")
MANUAL = os.path.join(ROOT, "x_manual.json")   # owner-approved actions done by hand (e.g. a tweet deletion): charges merged once by id
LOW_USD = 2.00
PRICES = {"post": 0.015, "post_url": 0.20, "delete": 0.010, "read": 0.005, "media": 0.005}   # read = per post returned; media = per media request
# Live results thread estimates (live_thread.py): root + photo, then ~1 reply + photo per match/segment (~13 on a weekly show).
# Since 2026-10-21 only PLE/PPV roots carry the site URL; weekly-show roots and all weekly replies are link-free.
THREAD_EST = {"weekly_root_usd": round(PRICES["post"] + PRICES["media"], 3), "ppv_root_usd": round(PRICES["post_url"] + PRICES["media"], 3),
              "reply_usd": round(PRICES["post"] + PRICES["media"], 3), "weekly_thread_13_replies_usd": round(14 * (PRICES["post"] + PRICES["media"]), 3),
              "ppv_thread_13_replies_usd": round(PRICES["post_url"] + 14 * PRICES["media"] + 13 * PRICES["post"], 3),
              "note": "weekly shows: no link in root or replies (saves ~$0.185 per weekly show vs a linked root); PLE/PPV roots keep the link"}
CREDITS_START = 1792219725   # 2026-10-17 06:48:45Z: first successful post after the $5 load (06:26 was still 402 credits-depleted)
MAX_ENTRIES = 3000
def _topups():
    try: return [t for t in json.load(open(TOPUPS)).get("top_ups", []) if float(t.get("usd", 0)) > 0]
    except Exception: return [{"date": "2026-10-17", "usd": 5.00, "note": "initial load"}]
def _rebase():
    """Console recalibration (x_topups.json 'rebase'): the real balance at a point in time, paid and free credits separately."""
    try: r = json.load(open(TOPUPS)).get("rebase")
    except Exception: r = None
    return r if r and r.get("at") and r.get("total_usd") is not None else None
def _seed():
    """Historical tally from the post logs (only successful calls since credits started)."""
    E = []
    try: px = json.load(open(os.path.join(ROOT, "data", "posted_x.json")))
    except Exception: px = {}
    for cid, p in (px.get("posted") or {}).items():
        if p.get("at", 0) >= CREDITS_START:
            E.append({"at": p["at"], "kind": "post", "usd": PRICES["post"], "endpoint": "POST /2/tweets", "src": "x_poster", "ref": p.get("tweet"), "seed": True})
    try: pl = json.load(open(os.path.join(ROOT, "data", "posted_live_x.json")))
    except Exception: pl = {}
    for e in pl.get("log", []):
        if e.get("ok") and e.get("at", 0) >= CREDITS_START:
            E.append({"at": e["at"], "kind": "post", "usd": PRICES["post"], "endpoint": "POST /2/tweets", "src": "live_x", "ref": e.get("tweet"), "seed": True})
    E.sort(key=lambda e: e["at"])
    return {"entries": E, "events": [{"at": 1792218369, "type": "credits_depleted", "src": "x_poster", "note": "HTTP 402 before the $5 load (seeded)"}],
            "archived": {"usd": 0.0, "counts": {}}, "seeded_at": int(time.time())}
def load():
    try: L = json.load(open(LEDGER))
    except Exception: L = _seed()
    L.setdefault("entries", []); L.setdefault("events", []); L.setdefault("archived", {"usd": 0.0, "counts": {}})
    try: manual = json.load(open(MANUAL)).get("charges", [])
    except Exception: manual = []
    have = set(L.get("manual_ids", [])) | {e.get("manual_id") for e in L["entries"] if e.get("manual_id")}
    for m in manual:
        if m.get("id") and m["id"] not in have and float(m.get("usd", 0)) > 0:
            L["entries"].append({"at": int(m.get("at") or time.time()), "kind": m.get("kind", "manual"), "usd": round(float(m["usd"]), 4),
                                 "endpoint": m.get("endpoint", ""), "src": m.get("src", "manual"), "ref": m.get("ref"), "note": m.get("note"), "manual_id": m["id"]})
            L.setdefault("manual_ids", []).append(m["id"])
    return L
def _summ(L):
    tu = _topups(); loaded = round(sum(float(t["usd"]) for t in tu), 4)
    counts = dict(L["archived"].get("counts", {}))
    for e in L["entries"]: counts[e["kind"]] = counts.get(e["kind"], 0) + e.get("n", 1)
    spent = round(L["archived"].get("usd", 0.0) + sum(e["usd"] for e in L["entries"]), 4)
    rem = round(loaded - spent, 4)
    rb = _rebase(); extra = {}
    if rb:   # balance = console figure at rebase time + later top-ups - estimated spend logged after it (free credits first)
        since = round(sum(e["usd"] for e in L["entries"] if e["at"] > rb["at"]), 4)
        later = round(sum(float(t["usd"]) for t in tu if float(t.get("at") or 0) > rb["at"]), 4)
        free0, paid0 = float(rb.get("free_usd") or 0), float(rb.get("paid_usd") or 0)
        free_rem = round(max(0.0, free0 - since), 4); paid_rem = round(paid0 + later - max(0.0, since - free0), 4)
        rem = round(float(rb["total_usd"]) + later - since, 4); loaded = round(float(rb["total_usd"]) + later, 4)
        extra = {"rebased": {k: rb.get(k) for k in ("time", "at", "total_usd", "paid_usd", "free_usd", "note")},
                 "spent_since_rebase_usd": since, "free_remaining_usd": free_rem, "paid_remaining_usd": paid_rem,
                 "spent_before_rebase_estimate_usd": round(spent - since, 4)}
    out = {"remaining_usd": rem, "spent_usd": spent, "loaded_total_usd": loaded, "low_balance": rem <= LOW_USD, "low_threshold_usd": LOW_USD, **extra,
           "counts": counts, "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "estimate_note": "estimated from our own call log; X console is the source of truth",
           "prices": PRICES, "thread_estimates": THREAD_EST, "top_ups": tu, "how_to_top_up": "add {date, usd, note} to x_topups.json on main",
           "events": L["events"][-200:], "archived": L["archived"], "entries": L["entries"]}
    if L.get("seeded_at"): out["seeded_at"] = L["seeded_at"]
    if L.get("manual_ids"): out["manual_ids"] = L["manual_ids"]   # survives entries being folded into 'archived'

    return out
def save(L):
    if len(L["entries"]) > MAX_ENTRIES:   # fold the oldest entries into the archived totals so the file stays small
        old, L["entries"] = L["entries"][:-MAX_ENTRIES], L["entries"][-MAX_ENTRIES:]
        a = L["archived"]; a["usd"] = round(a.get("usd", 0.0) + sum(e["usd"] for e in old), 4)
        for e in old: a.setdefault("counts", {})[e["kind"]] = a["counts"].get(e["kind"], 0) + e.get("n", 1)
    S = _summ(L); os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    tmp = LEDGER + ".tmp"; json.dump(S, open(tmp, "w"), indent=1); os.replace(tmp, LEDGER)
    return S
def record(kind, endpoint, src, n=1, ref=None, note=None, ok=True):
    """Log one billable call (kind in PRICES; n = number of units, e.g. posts returned by a read). Never raises."""
    try:
        L = load(); usd = round(PRICES.get(kind, 0) * n, 4) if ok else 0.0
        e = {"at": int(time.time()), "kind": kind, "usd": usd, "endpoint": endpoint, "src": src}
        if n != 1: e["n"] = n
        if ref: e["ref"] = ref
        if note: e["note"] = note
        L["entries"].append(e); S = save(L)
        print(f"[x-spend] {kind} {endpoint} ${usd:.3f} -> spent ${S['spent_usd']:.3f}, remaining ${S['remaining_usd']:.3f}" + (" (LOW: refill)" if S["low_balance"] else ""), flush=True)
    except Exception as ex: print("[x-spend] ledger error (ignored):", repr(ex)[:200], flush=True)
def event(typ, src, note=""):
    """Non-billable events: credits_depleted (HTTP 402), payment errors, rate limits, media failures."""
    try:
        L = load(); L["events"].append({"at": int(time.time()), "type": typ, "src": src, "note": note[:300]}); S = save(L)
        print(f"[x-spend] event {typ}: estimated remaining ${S['remaining_usd']:.3f}", flush=True)
    except Exception as ex: print("[x-spend] ledger error (ignored):", repr(ex)[:200], flush=True)
def ensure():
    """Create/refresh the ledger (seeded from history on first run) even when nothing is posted."""
    try: save(load())
    except Exception as ex: print("[x-spend] ledger error (ignored):", repr(ex)[:200], flush=True)
if __name__ == "__main__":
    L = _summ(load()); print(json.dumps({k: L.get(k) for k in ("remaining_usd", "free_remaining_usd", "paid_remaining_usd", "spent_since_rebase_usd", "spent_usd", "loaded_total_usd", "low_balance", "counts", "updated")}, indent=1))
