"""Owner rule: titles never change hands on a DQ / count-out / no contest unless the source explicitly says so (2026-10-26 Raw Becky Lynch vs Liv Morgan)."""
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
print("ok2")
