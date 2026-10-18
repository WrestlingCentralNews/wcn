"""/live/ show priority + conflict detector.

Priority when 2+ shows are eligible for /live at once (each eligible from its first confirmed result until 5:00 AM
Puerto Rico the next morning): 1 WWE PPV/PLE, 2 AEW (PPVs + weekly), 3 AAA, 4 NXT (weekly + PLEs), 5 TNA (weekly + PPVs).
Anything else (Raw/SmackDown vs anything, NJPW/ROH/CMLL/indies, two shows of the same rank) is UNRESOLVED: the owner
decides via live_overrides.json ({"<PR date YYYY-MM-DD>": "<event key or slug>"}, always wins); until then the show
with the most recent confirmed result is the temporary default.

Run:  python3 conflicts.py [days]   -> JSON list of upcoming same-night conflicts (default next 7 days) on stdout.
Each build also writes data/live_conflicts.json (aggregator.py).
"""
import os, re, sys, json, datetime
ROOT = os.path.dirname(os.path.abspath(__file__))
OVERRIDES = os.path.join(ROOT, "live_overrides.json")
OUT = os.path.join(ROOT, "data", "live_conflicts.json")
RANK_NAMES = {1: "WWE PPV/PLE", 2: "AEW", 3: "AAA", 4: "NXT", 5: "TNA"}
def rank(s):
    """s: show dict with slug/name/brand/kind (live.shows_on or a live state). -> 1..5 or None (unranked)."""
    slug, name, brand, kind = (s.get("slug") or "").lower(), s.get("name") or "", s.get("brand") or "", s.get("kind") or ""
    if slug.startswith("wwe-nxt") or re.search(r"\bNXT\b", name): return 4
    if brand == "WWE" and kind == "ppv": return 1
    if brand == "AEW" or slug.startswith("aew-"): return 2
    if slug.startswith("aaa") or re.match(r"(?i)AAA\b|Lucha Libre AAA", name): return 3
    if brand == "TNA" or slug.startswith("tna-"): return 5
    return None
def overrides():
    try: return {k: v for k, v in json.load(open(OVERRIDES)).items() if not k.startswith("_")}
    except Exception: return {}
def _match(s, v): return bool(v) and (s.get("key") == v or s.get("slug") == v or (s.get("key") or "").endswith("-" + v))
def priority_resolves(shows):
    """True when every show is ranked and the best rank is unique."""
    rs = [rank(s) for s in shows]
    if len(shows) < 2: return True
    if any(r is None for r in rs): return False
    return sorted(rs).count(min(rs)) == 1 and sorted(rs)[0] < sorted(rs)[1]
def choose(cands, pr_date=None, ovr=None):
    """cands: eligible shows, each with key/slug/name/brand/kind and 'last' (latest confirmed result ts).
    -> (show, how): how = only | override | priority | unresolved-default."""
    if not cands: return None, None
    if len(cands) == 1: return cands[0], "only"
    ovr = overrides() if ovr is None else ovr
    for d in ([pr_date] if pr_date else []) + sorted({c.get("date") for c in cands if c.get("date")}):
        v = ovr.get(d)
        hit = next((c for c in cands if _match(c, v)), None)
        if hit: return hit, "override"
    if priority_resolves(cands): return min(cands, key=lambda c: rank(c)), "priority"
    return max(cands, key=lambda c: c.get("last", 0)), "unresolved-default"
def upcoming(days=7, now=None):
    import live
    PR = datetime.timezone(datetime.timedelta(hours=-4))   # America/Puerto_Rico: AST all year
    now = now or datetime.datetime.now(PR); ovr = overrides(); out = []
    for i in range(days + 1):
        day = now.astimezone(live.ET).date() + datetime.timedelta(days=i)
        shows = live.shows_on(day)
        if len(shows) < 2: continue
        d = day.isoformat(); v = ovr.get(d)
        ok = priority_resolves(shows)
        win = min(shows, key=rank) if ok else None
        oh = next((s for s in shows if _match(s, v)), None)
        is_ppv = lambda s, b: s["kind"] == "ppv" and rank(s) == ({"WWE": 1, "AEW": 2}[b])
        out.append({"date": d, "shows": [{"key": s["key"], "name": s["name"], "kind": s["kind"], "rank": rank(s), "rank_name": RANK_NAMES.get(rank(s), "unranked"),
                                          "start_utc": s["start"].astimezone(datetime.timezone.utc).isoformat(timespec="minutes"),
                                          "started": now >= s["start"]} for s in sorted(shows, key=lambda s: s["start"])],
                    "resolved_by_priority": ok, "priority_pick": win["key"] if win else None,
                    "override": oh["key"] if oh else (v or None), "override_valid": bool(oh) if v else None,
                    "needs_owner_decision": not ok and not oh,
                    "any_started": any(now >= s["start"] for s in shows),
                    "both_ppv_wwe_aew": any(is_ppv(s, "WWE") for s in shows) and any(is_ppv(s, "AEW") for s in shows)})
    return out
def write(days=7):
    try:
        r = {"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "days": days, "conflicts": upcoming(days)}
        os.makedirs(os.path.dirname(OUT), exist_ok=True); json.dump(r, open(OUT, "w"), indent=1, ensure_ascii=False); return r
    except Exception as ex: print("live_conflicts: error (ignored)", repr(ex)[:200], flush=True)
if __name__ == "__main__":
    print(json.dumps(upcoming(int(sys.argv[1]) if len(sys.argv) > 1 else 7), indent=1, ensure_ascii=False))
