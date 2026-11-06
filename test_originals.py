"""WCN Originals: permanent, indexed, in sitemaps, honest byline/disclosure. No network."""
import os, re, tempfile, time
import originals, index_tier, stale, chrome

SENT = "By GONEdii Gazette G. Drafted with AI from WCN's confirmed records, then edited and fact-checked by our team."

def test_published_piece_and_flags():
    assert originals.ORIGINALS_LIVE and chrome.ORIGINALS_NAV
    ps = originals.pieces()
    assert any(p["slug"] == "312-days-jon-moxley-continental-champion" for p in ps)

def test_build_pages():
    d = tempfile.mkdtemp(); n = originals.build(d); assert n >= 1
    idx = open(os.path.join(d, "originals", "index.html")).read()
    assert "/originals/312-days-jon-moxley-continental-champion/" in idx
    art = open(os.path.join(d, "originals", "312-days-jon-moxley-continental-champion", "index.html")).read()
    assert "noindex" not in art and "AnalysisNewsArticle" in art
    assert "By <a" in art and "GONEdii Gazette G." in art and originals.DISCLOSURE.replace("'", "&#x27;") in art
    col = open(os.path.join(d, "originals", originals.COLUMN_SLUG, "index.html")).read()
    assert SENT.replace("'", "&#x27;") in col
    for h in (art, col, idx): assert "AI-assisted" not in h

def test_nav():
    h = chrome.header("en", "/", None); assert "/originals/" in h and "Originals" in h
    assert "Originales" in chrome.header("es", "/es/", None)

def test_sitemap_and_news():
    u = originals.sitemap_urls()
    assert chrome.SITE + "originals/" in u and chrome.SITE + "originals/312-days-jon-moxley-continental-champion/" in u
    p = [x for x in originals.pieces() if x.get("ts")][0]
    assert originals.news_entries(now=p["ts"] + 3600)
    assert not originals.news_entries(now=p["ts"] + 49 * 3600)

def test_permanent_and_indexed():
    assert originals.is_original("/originals/x/")
    assert index_tier.tier({"url": "originals/x/", "title": "x"})[0] == "index"
    assert stale.reason({"link": "https://wrestlingcentralnews.com/originals/x/", "ts": time.time()}) is None

if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"): f(); print("ok", k)
