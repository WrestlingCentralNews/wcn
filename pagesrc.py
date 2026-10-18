"""Sources with no usable RSS feed (PWInsider, WWE.com, TNA, Stardom, Bleacher Report): read the public news listing page,
take article links that weren't there before, and read each new article's public meta tags (title/description/photo).
Only public pages are read; nothing behind a login or paywall. State: data/pagesrc.json (saved with the rest of data/).
- First time a source is seen, every link already on the page is recorded as a baseline and NOT emitted (no backlog flood).
- After that, a link is emitted once, on the run that first sees it; its time is the page's own date when it has one
  (JSON-LD datePublished / a date in the URL), else the first-seen time. Anything dated over MAX_AGE_H old is skipped.
The box watcher (watcher/wcn_watch.py) uses LISTINGS + links() to spot new items between runs."""
import json, os, re, time, html, urllib.request, urllib.parse, datetime as dt
from concurrent.futures import ThreadPoolExecutor
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 WCN/1.0"}
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "pagesrc.json")
MAX_AGE_H = 48
MAX_NEW_PER_RUN = 12
# name -> (listing url, article-link regex, default category, title suffix to strip)
LISTINGS = {
 "PWInsider":       ("https://www.pwinsider.com/", r"/article/\d+/[a-z0-9-]+\.html", None, r"\s*\|\s*PWInsider(\.com)?$"),
 "WWE.com":         ("https://www.wwe.com/news", r"/article/[a-z0-9-]{12,}", "WWE", r"\s*\|\s*WWE$"),
 "TNA Wrestling":   ("https://tnawrestling.com/news/", r"/news/[a-z0-9-]{12,}", "TNA", r"\s*\|\s*TNA Wrestling$"),
 "STARDOM":         ("https://wwr-stardom.com/en/news/", r"/en/news/\d{6,8}[a-z0-9-]*/", "Global", r"\s*[|｜]\s*STARDOM.*$"),
 "Bleacher Report": ("https://bleacherreport.com/wrestling", r"/articles/\d+-[a-z0-9-]+", None, r"\s*\|\s*Bleacher Report.*$"),
}
# listing pages that also link other sports: keep only links whose URL slug names pro wrestling
SLUG_OK = {"Bleacher Report": r"wwe|aew|tna|nxt|\braw\b|-raw-|smackdown|wrestlemania|summerslam|royal-rumble|survivor-series|crown-jewel|wrestledream|"
                              r"full-gear|all-in|dynamite|collision|njpw|-roh-|stardom|aaa|cmll|pro-wrestling|wrestling-"}
ACR = set("WWE AEW TNA NXT ROH NJPW AAA CMLL MLW GCW NWA PWG IWGP DDT NOAH AJPW TJPW PPV PLE TV US UK USA UFC WWF WCW ECW NCAA ESPN TBS TNT CEO NBC FOX".split())
def get(url, t=15):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=t).read()[:2500000].decode("utf8", "ignore")
def links(name, h):
    base, rx = LISTINGS[name][0], LISTINGS[name][1]
    out = []
    for l in re.findall(r'href="([^"#]+)"', h):
        l = urllib.parse.urljoin(base, html.unescape(l)).split("?")[0]
        if re.search(rx, urllib.parse.urlparse(l).path) and urllib.parse.urlparse(l).netloc.endswith(urllib.parse.urlparse(base).netloc.replace("www.", "")):
            if name in SLUG_OK and not re.search(SLUG_OK[name], l.rsplit("/", 1)[-1]): continue
            if l not in out: out.append(l)
    return out
def _meta(h, p):
    m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]*content=["\']([^"\']*)' % p, h) or \
        re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']%s["\']' % p, h)
    return html.unescape(html.unescape(m.group(1))).strip() if m else None
def _date(url, h):
    for rx in (r'"datePublished"\s*:\s*"([^"]+)"', r'property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)'):
        m = re.search(rx, h)
        if m:
            try: return dt.datetime.fromisoformat(m.group(1).replace("Z", "+00:00")).timestamp()
            except Exception: pass
    m = re.search(r"(20\d\d)(\d\d)(\d\d)", url) or re.search(r"(20\d\d)/(\d\d)/(\d\d)", url)
    if m:
        try: return dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), 12, tzinfo=dt.timezone.utc).timestamp()
        except Exception: pass
    return None
def article(name, url):
    h = get(url, 12)
    t = _meta(h, "og:title") or (re.search(r"<title>\s*([^<]+?)\s*</title>", h) or [None, None])[1]
    if not t: return None
    t = re.sub(LISTINGS[name][3], "", html.unescape(t)).strip()
    if t.isupper() and len(t) > 12:                        # PWInsider headlines are ALL CAPS
        t = re.sub(r"[A-Za-z][A-Za-z']*", lambda m: m.group(0) if m.group(0) in ACR else m.group(0).capitalize(), t)
    return {"title": t, "desc": _meta(h, "og:description") or "", "image": _meta(h, "og:image"), "ts": _date(url, h)}
def load():
    try: return json.load(open(STATE))
    except Exception: return {}
def save(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    for k in st: st[k]["seen"] = dict(sorted(st[k]["seen"].items(), key=lambda kv: -kv[1])[:400])
    json.dump(st, open(STATE, "w"))
def fetch_all(status=None):
    """-> list of new items (aggregator.parse() shape minus id/categories, plus 'cat'), one pass over every listing."""
    st, now, out = load(), int(time.time()), []
    def one(name):
        try: return name, links(name, get(LISTINGS[name][0])), None
        except Exception as e: return name, [], str(e)[:120]
    with ThreadPoolExecutor(5) as ex: res = list(ex.map(one, LISTINGS))
    todo = []
    for name, ls, err in res:
        s = st.setdefault(name, {"seen": {}, "baseline": False})
        if status is not None: status[name] = {"ok": err is None and len(ls) > 0, "items": len(ls), "error": err, "kind": "page"}
        if not ls: continue
        if not s["baseline"]:
            for l in ls: s["seen"][l] = now
            s["baseline"] = True; continue
        fresh = [l for l in ls if l not in s["seen"]][:MAX_NEW_PER_RUN]
        for l in fresh: s["seen"][l] = now
        todo += [(name, l) for l in fresh]
    def art(nl):
        try: return nl, article(*nl)
        except Exception: return nl, None
    with ThreadPoolExecutor(8) as ex:
        for (name, l), a in ex.map(art, todo):
            if not a: continue
            if a["ts"] and a["ts"] < now - MAX_AGE_H * 3600: continue      # an old article newly linked from the page
            out.append({"title": a["title"], "summary": a["desc"], "link": l, "source": name, "ts": int(a["ts"]) if a["ts"] and a["ts"] <= now else None,
                        "image": a["image"], "cat": LISTINGS[name][2]})
    save(st)
    return out
if __name__ == "__main__":
    for name in LISTINGS:
        try: ls = links(name, get(LISTINGS[name][0])); print(name, len(ls), ls[:3])
        except Exception as e: print(name, "error", e)
