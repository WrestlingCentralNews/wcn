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
ok, _, holds = pubgate.gate(dict(c), by)
check(not ok, "headline says new signing while 3 sources say re-signing: not held")
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
print("FAIL count", fails) if fails else print("ok")
raise SystemExit(1 if fails else 0)
