import json, os, re, subprocess, shutil, datetime, timeline as tl
NOW = datetime.date(2026, 11, 2)
CH = {"x": {"name": "X Title", "group": "G", "champion": "B", "since": "2025-10-05", "source": "s"}}
DATA = {"x": {"reigns": [{"holder": "A", "start": "2024-01-01"}, {"holder": "B", "start": "2025-10-05"}]}}
def test_boundary_day_switches_champion():
    rs = tl.lineage(CH, DATA)["x"]["reigns"]
    assert tl.champion_on(rs, "2025-10-04")["holder"] == "A"
    assert tl.champion_on(rs, "2025-10-05")["holder"] == "B"
    assert tl.champion_on(rs, "2023-12-31") is None
def test_new_reign_extends_lineage_automatically():
    ch = {"x": dict(CH["x"], champion="C", since="2026-11-01")}
    rs = tl.lineage(ch, DATA)["x"]["reigns"]
    assert [r["holder"] for r in rs] == ["A", "B", "C"] and rs[1]["end"] == "2026-11-01" and rs[2]["end"] is None
def test_mismatch_keeps_only_current():
    ch = {"x": dict(CH["x"], since="2020-01-01")}
    assert [r["holder"] for r in tl.lineage(ch, DATA)["x"]["reigns"]] == ["B"]
def test_real_lineage_current_matches_champions():
    titles = json.load(open(os.path.join(tl.ROOT, "champions.json")))["titles"]
    lin = tl.lineage({t["id"]: t for t in titles})
    for t in titles:
        last = lin[t["id"]]["reigns"][-1]; assert last["holder"] == t["champion"] and last["start"] == t["since"] and last["end"] is None
        rs = lin[t["id"]]["reigns"]; assert all(rs[i]["start"] <= rs[i + 1]["start"] for i in range(len(rs) - 1))
def test_photos_are_licensed_and_local():
    cr = json.load(open(os.path.join(tl.ROOT, "champion_photos.json")))
    for k, c in cr.items():
        assert re.match(r"(CC BY|CC-BY|CC0|Public domain|PD)", c["license"], re.I) and "commons.wikimedia.org" in c["source"]
        assert os.path.isfile(os.path.join(tl.ROOT, "public", c["file"].lstrip("/")))
def test_markup_slider_daily_live_and_date_search():
    h = tl.html_block(tl.lineage(CH, DATA), NOW, credits={})
    assert 'type="range" id="tl-s" step="1"' in h and "addEventListener('input'" in h and 'type="date" id="tl-q"' in h
    assert "error" not in h.lower()
def test_js_pick_boundary_in_node():
    node = shutil.which("node")
    if not node: return
    body = tl.JS.split("function pick", 1)[1].split("window.wcnPick", 1)[0]
    code = "function pick" + body + "var r=[['A','2024-01-01','2025-10-05','',''],['B','2025-10-05',null,'','']];console.log(pick(r,'2025-10-04')[0]+pick(r,'2025-10-05')[0]+(pick(r,'2023-01-01')===null))"
    out = subprocess.run([node, "-e", code], capture_output=True, text=True).stdout.strip()
    assert out == "ABtrue"
def test_created_vs_gap_label_and_placement():
    lin = tl.lineage(CH, DATA); assert lin["x"]["created"] is True
    gap = tl.lineage(CH, {}); assert gap["x"]["created"] is False
    assert "Title created " in tl.JS and "History from " in tl.JS
    import stats_pages as sp
    h = sp.champions_html({k: dict(v, id=k, group="G", promo="P") for k, v in CH.items()}, ["G"], NOW)
    assert h.index('class="tl"') < h.index('<table class="stat"')
