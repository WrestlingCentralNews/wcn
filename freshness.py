"""Freshness rules (owner rule 2026-10-21): only up-to-date reports become news, old news is never presented as new.
A report's date is its REAL publish date, in this order: the article page's own published time (article:published_time,
og/itemprop datePublished, JSON-LD datePublished, <time pubdate>), a date in the URL path (/2022/12/...), then the feed's
pubDate when the feed is the outlet's own. 'updated'/'modified' dates and re-crawls never count. Google News / listing-page
dates for official promotion sites (they resurface years-old pages) and first-seen guesses are NOT a date: such a report is
'undated' and only publishes when another trusted outlet reports the same story within 48 hours.
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
def corroborated(c, bylink):
    """A story whose lead is undated publishes only if another trusted (tier 1) outlet, with a real date, reports it within 48h."""
    lead = bylink.get(c["link"])
    if not lead or not undated(lead): return True
    base = lead.get("added") or lead.get("ts") or time.time()
    for u in c.get("updates", []):
        m = bylink.get(u["link"])
        if not m or m["source"] == lead["source"] or editorial.tier(m["source"]) != 1: continue
        r = real_ts(m)
        if r and abs(base - r) <= MAX_AGE: return True
    return False
