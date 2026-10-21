"""python3 test_nonwrestling.py: 2026-10-21 'UFC 333 Start Times Revealed For Global Audiences' case. F4W's UFC 333 start-times
article (/news/ufc/) joined F4W's AAA Heroes Inmortales start-times story (same 'Start Times in US, UK, Australia' wording,
67h apart), became its lead (the AAA report was >48h older, so it couldn't lead), kept the AAA write-up and the AAA Heroes
Inmortales coverage box under a UFC headline and poster, and bumped a 3-day-old story to the top as new.
Checks: combat-sports filter, clustering, pubgate, event box, feed position cap, top-stories freshness, filler regex."""
import time, enrich, combat, pubgate, hubs, toppick, editorial
enrich.TIER = lambda s: 1
ok = 0
def check(cond, msg):
    global ok
    assert cond, msg
    ok += 1
def art(i, raw, link, ts, cats=("Global",), title=None, ss="", body="", img=None):
    return {"id": i, "raw_title": raw, "title": title or raw, "link": link, "source": "Wrestling Observer", "ts": ts, "added": ts + 60,
            "categories": list(cats), "summary": ss or raw + ".", "summary_src": ss, "body": body, "image": img, "kind": {"type": "news"}}
NOW = int(time.time())
UFC = art("ufc", "UFC 333 Start Times in US, UK, Australia and more", "https://www.f4wonline.com/news/ufc/ufc-333-start-times-us-uk-australia/",
          NOW - 9 * 3600, title="UFC 333 Start Times Revealed for Global Audiences",
          ss="UFC 333 takes place on Saturday, October 24 from the Etihad Arena with Alexander Volkanovski defending his UFC Featherweight Title.",
          img="https://www.f4wonline.com/wp-content/uploads/2026/10/UFC-333-Main-Events-Poster.jpg")
AAA = art("aaa", "AAA Heroes Inmortales XVIII Global Start Times: US, UK, Australia and more",
          "https://www.f4wonline.com/event-guides/aaa-heroes-inmortales-xviii-global-start-times-us-uk-australia/", NOW - 76 * 3600,
          title="AAA Heroes Inmortales XVIII Global Start Times Revealed", ss="AAA Heroes Inmortales XVIII takes place Saturday, October 24 2026.")
# 1. ingestion filter: non-wrestling combat sports
for a, why in [(UFC, "f4w /news/ufc/ section"),
               (art("p", "Ex-UFC fighter Michael ‘Venom’ Page says MMA fighters need to form union", "https://www.postwrestling.com/2026/10/21/x/", NOW), "MMA headline"),
               (art("ea", "EA Fight Night To Return - Fightful | WWE News, AEW News, Pro Wrestling Backstage News", "https://www.fightful.com/boxing/ea-fight-night-to-return/", NOW), "Fightful /boxing/ with site suffix"),
               (art("tix", "UFC 334 ticket sales update (10-20-2026)", "https://www.f4wonline.com/news/ufc/ufc-334-ticket-sales/", NOW, title="UFC 334 Ticket Sales Update From WrestleTix"), "'WrestleTix' is not wrestling"),
               (art("box", "Multiple-weight world champion granted release from ZUFFA Boxing without fighting once", "https://x/y/", NOW), "boxing headline"),
               (art("b", "Bellator champion vacates title", "https://x/z/", NOW), "Bellator"),
               (art("one", "Big night set for ONE Championship in Bangkok", "https://x/one/", NOW), "ONE Championship"),
               (art("pfl", "PFL Europe card finalized", "https://x/pfl/", NOW), "PFL")]:
    check(combat.nonwrestling(a), "not filtered: " + why)
for raw in ["Brock Lesnar Teases UFC Return Amid WWE Hiatus", "TKO Reports Record Quarter For WWE And UFC", "From WWE to Boxing: 4 Wrestlers Who Stepped Into the Ring",
            "MLW Fusion preview: MLW Featherweight Championship match", "AAA Heroes Inmortales XVIII card finalized",
            "Former UFC Fighter Signs With AEW", "Observer previews AEW WrestleDream and WWE Saudi issues"]:
    check(not combat.nonwrestling(art("k", raw, "https://www.f4wonline.com/news/wwe/k/", NOW)), "wrongly filtered: " + raw)
# 2. clustering: a UFC report never joins a wrestling story (combat counts as its own promotion)
check(enrich.conflict(UFC, AAA), "UFC vs AAA not a conflict")
out = enrich.cluster([dict(UFC), dict(AAA)])
check(len(out) == 2, "UFC 333 and AAA Heroes Inmortales start times merged into one story")
# 3. pubgate: the published story as it was
c = {"id": "cf2a43baa56bd", "title": UFC["title"], "raw_title": UFC["raw_title"], "summary": UFC["summary_src"], "link": UFC["link"],
     "source": "Wrestling Observer", "first_ts": AAA["ts"], "ts": UFC["ts"], "categories": ["Global"], "image": UFC["image"],
     "kind": {"type": "news"}, "updates": [{"ts": AAA["ts"], "link": AAA["link"], "title": AAA["title"], "source": "Wrestling Observer", "line": ""}],
     "long": ["Lucha Libre AAA revealed the Heroes Inmortales card during its October 17 Fox broadcast.", "The event is October 24."]}
bylink = {UFC["link"]: UFC, AAA["link"]: AAA}
good, fixes, holds = pubgate.gate(dict(c), bylink)
check(not good, "UFC/AAA story not held")
check(any(h.startswith("non-wrestling") for h in holds), "non-wrestling not named in holds")
check(any("another promotion than 1/1" in h for h in holds), "headline vs its reports' promotion not checked")
check(any("event box" in h for h in holds), "event box vs headline not checked")
check(pubgate.box_clash(c) and "Inmortales" in pubgate.box_clash(c), "box_clash missed the AAA box")
# the same mismatch with a wrestling headline (no UFC involved): headline about WWE, reports + box about AAA
c2 = dict(c, title="WWE Crown Jewel Start Times Set", raw_title="WWE Crown Jewel 2026 start times", summary="WWE Crown Jewel is November 7.",
          link="https://src/cj", image=None)
cj = art("cj", "WWE Crown Jewel 2026 start times", "https://src/cj", NOW - 3600, cats=("WWE",))
good, fixes, holds = pubgate.gate(dict(c2), {**bylink, cj["link"]: cj})
check(not good and any("event box" in h for h in holds), "WWE headline with AAA box/reports not held")
# write-up about another event than the headline -> dropped (summary shows instead)
check(pubgate.off_topic_long({"title": "Kenny Omega Wins IWGP Title At Wrestle Kingdom", "raw_title": "Kenny Omega wins IWGP title"},
                             ["Lucha Libre AAA revealed the Heroes Inmortales card.", "AAA's show is on October 24."]), "off-topic long-form kept")
check(not pubgate.off_topic_long({"title": "Will Ospreay Retains At WrestleDream", "raw_title": "Ospreay retains"},
                                 ["Will Ospreay retained the AEW title at WrestleDream."]), "on-topic long-form dropped")
legit = {"id": "x", "title": "AAA Heroes Inmortales XVIII Card Finalized", "raw_title": "AAA Heroes Inmortales XVIII card finalized",
         "summary": "AAA finalized the Heroes Inmortales XVIII card for October 24.", "link": "https://src/l", "source": "Fightful",
         "first_ts": NOW - 3600, "ts": NOW - 3600, "categories": ["Global"], "kind": {"type": "news"}, "updates": []}
check(pubgate.gate(dict(legit), {})[0], "legit AAA story held")
# 4. coverage box only for what the headline is about
ev = next(e for e in hubs.EVENTS if e["slug"] == "aaa-heroes-inmortales")
check(not hubs.box_fits(c, ev), "UFC headline got the AAA box")
check(hubs.box_fits(legit, ev), "AAA headline lost its box")
check(hubs.box_fits({"title": "Bandido Injured", "raw_title": "Bandido injured", "summary": "Bandido is hurt.", "updates": []}, ev), "story naming no promotion lost the box")
# 5. a story first reported > 48h ago is never bumped to the top as new
old = {"ts": NOW - 9 * 3600, "first_ts": NOW - 76 * 3600}
new = {"ts": NOW - 20 * 3600, "first_ts": NOW - 20 * 3600}
check(enrich.feed_ts(old) == NOW - 28 * 3600 and enrich.feed_ts(new) == NOW - 20 * 3600, "feed_ts cap")
check(enrich.feed_ts(old) < enrich.feed_ts(new), "3-day-old story with a late report sorts above a fresh one")
check(toppick.act(old) == NOW - 28 * 3600, "top stories treat a late report on an old story as fresh activity")
check(toppick.value(dict(old, imp=10), NOW) < toppick.value(dict(new, imp=10), NOW), "old story outranks fresh one in top stories")
# 6. start-times / this-day-in-history pieces are filler
for raw in ["UFC 333 Start Times in US, UK, Australia and more", "AAA Heroes Inmortales XVIII Global Start Times: US, UK, Australia",
            "10/19 This Day In History: Mike Graham Passes Away"]:
    check(editorial.verdict({"raw_title": raw}) == "gossip/other", "filler not dropped: " + raw)
check(editorial.verdict({"raw_title": "AAA Heroes Inmortales XVIII card finalized"}) is None, "real card news dropped")
print("ok", ok, "checks")
