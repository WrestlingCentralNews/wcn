"""Estimated X API pay-per-use spend ledger (X has no balance API, so we count every billable call ourselves).

Ledger: data/x_spend.json on the 'data' branch (saved with the rest of the state every run). Top-level fields first:
  remaining_usd, spent_usd, loaded_total_usd, low_balance (True at <= LOW_USD), counts {kind: n}, top_ups, events, entries.
Top-ups: add {"date": "YYYY-MM-DD", "usd": 5.00, "note": "..."} to x_topups.json in the repo (main branch); every run merges it in.
Prices are X's published pay-per-use rates (estimates; the developer console is the source of truth).
"""
import os, json, time
ROOT = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(ROOT, "data", "x_spend.json")
TOPUPS = os.path.join(ROOT, "x_topups.json")
LOW_USD = 2.00
PRICES = {"post": 0.015, "post_url": 0.20, "delete": 0.010, "read": 0.005, "media": 0.005}   # read = per post returned; media = per media request
CREDITS_START = 1792219725   # 2026-10-17 06:48:45Z: first successful post after the $5 load (06:26 was still 402 credits-depleted)
MAX_ENTRIES = 3000
def _topups():
    try: return [t for t in json.load(open(TOPUPS)).get("top_ups", []) if float(t.get("usd", 0)) > 0]
    except Exception: return [{"date": "2026-10-17", "usd": 5.00, "note": "initial load"}]
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
    return L
def _summ(L):
    tu = _topups(); loaded = round(sum(float(t["usd"]) for t in tu), 4)
    counts = dict(L["archived"].get("counts", {}))
    for e in L["entries"]: counts[e["kind"]] = counts.get(e["kind"], 0) + e.get("n", 1)
    spent = round(L["archived"].get("usd", 0.0) + sum(e["usd"] for e in L["entries"]), 4)
    rem = round(loaded - spent, 4)
    out = {"remaining_usd": rem, "spent_usd": spent, "loaded_total_usd": loaded, "low_balance": rem <= LOW_USD, "low_threshold_usd": LOW_USD,
           "counts": counts, "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "estimate_note": "estimated from our own call log; X console is the source of truth",
           "prices": PRICES, "top_ups": tu, "how_to_top_up": "add {date, usd, note} to x_topups.json on main",
           "events": L["events"][-200:], "archived": L["archived"], "entries": L["entries"]}
    if L.get("seeded_at"): out["seeded_at"] = L["seeded_at"]
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
    L = _summ(load()); print(json.dumps({k: L[k] for k in ("remaining_usd", "spent_usd", "loaded_total_usd", "low_balance", "counts", "updated")}, indent=1))
