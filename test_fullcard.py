"""Full Card reports (fullcard.py), homepage lead pin (toppick.pinned) and the Spanish/YouTube-clip block (aggregator.foreign_or_clip)."""
import os, sys, json, tempfile, datetime, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fullcard as F, toppick, pages
PAGE = """<meta property="og:image" content="https://www.wwe.com/f/sd.jpg" />
<a href="/x#1" data-tracking-label="contentTitle=a|contentType=quickHit|slot=1" class="x">Chelsea Green defends WWE Women&#039;s Title against Roxanne Perez</a>
<a href="/x#2" data-tracking-label="contentTitle=b|contentType=quickHit|slot=1" class="x">Giulia takes on Blake Monroe in a Street Fight</a>
<a href="/x#3" data-tracking-label="contentTitle=c|contentType=quickHit|slot=1" class="x">The MFTs once again collide with Bakusai</a>"""
FRI = datetime.datetime(2026, 10, 23, 0, 0, tzinfo=datetime.timezone.utc).timestamp()   # Thu night ET, show Fri 8 PM ET
def story(i, title, summ, ts): return {"id": i, "title": title, "summary": summ, "first_ts": ts, "ts": ts, "link": "https://x/" + i, "categories": ["WWE"], "updates": []}
class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); F.STATE = os.path.join(self.d, "fc.json"); F.MANUAL = os.path.join(self.d, "m.json")
        self.cl = [story("cg", "Chelsea Green To Defend WWE Women's Title On SmackDown", "Green vs Roxanne Perez on the October 23 SmackDown.", FRI - 86400),
                   story("nb", "Nikki Bella vs Chelsea Green Title Match Set For Oct. 30 SmackDown", "Nikki Bella challenges Chelsea Green.", FRI - 5 * 86400),
                   story("sf", "Street Fight and Two Tag Matches Booked for SmackDown", "Giulia faces Blake Monroe; The MFTs vs Bakusai.", FRI - 5 * 86400)]
    def run_(self, html, now=FRI, cl=None): return F.run(self.cl if cl is None else cl, now=now, fetch=lambda u: html, log=lambda *a: None)
    def test_parse_and_names(self):
        lines, img = F.parse_wwe(PAGE)
        self.assertEqual(lines[0], "Chelsea Green defends WWE Women's Title against Roxanne Perez"); self.assertEqual(img, "https://www.wwe.com/f/sd.jpg")
        self.assertEqual(F.names(lines[0]), ["Chelsea", "Green", "Roxanne", "Perez"])
    def test_report_built_and_linked(self):
        out = self.run_(PAGE); self.assertEqual(len(out), 1); c = out[0]
        self.assertEqual(c["title"], "WWE SmackDown Full Card For October 23, 2026"); self.assertEqual(c["categories"], ["WWE"])
        self.assertIn("-full-card-", pages.slugify(c["title"]) + "-" + c["id"])
        self.assertEqual([i["sid"] for i in c["card"]], ["cg", "sf", "sf"])   # Nikki (Oct 30) story is not linked to Green vs Perez
        self.assertTrue(c["lead_until"] > FRI and c["link"].endswith("/shows/smackdown/2026-10-23") and c["fullcard"])
        self.assertIn("Roxanne Perez", c["summary"]); self.assertIn(c, self.cl)
    def test_change_updates_same_report(self):
        a = self.run_(PAGE)[0]; ids = {c["id"] for c in self.cl}
        more = PAGE + '<a data-tracking-label="contentType=quickHit" href="#">CM Punk addresses the WWE Universe</a>'
        b = self.run_(more, now=FRI + 2 * 3600)[0]
        self.assertEqual(a["id"], b["id"]); self.assertEqual(len(b["card"]), 4); self.assertEqual(b["first_ts"], a["first_ts"]); self.assertGreater(b["ts"], a["ts"])
        self.assertEqual(sum(1 for c in self.cl if c.get("fullcard")), 1); self.assertEqual({c["id"] for c in self.cl}, ids)
    def test_no_or_incomplete_card_no_report(self):
        self.assertEqual(self.run_("<html>no preview yet</html>"), [])
        one = PAGE.split("\n")[1]
        self.assertEqual(self.run_(PAGE.split("\n")[0] + one, now=FRI + 3 * 3600), [])
    def test_far_from_show_not_fetched(self):
        seen = []
        F.run(self.cl, now=FRI - 4 * 86400, fetch=lambda u: seen.append(u) or PAGE, log=lambda *a: None)
        self.assertFalse(any("2026-10-23" in u for u in seen))
    def test_manual_card_any_promotion(self):
        json.dump({"cards": {"aew-dynamite/2026-10-28": {"matches": ["Hangman Page vs. Swerve Strickland", "Toni Storm defends against Mariah May"],
                   "source": "https://www.allelitewrestling.com/x", "source_name": "AEW"}}}, open(F.MANUAL, "w"))
        now = datetime.datetime(2026, 10, 28, 12, tzinfo=datetime.timezone.utc).timestamp()
        out = F.run([], now=now, fetch=lambda u: "", log=lambda *a: None)
        self.assertEqual([c["title"] for c in out], ["AEW Dynamite Full Card For October 28, 2026"]); self.assertEqual(out[0]["categories"], ["AEW"])
    def test_lead_pin_until_show(self):
        items = [{"id": f"s{i}", "title": "x", "ts": FRI, "first_ts": FRI, "imp": 30 - i, "image": "https://i/x.jpg", "img_w": 1200, "categories": ["WWE"]} for i in range(10)]
        card = {"id": "fc", "title": "card", "ts": FRI, "first_ts": FRI, "imp": 1, "image": "https://www.wwe.com/f/sd.jpg", "img_w": 1024, "categories": ["WWE"], "lead_until": FRI + 20 * 3600}
        self.assertEqual(toppick.pick(items + [card], now=FRI + 3600)[0]["id"], "fc")
        self.assertEqual(toppick.pick(items + [card], now=FRI + 21 * 3600)[0]["id"], "s0")   # show started: normal ranking
        nophoto = dict(card, image="/img/promo/wwe.jpg", img_w=None)
        self.assertEqual(toppick.pick(items + [nophoto], now=FRI + 3600)[0]["id"], "s0")   # lead keeps the real-photo rule
    def test_spanish_and_youtube_blocked(self):
        import aggregator as G
        es = {"raw_title": "Cody Rhodes le propina PUNT a Baron Corbin frente a Randy Orton: SmackDown highlights, 16 de Oct. 2026 - WWE", "link": "https://www.wwe.com/videos/x"}
        self.assertTrue(G.not_news(es)); self.assertTrue(G.not_news({"raw_title": "Resumen Completo de Money in the Bank 2026 - WWE", "link": "https://www.wwe.com/videos/y"}))
        self.assertTrue(G.not_news({"raw_title": "Full SmackDown highlights: Oct. 16, 2026", "link": "https://www.youtube.com/watch?v=1"}))
        for t in ["Cody Rhodes PUNTS Baron Corbin: SmackDown highlights, Oct. 16, 2026 - WWE", "La Parka and Los Garza return at Del Rio's show",
                  "Penta Reveals How His Family Helped Him Choose WWE Over AEW"]:
            self.assertFalse(G.foreign_or_clip({"raw_title": t, "link": "https://www.wwe.com/videos/z"}), t)
if __name__ == "__main__": unittest.main()
