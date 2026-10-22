"""One-off, owner-approved (2026-10-22): delete the wrong 'Sting Returns On AEW Dynamite' post (it was Sting's son Steve Borden)
and post the corrected story once. Idempotent: does nothing if data/posted_x.json already records the correction."""
import os, json, time, urllib.request, urllib.error
import x_poster as X, xspend
OLD, CARD = "2113070601929708024", "c0b362676d5fc"
HEAD = "Sting's Son Steve Borden Returns, Issues Blood & Guts Challenge On Dynamite"
S = X.load_state(); res = {"at": int(time.time())}
if S.get("corrections", {}).get(OLD, {}).get("new_tweet"):
    print("already corrected:", S["corrections"][OLD]); raise SystemExit(0)
url = f"https://api.x.com/2/tweets/{OLD}"
req = urllib.request.Request(url, method="DELETE", headers={"Authorization": X.oauth_header("DELETE", url)})
try:
    r = urllib.request.urlopen(req, timeout=30); code, body = r.status, json.load(r)
except urllib.error.HTTPError as e: code, body = e.code, e.read().decode("utf8", "ignore")[:300]
res["delete"] = {"code": code, "body": body}; print("DELETE", code, body)
if code == 200: xspend.record("delete", "DELETE /2/tweets/:id", "x_fix", ref=OLD, note="wrong 'Sting Returns' post (was Sting's son)")
if not (code == 200 or code == 404):
    json.dump(res, open("data/x_fix_result.json", "w")); raise SystemExit("delete failed; not posting")
S.setdefault("deleted", {})[OLD] = {"card": CARD, "at": int(time.time()), "reason": "AI headline said Sting; it was his son Steve Borden (owner-approved delete + repost)"}
for e in S["log"]:
    if str(e.get("tweet")) == OLD: e.update(deleted=True, deleted_at=int(time.time()))
cards = json.load(open("public/news.json")); cards = cards if isinstance(cards, list) else (cards.get("stories") or cards.get("items"))
c = next(x for x in cards if x["id"] == CARD); c = dict(c, title=HEAD)
text = X.tweet_text(c); print("TEXT:", text)
if os.environ.get("DRY") == "1": raise SystemExit(0)
media, img, why, merr = X.attach_photo(X.photo_candidates(c), src="x_fix")
code, body, _ = X.post_tweet(text, [media] if media else None); print("POST", code, body)
res["post"] = {"code": code, "body": body, "text": text, "photo": why if media else None}
if code in (200, 201):
    tid = body["data"]["id"]; now = int(time.time())
    xspend.record("post", "POST /2/tweets", "x_fix", ref=tid, note="corrected Steve Borden post")
    S["posted"][CARD] = {"tweet": tid, "at": now, "title": HEAD, "replaces": OLD}
    S["log"].append({"id": CARD, "at": now, "code": code, "ok": True, "tweet": tid, "correction_of": OLD, "media": media})
    S.setdefault("corrections", {})[OLD] = {"new_tweet": tid, "at": now}
    res["url"] = f"https://x.com/wrestlingWCN/status/{tid}"
X.save_state(S); json.dump(res, open("data/x_fix_result.json", "w"), indent=1); print(json.dumps(res)[:800])
