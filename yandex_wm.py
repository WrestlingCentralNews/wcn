"""Submit WCN's sitemaps to Yandex Webmaster (API v4).

Exit codes: 0 = submitted, or skipped because of a transient Yandex/network problem (timeouts, connection
errors, 5xx, 429) after retries (GitHub ::warning:: + status file, so the box's daily retry knows);
2 = bad/expired token (401/403); 3 = host missing or not verified; 4 = other unexpected API answer.
Status is written to $YANDEX_STATUS_FILE (default data/yandex_status.json) and the GitHub step summary.
"""
import os, json, sys, time, socket, urllib.request, urllib.error
from datetime import datetime, timezone

_g = socket.getaddrinfo   # Yandex's IPv6 path is unreachable from GitHub runners; force IPv4
socket.getaddrinfo = lambda *a, **k: [x for x in _g(*a, **k) if x[0] == socket.AF_INET] or _g(*a, **k)
B = "https://api.webmaster.yandex.net/v4"
SITEMAPS = ["https://wrestlingcentralnews.com/sitemap.xml", "https://wrestlingcentralnews.com/es/sitemap.xml"]
STATUS_FILE = os.environ.get("YANDEX_STATUS_FILE", "data/yandex_status.json")
GHA = os.environ.get("GITHUB_ACTIONS") == "true"
BACKOFF = [5, 15, 40]          # 4 attempts per call, ~1 min worst case


class Transient(Exception): pass
class Fatal(Exception):
    def __init__(self, code, msg): super().__init__(msg); self.code = code


def status(state, detail, **extra):
    rec = {"state": state, "detail": detail, "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "runner": "github" if GHA else "box", **extra}
    try:
        os.makedirs(os.path.dirname(STATUS_FILE) or ".", exist_ok=True)
        with open(STATUS_FILE, "w") as f: json.dump(rec, f, indent=1)
    except OSError as e: print("could not write status file:", e)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(f"### Yandex sitemaps: {state}\n\n{detail}\n\n```json\n{json.dumps(rec, indent=1)}\n```\n")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f: f.write(f"state={state}\n")
    print("YANDEX_STATUS", json.dumps(rec))


def req(tok, m, p, body=None, ok_codes=()):
    last = None
    for i in range(len(BACKOFF) + 1):
        r = urllib.request.Request(B + p, method=m, data=json.dumps(body).encode() if body else None,
                                   headers={"Authorization": "OAuth " + tok, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(r, timeout=25) as f:
                return f.status, json.loads(f.read() or b"{}")
        except urllib.error.HTTPError as e:
            txt = e.read().decode(errors="replace")[:300]
            if e.code in ok_codes: return e.code, txt
            if e.code in (401, 403): raise Fatal(2, f"{m} {p}: HTTP {e.code} (token invalid/expired or no access): {txt}")
            if e.code == 429 or e.code >= 500: last = f"{m} {p}: HTTP {e.code} {txt[:120]}"
            else: raise Fatal(4, f"{m} {p}: HTTP {e.code}: {txt}")
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionError, OSError) as e:
            last = f"{m} {p}: {type(e).__name__}: {getattr(e, 'reason', e)}"
        except json.JSONDecodeError as e:
            last = f"{m} {p}: bad JSON ({e})"
        if i < len(BACKOFF):
            print(f"transient ({last}); retry {i + 1}/{len(BACKOFF)} in {BACKOFF[i]}s"); time.sleep(BACKOFF[i])
    raise Transient(last)


def main():
    tok = os.environ.get("YANDEX_WEBMASTER_TOKEN", "").strip()
    if not tok: raise Fatal(2, "YANDEX_WEBMASTER_TOKEN is not set")
    s, u = req(tok, "GET", "/user"); uid = u["user_id"]; print("user", s)
    s, h = req(tok, "GET", f"/user/{uid}/hosts")
    hosts = h.get("hosts", []); print("hosts", s, [(x["host_id"], x.get("verified")) for x in hosts])
    mine = [x for x in hosts if "wrestlingcentralnews" in x["host_id"]]
    if not mine: raise Fatal(3, "wrestlingcentralnews.com is not added in Yandex Webmaster")
    host = next((x for x in mine if x.get("verified")), None)
    if not host: raise Fatal(3, f"host not verified in Yandex Webmaster: {[x['host_id'] for x in mine]}")
    hid = host["host_id"]
    s, sm = req(tok, "GET", f"/user/{uid}/hosts/{hid}/user-added-sitemaps")
    have = {x.get("sitemap_url") for x in (sm.get("sitemaps", []) if isinstance(sm, dict) else [])}
    print("already added", sorted(have))
    added = []
    for url in SITEMAPS:
        if url in have: continue
        s, r = req(tok, "POST", f"/user/{uid}/hosts/{hid}/user-added-sitemaps", {"url": url}, ok_codes=(409,))
        print("add", url, s, r); added.append(url)
    s, det = req(tok, "GET", f"/user/{uid}/hosts/{hid}/sitemaps")
    n = len(det.get("sitemaps", [])) if isinstance(det, dict) else 0
    print("detected", s, json.dumps(det)[:600])
    status("ok", f"host {hid}; user-added {sorted(have | set(added))}; newly added {added}; {n} sitemaps detected by Yandex",
           host=hid, added=added, detected=n)


if __name__ == "__main__":
    try:
        main()
    except Transient as e:
        msg = f"Yandex Webmaster unreachable/transient after retries: {e}. Not a config problem; will retry later."
        print(f"::warning title=Yandex sitemaps skipped::{msg}" if GHA else "WARNING: " + msg)
        status("transient", msg); sys.exit(0)
    except Fatal as e:
        print(f"::error title=Yandex sitemaps config problem::{e}" if GHA else "ERROR: " + str(e))
        status("error", str(e), exit_code=e.code); sys.exit(e.code)
