"""WCN Weekly: the week's top 10 stories, emailed every Monday via Kit (kit.com, free plan) v4 broadcasts API.

Runs from .github/workflows/newsletter.yml (Mondays 13:00 UTC = 9:00 AM Puerto Rico). Standard library only.
Ranking: x_poster.score() over stories first reported in the past 7 days (one per story cluster).
State: data/newsletter_sent.json (data branch) -> one send per ISO week, never twice.
Gate: repo variable NEWSLETTER_ENABLED=1; anything else = dry run (builds + writes the HTML, sends nothing).
  python newsletter.py                 # weekly send (gated)
  python newsletter.py --preview FILE  # write the email HTML to FILE, no API calls
  python newsletter.py --test          # send now ONLY to subscribers tagged 'wcn-test' (not recorded as the week's issue)
Never fails the workflow.
"""
import os, re, sys, json, time, html, datetime, urllib.request, urllib.error, urllib.parse
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from x_poster import score
NEWS = os.path.join(ROOT, "public", "news.json")
STATE = os.path.join(ROOT, "data", "newsletter_sent.json")
SITE = "https://wrestlingcentralnews.com/"
API = "https://api.kit.com/v4"
TOP_N, DAYS = 10, 7
TEST_TAG = "wcn-test"
PR = datetime.timezone(datetime.timedelta(hours=-4))          # Puerto Rico: AST, no DST
CATC = {"WWE": "#f26a14", "AEW": "#7cd618", "TNA": "#4ea8ff", "Indie": "#f05fc1", "Global": "#2fd3b4"}
e = lambda s: html.escape(s or "", quote=True)

def log(*a): print("[newsletter]", *a, flush=True)

def top_week(items, n=TOP_N, days=DAYS, now=None):
    now = now or time.time()
    week = [c for c in items if c.get("url") and now - c.get("first_ts", c["ts"]) < days * 86400]
    week.sort(key=lambda c: (score(c), c.get("sources", 1), c["ts"]), reverse=True)
    out, seen = [], set()
    for c in week:
        k = re.sub(r"[^a-z0-9]+", " ", c["title"].lower()).strip()
        if k in seen: continue
        seen.add(k); out.append(c)
        if len(out) >= n: break
    return out

def utm(url, i):
    q = urllib.parse.urlencode({"utm_source": "newsletter", "utm_medium": "email", "utm_campaign": "wcn-weekly", "utm_content": f"story{i}"})
    return url + ("&" if "?" in url else "?") + q

def short(t, n=230):
    t = re.sub(r"\s+", " ", t or "").strip()
    if len(t) <= n: return t
    t = t[:n].rsplit(" ", 1)[0].rstrip(",;:—-")
    return t + "…"

def email_html(stories, issue_date):
    """Table-based, inline-styled, single column (max 600px): renders in Gmail/Apple Mail/Outlook and on phones.
    Sent as the body of Kit's Classic 'Text only' template, which adds the unsubscribe link + mailing address footer."""
    F = "font-family:Arial,Helvetica,sans-serif;"
    rows = []
    for i, c in enumerate(stories, 1):
        cat = c["categories"][0]; col = CATC.get(cat, "#7cd618"); link = e(utm(SITE + c["url"], i))
        img = c.get("image_local") or c.get("image") or ""
        imgrow = (f'<tr><td style="padding:0 0 12px 0"><a href="{link}"><img src="{e(img)}" width="560" alt="{e(c["title"])}" '
                  f'style="display:block;width:100%;max-width:560px;height:auto;border:0;border-radius:10px;background:#13302c"></a></td></tr>') if img.startswith("http") else ""
        if i > 3: imgrow = ""                                       # images on the top 3 only: lighter, faster email
        rows.append(f'''<tr><td style="padding:0 0 26px 0"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{imgrow}
<tr><td style="{F}font-size:11px;font-weight:bold;letter-spacing:1px;text-transform:uppercase;color:{col};padding:0 0 6px 0">#{i} · {e(cat)}{" · " + str(c["sources"]) + " sources" if c.get("sources", 1) > 1 else ""}</td></tr>
<tr><td style="{F}font-size:{22 if i <= 3 else 18}px;line-height:1.3;font-weight:bold;padding:0 0 8px 0"><a href="{link}" style="color:#0a1a18;text-decoration:none">{e(c["title"])}</a></td></tr>
<tr><td style="{F}font-size:15px;line-height:1.55;color:#33433f;padding:0 0 10px 0">{e(short(c.get("summary")))}</td></tr>
<tr><td style="{F}font-size:14px;font-weight:bold"><a href="{link}" style="color:#d9570b;text-decoration:none">Read the full story on WCN &rarr;</a></td></tr>
</table></td></tr>''')
    home = e(utm(SITE, 0))
    return f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;margin:0 auto">
<tr><td style="background:#0a1a18;border-radius:12px 12px 0 0;padding:22px 20px 16px 20px;text-align:center">
<a href="{home}"><img src="{SITE}logo.png" width="150" alt="Wrestling Central News" style="display:inline-block;width:150px;max-width:60%;height:auto;border:0"></a>
<div style="{F}color:#7cd618;font-size:13px;font-weight:bold;letter-spacing:3px;padding-top:10px">WCN WEEKLY</div>
<div style="{F}color:#d3e0dc;font-size:13px;padding-top:4px">The week's 10 biggest stories in wrestling · {e(issue_date)}</div></td></tr>
<tr><td style="background:#f26a14;height:4px;line-height:4px;font-size:0">&nbsp;</td></tr>
<tr><td style="background:#ffffff;padding:24px 20px 4px 20px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{"".join(rows)}</table></td></tr>
<tr><td style="background:#0a1a18;border-radius:0 0 12px 12px;padding:20px;text-align:center;{F}font-size:13px;line-height:1.6;color:#d3e0dc">
<a href="{home}" style="display:inline-block;background:#7cd618;color:#0a1a18;font-weight:bold;text-decoration:none;padding:10px 22px;border-radius:999px">All the latest news on WCN</a><br><br>
Follow WCN: <a href="https://x.com/wrestlingWCN" style="color:#7cd618">X @wrestlingWCN</a> · <a href="https://www.facebook.com/p/Wrestling-Central-News-61595290838604/" style="color:#7cd618">Facebook</a><br>
You're getting this because you signed up at wrestlingcentralnews.com. Questions? Just reply to this email.</td></tr></table>'''

def load_state():
    try: s = json.load(open(STATE))
    except Exception: s = {}
    s.setdefault("sent", {}); s.setdefault("tests", []); return s
def save_state(s):
    s["tests"] = s["tests"][-50:]; os.makedirs(os.path.dirname(STATE), exist_ok=True); json.dump(s, open(STATE, "w"), indent=1)

def call(method, path, key, body=None, t=30):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-Kit-Api-Key": key, "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "WCN-Newsletter/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=t) as r: return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as ex:
        try: b = json.loads(ex.read() or b"{}")
        except Exception: b = {}
        return ex.code, b

def tag_id(key, name):
    st, r = call("GET", "/tags?per_page=500", key)
    for t in (r.get("tags") or []) if st == 200 else []:
        if t.get("name") == name: return t["id"]
    return None

def build(now=None):
    now = now or time.time()
    stories = top_week(json.load(open(NEWS)).get("items", []), now=now)
    d = datetime.datetime.fromtimestamp(now, PR)
    issue = d.strftime("%B %-d, %Y")
    lead = stories[0]["title"] if stories else ""
    subject = f"WCN Weekly: {lead}"[:150]
    preview = short(" · ".join(c["title"] for c in stories[1:4]), 140) or "The week's biggest wrestling stories"
    return stories, subject, preview, email_html(stories, issue), d

def main(argv):
    if "--preview" in argv:
        out = argv[argv.index("--preview") + 1]
        stories, subject, preview, body, _ = build()
        open(out, "w").write(f'<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(subject)}</title><body style="margin:0;padding:16px 8px;background:#eef2f1">{body}</body>')
        log(f"preview written: {out} · subject: {subject} · {len(stories)} stories"); return
    test = "--test" in argv
    enabled = os.environ.get("NEWSLETTER_ENABLED", "").strip() == "1"
    key = os.environ.get("KIT_API_KEY", "").strip()
    if not key: log("KIT_API_KEY missing; skipping"); return
    stories, subject, preview, body, d = build()
    if len(stories) < 3: log(f"only {len(stories)} stories this week; skipping"); return
    week = "%d-W%02d" % d.isocalendar()[:2]
    s = load_state()
    body_req = {"subject": subject, "preview_text": preview, "content": body, "description": f"WCN Weekly {week}",
                "public": False, "published_at": None, "send_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                "email_address": None, "thumbnail_url": stories[0].get("image_local") or stories[0].get("image") or None, "thumbnail_alt": stories[0]["title"]}
    if test:
        tid = tag_id(key, TEST_TAG)
        if not tid: log(f"no '{TEST_TAG}' tag in Kit; refusing to send a test to everyone"); return
        body_req["subscriber_filter"] = [{"all": [{"type": "tag", "ids": [tid]}], "any": None, "none": None}]
        body_req["description"] += " (TEST)"; body_req["subject"] = "[TEST] " + subject
    else:
        if week in s["sent"]: log(f"{week} already sent ({s['sent'][week].get('broadcast_id')}); nothing to do"); return
        st, r = call("GET", "/broadcasts?per_page=100", key)     # belt and braces: Kit itself is the 2nd source of truth
        dup = [b for b in (r.get("broadcasts") or []) if b.get("description") == body_req["description"]] if st == 200 else []
        if dup:
            s["sent"][week] = {"ts": int(time.time()), "broadcast_id": dup[0]["id"], "subject": dup[0].get("subject"), "note": "found in Kit"}
            save_state(s); log(f"{week} already in Kit as broadcast {dup[0]['id']}; recorded, not resending"); return
        if not enabled: log(f"DRY RUN (NEWSLETTER_ENABLED!=1) {week}: would send '{subject}' with {len(stories)} stories"); return
    st, r = call("POST", "/broadcasts", key, body_req)
    b = r.get("broadcast") or {}
    if st in (200, 201) and b.get("id"):
        rec = {"ts": int(time.time()), "broadcast_id": b["id"], "status": b.get("status"), "subject": body_req["subject"], "stories": [c["id"] for c in stories]}
        if test: s["tests"].append(rec)
        else: s["sent"][week] = rec
        save_state(s); log(f"{'TEST ' if test else ''}broadcast {b['id']} scheduled now ({b.get('status')}): {body_req['subject']}")
    else:
        log(f"broadcast failed HTTP {st}: {r.get('errors') or r}")

if __name__ == "__main__":
    try: main(sys.argv[1:])
    except Exception as ex: log(f"error (ignored): {ex!r}")
    sys.exit(0)
