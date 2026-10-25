"""Pages carrying a robots noindex meta never go in a sitemap (EN, ES or news)."""
import os, sys, tempfile, time, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extras, pages

def story(i, words):
    return {"id": f"id{i}", "url": f"story/s{i}.html", "title": f"Story {i}", "summary": " ".join(["word"] * words), "long": [" ".join(["word"] * words)],
            "ts": time.time(), "first_ts": time.time(), "categories": ["WWE"], "link": "https://example.com/x"}

class T(unittest.TestCase):
    def test_noindex_follows_thin(self):
        self.assertTrue(pages.noindex(story(1, 10))); self.assertFalse(pages.noindex(story(2, 200)))
    def test_news_sitemap_skips(self):
        d = tempfile.mkdtemp(); old = extras.PUB; extras.PUB = d
        try:
            cs = [story(1, 10), story(2, 200)]; tr = {"id1": {"url": "es/noticias/a.html", "t": "A"}, "id2": {"url": "es/noticias/b.html", "t": "B"}}
            n = extras.news_sitemap(cs, tr, skip=lambda c, lang: pages.noindex(c, lang))
            x = open(os.path.join(d, "sitemap-news.xml")).read()
            self.assertEqual(n, 2); self.assertIn("story/s2.html", x); self.assertIn("es/noticias/b.html", x)
            self.assertNotIn("story/s1.html", x); self.assertNotIn("es/noticias/a.html", x)
            self.assertEqual(extras.news_sitemap(cs, tr), 4)   # no predicate: unchanged behaviour
        finally: extras.PUB = old

if __name__ == "__main__": unittest.main()
