"""python3 test_roster.py: official-roster cross-check for signing/release stories (owner rule 2026-10-21)."""
import time, roster, pubgate, enrich, editorial
DAY = 86400; NOW = int(time.time())
import tempfile, os; roster.PATH = os.path.join(tempfile.mkdtemp(), "rosters.json")   # never touch data/rosters.json
def db_with(promo, names_first, baseline=NOW - 60 * DAY, fetched=NOW - 3600):
    return {promo: {"ok": True, "fetched": fetched, "baseline": baseline,
                    "names": {roster.key(n): {"name": n, "first": f, "last": fetched} for n, f in names_first.items()}}}
ok = 0
def check(c, m):
    global ok; assert c, m; ok += 1
def story(title, src="Fightful", link="https://www.fightful.com/x", updates=()):
    return {"title": title, "raw_title": title, "source": src, "link": link, "updates": list(updates)}
db = db_with("WWE", {"Dragon Lee": NOW - 400 * DAY, "Bron Breakker": NOW - 5 * DAY}) | db_with("TNA", {"Leon Slater": NOW - 90 * DAY})
# release while still listed -> held; 2 trusted outlets or official site -> passes with a note
h, n = pubgate.roster_check(story("WWE Releases Dragon Lee"), "release", {}, db)
check(h and "still listed" in h[0], "release of listed wrestler not held")
two = story("WWE Releases Dragon Lee", updates=[{"link": "https://pwinsider.com/a", "source": "PWInsider", "title": "Dragon Lee released by WWE"}])
check(editorial.tier("Fightful") <= 2 and editorial.tier("PWInsider") <= 2, "test outlets not trusted tiers")
h, n = pubgate.roster_check(two, "release", {}, db); check(not h and "trusted" in n, "2 trusted outlets didn't confirm")
h, n = pubgate.roster_check(story("WWE Releases Dragon Lee", src="WWE", link="https://www.wwe.com/article/x"), "release", {}, db)
check(not h and "official" in n, "official WWE statement didn't confirm")
# 'new' signing of a wrestler listed > 14 days -> held; newly listed -> support note
h, n = pubgate.roster_check(story("Dragon Lee Signs With WWE"), "new", {}, db); check(h and "re-signing" in h[0], "long-listed 'new' signing not held")
h, n = pubgate.roster_check(story("Bron Breakker Signs With WWE"), "new", {}, db); check(not h and n == "newly added to the WWE roster", "new roster add note")
h, n = pubgate.roster_check(story("Leon Slater Re-Signs With TNA"), "re-sign", {}, db); check(not h and n == "still on the TNA roster", "still-listed note")
# never hold: stale/failed roster, executive, unknown promotion, no data
check(pubgate.roster_check(story("WWE Releases Dragon Lee"), "release", {}, db_with("WWE", {"Dragon Lee": NOW - 400 * DAY}, fetched=NOW - 5 * DAY))[0] == [], "stale roster held")
check(pubgate.roster_check(story("WWE Releases Dragon Lee"), "release", {}, {})[0] == [], "missing roster held")
check(pubgate.roster_check(story("AEW Releases Tony Khan"), "release", {}, db_with("AEW", {"Tony Khan": NOW - 400 * DAY}))[0] == [], "executive held")
check(pubgate.roster_check(story("Dragon Lee Leaves CMLL"), "release", {}, db)[0] == [], "promotion without roster held")
# not contract stories: no roster hold/note
for title, k in [("Jacy Jayne Feared Release Before NXT Title Win", "release"), ("Dragon Lee Joins Eight-Man Tag On NXT", "new"),
                 ("WWE's Dragon Lee Set For Highspots Virtual Signing", "new")]:
    check(pubgate.roster_check(story(title), k, {}, db) == ([], None), "non-contract story checked: " + title)
# failed fetch keeps the old snapshot; aliases match (Edge -> Adam Copeland)
d0 = roster.refresh(now=NOW, fetch={"WWE": lambda: (_ for _ in ()).throw(OSError("down"))}, log=lambda *a: None)
check(d0["WWE"]["ok"] is False, "failed fetch not marked")
check(roster.key("Edge") == roster.key("Adam Copeland") and roster.key("ADAM COPELAND") == roster.key("Adam Copeland"), "alias/case key")
# return / retirement
h, n = pubgate.roster_check(story("WWE Star Dragon Lee Announces Retirement"), None, {}, db); check(h and "retirement" in h[0], "retired-but-listed not held")
h, n = pubgate.roster_check(story("Bron Breakker Returns To WWE"), None, {}, db); check(not h and "newly added" in n, "return note")
# on demand: no contract story -> no fetch; contract story -> one fetch per promo per day
calls = []
orig = roster.FETCH; roster.FETCH = {"WWE": lambda: calls.append(1) or {f"W{i}" for i in range(150)} | {"Dragon Lee"}}
pubgate._RDB = None; os.path.exists(roster.PATH) and os.remove(roster.PATH)
pubgate.roster_check(story("Dragon Lee Wins Title On WWE Raw"), None, {})
check(calls == [], "fetched for a non-contract story")
pubgate.roster_check(story("WWE Releases Dragon Lee"), "release", {}); pubgate.roster_check(story("WWE Releases Dragon Lee"), "release", {})
check(calls == [1], f"expected exactly one fetch, got {len(calls)}")
roster.FETCH = {"WWE": lambda: (_ for _ in ()).throw(OSError("down"))}; pubgate._RDB = None; os.remove(roster.PATH)
check(pubgate.roster_check(story("WWE Releases Dragon Lee"), "release", {})[0] == [], "failed on-demand fetch held (must fail open)")
roster.FETCH = orig
print("ok", ok, "checks")
