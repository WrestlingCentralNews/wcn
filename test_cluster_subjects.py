"""python3 test_cluster_subjects.py: clustering never mixes promotions or wrestlers (2026-10-21 'WWE Star Signs New Contract' case:
Dragon Lee's WWE re-signing + Santino Marella's TNA re-signing + Shotzi Blackheart's TNA signing in one story, WWE headline,
Dragon Lee photo, Santino/Shotzi body), nameless teasers, card photo/headline/write-up from the same subject."""
import enrich, vision, translate
enrich.TIER = lambda s: 1
T0 = 1792509645
def a(i, raw, src, dt, cats, title=None, img=None, body="", ss=""):
    return {"id": i, "raw_title": raw, "title": title or raw, "link": f"https://src/{i}", "source": src, "ts": T0 + dt * 60, "categories": cats,
            "summary": raw + ".", "summary_src": ss, "body": body, "image": img, "kind": {"type": "news"}}
ARTS = [
    a("san1", "Santino Marella Re-Signs With TNA Wrestling", "Ringside News", 0, ["TNA"], img="https://r/santino-marella-re-signs-with-tna-wrestling-49.jpg",
      ss="Santino Marella isn't going anywhere when his current TNA deal runs out."),
    a("san2", "TNA Wrestling Re-Signs Director of Authority Santino Marella", "Official: TNA", 10, ["TNA"], img="https://t/tna-santino.jpg"),
    a("san3", "Santino Marella Signs New TNA Deal", "PWInsider", 33, ["TNA"]),
    a("san4", "Former WWE Star Santino Marella Re-Signs With TNA Wrestling", "Wrestling Inc", 175, ["TNA"]),
    a("both", "TNA signs two fan favorites", "Cageside Seats", 110, ["TNA"], title="TNA Signs Shotzi Blackheart, Re-Signs Santino Marella",
      img="https://c/Shotzi-Blackheart-scaled.webp", ss="TNA made two moves. First is the announcement that Shotzi Blackheart inked a deal with TNA."),
    a("sho1", "TNA Wrestling Signs Shotzi Blackheart", "Official: TNA", -1430, ["TNA"], img="https://e/Shotzi-Blackheart-scaled.webp"),
    a("sho2", "Shotzi Blackheart Officially Signs With TNA Wrestling", "Fightful", -1410, ["TNA"]),
    a("sho3", "TNA Wrestling confirms new signing", "Wrestleview.com", -1300, ["TNA"], body="TNA Wrestling has confirmed the signing of Shotzi Blackheart."),
    a("tease", "Exclusive: WWE Star Signs New Deal", "PWInsider", 460, ["WWE"], title="WWE Star Signs New Contract", ss="A WWE performer has signed a new deal."),
    a("lee1", "Dragon Lee Re-Signs With WWE", "Ringside News", 1038, ["WWE"], img="https://r/dragon-lee-re-signs-with-wwe-19.jpg"),
    a("lee2", "Major Update on Dragon Lee's WWE Contract Status", "Sports Illustrated", 1300, ["WWE"], title="Dragon Lee Signs New WWE Contract",
      img="https://m/20261019_Raw_DragonLee_photo.jpg"),
    a("lee3", "WWE reportedly re-signs former Tag Team Champion", "Wrestling Observer", 1237, ["WWE"], title="WWE Re-Signs Former Tag Team Champion",
      img="https://f/WWE-Logo-2026.jpg", ss="Dragon Lee has reportedly re-signed with WWE. According to PWInsider, Lee and WWE negotiated a new deal."),
    a("lee4", "Report: Dragon Lee Re-Signs With WWE", "Fightful", 1415, ["WWE"]),
]
by = {x["id"]: x for x in ARTS}
out = enrich.cluster(ARTS)
def members(c): return {u["link"].rsplit("/", 1)[1] for u in c["updates"]} | {c["link"].rsplit("/", 1)[1]}
groups = {frozenset(members(c)): c for c in out}
def find(i): return next(c for c in out if i in members(c))
san, lee, sho, tz = find("san1"), find("lee1"), find("sho1"), find("tease")
# 1. three separate stories + the nameless teaser alone (and unpublishable)
assert members(san) >= {"san1", "san2", "san3", "san4"} and not members(san) & {"lee1", "lee2", "lee3", "lee4", "tease", "sho1", "sho2"}, members(san)
assert members(lee) == {"lee1", "lee2", "lee3", "lee4"}, members(lee)            # the F4W teaser joins: its own text names Dragon Lee
assert members(sho) >= {"sho1", "sho2", "sho3"} and not members(sho) & {"lee1", "tease", "san1"}, members(sho)   # 'confirms new signing' joins via its text
assert members(tz) == {"tease"} and tz.get("unnamed"), (members(tz), tz)
assert not any(c.get("unnamed") for c in (san, lee, sho))
# 2. headline / promotion / photo from the story's own subject
assert "Santino" in san["title"] and san["categories"] == ["TNA"], san["title"]
assert "Dragon Lee" in lee["title"] and lee["categories"] == ["WWE"], lee["title"]   # never the teaser's 'WWE Re-Signs Former Tag Team Champion'
assert "Shotzi" in sho["title"], sho["title"]
assert "shotzi" not in (san["image"] or "").lower() and "dragon" not in (san["image"] or "").lower(), san["image"]
assert "Logo" not in (lee["image"] or ""), lee["image"]
# 3. the pair rules themselves
assert enrich.conflict(by["tease"], by["san3"])                # WWE vs TNA
assert enrich.conflict(by["lee1"], by["san1"])                 # Dragon Lee vs Santino Marella
assert not enrich.similar(by["tease"], by["san3"])             # 'signs new deal' alone is not a match
assert not enrich.conflict(by["both"], by["san1"]) and not enrich.conflict(by["both"], by["sho1"])
assert enrich.promos("Former WWE, MLW wrestler reportedly signs with TNA Wrestling") == {"tna"}
assert enrich.promos("Former WWE NXT titleholder debuts at TNA taping") == {"tna"}
assert enrich.teaser(by["tease"]) and enrich.teaser(by["lee3"]) and not enrich.teaser(by["lee1"])
assert enrich.subjects("Dragon Lee Re-Signs With WWE") == {"dragon lee"}       # not aliased to today's Mistico (CMLL)
assert enrich.conflict({"raw_title": "Tony Khan Addresses Toni Storm's AEW Return", "title": ""},
                       {"raw_title": "Tony Khan Addresses Kairi Sane AEW Signing", "title": ""})   # a shared executive is not a shared subject
# 4. image file-name rules
assert enrich.img_clash("https://c/Shotzi-Blackheart-scaled.webp", frozenset({"santino marella"}), frozenset({"tna"}))
assert enrich.img_clash("https://f/WWE-Logo-2026.jpg", frozenset({"santino marella"}), frozenset({"tna"}))
assert not enrich.img_clash("https://r/santino-marella-re-signs-with-tna-wrestling-49.jpg", frozenset({"santino marella"}), frozenset({"tna"}))
_cache = vision.cache; vision.cache = lambda: {}
try:
    img, _, st = vision.choose({"id": "x1", "title": "WWE Star Signs New Contract", "raw_title": "Exclusive: WWE Star Signs New Deal",
                                "image": "https://m/Dragon-Lee-Raw.jpg", "link": "https://src/tease"}, [], fetch=False)
    assert "Dragon" not in (img or ""), (img, st)              # nameless headline never gets a named wrestler's photo
    img, _, st = vision.choose({"id": "x2", "title": "Santino Marella Re-Signs With TNA Wrestling", "raw_title": "Santino Marella Re-Signs With TNA Wrestling",
                                "summary": "", "image": "https://e/Shotzi-Blackheart-scaled.webp", "link": "https://src/san4"},
                               ["https://e/Shotzi-Blackheart-scaled.webp"], budget_ok=False, fetch=False)
    assert "Shotzi" not in (img or ""), (img, st)              # photo labelled with another wrestler is rejected even for a guessed key name
finally: vision.cache = _cache
# 5. write-ups: a long-form about other people is never shared into / kept on this report
santino_long = ["TNA Wrestling has announced the re-signing of Santino Marella with the promotion."]
assert enrich.long_mismatch(by["lee4"], santino_long) and not enrich.long_mismatch(by["san4"], santino_long)
assert not enrich.same_story(by["san1"], by["lee4"]) and enrich.same_story(by["san1"], by["san4"])
# 6. Spanish: a cached translation about another wrestler is re-done under a new slug
assert translate.changed_topic("Dragon Lee Re-Signs With WWE", "Santino Marella Re-Signs With TNA Wrestling")
print("ok", len(out), "stories:", sorted(c["title"] for c in out))
