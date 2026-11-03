import pages
def test_feeds_page():
    h = pages.feeds_page()
    assert 'noindex,follow' in h and '/feed.xml' in h and '/es/feed.xml' in h
    for s in pages.FEED_CATS.values(): assert f'/feed/{s}.xml' in h
