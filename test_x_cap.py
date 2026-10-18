"""python3 test_x_cap.py -- BREAKING posts skip the daily cap / min gap; normal posts keep them (dry run, no network, no keys)."""
import unittest, json, os, tempfile, time, io, contextlib
import x_poster as XP
def card(i, title, kind="news"):
    now = time.time()
    return {"id": f"c{i}", "title": title, "link": f"https://example.org/{i}", "ts": now - 60, "first_ts": now - 60, "categories": ["AEW"],
            "kind": {"type": kind}, "sources": 4, "trusted": 2, "image": None, "updates": []}
BRK = "Ilja Dragunov Debuts As All Elite At WrestleDream"
NRM = "Tony Khan Says Dragunov Contract Talks Went Smoothly"
class T(unittest.TestCase):
    def go(self, items, log):
        d = tempfile.mkdtemp(); XP.NEWS = os.path.join(d, "news.json"); XP.STATE = os.path.join(d, "posted_x.json")
        json.dump({"items": items}, open(XP.NEWS, "w")); json.dump({"posted": {}, "links": [], "log": log}, open(XP.STATE, "w"))
        XP.live_posted = lambda: {}
        for k in ("X_API_KEY", "X_POST_ENABLED"): os.environ.pop(k, None)
        f = io.StringIO()
        with contextlib.redirect_stdout(f): XP.run()
        return f.getvalue()
    def full(self, breaking=False):
        now = int(time.time()); return [{"id": f"o{i}", "at": now - 600 - i * 60, "ok": True, **({"breaking": True} if breaking else {})} for i in range(XP.DAILY_CAP)]
    def test_breaking_skips_cap(self):
        out = self.go([card(1, BRK), card(2, NRM)], self.full())
        dry = [l for l in out.splitlines() if "DRY RUN" in l]
        self.assertEqual(len(dry), 1); self.assertIn("BREAKING", dry[0]); self.assertIn("daily cap", out)
    def test_normal_kept_by_cap(self):
        out = self.go([card(2, NRM)], self.full()); self.assertNotIn("DRY RUN", out); self.assertIn("daily cap", out)
    def test_breaking_skips_min_gap(self):
        now = int(time.time()); out = self.go([card(1, BRK)], [{"id": "o", "at": now - 60, "ok": True}])
        self.assertIn("DRY RUN", out)
    def test_normal_waits_min_gap(self):
        now = int(time.time()); out = self.go([card(2, NRM)], [{"id": "o", "at": now - 60, "ok": True}])
        self.assertNotIn("DRY RUN", out); self.assertIn("min gap", out)
    def test_breaking_posts_dont_use_normal_cap(self):
        out = self.go([card(2, NRM)], self.full(breaking=True)); self.assertIn("DRY RUN", out)
    def test_breaking_safety_limit(self):
        now = int(time.time()); log = [{"id": f"b{i}", "at": now - 600 - i, "ok": True, "breaking": True} for i in range(XP.BREAKING_MAX_24H)]
        out = self.go([card(1, BRK)], log); self.assertNotIn("DRY RUN", out); self.assertIn("safety limit", out)
    def test_untrusted_breaking_not_exempt(self):
        c = card(1, BRK); c["trusted"] = 0; c["sources"] = 8
        out = self.go([c], self.full()); self.assertNotIn("DRY RUN", out)
if __name__ == "__main__": unittest.main()
