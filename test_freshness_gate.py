"""python3 test_freshness_gate.py: nameless teasers never publish, new signing vs re-signing, real publish dates (freshness gate),
pre-publish consistency gate, all-member merge of same-wrestler groups (2026-10-21 owner rules)."""
import time, enrich, freshness, pubgate
enrich.TIER = lambda s: 1
T0 = 1792509645   # 2026-10-20 15:20 UTC
def A(t, src="Fightful", ts=T0, link=None, **kw):
    d = {"raw_title": t, "title": t, "summary": t + ".", "source": src, "ts": ts, "link": link or "https://src/" + t.replace(" ", "-"),
         "categories": ["WWE"], "kind": {"type": "news"}, "id": str(abs(hash((t, src, ts))))}
    d.update(kw); return d
fails = 0
def check(ok, msg):
    global fails
    if not ok: fails += 1; print("FAIL", msg)
# --- no-name rule: teasers ---
for t in ["TNA Signing Confirmed", "AAA Star Dealing With Injury", "WWE Signs New ID Talent", "TNA Wrestler Joins Netflix Series Cast",
          "Exclusive: WWE Star Signs New Deal", "WWE Star Signs New Contract", "Additional WWE ID Talent Exit", "Former WWE Superstar Officially Signs With TNA Wrestling",
          "Injury Update: Knockouts Talent Sidelined With Knee Injury", "AEW Star Released", "Former NXT Star Debuts In AAA"]:
    check(enrich.teaser(A(t)), "teaser not caught: " + t)
for t in ["NXT Women's Title Contract Signing Set", "Dragon Lee Re-Signs With WWE", "Shotzi Blackheart Signs With TNA Wrestling",
          "Gowen Retires After 24-Year Wrestling Career", "Injured AEW Stars Borden and Ford Backstage at Dynamite", "Chad Wicks Arrested",
          "Santino Marella Re-Signs With TNA Wrestling"]:
    check(not enrich.teaser(A(t)), "named headline treated as teaser: " + t)
g = enrich.cluster([A("TNA Signing Confirmed", "PWInsider"), A("AAA Star Dealing With Injury", "PWInsider", T0 + 60, categories=["Global"])])
check(all(c.get("unnamed") for c in g), "nameless-only story not flagged unnamed")
# --- new signing / re-signing / expiring / release ---
for t, k in [("Dragon Lee Re-Signs With WWE", "re-sign"), ("Santino Marella Signs Contract Extension With TNA", "re-sign"),
             ("Shotzi Blackheart Signs With TNA Wrestling", "new"), ("Kairi Sane Is All Elite", "new"), ("Dragon Lee's WWE Contract Expires", "expiring"),
             ("Max Caster Released By TNA", "release"), ("Former Champion Parts Ways With AEW", "release")]:
    check(enrich.signing_kind(t) == k, f"signing_kind({t!r}) = {enrich.signing_kind(t)} != {k}")
c = {"id": "c1", "title": "Dragon Lee Signs With WWE", "raw_title": "Dragon Lee Signs With WWE", "summary": "Dragon Lee has a new WWE deal.",
     "link": "l0", "source": "x", "categories": ["WWE"], "updates": [{"link": f"l{i}"} for i in range(1, 4)]}
by = {"l0": A("Dragon Lee Signs With WWE", link="l0"), **{f"l{i}": A("Dragon Lee Re-Signs With WWE", link=f"l{i}") for i in range(1, 4)}}
cc = dict(c); ok, _, holds = pubgate.gate(cc, by)
check(ok and cc["title"] == "Dragon Lee Signs With WWE" and "new" not in cc["summary"].lower(), f"unclear signing not neutral-published: {ok} {cc['title']} {cc['summary']} {holds}")
cc = dict(c, title="Amazing Red Signs New TNA Deal", raw_title="Report: Amazing Red Signs With TNA Wrestling", summary="Amazing Red signed a new deal with TNA.", categories=["TNA"])
by2 = {"l0": A("Amazing Red Signs New TNA Deal", link="l0"), **{f"l{i}": A("Amazing Red Signs With TNA", link=f"l{i}") for i in range(1, 4)}}
ok, _, holds = pubgate.gate(cc, by2)
check(ok and cc["title"] == "Amazing Red Signs With TNA" and "new" not in cc["summary"].lower(), f"Amazing Red not neutral: {cc['title']} {cc['summary']} {holds}")
# --- freshness: real publish date ---
html = '<meta property="article:modified_time" content="2026-10-21T10:00:00Z"><meta property="article:published_time" content="2022-05-02T09:00:00Z">'
check(freshness.page_published(html) == 1651482000, "published_time not used / modified used")
check(freshness.page_published('<meta property="article:modified_time" content="2026-10-21T10:00:00Z">') is None, "modified date taken as publish date")
check(freshness.page_published('<script type="application/ld+json">{"datePublished":"2026-10-19T12:00:00+00:00"}</script>') == 1792411200, "JSON-LD datePublished")
check(freshness.page_published('By Mike Johnson on 2026-10-21 10:33:00') == 1792593180, "PWInsider byline date (US Eastern)")
old = A("Dragon Lee Signs With WWE NXT", "Official: WWE.com", T0, link="https://www.wwe.com/article/2022/05/dragon-lee-signs", added=T0, fresh_v=1)
check(freshness.real_ts(old) and freshness.real_ts(old) < T0 - 365 * 86400, "URL /2022/05/ date not used")
check(freshness.stale_reason(old), "2022 article not stale")
check(freshness.real_ts(A("Raw highlights, Oct. 19, 2026", "Official: WWE.com")) is not None, "title date")
# official pages: listing date is the crawl time, not the publish date
off = A("Dragon Lee signs with WWE", "Official: WWE.com", T0, link="https://www.wwe.com/article/dragon-lee-signs-with-wwe", added=T0)
check(freshness.undated(off), "official page with only crawl time treated as dated")
c = {"link": off["link"], "updates": []}
check(not freshness.corroborated(c, {off["link"]: off}), "undated official page published without corroboration")
fresh = A("Dragon Lee Re-Signs With WWE", "Fightful", T0 - 3600, link="https://f/dl")
c = {"link": off["link"], "updates": [{"link": fresh["link"]}]}
check(freshness.corroborated(c, {off["link"]: off, fresh["link"]: fresh}), "undated lead + fresh trusted report not accepted")
n48 = A("Some Wrestler Wins Title", ts=T0 - 50 * 3600, added=T0, fresh_v=1)
check(freshness.stale_reason(n48), "50h-old news not skipped at ingest")
check(not freshness.stale_reason(A("Some Wrestler Wins Title", ts=T0 - 20 * 3600, added=T0, fresh_v=1)), "20h-old news skipped")
# lead comes from the newest reports, never the old one
g = enrich.cluster([A("Dragon Lee Signs With WWE", "Fightful", T0 - 3 * 86400, link="https://www.wwe.com/2022/dragon-lee-signs"),
                    A("Dragon Lee Re-Signs With WWE", "Fightful", T0, link="https://f/new1"), A("Report: Dragon Lee Re-Signs With WWE", "PWInsider", T0 + 600, link="https://p/new2")])
check(len(g) == 1 and "2022" not in g[0]["link"], "old report leads the story: " + str([(x["title"], x["link"]) for x in g]))
# --- publish gate ---
c = {"id": "c2", "title": "Dragon Lee Re-Signs With WWE", "raw_title": "x", "summary": "Santino Marella re-signed with TNA Wrestling.", "link": "l", "source": "x",
     "categories": ["WWE"], "updates": []}
check(not pubgate.gate(dict(c), {})[0], "headline/summary about different wrestlers not held")
c = {"id": "c3", "title": "Hardys Take Creative Control of TNA Impact", "raw_title": "x", "summary": "Matt and Jeff Hardy will run the TNA Impact taping.",
     "link": "l", "source": "x", "categories": ["TNA"], "updates": []}
check(pubgate.gate(dict(c), {})[0], "Hardys / Hardy held as a mismatch")
c = {"id": "c4", "title": "Kenny Omega Returns at NJPW Power Struggle", "raw_title": "x", "summary": "Kenny Omega returned at NJPW Power Struggle.",
     "link": "l", "source": "x", "categories": ["AEW"], "updates": []}
ok, fx, _ = pubgate.gate(c, {}); check(ok and "Global" in c["categories"], "tag doesn't follow headline promotion")
# --- all-member merge: same wrestler, matching reports beyond the oldest/newest pair ---
sh = [A("Shotzi Blackheart Signs With TNA Wrestling", "Official: TNA", T0, categories=["TNA"]),
      A("Shotzi Blackheart Officially Signs With TNA", "Fightful", T0 + 60, categories=["TNA"]),
      A("Shotzi Blackheart Plans To Keep Indie Dates After TNA Signing", "Wrestling Observer", T0 + 7200, categories=["TNA"]),
      A("Shotzi Blackheart Plans To Keep Indie Dates With TNA", "411MANIA", T0 + 9000, categories=["TNA"]),
      A("Shotzi Blackheart Will Keep Indie Dates Under TNA Deal", "Fightful", T0 + 9600, categories=["TNA"])]
g = enrich.cluster(sh)
check(len(g) == 1, "Shotzi reports split into %d stories" % len(g))
check(len(g) >= 1 and "sign" in g[0]["title"].lower() and "Shotzi" in g[0]["title"], "Shotzi story doesn't lead with the signing: " + (g[0]["title"] if g else ""))
x = enrich.cluster([A("Anya Rune Steps Away From Wrestling", "Fightful", T0), A("Max Caster Steps Away From Wrestling", "Fightful", T0 + 60)])
check(len(x) == 2, "two different wrestlers 'stepping away' merged")
# --- undated official pages: narrow middle ground (owner decision 2026-10-21 16:26 UTC) ---
freshness.URL_SEEN = {}
def O(t, link, body="", **kw):
    d = A(t, "TNA Wrestling", T0, link=link, added=T0, body=body); d.update(kw); return d
def pub(a): return freshness.corroborated({"link": a["link"], "updates": []}, {a["link"]: a}, now=T0)
up = O("NXT Halloween Havoc 2026 Card Updated", "https://www.wwe.com/shows/nxt/halloween-havoc-2026-card", "NXT Halloween Havoc takes place Saturday, October 25.", ts_guessed=True)
check(freshness.undated(up) and pub(up), "(a) official 2026 upcoming-event page not published")
hof = O("TNA Wrestling Announces Inductors For Class of 2026 Hall of Fame", "https://tnawrestling.com/news/class-of-2026-hall-of-fame",
        "The induction ceremony is on Sunday, October 11, in Tampa.", ts_guessed=True, added=T0 + 6 * 86400)
check(not pub(hof), "(a) official page about a 2026 event that already happened published")
check(not pub(O("TNA Lockdown 2026 Results", "https://tnawrestling.com/news/tna-lockdown-2026-live-results", "Live from Chicago.", ts_guessed=True)),
      "(a) 2026 results page for an event we can't place as current published")
check(not pub(O("WWE reveals 13 live events for Road to WrestleMania 2025 tour", "https://www.wwe.com/article/road-to-wrestlemania-2025-tour", "On sale now for 2026 fans.", ts=T0 - 3600)),
      "past year (2025) page published")
check(not pub(O("WrestleMania 32 Produced Record Economic Impact", "https://www.wwe.com/shows/wrestlemania/article/wm-impact", ts=T0 - 3600)), "WrestleMania 32 page published")
fb = O("AEW Dynamite: Coral Gables", "https://www.allelitewrestling.com/aew-event/aew-dynamite-coral-gables", ts=T0 - 12 * 3600, source="AEW", via="AEW")   # AEW's own feed, 12h before first seen
check(not pub(O("More big matches set for Lucha Kingdom", "https://www.njpw1972.com/676463", ts=T0 - 12 * 3600, source="NEW JAPAN PRO-WRESTLING", via="Google News: Global")),
      "(b) Google News index date taken as the official feed pubDate")
check(freshness.undated(fb) and pub(fb), "(b) official feed pubDate within 48h + new URL not published")
freshness.URL_SEEN = {freshness._norm(fb["link"]): T0 - 10 * 86400}
check(not pub(fb), "(b) URL first seen 10 days ago (resurfaced page) published")
freshness.URL_SEEN = {}
check(not pub(O("AEW Dynamite: West Valley City", "https://www.allelitewrestling.com/aew-event/wvc", ts=T0 - 60 * 3600, source="AEW", via="AEW")), "(b) feed pubDate 60h old published")
check(not pub(O("Dragon Lee signs with WWE", "https://www.wwe.com/article/dragon-lee-signs-with-nxt", ts=T0, ts_guessed=True)), "(b) crawl time taken as a feed pubDate")
check(pub(O("New tour dates", "https://www.wwe.com/article/tour", ts_guessed=True, lastmod=T0 - 3600)), "(b) sitemap lastmod within 48h not used")
check(not pub(A("Some Wrestler Teases Return", "Some Blog", T0, link="https://blog/x", ts_guessed=True, added=T0, body="2026 tour event")),
      "non-official undated page published without corroboration")
print("FAIL count", fails) if fails else print("ok")
raise SystemExit(1 if fails else 0)
