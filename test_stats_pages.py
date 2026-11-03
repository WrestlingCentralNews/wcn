import json, os, stats_pages as sp
TITLES = json.load(open(os.path.join(os.path.dirname(__file__), "champions.json")))["titles"]
def show(date, brand, kind="weekly", slug="wwe-raw"): return {"date": date, "brand": brand, "kind": kind, "slug": slug, "key": f"{date}-{slug}"}
def m(w, l, stip, title="change", fin="", **k): return dict(winner=w, loser=l, stip=stip, title=title, fin_en=fin, pre=False, confirmed=True, conflict=False, order=1, **k)
ART = lambda title, link="https://www.fightful.com/wrestling/x/", ts=1793145600: {"title": title, "link": link, "ts": ts}
def run(s, mm, arts=()):
    champ = {t["id"]: dict(t) for t in TITLES}
    return sp.title_change(s, mm, TITLES, champ, list(arts))
def test_dq_never_changes_title():   # Raw 10-26: Becky Lynch won by DQ, Liv Morgan retained
    t, why = run(show("2026-10-26", "WWE"), m("Becky Lynch", "Liv Morgan", "Women’s World Championship", fin="by disqualification"))
    assert t is None and "DQ" in why
def test_contender_match_flagged():  # iMPACT 10-22 X Division #1 contender four-way
    t, why = run(show("2026-10-22", "TNA", slug="tna-impact"), m("Cedric Alexander", "Rich Swann", "TNA X-Division Championship Number One Contenders Four-Way"))
    assert t is None and "contender" in why
def test_eliminator_without_headline_flagged():  # Dynamite 10-21 tag eliminator mislabeled as a change
    t, why = run(show("2026-10-28", "AEW", slug="aew-dynamite"), m("Mark Davis and Jake Doyle", "The Young Bucks", "AEW World Tag Team Championship"),
                 [ART("Mark Davis & Jake Doyle earn AEW tag title shot at Full Gear")])
    assert t is None and why
def test_real_change_applied_with_trusted_headline():
    t, why = run(show("2026-11-03", "WWE", slug="wwe-nxt"), m("Wren Sinclair", "Kelani Jordan", "NXT Women's Championship"),
                 [ART("Wren Sinclair Wins NXT Women's Championship On WWE NXT", ts=1793750400)])
    assert t and t["id"] == "nxt-womens" and why is None
def test_untrusted_headline_not_enough():
    t, why = run(show("2026-11-03", "WWE", slug="wwe-nxt"), m("Wren Sinclair", "Kelani Jordan", "NXT Women's Championship"),
                 [ART("Wren Sinclair Wins NXT Women's Championship", link="https://www.sportskeeda.com/x", ts=1793750400)])
    assert t is None and "headline" in why
def test_ambiguous_stip_flagged():
    t, why = run(show("2026-11-03", "WWE"), m("Someone", "Other", "Championship match"), [ART("Someone wins title", ts=1793750400)])
    assert t is None and "maps to 0" in why
def test_stip_maps_to_one_title():
    for stip, tid in [("Women’s World Championship", "wwe-womens-world"), ("Intercontinental Championship", "wwe-ic"), ("AEW World Title", "aew-world"),
                      ("TBS Title", "aew-tbs"), ("AAA Mega Championship", "aaa-mega"), ("NXT Title", "nxt"), ("Undisputed WWE Championship", "wwe-undisputed")]:
        brand = {"aew": "AEW", "aaa": "AAA"}.get(tid.split("-")[0], "WWE")
        hits = sp.title_for(stip, brand, TITLES); assert [h["id"] for h in hits] == [tid], (stip, hits)
def test_members_split():
    assert sp.members("The Vision (Bron Breakker & Austin Theory)") == ["Bron Breakker", "Austin Theory"]
    assert sp.members('"Hangman" Adam Page, Brody King, and Bandido') == ['"Hangman" Adam Page', "Brody King", "Bandido"]
    assert sp.members("FTR") == ["FTR"]
def test_records_count_and_method():
    d = dict(show("2026-10-17", "AEW", kind="ppv", slug="aew-wrestledream"), matches=[m("A & B", "C & D", "", title=None), m("E", "F", "", title=None, fin="time limit draw"),
             dict(m("G", "H", "", title=None), confirmed=None)])
    rec, n = sp.records([d])
    assert n == 2 and rec["a"]["big"]["w"] == 1 and rec["d"]["big"]["l"] == 1 and rec["e"]["big"]["d"] == 1 and "g" not in rec
    h, idx = sp.records_html(rec, n); assert "noindex" in h and not idx and "only matches WCN reported" in h
def test_seed_has_sources():
    for t in TITLES: assert t["champion"] and t["since"] and t["source"].startswith("https://"), t["id"]
