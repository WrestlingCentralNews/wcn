"""Owner rule: titles never change hands on a DQ / count-out / no contest unless the source explicitly says so (2026-10-26 Raw Becky Lynch vs Liv Morgan).
Also: eliminator/contender matches never show change/retain (2026-10-21 Dynamite)."""
import json, os, tempfile, live
m = {"winner": "Becky Lynch", "loser": "Liv Morgan", "stip": "Women’s World Championship", "title": "change", "fin_en": "by disqualification", "fin_es": "por descalificación", "who": "", "move": ""}
assert live.guard_title(dict(m))["title"] == "no_change"
assert live.guard_title(dict(m, fin_en="by count-out"))["title"] == "no_change"
assert live.guard_title(dict(m, fin_en="by pinfall"))["title"] == "change"
assert live.guard_title(dict(m, change_explicit=True))["title"] == "change"
t = live.text_en(live.guard_title(dict(m))); assert "NEW CHAMPION" not in t and "does not change hands" in t, t
assert "CAMBIO" not in live.text_es(live.guard_title(dict(m)))
d = tempfile.mkdtemp(); live.LIVE_DIR = d
json.dump({"key": "x", "matches": [dict(m, en="Becky Lynch beat Liv Morgan by disqualification — NEW CHAMPION.")]}, open(os.path.join(d, "x.json"), "w"))
st = live.load("x"); assert st["matches"][0]["title"] == "no_change" and "NEW CHAMPION" not in st["matches"][0]["en"]
print("ok")
# eliminator: champion losing must not read as a title change (2026-10-21 Dynamite Davis & Doyle vs Young Bucks)
lines = ["The Young Bucks (c) vs. Mark Davis and Jake Doyle in an Eliminator Match for the AEW World Tag Team Championship"]
c = live.card_of(lines); assert c and c[0]["nontitle"], c
r = {"winner": "Mark Davis and Jake Doyle", "loser": "The Young Bucks", "stip": "", "title": None}
live.apply_card(r, c); assert r["title"] is None, r
r = {"winner": "The Young Bucks", "loser": "X", "stip": "", "title": None}
assert live.guard_title({"title": "change", "stip": "Women's World Championship No. 1 Contender's Match", "fin_en": ""})["title"] is None
assert live.guard_title({"title": "retain", "stip": "AEW Continental Championship Eliminator", "fin_en": "by submission"})["title"] is None
print("ok2")
# Prefer nontitle card over a bare Championship/(c) listing from another source
card = live.card_of([
    "The Young Bucks (c) vs. Mark Davis and Jake Doyle in an Eliminator Match for the AEW World Tag Team Championship",
    "AEW World Tag Team Championship: The Young Bucks (c) vs. Mark Davis and Jake Doyle",
])
r = {"winner": "Mark Davis and Jake Doyle", "loser": "The Young Bucks", "stip": "", "title": None}
best = live.card_match(card, r); assert best and best.get("nontitle"), best
live.apply_card(r, [best]); assert r["title"] is None and "Eliminator" in (r.get("stip") or ""), r
print("ok3")
# Durable override + load repair: bad stored JSON (as on data branch after bbdaf21 was wiped) must clear on load
live.MATCH_OV_PATH = os.path.join(os.path.dirname(live.__file__), "live_match_overrides.json")
bad = {
    "key": "2026-10-21-aew-dynamite",
    "matches": [
        {"winner": "Mark Davis and Jake Doyle", "loser": "The Young Bucks", "stip": "AEW World Tag Team Championship", "title": "change",
         "fin_en": "", "fin_es": "", "who": "", "move": "", "en": "Mark Davis and Jake Doyle beat The Young Bucks — NEW CHAMPIONS.",
         "es": "Mark Davis and Jake Doyle vencieron a The Young Bucks — ¡CAMBIO DE TÍTULO!", "sources": [{"name": "Wrestling Inc", "url": "https://example.com"}]},
        {"winner": "Jon Moxley", "loser": "Roderick Strong", "stip": "AEW Continental Championship", "title": "retain",
         "fin_en": "by submission", "fin_es": "por rendición", "who": "", "move": "",
         "en": "Jon Moxley beat Roderick Strong by submission to retain.",
         "es": "Jon Moxley venció a Roderick Strong por rendición y retuvo el título.", "sources": [{"name": "Wrestling Observer", "url": "https://example.com"}]},
    ],
}
json.dump(bad, open(os.path.join(d, "2026-10-21-aew-dynamite.json"), "w"))
st = live.load("2026-10-21-aew-dynamite")
a, b = st["matches"][0], st["matches"][1]
assert a["title"] is None and "NEW CHAMPION" not in a["en"] and "Eliminator" in a["stip"], a
assert b["title"] is None and "retain" not in b["en"] and "Eliminator" in b["stip"], b
assert "CAMBIO" not in a["es"] and "retuvo" not in b["es"]
# repair_stored writes the fix back so the data-branch orphan keeps it
fixed = live.repair_stored(); assert "2026-10-21-aew-dynamite" in fixed, fixed
saved = json.load(open(os.path.join(d, "2026-10-21-aew-dynamite.json")))
assert saved["matches"][0]["title"] is None and "NEW CHAMPION" not in saved["matches"][0]["en"]
assert saved["matches"][1]["title"] is None and "to retain" not in saved["matches"][1]["en"]
print("ok4")
