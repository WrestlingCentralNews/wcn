"""Stale-content guard: an OLD article that a feed (usually Google News re-indexing an official site) hands us with a
FRESH date, e.g. wwe.com/shows/eliminationchamber/2017/... arriving dated Oct 16 2026 and landing on that week's SmackDown page.
The feed date can't be trusted for these, so we look at what the item itself says about when it was written:
  1. a date in the URL path (/2017/, /2017/01/, /2017/01/31/, -2017-01-31) more than GRACE_DAYS before the feed date;
  2. promotion sites (WWE, AEW, TNA, ...: their evergreen pages resurface via Google News) whose photo path is dated 2+ years
     before the feed date AND whose text only mentions years 2+ years old (no current/last-year mention at all).
reason(a) -> 'stale: ...' or None. Used as an editorial drop (story never published) and by hubs.tag (never on an event page)."""
import re, time, datetime as dt
GRACE_DAYS = 45
OFFICIAL = re.compile(r"^(WWE|WWE\.com|AEW|All Elite Wrestling|TNA Wrestling|TNA|NJPW|NEW JAPAN PRO-WRESTLING|ROH|Ring of Honor|STARDOM|CMLL|Lucha Libre AAA|GCW|MLW)$", re.I)
_EOM = lambda y, m: (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1))
def url_date(link):
    """Latest date the URL path could mean (end of the year/month when only those are given), or None."""
    p = re.sub(r"^[a-z]+://[^/]+", "", link or "", flags=re.I).split("?")[0].split("#")[0]
    m = re.search(r"/((?:19|20)\d\d)/(0[1-9]|1[0-2])/([0-2]\d|3[01])(?:/|$)", p) or re.search(r"[/_-]((?:19|20)\d\d)-(0[1-9]|1[0-2])-([0-2]\d|3[01])(?:[/_.-]|$)", p)
    if m:
        try: return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError: return None
    m = re.search(r"/((?:19|20)\d\d)/(0[1-9]|1[0-2])(?:/|$)", p)
    if m: return _EOM(int(m.group(1)), int(m.group(2)))
    m = re.search(r"/((?:19|20)\d\d)(?:/|$)", p)          # a bare year folder: /shows/eliminationchamber/2017/...
    if m: return dt.date(int(m.group(1)), 12, 31)
    return None
def _img_year(url):
    m = re.search(r"/((?:19|20)\d\d)/(?:0[1-9]|1[0-2])/", url or "") or re.search(r"/((?:19|20)\d\d)(?:0[1-9]|1[0-2])[0-3]\d_", url or "")
    return int(m.group(1)) if m else None
def reason(a):
    ts = a.get("ts") or a.get("first_ts")
    if not ts: return None
    fd = dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).date(); y = fd.year
    ud = url_date(a.get("link"))
    if ud and (fd - ud).days > GRACE_DAYS: return f"stale: URL dated {ud.isoformat()[:4 if ud.month == 12 and ud.day == 31 else 10]}, feed date {fd}"
    if OFFICIAL.match(a.get("source") or ""):
        iy = _img_year(a.get("image"))
        txt = " ".join(str(a.get(k) or "") for k in ("raw_title", "title", "summary_src", "src_summary", "body"))
        yrs = [int(v) for v in re.findall(r"\b((?:19|20)\d\d)\b", txt) if int(v) <= y + 1]
        if iy and iy <= y - 2 and yrs and max(yrs) <= y - 2:
            return f"stale: official page with {iy} photo, text only mentions up to {max(yrs)}, feed date {fd}"
    return None
