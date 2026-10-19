#!/usr/bin/env python3
"""Always-on 2-minute source poller for GitHub Actions (.github/workflows/poller.yml).
Same detection + dispatch rules as the box watcher: it imports watcher/wcn_watch.py and runs its poll() / maybe_dispatch()
/ track() unchanged (conditional GETs on aggregator.FEEDS + pagesrc.LISTINGS, trusted tier 1-2 only, editorial verdict,
"covered by a run created after the item was seen", never while an update.yml run is queued, shared cap 20 workflow_dispatch
runs of update.yml per rolling hour + 60 s gap, counted from the GitHub API so the box watcher and this poller share it).
Runs for --minutes (default 330 = 5h30m, under the 6 h job limit) and then exits; the workflow saves the state
(~/.wcn/watcher.json) to the Actions cache and dispatches the next poller run.
Log goes to stdout (the job log): a HEARTBEAT line every cycle. Status: ~/.wcn/poller-status.json, force-pushed
every STATUS_EVERY_S to the orphan branch `poller-status` (one commit, never grows).
--simulate-new N: on cycle N inject one synthetic trusted item (test only; goes through the normal dispatch rules).
No secrets are read or printed: gh uses GH_TOKEN from the environment (the job's GITHUB_TOKEN)."""
import os, sys, time, json, argparse, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
os.environ.setdefault("WCN_REPO", ROOT)
sys.path.insert(0, HERE)
import wcn_watch as W
STATUS = os.path.join(W.HOME, "poller-status.json")
STATUS_EVERY_S = 600
_last = {}
_orig_log = W.log
def log(*a):
    line = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + " " + " ".join(str(x) for x in a)
    print(line, flush=True)
    s = " ".join(str(x) for x in a)
    if s.startswith("poll:"): _last["poll"] = s
    if s.startswith("DISPATCHED") or "covered by run" in s: _last["dispatch"] = line
    try: _orig_log(*a)
    except Exception: pass
W.log = log
W.git_pull = lambda S: None     # the job checks out the current main at start; each run is <6 h
def push_status(st):
    """one orphan commit on branch poller-status (force-pushed; token never printed)"""
    tok, repo = os.environ.get("GH_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not tok or not repo: return
    d = "/tmp/poller-status"
    sh = lambda *c: subprocess.run(c, cwd=d, capture_output=True, text=True, timeout=60)
    try:
        subprocess.run(["rm", "-rf", d]); os.makedirs(d)
        json.dump(st, open(os.path.join(d, "status.json"), "w"), indent=1)
        open(os.path.join(d, "README.md"), "w").write("Live status of the GitHub Actions poller (.github/workflows/poller.yml). Auto-generated, force-pushed.\n")
        sh("git", "init", "-q", "-b", "poller-status"); sh("git", "config", "user.name", "WCN Bot"); sh("git", "config", "user.email", "wcn@mail.grokbot.com")
        sh("git", "add", "-A"); sh("git", "commit", "-qm", "poller status " + st["updated"])
        r = sh("git", "push", "-qf", f"https://x-access-token:{tok}@github.com/{repo}.git", "poller-status:poller-status")
        if r.returncode: log("status push failed (exit", r.returncode, ")")
    except Exception as e: log("status push error:", type(e).__name__)
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--minutes", type=float, default=330); ap.add_argument("--simulate-new", type=int, default=0)
    a = ap.parse_args()
    t_start = time.time(); deadline = t_start + a.minutes * 60
    run = os.environ.get("GITHUB_RUN_ID", "local")
    S = W.load()
    log(f"poller start run={run} minutes={a.minutes:g} state={'restored, cycle %s, last poll %s' % (S.get('cycle'), time.strftime('%H:%M:%SZ', time.gmtime(S['last_poll']))) if S.get('last_poll') else 'fresh (sources will baseline on first sight)'}")
    nxt = 0; cycles = 0; dispatched = 0; pushed = 0
    grace = deadline + 120            # after the last poll: up to 2 min more to dispatch/track anything still pending
    while time.time() < grace:
        now = time.time()
        try:
            if now >= nxt and now < deadline:
                nxt = now + W.POLL_S
                new = W.poll(S); cycles += 1; S["cycle"] = S.get("cycle", 0) + 1; S["last_poll"] = int(now)
                if a.simulate_new and cycles == a.simulate_new:
                    new.append({"feed": "SIMULATED", "source": "Fightful", "title": "[poller test] simulated new trusted item", "link": "https://example.invalid/poller-test-" + run,
                                "ts": int(now), "seen_at": int(now)})
                    log("  SIMULATED new trusted item injected (test)")
                S.setdefault("pending", []).extend(new)
                nd = len(S.get("dispatches", []))
                W.maybe_dispatch(S)
                if len(S.get("dispatches", [])) > nd: dispatched += 1
                hour = [d for d in S.get("dispatches", []) if now - d["at"] < 3600]
                log(f"HEARTBEAT cycle {cycles} (total {S['cycle']}) | {_last.get('poll', '')[6:]} | pending {len(S.get('pending', []))} | "
                    f"tracking {len(S.get('tracking', []))} | dispatched this run {dispatched} | ends in {max(0, deadline - now) / 60:.0f} min")
                st = {"updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "run_id": run, "run_url": f"https://github.com/{os.environ.get('GITHUB_REPOSITORY','')}/actions/runs/{run}",
                      "run_started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t_start)), "run_ends": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(deadline)),
                      "poll_every_s": W.POLL_S, "cycles_this_run": cycles, "cycles_total": S["cycle"], "last_poll": _last.get("poll"),
                      "pending": len(S.get("pending", [])), "dispatched_this_run": dispatched, "dispatches_last_hour_by_poller": len(hour), "last_dispatch": _last.get("dispatch")}
                json.dump(st, open(STATUS, "w"), indent=1)
                if now - pushed >= STATUS_EVERY_S or cycles == 1: push_status(st); pushed = now
            elif S.get("pending"):
                nd = len(S.get("dispatches", [])); W.maybe_dispatch(S)
                if len(S.get("dispatches", [])) > nd: dispatched += 1
            W.track(S); W.save(S)
        except Exception as e:
            log("cycle error:", repr(e)[:300])
        if now >= deadline and not S.get("pending"): break
        wake = min(nxt if nxt > now and nxt < deadline else now + W.POLL_S, now + (W.TRACK_S if S.get("tracking") or S.get("pending") else W.POLL_S), max(deadline, now + 2) if now < deadline else grace)
        while time.time() < wake: time.sleep(2)
    W.save(S)
    log(f"poller done: {cycles} cycles in {(time.time() - t_start) / 60:.1f} min, dispatched {dispatched}, pending {len(S.get('pending', []))} (carried to next run via cache)")
if __name__ == "__main__": main()
