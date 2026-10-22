"""python3 test_fb_feed.py: curated Facebook feed rules (cap, slots, dedup, no filler / live results, valid RSS)."""
import os, tempfile, time, datetime, xml.etree.ElementTree as ET
import fb_feed as F
d = tempfile.mkdtemp(); F.STATE = os.path.join(d, "s.json"); F.OUT = os.path.join(d, "f.xml"); F.LIVE_DIR = os.path.join(d, "live")
noon = datetime.datetime(2026, 10, 20, 18, 0, tzinfo=F.PR).timestamp()
def c(i, t, imp=20, kind="news", brk=None, s=""):
    x = {"id": i, "title": t, "summary": s or t + ".", "link": f"https://src/{i}", "first_ts": noon - 3600, "ts": noon - 3600, "imp": imp,
         "image": "https://wrestlingcentralnews.com/img/promo/wwe.jpg", "categories": ["WWE"], "kind": {"type": kind}, "url": f"story/{i}.html"}
    if brk: x["brk"] = brk
    return x
cl = [c("a", "Seth Rollins Signs New WWE Contract", 30), c("b", "Seth Rollins Signs New WWE Contract Extension", 29),
      c("e", "WWE Crown Jewel Explained: Everything You Need To Know", 40), c("r", "Penta Beats Bron Breakker On Raw", 40, "match"),
      c("q", "Live Raw Results", 40, "results"), c("k", "Kairi Sane Returns To WWE", 25, brk="return"),
      c("m", "Jade Cargill Injury Update From Doctor", 22), c("n", "Mercedes Mone Wins TBS Title Again", 21)] + [c(f"f{i}", f"Filler {i} xyz{i}", 1) for i in range(10)]
for k in range(12): F.build(cl, noon + k * 3600)
S = F.load(); ids = [x["id"] for x in S["items"]]
assert ids[0] == "k", ids                         # BREAKING first
assert "e" not in ids and "r" not in ids and "q" not in ids, ids   # no explainer, no live results
assert not ("a" in ids and "b" in ids), ids       # one per story
assert len([x for x in S["items"] if x["day"] == "2026-10-20"]) <= 3
assert all("utm_source=facebook&utm_medium=social" in x["link"] for x in S["items"])
g = [x["guid"] for x in S["items"]]; F.build(cl, noon + 13 * 3600); assert [x["guid"] for x in F.load()["items"]][:len(g)] == g   # stable
r = ET.parse(F.OUT).getroot(); assert r.tag == "rss" and r.get("version") == "2.0"
it = r.find("channel").findall("item"); assert it and all(i.find("enclosure") is not None and i.find("guid").text for i in it)
# story URL changed after it was picked (new slug): same guid, link follows the new URL (no redirect stubs in the feed)
k = next(x for x in cl if x["id"] == "k"); k["url"] = "story/kairi-sane-new-slug-k.html"; F.build(cl, noon + 14 * 3600)
fk = next(x for x in F.load()["items"] if x["id"] == "k"); assert fk["guid"] == "wcn-fb-k" and fk["link"].startswith(F.SITE + "story/kairi-sane-new-slug-k.html?utm_source=facebook"), fk["link"]
assert "story/k.html" not in open(F.OUT).read()
print("ok", ids)
