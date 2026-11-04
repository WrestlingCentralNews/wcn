import json, os, tempfile, pages
def run(clusters, prev, path, reg=None):
    pages.PREV, keep = prev, pages.URL_REG
    pages.URL_REG = reg or os.path.join(os.path.dirname(path), "none.json")
    try: pages.assign_urls(clusters, path)
    finally: pages.URL_REG = keep
    return [c["url"] for c in clusters]
def test_first_slug_frozen():
    d = tempfile.mkdtemp(); p = os.path.join(d, "s.json")
    assert run([{"id": "c5b4b4410a9f1", "title": "WWE signs Elly Finch"}], [], p) == ["story/wwe-signs-elly-finch-c5b4b4410a9f1.html"]
    # headline rewritten and previous-run state lost: URL must not change
    assert run([{"id": "c5b4b4410a9f1", "title": "Elly Finch debuts on NXT"}], [], p) == ["story/wwe-signs-elly-finch-c5b4b4410a9f1.html"]
    assert json.load(open(p)) == {"c5b4b4410a9f1": "story/wwe-signs-elly-finch-c5b4b4410a9f1.html"}
def test_existing_keeps_current_url():
    d = tempfile.mkdtemp(); p = os.path.join(d, "s.json"); r = os.path.join(d, "reg.json")
    json.dump({"story/old-a-c000000000001.html": {"seen": 1}, "story/current-a-c000000000001.html": {"seen": 9}}, open(r, "w"))
    assert run([{"id": "c000000000001", "title": "Brand new title"}], [], p, r) == ["story/current-a-c000000000001.html"]
    prev = [{"id": "c000000000002", "url": "story/live-b-c000000000002.html"}]
    assert run([{"id": "c000000000002", "title": "Other"}], prev, p, r) == ["story/live-b-c000000000002.html"]
