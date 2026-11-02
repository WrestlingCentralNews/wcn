"""R5 (2026-11-02) build check, run after aggregator.py and before deploy. Fails the run (exit 1, so nothing is deployed) when
(a) a story id that was live last run now has a different URL (owner rule: a published URL never changes), or
(b) a published URL would not be served: any story URL in data/url_registry.json / legacy_urls.json, or any URL in this build's
    sitemaps, with no file in public/ (GitHub Pages would answer 404).
Prints only paths and ids. Usage: python urlguard.py [--prev data/prev_news.json]"""
import json, os, re, sys
ROOT = os.path.dirname(os.path.abspath(__file__)); PUB = os.path.join(ROOT, "public"); SITE = "https://wrestlingcentralnews.com/"
def served(path):
    path = path.split("?")[0].split("#")[0].lstrip("/")
    if path == "" : return os.path.exists(os.path.join(PUB, "index.html"))
    f = os.path.join(PUB, path)
    return os.path.isfile(f) or os.path.isfile(os.path.join(f, "index.html"))
def items(p):
    try: d = json.load(open(p))
    except Exception: return []
    return d.get("items", d) if isinstance(d, dict) else d
def check(prev_items, cur_items, registry, sitemap_urls):
    errs = []
    cur = {c["id"]: c.get("url") for c in cur_items if c.get("id")}
    for p in prev_items:
        i, u = p.get("id"), p.get("url") or ""
        if i in cur and u.startswith("story/") and cur[i] != u: errs.append(f"URL changed for {i}: {u} -> {cur[i]}")
    for u in registry:
        if not served(u): errs.append(f"published URL not served: {u}")
    for u in sitemap_urls:
        if not served(u.replace(SITE, "")): errs.append(f"sitemap URL not served: {u}")
    return errs
def main():
    a = sys.argv[1:]; prevf = a[a.index("--prev") + 1] if "--prev" in a else os.path.join(ROOT, "data", "prev_news.json")
    reg = list((json.load(open(os.path.join(ROOT, "data", "url_registry.json"))) if os.path.exists(os.path.join(ROOT, "data", "url_registry.json")) else {}).keys())
    try: reg += json.load(open(os.path.join(ROOT, "legacy_urls.json"))).get("story", [])
    except Exception: pass
    sm = []
    for f in ("sitemap.xml", "es/sitemap.xml", "sitemap-news.xml"):
        try: sm += re.findall(r"<loc>([^<]+)</loc>", open(os.path.join(PUB, f)).read())
        except Exception: pass
    errs = check(items(prevf), items(os.path.join(PUB, "news.json")), reg, sm)
    print(f"urlguard: {len(reg)} registry URLs, {len(sm)} sitemap URLs, {len(errs)} problems", flush=True)
    for x in errs[:50]: print("::error::urlguard " + x, flush=True)
    sys.exit(1 if errs else 0)
if __name__ == "__main__": main()
