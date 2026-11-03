"""Owner 2026-11-02: an event's performers come only from sources for THIS edition (date/year), main event first."""
import unittest, datetime, json, os, tempfile
import hubs
ET = hubs.ET
def ts(y, m, d): return int(datetime.datetime(y, m, d, 12, tzinfo=ET).timestamp())
def C(title, when, kind="match", src="Fightful", trusted=1): return {"title": title, "first_ts": when, "ts": when, "kind": {"type": kind}, "source": src, "trusted": trusted}
HH26 = datetime.date(2026, 10, 31)
class Edition(unittest.TestCase):
    def test_past_year_source_rejected(self):
        old = C("Oba Femi vs Trick Williams Set For NXT Halloween Havoc 2025", ts(2025, 10, 20))
        self.assertFalse(hubs.edition_ok(old, HH26, True))
        named = C("Oba Femi vs Trick Williams Set For NXT Halloween Havoc 2025", ts(2026, 10, 20))   # dated inside the window but names 2025
        self.assertFalse(hubs.edition_ok(named, HH26, True))
        m, o = hubs.perf_titles([old, named, C("Zilla Fatu vs Charlie Dempsey Set For NXT Halloween Havoc", ts(2026, 10, 28))], HH26, True)
        self.assertEqual(o, ["Zilla Fatu vs Charlie Dempsey Set For NXT Halloween Havoc"]); self.assertEqual(m, [])
    def test_results_before_event_rejected(self):
        self.assertFalse(hubs.edition_ok(C("Waller Retains NXT Title at Halloween Havoc", ts(2026, 10, 26), "results"), HH26, True))
        self.assertTrue(hubs.edition_ok(C("Myles Borne Beats Tavion Heights", ts(2026, 11, 1), "results"), HH26, True))
    def test_same_wrestlers_other_year_ok_by_date(self):
        # the same pair may main event again a year later: accepted because the source is dated for this edition
        self.assertTrue(hubs.edition_ok(C("Oba Femi vs Trick Williams main event set for Halloween Havoc 2026", ts(2026, 10, 25)), HH26, False))
    def test_prev_edition_bounds_window(self):
        self.assertFalse(hubs.edition_ok(C("A vs B set", ts(2026, 9, 1)), HH26, False, prev=datetime.date(2026, 9, 15)))
    def test_card_other_year_rejected_and_main_first(self):
        d = tempfile.mkdtemp(); os.makedirs(d + "/data")
        json.dump({"wwe-nxt-halloween-havoc/2026-10-31": {"date": "2025-10-25", "lines": ["Trick Williams vs Oba Femi"]},
                   "aew-full-gear/2026-11-14": {"date": "2026-11-14", "lines": ["Kyle Fletcher vs Adam Page"], "main_event": ["Kenny Omega vs Will Ospreay"]}}, open(d + "/data/fullcards.json", "w"))
        old = hubs.ROOT; hubs.ROOT = d
        try:
            a = [hubs.sports_event("NXT Halloween Havoc", HH26, None, "p/", "WWE", True, "Arena", "Orlando, Florida")]
            hubs.event_extras(a, "wwe-nxt-halloween-havoc/2026-10-31", None, "en", ev_date=HH26)
            b = [hubs.sports_event("AEW Full Gear", datetime.date(2026, 11, 14), None, "q/", "AEW", False, "Arena", "Newark, New Jersey")]
            hubs.event_extras(b, "aew-full-gear/2026-11-14", None, "en", mains=[], ev_date=datetime.date(2026, 11, 14))
        finally: hubs.ROOT = old
        self.assertFalse([p for p in a[0].get("performer", []) if p["@type"] == "Person"])
        names = [p["name"] for p in b[0]["performer"] if p["@type"] == "Person"]
        self.assertEqual(names[:2], ["Kenny Omega", "Will Ospreay"]); self.assertIn("Main event: Kenny Omega vs. Will Ospreay", b[0]["description"])
if __name__ == "__main__": unittest.main()
