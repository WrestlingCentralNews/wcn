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
class Alias(unittest.TestCase):
    def test_old_addresses_are_real_pages(self):
        import tempfile, os
        d = tempfile.mkdtemp(); ed = tempfile.mkdtemp()
        red = {"story/old-merged-abc.html": {"to": "story/new-xyz.html", "es": False},
               "story/gone-def.html": {"to": "?promo=WWE", "es": False, "cat": "WWE"}}
        n = pages.alias_pages(red, {"story/new-xyz.html": "<html>FULL STORY</html>"}, [st()], {}, d, ed)
        self.assertEqual((n["story"], n["gone"]), (1, 1))
        self.assertEqual(open(os.path.join(d, "old-merged-abc.html")).read(), "<html>FULL STORY</html>")
        a = open(os.path.join(d, "gone-def.html")).read()   # 200 page in place: no redirect, no 'archived' wording, noindex, self canonical
        for bad in ('http-equiv="refresh"', 'location.replace("/', "rchiv", "no longer"): self.assertNotIn(bad, a)
        self.assertIn("noindex,follow", a); self.assertIn("Latest WWE news", a)
        self.assertIn('rel="canonical" href="https://wrestlingcentralnews.com/story/gone-def.html"', a)
        open(os.path.join(d, "keep.html"), "w").write("LIVE")
        pages.alias_pages({"story/keep.html": {"to": "story/new-xyz.html"}}, {"story/new-xyz.html": "X"}, [], {}, d, ed)
        self.assertEqual(open(os.path.join(d, "keep.html")).read(), "LIVE")   # a live page is never overwritten
class Mismatch(unittest.TestCase):
    def test_wrong_merge_rebuilt_or_archived(self):
        import tempfile, os
        d = tempfile.mkdtemp(); ed = tempfile.mkdtemp()
        surv = st(id="c0a7232efef7c", title="NXT Viewership Rises To 732,000 For October 13 Episode", url="story/nxt-viewership-c0a7232efef7c.html",
                  link="https://v/1")
        A = {"https://p/smackdown": {"link": "https://p/smackdown", "title": "Cody Rhodes Delivers Punt on SmackDown", "source": "POST Wrestling",
             "ts": 1792204547, "categories": ["WWE"], "summary": "Cody Rhodes finally unleashed the Punt kick on SmackDown. " * 4}}
        red = {"story/cody-rhodes-delivers-punt-on-smackdown-c0a7232efef7c.html": {"to": surv["url"], "lead": "https://p/smackdown", "links": ["https://p/smackdown"], "es": False},
               "story/old-gone-c0a7232efef7d.html": {"to": surv["url"], "lead": "https://p/gone", "links": ["https://p/gone"], "es": False, "cat": "WWE"},
               "story/nxt-ratings-c0a7232efef7e.html": {"to": surv["url"], "lead": "https://v/1", "links": ["https://v/1"], "es": False}}
        n = pages.alias_pages(red, {surv["url"]: "<html>NXT PAGE</html>"}, [surv], {}, d, ed, A=A)
        self.assertEqual((n["mismatch"], n["rebuilt"], n["gone"], n["story"]), (2, 1, 1, 1))
        h = open(os.path.join(d, "cody-rhodes-delivers-punt-on-smackdown-c0a7232efef7c.html")).read()
        self.assertIn("Cody Rhodes Delivers Punt", h); self.assertNotIn("NXT PAGE", h)
        self.assertIn('rel="canonical" href="https://wrestlingcentralnews.com/story/cody-rhodes-delivers-punt-on-smackdown-c0a7232efef7c.html"', h)
        self.assertIn("noindex", open(os.path.join(d, "old-gone-c0a7232efef7d.html")).read())
        self.assertEqual(open(os.path.join(d, "nxt-ratings-c0a7232efef7e.html")).read(), "<html>NXT PAGE</html>")
if __name__ == "__main__": unittest.main()
