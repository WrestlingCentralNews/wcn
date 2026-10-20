"""python3 test_x_manual.py -- x_manual.json: the manual delete charge lands in the ledger once; the deleted tweet is flagged in posted_x state."""
import unittest, json, os, tempfile, shutil
import xspend, x_poster as XP
ROOT = os.path.dirname(os.path.abspath(__file__))
class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); xspend.LEDGER = os.path.join(self.d, "x_spend.json"); xspend.ROOT = self.d
        os.makedirs(os.path.join(self.d, "data"))
        xspend.MANUAL = XP.MANUAL = os.path.join(ROOT, "x_manual.json"); xspend.TOPUPS = os.path.join(ROOT, "x_topups.json")
        XP.STATE = os.path.join(self.d, "posted_x.json")
        json.dump({"posted": {"c11f0df54e806": {"tweet": "2111693641613725907", "at": 1792302000, "title": "AAA on FOX Results: La Catalina Debuts in Tag Title Match"}},
                   "links": [], "log": [{"id": "c11f0df54e806", "at": 1792302000, "ok": True, "tweet": "2111693641613725907", "breaking": True}]}, open(XP.STATE, "w"))
        json.dump({"entries": [{"at": 1, "kind": "post", "usd": 0.015, "endpoint": "POST /2/tweets", "src": "x"}], "events": []}, open(xspend.LEDGER, "w"))
    def tearDown(self): shutil.rmtree(self.d)
    def test_charge_once(self):
        xspend.ensure(); xspend.ensure()
        L = json.load(open(xspend.LEDGER)); m = [e for e in L["entries"] if e.get("manual_id") and e.get("ref") == "2111693641613725907"]
        self.assertEqual(len(m), 1); self.assertEqual(m[0]["usd"], 0.005); self.assertEqual(m[0]["ref"], "2111693641613725907")
        self.assertAlmostEqual(L["spent_usd"], 0.03, places=4); self.assertEqual(L["counts"].get("content_mgmt"), 1)
        self.assertEqual(len([e for e in L["entries"] if e.get("manual_id")]), 2); self.assertEqual(L["counts"].get("delete"), 1)   # + Crown Jewel explainer delete ($0.010)
    def test_deleted_flag(self):
        S = XP.load_state(); XP.save_state(S); S = json.load(open(XP.STATE))
        p = S["posted"]["c11f0df54e806"]; self.assertTrue(p["deleted"])            # still in 'posted' -> never re-posted
        self.assertTrue(S["log"][0]["deleted"]); self.assertIn("2111693641613725907", S["deleted"])
    def test_rebase(self):
        xspend.ensure(); L = json.load(open(xspend.LEDGER))
        self.assertEqual(L["remaining_usd"], 9.61); self.assertEqual(L["free_remaining_usd"], 4.61); self.assertEqual(L["paid_remaining_usd"], 5.0)
        self.assertFalse(L["low_balance"])
        rb = xspend._rebase()["at"]; D = json.load(open(xspend.LEDGER)); D["entries"].append({"at": rb + 60, "kind": "post", "usd": 4.70, "endpoint": "x", "src": "t"})
        json.dump(D, open(xspend.LEDGER, "w")); xspend.ensure(); L = json.load(open(xspend.LEDGER))
        self.assertAlmostEqual(L["remaining_usd"], 4.91); self.assertEqual(L["free_remaining_usd"], 0.0); self.assertAlmostEqual(L["paid_remaining_usd"], 4.91)
        D = json.load(open(xspend.LEDGER)); D["entries"].append({"at": rb + 120, "kind": "post", "usd": 3.0, "endpoint": "x", "src": "t"})
        json.dump(D, open(xspend.LEDGER, "w")); xspend.ensure(); L = json.load(open(xspend.LEDGER))
        self.assertTrue(L["low_balance"])   # 1.91 <= 2.00 (incl. the 2026-10-20 $0.010 delete)
if __name__ == "__main__": unittest.main()
