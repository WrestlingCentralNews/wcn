"""Static story pages, sitemap.xml and robots.txt for WCN."""
import os, re, json, html, shutil, time, datetime, hashlib, email.utils
import chrome, hubs, imgmeta
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
def nl_block(where, compact=False, head="h2", base="../", lang="en"):
    """WCN Weekly signup. Native form -> Kit; newsletter.js upgrades it to fetch() + inline 'check your inbox' message."""
    if lang == "es":
        title = "Recibe el <b>WCN Weekly</b>" if not compact else "No te pierdas nada: <b>WCN Weekly</b>"
        sub = "Las 10 noticias más importantes de la lucha libre de la semana, cada lunes por la mañana (boletín en inglés). Gratis, sin spam."
        ph, btn, fine = "Tu correo electrónico", "Suscribirme", f'Doble confirmación vía Kit. Consulta nuestra <a href="/privacy.html">Política de privacidad</a>.'
    else:
        title = "Get the <b>WCN Weekly</b>" if not compact else "Never miss a big story: <b>WCN Weekly</b>"
        sub = "The 10 biggest wrestling stories of the week, every Monday morning. Free, no spam, unsubscribe anytime."
        ph, btn, fine = "Your email address", "Subscribe", f'Double opt-in via Kit. See our <a href="{base}privacy.html">Privacy Policy</a>.'
    return (f'<section class="nl{" nl-box" if compact else ""}" aria-label="WCN Weekly newsletter"><div><{head}>{title}</{head}><p class="nl-sub">{sub}</p></div>'
            f'<form class="nl-form" action="{KIT_ACTION}" method="post" data-where="{where}"><div class="nl-row">'
            f'<input type="email" name="email_address" required autocomplete="email" inputmode="email" placeholder="{ph}" aria-label="{ph}">'
            f'<button type="submit">{btn}</button></div><p class="nl-msg" role="status" aria-live="polite"></p>'
            f'<p class="nl-fine">{fine}</p></form></section>')
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
def rss(items, self_url, title="Wrestling Central News", link=SITE, desc=TAGLINE, lang="en-us"):
    last = max([int(c["ts"]) for c in items if not isinstance(c, str)] or [int(time.time())])
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" '
            'xmlns:media="http://search.yahoo.com/mrss/" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>'
            f"<title>{xe(title)}</title><link>{xe(link)}</link><description>{xe(desc)}</description><language>{lang}</language>"
            f'<atom:link href="{xe(self_url)}" rel="self" type="application/rss+xml"/>'
            f"<lastBuildDate>{rfc822(last)}</lastBuildDate><ttl>15</ttl>"
            f"<image><url>{SITE}logo.png</url><title>{xe(title)}</title><link>{xe(link)}</link></image>"
            + "".join(x if isinstance(x, str) else rss_item(x) for x in items) + "</channel></rss>\n")
def build_feeds(clusters):
    """RSS 2.0: /feed.xml (newest 50) + /feed/<cat>.xml (newest 30 per primary category)."""
    srt = sorted(clusters, key=lambda c: -int(c.get("first_ts", c["ts"])))
    open(os.path.join(PUB, "feed.xml"), "w").write(rss(srt[:50], SITE + "feed.xml"))
    os.makedirs(os.path.join(PUB, "feed"), exist_ok=True)
    for cat, slug in FEED_CATS.items():
        its = [c for c in srt if c["categories"][0] == cat][:30]
        open(os.path.join(PUB, "feed", slug + ".xml"), "w").write(
            rss(its, f"{SITE}feed/{slug}.xml", title=f"Wrestling Central News: {cat}", desc=f"The latest {cat} news from Wrestling Central News. " + TAGLINE))
SN_MAX, SN_DAYS = 60, 30
def sn_item(c):
    """SmartFormat v2.2 item: full text (our own wording only) with the lead image first, WCN Staff byline, media:thumbnail."""
    url = SITE + c["url"]; img = c.get("image") or ""
    if not img.startswith("https://"): img = SITE + "og-image.jpg"
    paras = c.get("long") or [c.get("summary") or ""]
    desc = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c.get("summary") or "")).strip()
    cr = c.get("image_credit") or {}
    body = f'<figure><img src="{e(img)}" alt="{e(c["title"])}">' + (f'<figcaption>{e(cr.get("text"))}</figcaption>' if cr.get("text") else "") + "</figure>"
    k = c.get("kind") or {}
    if k.get("type") == "quote" and k.get("who") and k.get("quote"): body += f'<blockquote><p>“{e(k["quote"])}”</p><cite>— {e(k["who"])}</cite></blockquote>'
    body += "".join(f"<p>{e(p)}</p>" for p in paras if p)
    srcs = list(dict.fromkeys([(c.get("source"), c.get("link"))] + [(u.get("source"), u.get("link")) for u in c.get("updates", [])]))
    srcs = [(n, l) for n, l in srcs if n and l and l.startswith("http")][:8]
    if srcs: body += "<p><small>Sources: " + ", ".join(f'<a href="{e(l)}">{e(n)}</a>' for n, l in srcs) + "</small></p>"
    cats = ",".join(dict.fromkeys(list(c["categories"]) + ["wrestling"]))
    return (f"<item><title>{xe(c['title'])}</title><link>{xe(url)}</link><guid isPermaLink=\"true\">{xe(url)}</guid>"
            f"<description>{xe(desc)}</description><pubDate>{rfc822(c.get('first_ts', c['ts']))}</pubDate>"
            f"<content:encoded><![CDATA[{body.replace(']]>', ']]&gt;')}]]></content:encoded>"
            f"<category>{xe(cats)}</category><dc:creator>WCN Staff</dc:creator><dc:language>en</dc:language>"
            f'<media:thumbnail url="{xe(img)}"/><media:status>active</media:status></item>')
def build_smartnews(clusters):
    """SmartNews SmartFormat v2.2 feed: /feed/smartnews.xml (English stories first published in the last 30 days, newest first)."""
    now = time.time()
    its = sorted([c for c in clusters if now - int(c.get("first_ts", c["ts"])) < SN_DAYS * 86400], key=lambda c: -int(c.get("first_ts", c["ts"])))[:SN_MAX]
    xml = ('<?xml version="1.0" encoding="utf-8"?>\n<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" '
           'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:media="http://search.yahoo.com/mrss/" xmlns:snf="http://www.smartnews.be/snf"><channel>'
           f"<title>Wrestling Central News</title><link>{SITE}</link><description>Pro wrestling news, 24/7</description>"
           f"<pubDate>{rfc822(max([int(c['ts']) for c in its] or [int(now)]))}</pubDate><language>en</language>"
           f"<copyright>© {time.gmtime().tm_year} Wrestling Central News</copyright><ttl>15</ttl>"
           f"<snf:logo><url>{SITE}img/smartnews/logo.png</url></snf:logo><snf:darkModeLogo><url>{SITE}img/smartnews/logo-dark.png</url></snf:darkModeLogo>"
           + "".join(sn_item(c) for c in its) + "</channel></rss>\n")
    os.makedirs(os.path.join(PUB, "feed"), exist_ok=True)
    open(os.path.join(PUB, "feed", "smartnews.xml"), "w").write(xml)
def feed_links(cat=None):
    s = f'<link rel="alternate" type="application/rss+xml" title="Wrestling Central News" href="{SITE}feed.xml">'
    if cat in FEED_CATS: s += f'<link rel="alternate" type="application/rss+xml" title="Wrestling Central News: {cat}" href="{SITE}feed/{FEED_CATS[cat]}.xml">'
    return s
def ad(slot, size, cls="ad-feed"): return f'<div class="ad {cls}" data-slot="{slot}" data-size="{size}"></div>'
S = {
 "en": {"conf": "✔ CONFIRMED BY {n} SOURCES", "timeline": "Story timeline · {n} reports", "source": "Source", "more": "More {cat} news", "by": "By",
        "staff": "WCN Staff", "pub": "Published", "first": "First reported", "upd": "Updated", "part": "Part of our coverage of", "hub_go": "Full card & results →"},
 "es": {"conf": "✔ CONFIRMADO POR {n} FUENTES", "timeline": "Cronología · {n} reportes", "source": "Fuente", "more": "Más noticias de {cat}", "by": "Por",
        "staff": "Redacción WCN", "pub": "Publicado", "first": "Publicado", "upd": "Actualizado", "part": "Parte de nuestra cobertura de", "hub_go": "Cartelera y resultados →"},
}
def schema_image(c):
    """ImageObject list for NewsArticle: the story photo at its largest known version (imgmeta.apply sets image/img_w/img_h;
    >=1200px wide when the source has one) with its real size, then the 1200x630 site card as a fallback."""
    out = []
    img = c.get("image") or ""
    if img.startswith("https://"):
        o = {"@type": "ImageObject", "url": img, "contentUrl": img}
        if c.get("img_w") and c.get("img_h"): o["width"], o["height"] = c["img_w"], c["img_h"]
        out.append(o)
    out.append({"@type": "ImageObject", "url": SITE + "og-image.jpg", "width": 1200, "height": 630})
    return out
def byline_html(c, lang):
    """'By WCN Staff · Published X' or, for stories with follow-up reports, 'First reported X · Updated Y' (first_ts vs latest ts)."""
    t = S[lang]; pub, mod = c.get("first_ts", c["ts"]), c["ts"]
    staff_url = chrome.STATIC["staff"][1 if lang == "es" else 0]
    upd = bool(c.get("updates")) and mod - pub > 300
    s = (f'<div class="byline">{t["by"]} <a rel="author" href="{staff_url}">{t["staff"]}</a> · {t["first"] if upd else t["pub"]} '
         f'<time datetime="{iso(pub)}" data-ts="{int(pub)}">{chrome.stamp(pub, lang)}</time>')
    if upd: s += f' · {t["upd"]} <time datetime="{iso(mod)}" data-ts="{int(mod)}">{chrome.stamp(mod, lang)}</time>'
    return s + "</div>"
def page(c, related, lang="en", L=None, alt=None):
    """Story page. lang='es' uses L = {'t','s','url','p'} (Spanish translation) and related = [(cluster, L)]."""
    t = S[lang]; es = lang == "es"
    title = L["t"] if es else c["title"]; summary = L["s"] if es else c["summary"]
    rel_url = L["url"] if es else c["url"]; url = SITE + rel_url
    col = CATC.get(c["categories"][0], "#7cd618")
    paras = (L.get("p") or [summary]) if es else (c.get("long") or [c["summary"]])
    desc = re.sub(r"\s+", " ", summary)[:158]
    img = c.get("image") or ""; big = img if img.startswith("https://") else SITE + "og-image.jpg"
    iw, ih = (c.get("img_w"), c.get("img_h")) if img.startswith("https://") else (1200, 630)
    wh = f' width="{iw}" height="{ih}"' if iw and ih else ""
    imgx = (f'<meta property="og:image:width" content="{iw}"><meta property="og:image:height" content="{ih}">' if iw and ih else "") + \
           (f'<link rel="preload" as="image" href="{e(img)}" fetchpriority="high" referrerpolicy="no-referrer">' if img else "")
    body = []
    for i, p in enumerate(paras):
        body.append(f"<p>{e(p)}</p>")
        if i in (1, 3) and i < len(paras) - 1: body.append(ad("inArticle", "In-Article"))
    k = c.get("kind") or {}
    quote = ""
    if k.get("type") == "quote" and k.get("who") and not es:
        quote = f'<blockquote class="qc big"><span class="qm">“</span>{e(k.get("quote") or c["summary"].split(". ")[0])}<cite>— {e(k.get("who"))}</cite></blockquote>'
    tl = "" if es else "".join(f'<li><time datetime="{iso(u["ts"])}">{nice(u["ts"])}</time><b>{e(u["title"])}</b><span>{e(u["line"])}</span></li>' for u in c.get("updates", []))
    tl = f'<section class="timeline upd"><h2>{t["timeline"].format(n=len(c["updates"]) + 1)}</h2><ol>{tl}</ol></section>' if tl else ""
    if es: rel = "".join(f'<a class="rel" href="/{r2["url"]}" style="--c:{CATC.get(r["categories"][0])}"><div class="ri" style="background-image:url(\'{e(r.get("image") or "")}\')"></div><span>{e(r2["t"])}</span></a>' for r, r2 in related)
    else: rel = "".join(f'<a class="rel" href="/{r["url"]}" style="--c:{CATC.get(r["categories"][0])}"><div class="ri" style="background-image:url(\'{e(r.get("image") or "")}\')"></div><span>{e(r["title"])}</span></a>' for r in related)
    tags = "".join(f'<span class="tag" style="--c:{CATC[x]}">{x}</span>' for x in c["categories"])
    conf = f'<span class="tag conf">{t["conf"].format(n=c["sources"])}</span>' if c.get("sources", 1) > 1 else ""
    hl = hubs.hub_link(c, lang)
    hub = f'<a class="hubbox" href="/{hl[1]}"><small>{t["part"]}</small><b>{e(hl[0])}</b><span>{t["hub_go"]}</span></a>' if hl else ""
    pub, mod = c.get("first_ts", c["ts"]), c["ts"]
    ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": title[:110], "description": desc, "image": schema_image(c), "url": url,
          "datePublished": iso(pub), "dateModified": iso(mod), "mainEntityOfPage": {"@type": "WebPage", "@id": url}, "articleSection": c["categories"][0],
          "inLanguage": lang, "isAccessibleForFree": True, "author": [chrome.staff_author(lang)], "publisher": chrome.PUBLISHER}
    home = SITE + ("es/" if es else "")
    crumbs = [("WCN en español" if es else "WCN", home), (title[:70], url)]
    head = chrome.head(f"{title} | WCN", desc, url, lang, alts=alt, og_type="article", image=big, ads=True, ld=[ld, chrome.breadcrumbs(crumbs)],
                       extra=(f'<meta property="og:image:alt" content="{e(title)}">{imgx}<meta property="article:publisher" content="{chrome.FB}">'
                              f'<meta property="article:published_time" content="{iso(pub)}"><meta property="article:modified_time" content="{iso(mod)}"><meta property="article:section" content="{e(c["categories"][0])}">'))
    en_u = "/" + (alt or {}).get("en", SITE).replace(SITE, ""); es_u = "/" + (alt or {}).get("es", SITE + "es/").replace(SITE, "")
    hero = (f'<div class="story-hero"><img class="bg" src="{e(img)}" alt="" aria-hidden="true" decoding="async" referrerpolicy="no-referrer"><img class="fg" src="{e(img)}"{wh} alt="{e(title)}" fetchpriority="high" decoding="async" referrerpolicy="no-referrer"></div>'
            if img else f'<div class="story-hero ph-h"><span>{c["categories"][0]}</span></div>')
    credit = f'<p class="pcredit"><a href="{e(c["image_credit"]["url"])}" rel="nofollow noopener" target="_blank">{e(c["image_credit"]["text"])}</a></p>' if c.get("image_credit") else ""
    return (f'{head}\n<body class="story-page" style="--c:{col}"><div class="spot s1"></div><div class="spot s2"></div>\n'
            f'{chrome.header(lang, en_u, es_u, "news", back=True)}\n{ad("leaderboard", "728×90 Leaderboard", "ad-leader")}\n'
            f'<main class="layout"><aside class="side">{ad("leftSkyscraper", "300×600 Half-page", "ad-sky")}</aside>\n'
            f'<article class="story"><div class="tags">{conf}{tags}</div><h1>{e(title)}</h1>{byline_html(c, lang)}\n{hero}\n{credit}{quote}{hub}<div class="prose">{"".join(body)}</div>{tl}\n'
            f'<p class="credit">{t["source"]}: <a href="{e(c["link"])}" rel="nofollow noopener" target="_blank">{e(c["source"])}</a></p>\n'
            f'{nl_block("story-es" if es else "story", compact=True, head="h3", base="/", lang=lang)}\n{ad("storyBottom", "Responsive Banner")}\n'
            f'<section class="related"><h2>{t["more"].format(cat=e(c["categories"][0]))}</h2><div class="relgrid">{rel}</div></section></article>\n'
            f'<aside class="side">{ad("rightSkyscraper", "300×600 Half-page", "ad-sky")}</aside></main>\n'
            f'{nl_block("footer-story-es" if es else "footer-story", base="/", lang=lang)}\n{chrome.footer(lang)}\n'
            f'{ad("mobileSticky", "320×50 Mobile", "ad-mobile")}<script src="/story.js"></script>{chrome.SCRIPTS}</body></html>')
# Google tag + Consent Mode v2 (region-aware): denied by default in EEA/UK/CH until the banner choice, granted elsewhere;
# a stored banner choice (wcn_consent) is re-applied before config. Loaded directly in <head> on every page.
GA_HEAD = chrome.GA_HEAD
SW_PRECACHE = ["/index.html", "/offline.html", "/style.css", "/app.js", "/story.js", "/pwa.js", "/push.js", "/newsletter.js", "/time.js", "/logo-header.png", "/logo.png",
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
{chrome.header("en", "/newsletter/", "/es/", None, back=True)}
<main class="nl-page"><h1>The week in wrestling, <b>every Monday.</b></h1>
<p class="lede">WCN Weekly brings you the 10 biggest stories from WWE, AEW, TNA, the indies and around the world: our own headlines, a quick summary of each, and a link to the full story.</p>
{nl_block("newsletter-page", base="/")}
<ul class="nl-perks"><li><b>10 stories, 2 minutes</b>Ranked by how big the story is and how many trusted outlets confirmed it.</li><li><b>Every Monday morning</b>Lands at 9:00 AM Puerto Rico time (AST), right before Raw week kicks off.</li><li><b>Free, no spam</b>One email a week. Unsubscribe with one click, anytime.</li></ul>
{f'<section class="nl-sample"><h2>This week so far</h2><ol>{lis}</ol></section>' if lis else ''}
<p style="margin-top:28px"><a href="/" style="color:#7cd618">← Back to the news</a></p></main>
{chrome.footer("en")}
<script src="/newsletter.js" defer></script><script src="/pwa.js" defer></script><script src="/push.js" defer></script></body></html>'''
    os.makedirs(os.path.join(PUB, "newsletter"), exist_ok=True)
    open(os.path.join(PUB, "newsletter", "index.html"), "w").write(html_)
# ---------- redirect stubs for story URLs that changed (re-clustering splits/merges, new lead headline) ----------
PREV = []            # previous run's news.json items (set by aggregator before build)
REDIRECTS = os.path.join(ROOT, "data", "redirects.json")   # {old_rel_url: {links, lead, es, at, to}}
REDIRECT_DAYS = 60
def _members(c): return [c["link"]] + [u["link"] for u in c.get("updates", [])]
def redirects(clusters, tr, old_tr):
    """Record every story URL (EN + ES) from the previous run that no longer exists and point it at the best matching current
    story: the one holding the old lead report, else the most shared reports, else the home page. Stubs never enter sitemaps."""
    import translate
    try: R = json.load(open(REDIRECTS))
    except Exception: R = {}
    now = int(time.time())
    cur_en = {c["url"] for c in clusters}; cur_es = {x["url"] for x in tr.values()}
    for p in PREV:
        if not p.get("url"): continue
        olds = [(p["url"], False)]
        x = old_tr.get(p["id"])
        if x: olds.append((f"es/noticias/{x.get('sl') or translate.slug_es(x['t'])}-{p['id']}.html", True))
        for u, es in olds:
            if u not in (cur_es if es else cur_en) and u not in R:
                R[u] = {"links": _members(p), "lead": p["link"], "es": es, "at": now}
                if es and p["id"] in tr and tr[p["id"]]["url"] != u:   # same id, new Spanish slug: the old slug names the OLD story
                    ot = x.get("en") or x["t"]       # English headline the old translation was made from (newer cache entries), else the Spanish one
                    best = max(clusters, key=lambda c: translate.topic_score(ot, c["title"]))
                    if translate.topic_score(ot, best["title"]) >= 0.3: R[u]["to_id"] = best["id"]
                    else: R[u]["to_id"] = "-"       # no confident match: Spanish home page, never a different story
    by_link = {}
    for c in clusters:
        for l in _members(c): by_link.setdefault(l, c)
    out = {}
    for u, r in R.items():
        if now - r.get("at", now) > REDIRECT_DAYS * 86400 or u in cur_en or u in cur_es: continue   # expired, or the URL is live again
        c = None if r.get("to_id") == "-" else next((x for x in clusters if x["id"] == r.get("to_id")), None) or by_link.get(r.get("lead"))
        if not c and r.get("to_id") != "-":
            cnt = {}
            for l in r.get("links", []):
                if l in by_link: cnt[by_link[l]["id"]] = cnt.get(by_link[l]["id"], 0) + 1
            if cnt: k = max(cnt, key=cnt.get); c = next(x for x in clusters if x["id"] == k)
        if c: to = (tr[c["id"]]["url"] if r["es"] and c["id"] in tr else c["url"])
        else: to = "es/" if r["es"] else ""
        out[u] = {**r, "to": to}
    os.makedirs(os.path.dirname(REDIRECTS), exist_ok=True); json.dump(out, open(REDIRECTS, "w"))
    return out
def stub(to):
    t = SITE + to
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>Moved | Wrestling Central News</title>'
            f'<link rel="canonical" href="{e(t)}"><meta http-equiv="refresh" content="0; url=/{e(to)}">'
            f'<script>location.replace("/{e(to)}"+location.hash)</script></head>'
            f'<body><p>This story moved: <a href="/{e(to)}">{e(t)}</a></p></body></html>')
def build(clusters):
    import translate, extras
    build_sw()
    imgmeta.run(clusters); imgmeta.apply(clusters)   # cards, story heroes, og:image and NewsArticle use the largest version of each photo
    nh = hubs.tag(clusters)
    old_tr = translate.load()      # before run() prunes ids that no longer exist (needed for the old Spanish URLs)
    tr = translate.run(clusters)   # {cluster_id: {t, s, url, p}} Spanish, cached; only new/changed stories cost anything
    tmp = SD + ".new"; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    ESD = os.path.join(PUB, "es", "noticias"); etmp = ESD + ".new"; shutil.rmtree(etmp, ignore_errors=True); os.makedirs(etmp)
    red = redirects(clusters, tr, old_tr)
    for u, r in red.items():
        d = etmp if u.startswith("es/noticias/") else tmp if u.startswith("story/") else None
        if d and not os.path.exists(os.path.join(d, os.path.basename(u))): open(os.path.join(d, os.path.basename(u)), "w").write(stub(r["to"]))
    bycat = {}
    for c in clusters: bycat.setdefault(c["categories"][0], []).append(c)
    for c in clusters:
        rel = [r for r in bycat[c["categories"][0]] if r is not c][:6]
        x = tr.get(c["id"])
        alt = {"en": SITE + c["url"], "es": SITE + x["url"]} if x else None
        open(os.path.join(tmp, os.path.basename(c["url"])), "w").write(page(c, rel, alt=alt or {"en": SITE + c["url"]}))
        if x:
            rel_es = [(r, tr[r["id"]]) for r in bycat[c["categories"][0]] if r is not c and r["id"] in tr][:6]
            open(os.path.join(etmp, os.path.basename(x["url"])), "w").write(page(c, rel_es, lang="es", L=x, alt=alt))
    shutil.rmtree(SD, ignore_errors=True); os.replace(tmp, SD)   # only current (<=60 day) stories survive
    shutil.rmtree(ESD, ignore_errors=True); os.replace(etmp, ESD)  # same pruning for Spanish pages
    hub_pages = hubs.build(clusters, tr)
    build_newsletter_page(clusters)
    build_feeds(clusters)
    build_smartnews(clusters)
    # Spanish feed
    es_items = [c for c in sorted(clusters, key=lambda c: -int(c.get("first_ts", c["ts"]))) if c["id"] in tr][:50]
    def es_rss_item(c):
        x = tr[c["id"]]; return rss_item(dict(c, title=x["t"], summary=x["s"], url=x["url"], byline="Redacción WCN"))
    open(os.path.join(PUB, "es", "feed.xml"), "w").write(rss([es_rss_item(c) for c in es_items], SITE + "es/feed.xml", title="Wrestling Central News en español",
        link=SITE + "es/", desc="Noticias de lucha libre en español: WWE, AEW, TNA, independientes y lucha libre mundial, actualizadas cada 15 minutos.", lang="es"))
    static = extras.build_trust(clusters, tr) + extras.build_es_home(clusters, tr)
    n_news = extras.news_sitemap(clusters, tr)
    # sitemaps: English (+ trust/hub pages) and Spanish (/es/ only), with hreflang alternates
    hub_en = sorted(p for p in hub_pages if not p.startswith("es/")); hub_es = sorted(p for p in hub_pages if p.startswith("es/"))
    now_iso = iso(time.time())
    en = [(SITE, now_iso, {"en": SITE, "es": SITE + "es/"}), (SITE + "newsletter/", None, None)]
    en += [(SITE + p, now_iso, None) for p in hub_en]
    en += [(SITE + p, None, None) for p in static if not p.startswith("es/")]
    en += [(SITE + c["url"], iso(c["ts"]), {"en": SITE + c["url"], "es": SITE + tr[c["id"]]["url"]} if c["id"] in tr else None) for c in clusters]
    open(os.path.join(PUB, "sitemap.xml"), "w").write(extras.urlset(en, alts=True))
    es = [(SITE + "es/", now_iso, {"en": SITE, "es": SITE + "es/"})] + [(SITE + p, now_iso, None) for p in hub_es]
    es += [(SITE + p, None, None) for p in static if p.startswith("es/") and p != "es/"]
    es += [(SITE + tr[c["id"]]["url"], iso(c["ts"]), {"en": SITE + c["url"], "es": SITE + tr[c["id"]]["url"]}) for c in clusters if c["id"] in tr]
    open(os.path.join(PUB, "es", "sitemap.xml"), "w").write(extras.urlset(es, alts=True))
    extras.robots()
    # pages for IndexNow beyond story URLs: hubs/events (with content hash so changed pages are re-pinged), static pages, Spanish stories
    idx = {p: h for p, h in hub_pages.items()}
    idx.update({p: "static" for p in static}); idx.update({tr[c["id"]]["url"]: "story" for c in clusters if c["id"] in tr})
    idx.update({"es/feed.xml": "feed", "sitemap-news.xml": "news-" + str(int(time.time() // 21600))})
    idx.update({u: "redirect:" + r["to"] for u, r in red.items()})   # moved story URLs: pinged once, and again if their target changes
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True); json.dump(idx, open(os.path.join(ROOT, "data", "indexnow_pages.json"), "w"))
    print(f"pages: redirect stubs {len(red)}", flush=True)
    print(f"pages: hubs tagged {nh} stories, {len(hub_pages)} hub pages, es stories {len(tr)}, news sitemap {n_news}", flush=True)
