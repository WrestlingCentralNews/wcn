"""Full Card reports on X (x_poster.card_text / card_due / run): one clean card-list post per show, regular (never BREAKING),
link-free 'link in bio', @promotion tag + show hashtag, <= 280 chars (appearances trimmed first), never reposted on card updates."""
import os, sys, json, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import x_poster as X
START = 1792800000            # 2026-10-24 00:00 UTC = Fri Oct 23 8 PM ET
NOW = START - 10 * 3600   # Fri 10 AM ET
LINES = ["Chelsea Green defends WWE Women's Title against Roxanne Perez", "Giulia takes on Blake Monroe in a Street Fight",
         "Michin & B-Fab challenge Alexa Bliss & Tatum Paxley for the WWE Women’s Tag Team Title", "The MFTs once again collide with Bakusai"]
def card(**k):
    c = {"id": "c6043e880ffa3", "title": "WWE SmackDown Full Card For October 23, 2026", "summary": "x", "link": "https://www.wwe.com/shows/smackdown/2026-10-23",
         "ts": NOW, "first_ts": NOW, "categories": ["WWE"], "kind": {"type": "news"}, "updates": [], "sources": 1, "trusted": 1,
         "fullcard": "wwe-smackdown/2026-10-23", "show_name": "WWE SmackDown", "lead_until": START, "image": "https://www.wwe.com/f/sd.jpg",
         "image_status": "override", "card": [{"line": l, "sid": None} for l in LINES],
         "appearances": ["CM Punk", "Cody Rhodes", "Jade Cargill", "Tiffany Stratton", "Gunther", "Trick Williams", "Karl Anderson"]}
    c.update(k); return c
class T(unittest.TestCase):
    def test_text(self):
        t = X.card_text(card(), NOW)
        self.assertEqual(t, "SmackDown Tonight: Full Card\n\n- Chelsea Green (c) vs. Roxanne Perez: Women's Title\n- Giulia vs. Blake Monroe: Street Fight\n"
                            "- Alexa Bliss & Tatum Paxley (c) vs. Michin & B-Fab: Women's Tag Team Title\n- The MFTs vs. Bakusai\n\n"
                            "@WWE #SmackDown #WWE\nFull card: link in bio")
        self.assertLessEqual(X.x_len(t), 280); self.assertFalse(X.has_url(t)); self.assertFalse(X.is_breaking(card()))
    def test_appearances_kept_when_room_and_trimmed_first(self):
        t = X.card_text(card(card=[{"line": LINES[1]}, {"line": LINES[3]}]), NOW)
        self.assertIn("Also advertised: CM Punk, Cody Rhodes", t); self.assertIn(": Street Fight", t); self.assertLessEqual(X.x_len(t), 280)
        many = card(card=[{"line": f"Wrestler{i} Longname{i} takes on Opponent{i} Surname{i} in a Last Man Standing Match"} for i in range(6)])
        t = X.card_text(many, NOW); self.assertLessEqual(X.x_len(t), 280); self.assertNotIn("Also advertised", t); self.assertIn("+ more", t)
    def test_when_and_handles(self):
        self.assertTrue(X.card_text(card(), START - 30 * 3600).startswith("SmackDown Tomorrow: Full Card"))
        aew = card(fullcard="aew-dynamite/2026-10-28", show_name="AEW Dynamite", categories=["AEW"], title="AEW Dynamite Full Card For October 28, 2026",
                   card=[{"line": "Hangman Page vs. Swerve Strickland in a Texas Death Match"}, {"line": "Toni Storm defends the AEW Women's World Championship against Mariah May"}])
        t = X.card_text(aew, NOW); self.assertIn("@AEW #AEWDynamite #AEW", t); self.assertIn("Toni Storm (c) vs. Mariah May: Women's World Championship", t)
    def test_due_only_before_show(self):
        self.assertTrue(X.card_due(card(), NOW)); self.assertFalse(X.card_due(card(), START + 1)); self.assertFalse(X.card_due(card(card=[{"line": "x"}]), NOW))
    def run_x(self, items, state=None):
        d = tempfile.mkdtemp(); X.NEWS = os.path.join(d, "n.json"); X.STATE = os.path.join(d, "s.json"); X.LIVE_STATE = os.path.join(d, "none.json")
        json.dump({"items": items}, open(X.NEWS, "w")); json.dump(state or {}, open(X.STATE, "w"))
        os.environ["X_POST_ENABLED"] = "0"; out = []; X.log = lambda *a: out.append(" ".join(map(str, a)))
        X.time.time, real = (lambda: NOW), X.time.time
        try: X.run()
        finally: X.time.time = real
        return out
    def test_run_picks_card_once(self):
        low = card(id="s1", fullcard=None, title="Some story", first_ts=NOW - 3600)
        out = self.run_x([low, card(ts=NOW - 600)])
        self.assertTrue(any("DRY RUN" in l and "SmackDown Tonight: Full Card" in l for l in out), out); self.assertFalse(any("Some story" in l for l in out))
        out = self.run_x([card(ts=NOW)], {"posted": {"c6043e880ffa3": {"tweet": "1", "at": NOW - 999}}})   # card changed later: same id -> no repost
        self.assertFalse(any("DRY RUN" in l for l in out), out)
    def test_run_respects_cap(self):
        log = [{"ok": True, "at": NOW - 100 * i - 3000, "id": f"p{i}"} for i in range(X.DAILY_CAP)]
        out = self.run_x([card()], {"log": log}); self.assertTrue(any("daily cap" in l for l in out), out)
if __name__ == "__main__": unittest.main()
