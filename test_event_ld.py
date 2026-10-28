"""Event JSON-LD: organizer url, real description, image only when real, performers only from the official card, offers never priced."""
import unittest, datetime, json, os, tempfile
import hubs
class T(unittest.TestCase):
    def test_upcoming_ple(self):
        ev = hubs.sports_event("WWE Crown Jewel 2026", datetime.date(2026, 11, 7), None, "events/x/", "WWE", False, "RAC Arena", "Perth")
        self.assertEqual(ev["organizer"]["url"], "https://www.wwe.com/")
        self.assertIn("RAC Arena", ev["description"])
        self.assertEqual(ev["offers"]["url"], "https://www.wwe.com/events"); self.assertNotIn("price", ev["offers"])
        self.assertNotIn("image", ev); self.assertNotIn("performer", ev)
    def test_aired_no_offer_and_global(self):
        ev = hubs.sports_event("AAA Heroes Inmortales 2026", datetime.date(2026, 10, 24), None, "events/y/", "Global", True, "Arena", "CDMX")
        self.assertNotIn("offers", ev); self.assertEqual(ev["organizer"]["url"], "https://www.luchalibreaaa.com/")
    def test_weekly_show_no_venue_no_event(self):
        # TV episode without a confirmed venue: no Event markup at all (never a VirtualLocation / invented venue)
        self.assertIsNone(hubs.sports_event("WWE Raw (Oct 26)", datetime.date(2026, 10, 26), "20:00", "events/z/", "WWE", False, show="wwe-raw"))
    def test_card_performers(self):
        d = tempfile.mkdtemp(); os.makedirs(d + "/data")
        json.dump({"wwe-raw/2026-10-26": {"lines": ["Chelsea Green defends WWE Women's Title against Roxanne Perez"], "appearances": ["CM Punk"]}}, open(d + "/data/fullcards.json", "w"))
        old = hubs.ROOT; hubs.ROOT = d
        try:
            ld = [hubs.sports_event("WWE Raw", datetime.date(2026, 10, 26), "20:00", "p/", "WWE", False, "Arena", "Austin, Texas", desc="Raw card.", show="wwe-raw")]
            hubs.event_extras(ld, "wwe-raw/2026-10-26", "https://wrestlingcentralnews.com/img/a.jpg", "en")
            hubs.event_extras(x := [hubs.sports_event("WWE Raw", datetime.date(2026, 10, 26), "20:00", "p/", "WWE", False, "Arena", "Austin, Texas", show="wwe-raw")], "wwe-raw/2026-10-19", "/rel.jpg", "en")
        finally: hubs.ROOT = old
        names = [p["name"] for p in ld[0]["performer"]]
        self.assertEqual(names, ["Chelsea Green", "Roxanne Perez", "CM Punk"])
        self.assertEqual(ld[0]["image"], ["https://wrestlingcentralnews.com/img/a.jpg"])
        self.assertIn("Announced: Chelsea Green", ld[0]["description"])
        self.assertNotIn("performer", x[0]); self.assertNotIn("image", x[0])
class Thin(unittest.TestCase):
    def test_has_card_and_page_robots(self):
        d = tempfile.mkdtemp(); os.makedirs(d + "/data")
        json.dump({"aew-worlds-end/2026-12-19": {"lines": ["A vs B", "C vs D"]}, "x/2026-01-01": {"appearances": ["CM Punk"]}}, open(d + "/data/fullcards.json", "w"))
        old, ob = hubs.ROOT, hubs.BUILD; hubs.ROOT = d; hubs.BUILD = d
        try:
            self.assertTrue(hubs._has_card("aew-worlds-end/2026-12-19")); self.assertFalse(hubs._has_card("x/2026-01-01")); self.assertFalse(hubs._has_card("nope/2026-01-01"))
            hubs.page("events/t/", "en", "T", "D", "H", "", [("WCN", hubs.SITE)], [], {}, robots=hubs.THIN_ROBOTS)
            hubs.page("events/u/", "en", "T", "D", "H", "", [("WCN", hubs.SITE)], [], {})
            self.assertIn('content="noindex,follow', open(d + "/events/t/index.html").read())
            self.assertNotIn("noindex", open(d + "/events/u/index.html").read())
        finally: hubs.ROOT, hubs.BUILD = old, ob
class Required(unittest.TestCase):
    """Search Console 'Events structured data issues' (Oct 28 2026): missing location (critical), organizer, eventStatus."""
    def test_every_configured_event_is_complete(self):
        for ev in hubs.EVENTS:
            for lang in ("en", "es"):
                x = hubs.sports_event(ev["name"], datetime.date.fromisoformat(ev["date"]), ev.get("time"), "events/x/", ev["brand"], False, ev["venue"], ev["city"], lang=lang, **hubs._evkw(ev))
                self.assertEqual(hubs.event_problems(x), [], ev["slug"])
                self.assertEqual(x["location"]["@type"], "Place"); self.assertTrue(x["location"]["address"]["addressCountry"])
                self.assertEqual(x["eventAttendanceMode"], "https://schema.org/OfflineEventAttendanceMode")
                self.assertTrue(x["organizer"]["url"].startswith("https://"), ev["slug"])
    def test_status_only_from_data(self):
        a = hubs.sports_event("X", datetime.date(2026, 11, 7), None, "e/", "WWE", False, "V", "Riyadh, Saudi Arabia")
        self.assertEqual(a["eventStatus"], "https://schema.org/EventScheduled")
        b = hubs.sports_event("X", datetime.date(2026, 11, 7), None, "e/", "WWE", False, "V", "Riyadh, Saudi Arabia", ev_status="postponed")
        self.assertEqual(b["eventStatus"], "https://schema.org/EventPostponed"); self.assertNotIn("offers", b)
        c = hubs.sports_event("X", datetime.date(2026, 11, 7), None, "e/", "WWE", False, "V", "Riyadh, Saudi Arabia", ev_status="cancelled")
        self.assertEqual(c["eventStatus"], "https://schema.org/EventCancelled")
    def test_address(self):
        self.assertEqual(hubs.postal_address("Perth, Western Australia"), {"@type": "PostalAddress", "addressLocality": "Perth", "addressRegion": "Western Australia", "addressCountry": "AU"})
        self.assertEqual(hubs.postal_address("Riyadh, Saudi Arabia")["addressCountry"], "SA")
        self.assertIsNone(hubs.sports_event("X", datetime.date(2026, 11, 7), None, "e/", "WWE", False, None, "Orlando, Florida"))
    def test_guard_drops_bare_nested_event(self):
        ld = [{"@type": "LiveBlogPosting", "headline": "h", "about": {"@type": "Event", "name": "WWE Raw", "startDate": "2026-10-26"}},
              {"@type": "SportsEvent", "name": "n", "startDate": "2026-10-26", "location": {"@type": "VirtualLocation", "url": "u"}}]
        out = hubs.guard_events(ld)
        self.assertEqual(len(out), 1); self.assertNotIn("about", out[0])
        ok = hubs.sports_event("X", datetime.date(2026, 11, 7), None, "e/", "WWE", False, "V", "Riyadh, Saudi Arabia")
        self.assertEqual(hubs.guard_events([ok]), [ok])
    def test_episode_venue_needs_source(self):
        old = hubs.CFG.get("venues")
        try:
            hubs.CFG["venues"] = {"wwe-raw/2026-11-02": {"venue": "A", "city": "Austin, Texas"}, "wwe-nxt/2026-11-03": {"venue": "B", "city": "Orlando, Florida", "source": "https://www.wwe.com/x"}}
            self.assertIsNone(hubs.episode_venue("wwe-raw", "2026-11-02")); self.assertEqual(hubs.episode_venue("wwe-nxt", "2026-11-03")["venue"], "B")
        finally: hubs.CFG["venues"] = old
if __name__ == "__main__": unittest.main()
