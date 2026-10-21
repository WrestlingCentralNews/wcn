"""Freshness rules (owner rule 2026-10-21): only up-to-date reports become news, old news is never presented as new.
A report's date is its REAL publish date, in this order: the article page's own published time (article:published_time,
og/itemprop datePublished, JSON-LD datePublished, <time pubdate>), a date in the URL path (/2022/12/...), then the feed's
pubDate when the feed is the outlet's own. 'updated'/'modified' dates and re-crawls never count. Google News / listing-page
dates for official promotion sites (they resurface years-old pages) and first-seen guesses are NOT a date: such a report is
'undated' and only publishes when another trusted outlet reports the same story within 48 hours, or (official pages) under
the narrow rules in official_reason().
  * ingest: a new report published > MAX_AGE (48h) before we first saw it is dropped ('stale: ...');
    reports already stored before this rule use the 7-day sweep limit (SWEEP_AGE) instead;
  * clustering: an old report never leads a story (enrich.cluster lead order);
  * publish: aggregator holds a story whose lead is undated and uncorroborated (see corroborated())."""
import re, time, json, email.utils, datetime as dt
import stale, editorial
MAX_AGE = 48 * 3600
SWEEP_AGE = 7 * 86400
_PUB = [r'<meta[^>]+(?:property|name|itemprop)=["\'](?:article:published_time|og:published_time|article:published|datePublished|'
        r'publish[-_]?date|pubdate|parsely-pub-date|sailthru\.date|dc\.date\.issued|dcterms\.created)["\'][^>]*?content=["\']([^"\']+)',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*?(?:property|name|itemprop)=["\'](?:article:published_time|datePublished|pubdate|publish[-_]?date)["\']',
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'<time[^>]+(?:pubdate|itemprop=["\']datePublished["\'])[^>]*datetime=["\']([^"\']+)',
        r'<time[^>]+datetime=["\']([^"\']+)["\'][^>]*(?:pubdate|itemprop=["\']datePublished["\'])']
def parse(d):
    d = (d or "").strip()
    if not d: return None
    try:
        x = email.utils.parsedate_to_datetime(d)
        if x is not None: return (x if x.tzinfo else x.replace(tzinfo=dt.timezone.utc)).timestamp()
    except Exception: pass
    m = re.match(r"(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}(?::\d{2})?)(?:\.\d+)?\s*(Z|[+-]\d{2}:?\d{2})?)?", d)
    if not m: return None
    tz = (m.group(3) or "+00:00").replace("Z", "+00:00")
    if len(tz) == 5: tz = tz[:3] + ":" + tz[3:]
    try: return dt.datetime.fromisoformat(f"{m.group(1)}T{m.group(2) or '00:00'}{tz}").timestamp()
    except Exception: return None
_BYLINE = re.compile(r"(?i)\bBy\b.{0,200}?\bon (20\d\d-\d\d-\d\d \d\d:\d\d(?::\d\d)?)")   # PWInsider: 'By Mike Johnson on 2026-10-21 10:33:00' (US Eastern)
def page_published(h):
    """Publish time the article page states about itself (never its modified/updated time), or None."""
    for rx in _PUB:
        for m in re.finditer(rx, h or "", re.I):
            ts = parse(m.group(1))
            if ts and 946684800 < ts < time.time() + 86400: return int(ts)
    m = _BYLINE.search(h or "")
    if m:
        ts = parse(m.group(1).replace(" ", "T") + "-04:00")
        if ts and ts < time.time() + 86400: return int(ts)
    return None
def weak_feed_date(a):
    """The feed/listing date can't be trusted as the publish date."""
    src = a.get("source") or ""; via = a.get("via") or ""
    return bool(a.get("ts_guessed") or via == "pagesrc" or (stale.OFFICIAL.match(src) or src in ("WWE", "AEW", "TNA Wrestling", "Official: WWE.com", "Official: AEW", "Official: TNA", "Official: NJPW")))
def real_ts(a):
    """(int) best real publish time of report a, or None if undetermined."""
    if a.get("pub_ts"): return int(a["pub_ts"])
    ud = stale.url_date(a.get("link"))
    if ud:
        u = int(dt.datetime(ud.year, ud.month, ud.day, 23, 59, tzinfo=dt.timezone.utc).timestamp())
        return min(u, int(a["ts"])) if a.get("ts") and not weak_feed_date(a) else u
    if a.get("ts") and not weak_feed_date(a): return int(a["ts"])
    td = title_date(a)       # 'Raw highlights, Oct. 19, 2026' / 'Results 10/19/26': the page names its own date
    if td: return td
    slug = re.sub(r"[-_/]+", " ", re.sub(r"^[a-z]+://[^/]+", "", a.get("link") or "").split("?")[0])
    m = re.search(r"\b((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*) (\d{1,2}) ((?:19|20)\d\d)\b", slug, re.I)   # '...-highlights-oct-16-2026'
    if m:
        td = title_date({"raw_title": " ".join(m.groups())})
        if td: return td
    m = re.search(r"/(\d\d)(0[1-9]|1[0-2])([0-3]\d)news\b", a.get("link") or "")      # STARDOM '/en/news/261019news/'
    if m:
        try: return int(dt.datetime(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)), 23, 59, tzinfo=dt.timezone.utc).timestamp())
        except Exception: pass
    return None
_MON = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
def title_date(a):
    t = a.get("raw_title") or ""; ref = a.get("ts") or a.get("added") or time.time()
    y0 = time.gmtime(ref).tm_year
    m = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+((?:19|20)\d\d))?", t, re.I) \
        or re.search(r"\b(\d{1,2})(?:\s+de)?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?,?\s+((?:19|20)\d\d)", t, re.I)
    try:
        if m and m.group(1)[0].isdigit(): mo, d, y = _MON[m.group(2)[:3].lower()], int(m.group(1)), int(m.group(3))
        elif m: mo, d, y = _MON[m.group(1)[:3].lower()], int(m.group(2)), int(m.group(3) or y0)
        else:
            m = re.search(r"\b(1[0-2]|0?[1-9])[/.-]([12]\d|3[01]|0?[1-9])(?:[/.-]((?:20)?\d\d))?\b", t)
            if not m: return None
            mo, d = int(m.group(1)), int(m.group(2)); y = int(m.group(3)) if m.group(3) else y0
            if y < 100: y += 2000
        return int(dt.datetime(y, mo, d, 23, 59, tzinfo=dt.timezone.utc).timestamp())
    except Exception: return None
def undated(a): return real_ts(a) is None
def older_than(a, newest, gap):
    """True if a's real date is more than gap before newest (another report of the same story)."""
    r = real_ts(a)
    return bool(r and newest and newest - r > gap)
def stale_reason(a, limit=None):
    """'stale: ...' if report a was already old when we first saw it, else None."""
    r = real_ts(a); seen = a.get("added") or a.get("ts")
    if not r or not seen: return None
    lim = limit or (MAX_AGE if a.get("fresh_v") else SWEEP_AGE)
    if seen - r > lim:
        return f"stale: published {time.strftime('%Y-%m-%d', time.gmtime(r))}, first seen {time.strftime('%Y-%m-%d', time.gmtime(seen))}"
    return None
# ---- undated OFFICIAL pages (owner decision 2026-10-21, narrow middle ground) ----
# An undated report from an official promotion site/feed publishes only if one of:
#  (a) its URL, title or body names the current year AND its URL/title refers to an upcoming or current event or season
#      (an event in events.json that is already over, or a results page for an event we can't place as current, doesn't count);
#  (b) the site's own sitemap lastmod or feed pubDate is within 48h of when we first saw it AND we never saw that URL more
#      than 48h before that (url first-seen record, data/url_first_seen.json);
#  (c) a dated tier-1 outlet reports it within 48h (corroborated()).
# Never: an undated page whose URL or title names a past year ('Road to WrestleMania 2025') or a past WrestleMania ('WrestleMania 32').
OFFICIAL_HOSTS = re.compile(r"(?:^|\.)(wwe\.com|allelitewrestling\.com|tnawrestling\.com|impactwrestling\.com|njpw1972\.com|njpw\.co\.jp|"
                            r"luchalibreaaa\.com|aaa\.com\.mx|rohwrestling\.com|cmll\.com|stardom-world\.com|mlw\.com|nwa\.com|gcwrestling\.com)$", re.I)
URL_SEEN = {}          # normalised URL -> first time we saw it (filled by load_url_seen)
def _norm(u): return re.sub(r"^https?://(www\.)?", "", (u or "").split("#")[0].split("?")[0]).rstrip("/").lower()
def load_url_seen(path, arts, keep_days=400):
    """Persistent URL first-seen record: earliest 'added' of any report with that URL (survives the 60-day article retention)."""
    global URL_SEEN
    try: URL_SEEN = json.load(open(path))
    except Exception: URL_SEEN = {}
    for a in arts:
        k = _norm(a.get("link")); t = int(a.get("added") or a.get("ts") or time.time())
        if k and (k not in URL_SEEN or t < URL_SEEN[k]): URL_SEEN[k] = t
    cut = time.time() - keep_days * 86400
    URL_SEEN = {k: v for k, v in URL_SEEN.items() if v > cut}
    try: json.dump(URL_SEEN, open(path, "w"))
    except Exception: pass
    return URL_SEEN
OWN_FEEDS = {"AEW", "MLW"}   # promotions' own RSS feeds (aggregator sets it from FEEDS); Google News / listing-page dates don't count
def own_feed(a):
    """a's ts is the pubDate of the promotion's OWN feed (not Google News' index date, a listing page or a first-seen guess)."""
    if a.get("ts_guessed") or not a.get("ts"): return False
    return (a.get("via") or a.get("source")) in OWN_FEEDS
def is_official(a):
    host = re.sub(r"^https?://", "", a.get("link") or "").split("/")[0]
    return bool(stale.OFFICIAL.match(a.get("source") or "") or (a.get("source") or "").startswith("Official:") or OFFICIAL_HOSTS.search(host))
_EVENTISH = re.compile(r"(?i)\b(card|line-?up|preview|tickets?|on sale|presale|tour|live events?|season|hall of fame|class of|inductees?|inductors?|"
                       r"event|ppv|ple|pay-?per-?view|premium live|set for|announce[sd]?|returns? to|heads? to|coming to|tonight|this week|"
                       r"tournament|schedule|countdown|kick-?off|press conference|media day|draft|special)\b")
_RESULTS = re.compile(r"(?i)\b(results?|recap|winners)\b")
def _events():
    try:
        import os
        return json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "events.json"))).get("events", [])
    except Exception: return []
def past_year(a, now=None):
    """URL or title names a year before the current one, or a past WrestleMania number."""
    y = time.gmtime(now or time.time()).tm_year
    t = (a.get("raw_title") or a.get("title") or "") + " " + re.sub(r"[-_/]+", " ", re.sub(r"^[a-z]+://[^/]+", "", a.get("link") or ""))
    if any(int(x) < y for x in re.findall(r"(?<!\d)((?:19|20)\d\d)(?!\d)", t)): return True
    return any(int(n) < y - 1984 for n in re.findall(r"(?i)wrestle\s?mania\s*(\d{1,2})\b", t))
def _latest_date(t, y):
    """Latest 'Month D' date (current year) the text states, or None."""
    best = None
    for m in re.finditer(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*[-–]\s*(\d{1,2}))?(?:,?\s+((?:19|20)\d\d))?\b", t):
        yy = int(m.group(4) or y)
        if yy != y: continue
        try: ts = dt.datetime(yy, _MON[m.group(1)[:3].lower()], int(m.group(3) or m.group(2)), 23, 59, tzinfo=dt.timezone.utc).timestamp()
        except Exception: continue
        best = ts if best is None or ts > best else best
    return best
def official_reason(a, now=None):
    """Which of (a)/(b) lets an undated official page publish, or None."""
    now = now or time.time(); y = str(time.gmtime(now).tm_year)
    if past_year(a, now): return None
    seen = int(a.get("added") or a.get("ts") or now)
    head = (a.get("raw_title") or "") + " " + (a.get("title") or "") + " " + re.sub(r"[-_/]+", " ", a.get("link") or "")
    body = (a.get("summary_src") or "") + " " + (a.get("body") or "")
    if y in head or y in body:
        ok = bool(_EVENTISH.search(head))
        last = _latest_date(head + " " + body[:800], int(y))
        if last and last < seen - 2 * 86400: ok = False     # the event date the page states is already past ('Sunday, October 11')
        for e in _events():        # a named event that is already over (2+ days) is not upcoming/current
            if e.get("match") and re.search(e["match"], head, re.I):
                try: d = dt.datetime.fromisoformat(e["date"]).replace(tzinfo=dt.timezone.utc).timestamp()
                except Exception: continue
                ok = ok and d > seen - 2 * 86400
                if _RESULTS.search(head): ok = ok or abs(d - seen) <= 2 * 86400
                break
        else:
            if _RESULTS.search(head): ok = False      # results page for an event we can't place as current
        if ok: return "a: names " + y + " and an upcoming/current event"
    first = URL_SEEN.get(_norm(a.get("link")), seen)
    for k in ("lastmod", "feed_pub"):
        t = a.get(k)
        if k == "feed_pub" and t is None and own_feed(a): t = a.get("ts")   # the promotion's own feed pubDate
        if t and abs(seen - int(t)) <= MAX_AGE and first >= seen - MAX_AGE:
            return f"b: {'sitemap lastmod' if k == 'lastmod' else 'feed pubDate'} within 48h, URL new"
    return None
def corroborated(c, bylink, now=None):
    """A story whose lead is undated publishes only if another trusted (tier 1) outlet, with a real date, reports it within 48h,
    or (official promotion pages only) official_reason() allows it."""
    lead = bylink.get(c["link"])
    if not lead or not undated(lead): return True
    if is_official(lead) and official_reason(lead, now): return True
    base = lead.get("added") or lead.get("ts") or time.time()
    for u in c.get("updates", []):
        m = bylink.get(u["link"])
        if not m or m["source"] == lead["source"] or editorial.tier(m["source"]) != 1: continue
        r = real_ts(m)
        if r and abs(base - r) <= MAX_AGE: return True
    return False
