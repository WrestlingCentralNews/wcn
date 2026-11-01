import unittest, re, time
import pages, translate, indie_gate, live, hubs, extras
def st(**k):
    c = {"id": "abc", "title": "Local show draws a crowd", "summary": " ".join(["word"] * 80), "categories": ["WWE"],
         "updates": [], "imp": 5, "url": "/news/x.html", "source": "S", "link": "https://s/x", "ts": time.time()}
    c.update(k); return c
class T(unittest.TestCase):
    def test_es_top(self):
        self.assertFalse(translate.es_top(st()))
        self.assertTrue(translate.es_top(st(imp=17)))
        self.assertTrue(translate.es_top(st(brk=1)))
        self.assertTrue(translate.es_top(st(kind={"type": "results"})))
        self.assertTrue(translate.es_top(st(), {"top": 1}))
    def test_es_noindex_non_top(self):
        L = {"t": "Un luchador firma", "s": "x", "url": "/es/news/x.html"}
        self.assertTrue(pages.noindex(st(), "es", L))
    def test_indie_global_minor(self):
        self.assertTrue(indie_gate.minor(st(categories=["Indie"])))
        self.assertTrue(pages.noindex(st(categories=["Global"])))
        self.assertFalse(indie_gate.minor(st(categories=["Global"], title="AAA Triplemania card set")))
        self.assertFalse(indie_gate.minor(st(categories=["Indie"], brk=1)))
        self.assertFalse(indie_gate.minor(st(categories=["Indie", "WWE"])))
        self.assertFalse(translate.es_top(st(categories=["Indie"], imp=30)))
    def test_no_kit_box_on_story(self):
        h = pages.page(st(), [])
        self.assertNotIn("kit.com", h.lower()); self.assertNotIn('<form', h)
    def test_glance(self):
        ms = [{"id": "m1", "winner": "A", "loser": "B", "fin_en": "pinfall", "title": "retain", "stip": "World Title"},
              {"id": "m2", "winner": "C", "loser": "D", "fin_en": "submission"}]
        g = live.glance(ms, "en")
        self.assertIn("At a glance", g); self.assertIn("2 matches · 1 successful title defenses · 0 title changes", g)
        self.assertEqual(live.glance(ms[:1], "en"), "")
    def test_strip(self):
        hubs.RECENT.clear(); self.assertEqual(extras.results_strip("en"), "")
        hubs.RECENT["en"] = [(time.time() - 3600, "events/raw-2026-10-27/", "Raw", "Oct 27", 9, False)]
        s = extras.results_strip("en"); self.assertIn('href="/events/raw-2026-10-27/"', s); self.assertIn("9 results", s)
        hubs.RECENT.clear()
class U(unittest.TestCase):
    def test_story_url_never_changes(self):
        old = "story/old-headline-words-abc.html"; pages.PREV[:] = [{"id": "abc", "url": old}]
        c = st(title="Completely different rewritten headline after update"); pages.assign_urls([c])
        self.assertEqual(c["url"], old); pages.PREV[:] = []
if __name__ == "__main__": unittest.main()
