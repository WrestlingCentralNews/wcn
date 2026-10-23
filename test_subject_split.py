"""2026-10-23: stories about different named people never merge; roundup headlines name no key person or departure."""
import json, os, sys, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import enrich, vision, departed

T = time.time() - 3600
def art(t, link, src, dt=0):
    import hashlib
    return {"id": hashlib.md5(link.encode()).hexdigest()[:12], "image": None, "raw_title": t, "title": t, "link": link, "source": src, "ts": T + dt, "summary": "", "categories": ["WWE"]}

caster = [art("Max Caster Steps Away From Wrestling For Therapy", "https://411mania.com/wrestling/max-caster-therapy/", "411mania"),
          art("Max Caster Announces He Is Stepping Away From Wrestling", "https://nodq.com/news/max-caster-stepping-away/", "NoDQ", 60),
          art("Max Caster Reveals Decision To Take A Break From Wrestling After TNA Exit", "https://www.f4wonline.com/news/max-caster-break/", "F4W", 120)]
anya = [art("Former WWE EVOLVE Star Anya Rune Announces Wrestling Hiatus", "https://www.ringsidenews.com/anya-rune-hiatus/", "Ringside News", 30),
        art("Former WWE ID Talent Anya Rune (Airica Demia) Announces She Is Stepping Away From Wrestling", "https://bodyslam.net/anya-rune-stepping-away/", "BodySlam", 90),
        art("Ex-WWE EVOLVE Star Formerly Known As Anya Rune Announces 'Step Back From Wrestling'", "https://wrestlingnews.co/anya/", "WN", 150)]

def test_head_after_descriptor():
    for a in anya: assert enrich._head(a) == "anya rune", a["raw_title"]
    assert enrich._head(art("Ex-WWE Star Officially Signs With TNA", "u1", "x")) is None
    assert enrich._head(caster[0]) == "max caster"

def test_conflict_and_cluster():
    for a in anya:
        for b in caster: assert enrich.conflict(a, b), (a["raw_title"], b["raw_title"])
    groups = enrich.cluster([dict(x) for x in caster + anya])
    links = [{c["link"]} | {u["link"] for u in c.get("updates", [])} for c in groups]
    for g in links:
        has_c = any("caster" in l for l in g); has_a = any("anya" in l for l in g)
        assert not (has_c and has_a), g

def test_roundup_no_key_person():
    c = {"id": "x", "title": "AEW Talent Set for NJPW Appearances",
         "raw_title": "AEW STARS IN NJPW, SLOANE JACOBS, ERIC YOUNG, THE WWF HILLBILLIES AND MORE", "summary": ""}
    assert vision.roundup_title(c["raw_title"])
    assert vision.key_person(c)[0] is None
    assert departed.from_text(c, "ERIC YOUNG") is None

def test_forget_prunes():
    d = tempfile.mkdtemp(); seen = os.path.join(d, "seen.json"); hand = os.path.join(d, "hand.json")
    json.dump({"forget": ["Eric Young"], "items": {}}, open(hand, "w"))
    json.dump({"eric young": {"name": "ERIC YOUNG", "promo": "TNA", "ts": 1792173600}, "max caster": {"name": "Max Caster", "promo": "TNA", "ts": 1}}, open(seen, "w"))
    oh, os_ = departed.HAND, departed.SEEN; departed.HAND, departed.SEEN = hand, seen
    try:
        assert departed.prune() == ["eric young"]
        assert list(json.load(open(seen))) == ["max caster"]
        departed.record("ERIC YOUNG", "TNA", 1792173600); assert "eric young" not in json.load(open(seen))
    finally: departed.HAND, departed.SEEN = oh, os_

if __name__ == "__main__":
    n = 0
    for k, f in list(globals().items()):
        if k.startswith("test_"): f(); n += 1
    print("ok", n)
