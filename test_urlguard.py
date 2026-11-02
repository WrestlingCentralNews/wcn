import os, tempfile, urlguard
def test_guard():
    d = tempfile.mkdtemp(); urlguard.PUB = d
    os.makedirs(os.path.join(d, "story")); open(os.path.join(d, "story/a.html"), "w").close()
    os.makedirs(os.path.join(d, "events/x")); open(os.path.join(d, "events/x/index.html"), "w").close()
    ok = urlguard.check([{"id": "1", "url": "story/a.html"}], [{"id": "1", "url": "story/a.html"}], ["story/a.html"], [urlguard.SITE + "events/x/"])
    assert ok == []
    bad = urlguard.check([{"id": "1", "url": "story/a.html"}], [{"id": "1", "url": "story/b.html"}], ["story/gone.html"], [urlguard.SITE + "events/y/"])
    assert len(bad) == 3
if __name__ == "__main__": test_guard(); print("ok")
