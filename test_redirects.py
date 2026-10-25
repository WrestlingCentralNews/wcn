"""Story/event URLs that ever existed never 404 while they are inside the 60-day window."""
import os, json, tempfile, unittest, time
import pages, hubs

def cl(i, title, cat="AEW", link=None):
    return {"id": i, "title": title, "url": f"story/{pages.slugify(title)}-{i}.html", "categories": [cat], "link": link or f"https://x.test/{i}", "updates": []}

class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.o = (pages.REDIRECTS, pages.URL_REG, pages.ROOT)
        pages.REDIRECTS = os.path.join(self.d, "r.json"); pages.URL_REG = os.path.join(self.d, "reg.json"); pages.PREV = []
    def tearDown(self): pages.REDIRECTS, pages.URL_REG, pages.ROOT = self.o
    def test_registry_url_gone_without_prev_state(self):
        a = cl("c111111111111", "Kenny Omega targets Wrestle Kingdom title shot")
        pages.redirects([a], {}, {})                        # run 1 records the URL
        b = cl("c222222222222", "Kenny Omega targets Wrestle Kingdom title shot")   # re-published under a new id, PREV lost
        out = pages.redirects([b], {}, {})
        self.assertEqual(out[a["url"]]["to"], b["url"])
    def test_gone_story_goes_to_promotion_section(self):
        a = cl("c333333333333", "TNA presents Bound for Glory today", cat="TNA")
        pages.redirects([a], {}, {})
        out = pages.redirects([cl("c444444444444", "Will Ospreay retains AEW world title")], {}, {})
        self.assertEqual(out[a["url"]]["to"], "?promo=TNA")
    def test_no_mixing_different_wrestlers(self):
        a = cl("c555555555555", "Mercedes Mone retains AEW women's title at WrestleDream")
        pages.redirects([a], {}, {})
        out = pages.redirects([cl("c666666666666", "Will Ospreay retains AEW world title at WrestleDream")], {}, {})
        self.assertFalse(out[a["url"]]["to"].startswith("story/"))
    def test_reused_id_different_topic_not_followed(self):
        a = cl("c777777777777", "AEW Collision draws 372K viewers on October 10")
        pages.redirects([a], {}, {})
        out = pages.redirects([cl("c777777777777", "Sami Zayn wins on SmackDown in Sacramento", cat="WWE")], {}, {})
        self.assertFalse(out[a["url"]]["to"].startswith("story/"))
    def test_hub_gone_target(self):
        self.assertEqual(hubs.gone_target("events/2026-09-05-aew-collision/"), "shows/aew-collision/")
        self.assertEqual(hubs.gone_target("es/eventos/resultados-aew-dynamite-2026-09-23/"), "es/programas/aew-dynamite/")
        self.assertEqual(hubs.gone_target("events/2026-10-12-aew-wrestledream/"), "upcoming/")
if __name__ == "__main__": unittest.main()
