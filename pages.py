"""Static story pages, sitemap.xml and robots.txt for WCN."""
import os, re, json, html, shutil, time, datetime, hashlib, email.utils
ROOT = os.path.dirname(os.path.abspath(__file__)); PUB = os.path.join(ROOT, "public"); SD = os.path.join(PUB, "story")
SITE = "https://wrestlingcentralnews.com/"
CATC = {"WWE": "#f26a14", "AEW": "#7cd618", "TNA": "#4ea8ff", "Indie": "#f05fc1", "Global": "#2fd3b4"}
e = lambda s: html.escape(s or "", quote=True)
def slugify(t): return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (t or "").lower())).strip("-")[:70].rstrip("-")
def iso(ts): return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat(timespec="seconds")
def nice(ts): return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%b %d, %Y · %H:%M UTC")
def assign_urls(clusters):
    for c in clusters: c["url"] = f"story/{slugify(c['title'])}-{c['id']}.html"
KIT_ACTION = "https://app.kit.com/forms/10060065/subscriptions"   # Kit form "WCN Weekly" (double opt-in)
def nl_block(where, compact=False, head="h2", base="../"):
    """WCN Weekly signup. Native form -> Kit; newsletter.js upgrades it to fetch() + inline 'check your inbox' message."""
    title = "Get the <b>WCN Weekly</b>" if not compact else "Never miss a big story: <b>WCN Weekly</b>"
    sub = "The 10 biggest wrestling stories of the week, every Monday morning. Free, no spam, unsubscribe anytime."
    return (f'<section class="nl{" nl-box" if compact else ""}" aria-label="WCN Weekly newsletter"><div><{head}>{title}</{head}><p class="nl-sub">{sub}</p></div>'
            f'<form class="nl-form" action="{KIT_ACTION}" method="post" data-where="{where}"><div class="nl-row">'
            f'<input type="email" name="email_address" required autocomplete="email" inputmode="email" placeholder="Your email address" aria-label="Email address">'
            f'<button type="submit">Subscribe</button></div><p class="nl-msg" role="status" aria-live="polite"></p>'
            f'<p class="nl-fine">Double opt-in via Kit. See our <a href="{base}privacy.html">Privacy Policy</a>.</p></form></section>')
TAGLINE = "Wrestling news from WWE, AEW, TNA, the indies and around the world, updated around the clock."
FEED_CATS = {"WWE": "wwe", "AEW": "aew", "TNA": "tna", "Indie": "indie", "Global": "global"}
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]")
def xe(s): return html.escape(_CTRL.sub("", str(s or "")), quote=True)
def rfc822(ts): return email.utils.format_datetime(datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc), usegmt=True)
def _imgtype(u):
    p = u.split("?")[0].lower()
    return "image/png" if p.endswith(".png") else "image/webp" if p.endswith(".webp") else "image/gif" if p.endswith(".gif") else "image/jpeg"
def rss_item(c):
    url = SITE + c["url"]; cat = c["categories"][0]
    desc = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c.get("summary") or "")).strip()
    img = c.get("image") or ""; media = ""
    if img.startswith("https://"):
        t = _imgtype(img)
        media = f'<enclosure url="{xe(img)}" length="0" type="{t}"/><media:content url="{xe(img)}" medium="image" type="{t}"/>'
    return (f"<item><title>{xe(c['title'])}</title><link>{xe(url)}</link><guid isPermaLink=\"true\">{xe(url)}</guid>"
            f"<pubDate>{rfc822(c.get('first_ts', c['ts']))}</pubDate><category>{xe(cat)}</category>"
            f"<dc:creator>{xe(c.get('byline') or 'WCN Staff')}</dc:creator><description>{xe(desc)}</description>{media}</item>")
def rss(items, self_url, title="Wrestling Central News", link=SITE, desc=TAGLINE):
    last = max([int(c["ts"]) for c in items] or [int(time.time())])
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" '
            'xmlns:media="http://search.yahoo.com/mrss/" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>'
            f"<title>{xe(title)}</title><link>{xe(link)}</link><description>{xe(desc)}</description><language>en-us</language>"
            f'<atom:link href="{xe(self_url)}" rel="self" type="application/rss+xml"/>'
            f"<lastBuildDate>{rfc822(last)}</lastBuildDate><ttl>15</ttl>"
            f"<image><url>{SITE}logo.png</url><title>{xe(title)}</title><link>{xe(link)}</link></image>"
            + "".join(rss_item(c) for c in items) + "</channel></rss>\n")
def build_feeds(clusters):
    """RSS 2.0: /feed.xml (newest 50) + /feed/<cat>.xml (newest 30 per primary category)."""
    srt = sorted(clusters, key=lambda c: -int(c.get("first_ts", c["ts"])))
    open(os.path.join(PUB, "feed.xml"), "w").write(rss(srt[:50], SITE + "feed.xml"))
    os.makedirs(os.path.join(PUB, "feed"), exist_ok=True)
    for cat, slug in FEED_CATS.items():
        its = [c for c in srt if c["categories"][0] == cat][:30]
        open(os.path.join(PUB, "feed", slug + ".xml"), "w").write(
            rss(its, f"{SITE}feed/{slug}.xml", title=f"Wrestling Central News: {cat}", desc=f"The latest {cat} news from Wrestling Central News. " + TAGLINE))
def feed_links(cat=None):
    s = f'<link rel="alternate" type="application/rss+xml" title="Wrestling Central News" href="{SITE}feed.xml">'
    if cat in FEED_CATS: s += f'<link rel="alternate" type="application/rss+xml" title="Wrestling Central News: {cat}" href="{SITE}feed/{FEED_CATS[cat]}.xml">'
    return s
def ad(slot, size, cls="ad-feed"): return f'<div class="ad {cls}" data-slot="{slot}" data-size="{size}"></div>'
def page(c, related):
    col = CATC.get(c["categories"][0], "#7cd618"); url = SITE + c["url"]
    paras = c.get("long") or [c["summary"]]
    desc = re.sub(r"\s+", " ", c["summary"])[:158]
    img = c.get("image") or ""; simg = img or SITE + "og-image.jpg"
    body = []
    for i, p in enumerate(paras):
        body.append(f"<p>{e(p)}</p>")
        if i in (1, 3) and i < len(paras) - 1: body.append(ad("inArticle", "In-Article"))
    k = c.get("kind") or {}
    quote = f'<blockquote class="qc big"><span class="qm">“</span>{e(k.get("quote") or c["summary"].split(". ")[0])}<cite>— {e(k.get("who"))}</cite></blockquote>' if k.get("type") == "quote" and k.get("who") else ""
    tl = "".join(f'<li><time>{nice(u["ts"])}</time><b>{e(u["title"])}</b><span>{e(u["line"])}</span></li>' for u in c.get("updates", []))
    tl = f'<section class="timeline upd"><h2>Story timeline · {len(c["updates"]) + 1} reports</h2><ol>{tl}</ol></section>' if tl else ""
    rel = "".join(f'<a class="rel" href="../{r["url"]}" style="--c:{CATC.get(r["categories"][0])}"><div class="ri" style="background-image:url(\'{e(r.get("image") or "")}\')"></div><span>{e(r["title"])}</span></a>' for r in related)
    tags = "".join(f'<span class="tag" style="--c:{CATC[t]}">{t}</span>' for t in c["categories"])
    conf = f'<span class="tag conf">✔ CONFIRMED BY {c["sources"]} SOURCES</span>' if c.get("sources", 1) > 1 else ""
    ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": c["title"][:110], "description": desc, "image": [simg], "url": url,
          "datePublished": iso(c.get("first_ts", c["ts"])), "dateModified": iso(c["ts"]), "mainEntityOfPage": {"@type": "WebPage", "@id": url}, "articleSection": c["categories"][0],
          "author": {"@type": "Organization", "name": "Wrestling Central News", "url": SITE}, "publisher": {"@type": "NewsMediaOrganization", "name": "Wrestling Central News", "url": SITE, "logo": {"@type": "ImageObject", "url": SITE + "logo.png", "width": 600, "height": 399}, "sameAs": ["https://x.com/wrestlingWCN", "https://www.facebook.com/p/Wrestling-Central-News-61595290838604/"]}}
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
{GA_HEAD}
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6049350409363098" crossorigin="anonymous"></script>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(c["title"])} | WCN</title><meta name="description" content="{e(desc)}"><link rel="canonical" href="{url}">{feed_links(c["categories"][0])}
<meta property="og:type" content="article"><meta property="og:title" content="{e(c["title"])}"><meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{url}"><meta property="og:site_name" content="Wrestling Central News"><meta property="og:image" content="{e(simg)}"><meta property="og:image:alt" content="{e(c["title"])}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{e(simg)}"><meta name="robots" content="max-image-preview:large"><meta name="twitter:site" content="@wrestlingWCN"><meta property="article:publisher" content="https://www.facebook.com/p/Wrestling-Central-News-61595290838604/"><meta property="article:published_time" content="{iso(c.get("first_ts", c["ts"]))}"><meta property="article:modified_time" content="{iso(c["ts"])}">
<script type="application/ld+json">{json.dumps(ld)}</script>
<link rel="icon" type="image/png" sizes="32x32" href="../favicon-32.png"><link rel="icon" type="image/png" sizes="512x512" href="../favicon-512.png"><link rel="apple-touch-icon" sizes="180x180" href="../apple-touch-icon.png"><meta name="theme-color" content="#0a1a18"><link rel="manifest" href="/manifest.webmanifest"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-status-bar-style" content="black"><meta name="apple-mobile-web-app-title" content="WCN"><link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;600;800&display=swap" rel="stylesheet"><link rel="stylesheet" href="../style.css"><script src="../ads-config.js"></script><script src="../analytics.js"></script></head>
<body class="story-page" style="--c:{col}"><div class="spot s1"></div><div class="spot s2"></div>
<header><div class="bar"><a class="logo" href="../index.html"><img src="../logo-header.png" width="240" height="160" alt="WCN"><span>WRESTLING CENTRAL NEWS</span></a><a class="back" href="../index.html" onclick="if(history.length>1&&document.referrer.indexOf(location.host)>-1){{history.back();return false}}">← All news</a><div class="social"><a class="soc soc-x" href="https://x.com/wrestlingWCN" target="_blank" rel="noopener me" aria-label="Follow WCN on X" title="Follow @wrestlingWCN on X"><svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M18.9 2H22l-7.2 8.2L23.3 22h-6.6l-5.2-6.8L5.5 22H2.4l7.7-8.8L1.9 2h6.8l4.7 6.2L18.9 2zm-1.2 18h1.8L7.4 3.9H5.5L17.7 20z"/></svg></a><a class="soc soc-fb" href="https://www.facebook.com/p/Wrestling-Central-News-61595290838604/" target="_blank" rel="noopener me" aria-label="Follow WCN on Facebook" title="Follow WCN on Facebook"><svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M13.5 22v-8.2h2.8l.4-3.2h-3.2V8.5c0-.9.3-1.6 1.6-1.6h1.7V4.1c-.3 0-1.3-.1-2.5-.1-2.5 0-4.2 1.5-4.2 4.3v2.4H7.3v3.2h2.8V22h3.4z"/></svg></a></div></div></header>
{ad("leaderboard", "728×90 Leaderboard", "ad-leader")}
<main class="layout"><aside class="side">{ad("leftSkyscraper", "300×600 Half-page", "ad-sky")}</aside>
<article class="story"><div class="tags">{conf}{tags}</div><h1>{e(c["title"])}</h1><div class="byline">WCN Staff · {nice(c["ts"])}</div>
{f'<div class="story-hero"><img class="bg" src="{e(img)}" alt="" aria-hidden="true" referrerpolicy="no-referrer"><img class="fg" src="{e(img)}" alt="{e(c["title"])}" referrerpolicy="no-referrer"></div>' if img else f'<div class="story-hero ph-h"><span>{c["categories"][0]}</span></div>'}
{f'<p class="pcredit"><a href="{e(c["image_credit"]["url"])}" rel="nofollow noopener" target="_blank">{e(c["image_credit"]["text"])}</a></p>' if c.get("image_credit") else ''}{quote}<div class="prose">{"".join(body)}</div>{tl}
<p class="credit">Source: <a href="{e(c["link"])}" rel="nofollow noopener" target="_blank">{e(c["source"])}</a></p>
{nl_block("story", compact=True, head="h3")}
{ad("storyBottom", "Responsive Banner")}
<section class="related"><h2>More {e(c["categories"][0])} news</h2><div class="relgrid">{rel}</div></section></article>
<aside class="side">{ad("rightSkyscraper", "300×600 Half-page", "ad-sky")}</aside></main>
{nl_block("footer-story")}
<footer>© 2026 Wrestling Central News (WCN) · <a href="../privacy.html">Privacy Policy</a> · <a class="nl-link" href="../newsletter/">Newsletter</a> · <a href="mailto:wcn@mail.grokbot.com">Contact</a> · <a class="rss-link" href="/feed.xml" type="application/rss+xml">RSS</a> · Follow us: <a href="https://x.com/wrestlingWCN" target="_blank" rel="noopener">X @wrestlingWCN</a> · <a href="https://www.facebook.com/p/Wrestling-Central-News-61595290838604/" target="_blank" rel="noopener">Facebook</a></footer>
{ad("mobileSticky", "320×50 Mobile", "ad-mobile")}<script src="../story.js"></script><script src="/newsletter.js" defer></script><script src="/pwa.js" defer></script><script src="/push.js" defer></script></body></html>'''
# Google tag + Consent Mode v2 (region-aware): denied by default in EEA/UK/CH until the banner choice, granted elsewhere;
# a stored banner choice (wcn_consent) is re-applied before config. Loaded directly in <head> on every page.
GA_HEAD = '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag(\'consent\',\'default\',{ad_storage:\'denied\',analytics_storage:\'denied\',ad_user_data:\'denied\',ad_personalization:\'denied\',wait_for_update:500,region:[\'AT\',\'BE\',\'BG\',\'HR\',\'CY\',\'CZ\',\'DK\',\'EE\',\'FI\',\'FR\',\'DE\',\'GR\',\'HU\',\'IS\',\'IE\',\'IT\',\'LV\',\'LI\',\'LT\',\'LU\',\'MT\',\'NL\',\'NO\',\'PL\',\'PT\',\'RO\',\'SK\',\'SI\',\'ES\',\'SE\',\'GB\',\'CH\']});gtag(\'consent\',\'default\',{ad_storage:\'granted\',analytics_storage:\'granted\',ad_user_data:\'granted\',ad_personalization:\'granted\'});try{var wc=localStorage.getItem(\'wcn_consent\');if(wc){var wv=wc===\'yes\'?\'granted\':\'denied\';gtag(\'consent\',\'update\',{ad_storage:wv,analytics_storage:wv,ad_user_data:wv,ad_personalization:wv})}}catch(e){}gtag(\'js\',new Date());gtag(\'config\',\'G-VXM9BRSC0B\');</script>\n<script async src="https://www.googletagmanager.com/gtag/js?id=G-VXM9BRSC0B"></script>'
SW_PRECACHE = ["/index.html", "/offline.html", "/style.css", "/app.js", "/story.js", "/pwa.js", "/push.js", "/newsletter.js", "/logo-header.png", "/logo.png",
               "/favicon-32.png", "/apple-touch-icon.png", "/pwa/icon-192.png", "/pwa/icon-512.png"]
def build_sw():
    """Write public/sw.js from sw.src.js; the cache version is a hash of the precached static files + SW source,
    so any CSS/JS/logo change ships a new SW that refreshes caches and deletes old ones."""
    src = open(os.path.join(ROOT, "sw.src.js")).read(); h = hashlib.sha256(src.encode())
    for u in SW_PRECACHE:
        if u == "/index.html": continue   # regenerated feed shell; network-first, so no version bump per news update
        h.update(open(os.path.join(PUB, u.lstrip("/")), "rb").read())
    out = src.replace("__VERSION__", h.hexdigest()[:12]).replace("__PRECACHE__", json.dumps(SW_PRECACHE))
    open(os.path.join(PUB, "sw.js"), "w").write(out)
def build_newsletter_page(clusters):
    """/newsletter/ landing page: pitch, signup form, and a live sample of this week's top stories (same ranking as the email)."""
    try:
        from newsletter import top_week
        sample = top_week(clusters, n=5)
    except Exception: sample = []
    lis = "".join(f'<li><a href="/{c["url"]}">{e(c["title"])}</a><span>{e(c["categories"][0])}</span></li>' for c in sample)
    url = SITE + "newsletter/"; desc = "WCN Weekly: the 10 biggest pro wrestling stories of the week from WWE, AEW, TNA, the indies and around the world, in your inbox every Monday. Free."
    html_ = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
{GA_HEAD}
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="max-image-preview:large">
<title>WCN Weekly Newsletter: Top Wrestling News Every Monday | WCN</title><meta name="description" content="{e(desc)}"><link rel="canonical" href="{url}">{feed_links()}
<meta property="og:type" content="website"><meta property="og:site_name" content="Wrestling Central News"><meta property="og:title" content="WCN Weekly: the week in wrestling, every Monday"><meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{url}"><meta property="og:image" content="{SITE}og-image.jpg"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:site" content="@wrestlingWCN"><meta name="twitter:image" content="{SITE}og-image.jpg">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png"><link rel="icon" type="image/png" sizes="512x512" href="/favicon-512.png"><link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png"><meta name="theme-color" content="#0a1a18"><link rel="manifest" href="/manifest.webmanifest"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-status-bar-style" content="black"><meta name="apple-mobile-web-app-title" content="WCN">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;600;800&display=swap" rel="stylesheet"><link rel="stylesheet" href="/style.css"><script src="/analytics.js"></script></head><body>
<div class="spot s1"></div><div class="spot s2"></div>
<header><div class="bar"><a class="logo" href="/"><img src="/logo-header.png" width="240" height="160" alt="WCN"><span>WRESTLING CENTRAL NEWS</span></a><a class="back" href="/">← All news</a></div></header>
<main class="nl-page"><h1>The week in wrestling, <b>every Monday.</b></h1>
<p class="lede">WCN Weekly brings you the 10 biggest stories from WWE, AEW, TNA, the indies and around the world: our own headlines, a quick summary of each, and a link to the full story.</p>
{nl_block("newsletter-page", base="/")}
<ul class="nl-perks"><li><b>10 stories, 2 minutes</b>Ranked by how big the story is and how many trusted outlets confirmed it.</li><li><b>Every Monday morning</b>Lands at 9:00 AM Puerto Rico time (AST), right before Raw week kicks off.</li><li><b>Free, no spam</b>One email a week. Unsubscribe with one click, anytime.</li></ul>
{f'<section class="nl-sample"><h2>This week so far</h2><ol>{lis}</ol></section>' if lis else ''}
<p style="margin-top:28px"><a href="/" style="color:#7cd618">← Back to the news</a></p></main>
<footer>© 2026 Wrestling Central News (WCN) · <a href="/privacy.html">Privacy Policy</a> · <a href="mailto:wcn@mail.grokbot.com">Contact</a> · <a class="rss-link" href="/feed.xml" type="application/rss+xml">RSS</a> · Follow us: <a href="https://x.com/wrestlingWCN" target="_blank" rel="noopener">X @wrestlingWCN</a> · <a href="https://www.facebook.com/p/Wrestling-Central-News-61595290838604/" target="_blank" rel="noopener">Facebook</a></footer>
<script src="/newsletter.js" defer></script><script src="/pwa.js" defer></script><script src="/push.js" defer></script></body></html>'''
    os.makedirs(os.path.join(PUB, "newsletter"), exist_ok=True)
    open(os.path.join(PUB, "newsletter", "index.html"), "w").write(html_)
def build(clusters):
    build_sw()
    tmp = SD + ".new"; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    bycat = {}
    for c in clusters: bycat.setdefault(c["categories"][0], []).append(c)
    for c in clusters:
        rel = [r for r in bycat[c["categories"][0]] if r is not c][:6]
        open(os.path.join(tmp, os.path.basename(c["url"])), "w").write(page(c, rel))
    shutil.rmtree(SD, ignore_errors=True); os.replace(tmp, SD)   # only current (<=60 day) stories survive
    build_newsletter_page(clusters)
    build_feeds(clusters)
    sm = [f"<url><loc>{SITE}</loc><changefreq>always</changefreq><priority>1.0</priority></url>",
          f"<url><loc>{SITE}newsletter/</loc><changefreq>weekly</changefreq><priority>0.6</priority></url>"] + \
         [f"<url><loc>{SITE}{c['url']}</loc><lastmod>{iso(c['ts'])}</lastmod></url>" for c in clusters]
    open(os.path.join(PUB, "sitemap.xml"), "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(sm) + "</urlset>")
    open(os.path.join(PUB, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITE}sitemap.xml\n")
