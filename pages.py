"""Static story pages, sitemap.xml and robots.txt for WCN."""
import os, re, json, html, shutil, time, datetime
ROOT = os.path.dirname(os.path.abspath(__file__)); PUB = os.path.join(ROOT, "public"); SD = os.path.join(PUB, "story")
SITE = "https://wrestlingcentralnews.com/"
CATC = {"WWE": "#f26a14", "AEW": "#7cd618", "TNA": "#4ea8ff", "Indie": "#f05fc1", "Global": "#2fd3b4"}
e = lambda s: html.escape(s or "", quote=True)
def slugify(t): return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (t or "").lower())).strip("-")[:70].rstrip("-")
def iso(ts): return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat(timespec="seconds")
def nice(ts): return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%b %d, %Y · %H:%M UTC")
def assign_urls(clusters):
    for c in clusters: c["url"] = f"story/{slugify(c['title'])}-{c['id']}.html"
def ad(slot, size, cls="ad-feed"): return f'<div class="ad {cls}" data-slot="{slot}" data-size="{size}"></div>'
def page(c, related):
    col = CATC.get(c["categories"][0], "#7cd618"); url = SITE + c["url"]
    paras = c.get("long") or [c["summary"]]
    desc = re.sub(r"\s+", " ", c["summary"])[:158]
    img = c.get("image") or ""
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
    ld = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": c["title"][:110], "description": desc, "image": [img] if img else [],
          "datePublished": iso(c.get("first_ts", c["ts"])), "dateModified": iso(c["ts"]), "mainEntityOfPage": url, "articleSection": c["categories"][0],
          "author": {"@type": "Organization", "name": "Wrestling Central News"}, "publisher": {"@type": "Organization", "name": "Wrestling Central News (WCN)", "url": SITE, "logo": {"@type": "ImageObject", "url": SITE + "logo.png", "width": 600, "height": 399}, "sameAs": ["https://x.com/wrestlingWCN", "https://www.facebook.com/p/Wrestling-Central-News-61595290838604/"]}}
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('consent','default',{{ad_storage:'denied',analytics_storage:'denied',ad_user_data:'denied',ad_personalization:'denied',wait_for_update:500}});</script>
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6049350409363098" crossorigin="anonymous"></script>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(c["title"])} | WCN</title><meta name="description" content="{e(desc)}"><link rel="canonical" href="{url}">
<meta property="og:type" content="article"><meta property="og:title" content="{e(c["title"])}"><meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{url}"><meta property="og:site_name" content="Wrestling Central News"><meta property="og:image" content="{e(img) if img else SITE + 'og-image.jpg'}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:site" content="@wrestlingWCN"><meta property="article:publisher" content="https://www.facebook.com/p/Wrestling-Central-News-61595290838604/"><meta property="article:published_time" content="{iso(c.get("first_ts", c["ts"]))}"><meta property="article:modified_time" content="{iso(c["ts"])}">
<script type="application/ld+json">{json.dumps(ld)}</script>
<link rel="icon" type="image/png" sizes="32x32" href="../favicon-32.png"><link rel="icon" type="image/png" sizes="512x512" href="../favicon-512.png"><link rel="apple-touch-icon" sizes="180x180" href="../apple-touch-icon.png"><meta name="theme-color" content="#0a1a18"><link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;600;800&display=swap" rel="stylesheet"><link rel="stylesheet" href="../style.css"><script src="../ads-config.js"></script><script src="../analytics.js"></script></head>
<body class="story-page" style="--c:{col}"><div class="spot s1"></div><div class="spot s2"></div>
<header><div class="bar"><a class="logo" href="../index.html"><img src="../logo-header.png" width="240" height="160" alt="WCN"><span>WRESTLING CENTRAL NEWS</span></a><a class="back" href="../index.html" onclick="if(history.length>1&&document.referrer.indexOf(location.host)>-1){{history.back();return false}}">← All news</a><div class="social"><a class="soc soc-x" href="https://x.com/wrestlingWCN" target="_blank" rel="noopener me" aria-label="Follow WCN on X" title="Follow @wrestlingWCN on X"><svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M18.9 2H22l-7.2 8.2L23.3 22h-6.6l-5.2-6.8L5.5 22H2.4l7.7-8.8L1.9 2h6.8l4.7 6.2L18.9 2zm-1.2 18h1.8L7.4 3.9H5.5L17.7 20z"/></svg></a><a class="soc soc-fb" href="https://www.facebook.com/p/Wrestling-Central-News-61595290838604/" target="_blank" rel="noopener me" aria-label="Follow WCN on Facebook" title="Follow WCN on Facebook"><svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M13.5 22v-8.2h2.8l.4-3.2h-3.2V8.5c0-.9.3-1.6 1.6-1.6h1.7V4.1c-.3 0-1.3-.1-2.5-.1-2.5 0-4.2 1.5-4.2 4.3v2.4H7.3v3.2h2.8V22h3.4z"/></svg></a></div></div></header>
{ad("leaderboard", "728×90 Leaderboard", "ad-leader")}
<main class="layout"><aside class="side">{ad("leftSkyscraper", "300×600 Half-page", "ad-sky")}</aside>
<article class="story"><div class="tags">{conf}{tags}</div><h1>{e(c["title"])}</h1><div class="byline">WCN Staff · {nice(c["ts"])}</div>
{f'<div class="story-hero"><img class="bg" src="{e(img)}" alt="" aria-hidden="true" referrerpolicy="no-referrer"><img class="fg" src="{e(img)}" alt="{e(c["title"])}" referrerpolicy="no-referrer"></div>' if img else f'<div class="story-hero ph-h"><span>{c["categories"][0]}</span></div>'}
{f'<p class="pcredit"><a href="{e(c["image_credit"]["url"])}" rel="nofollow noopener" target="_blank">{e(c["image_credit"]["text"])}</a></p>' if c.get("image_credit") else ''}{quote}<div class="prose">{"".join(body)}</div>{tl}
<p class="credit">Source: <a href="{e(c["link"])}" rel="nofollow noopener" target="_blank">{e(c["source"])}</a></p>
{ad("storyBottom", "Responsive Banner")}
<section class="related"><h2>More {e(c["categories"][0])} news</h2><div class="relgrid">{rel}</div></section></article>
<aside class="side">{ad("rightSkyscraper", "300×600 Half-page", "ad-sky")}</aside></main>
<footer>© 2026 Wrestling Central News (WCN) · <a href="../privacy.html">Privacy Policy</a> · <a href="mailto:wcn@mail.grokbot.com">Contact</a> · Follow us: <a href="https://x.com/wrestlingWCN" target="_blank" rel="noopener">X @wrestlingWCN</a> · <a href="https://www.facebook.com/p/Wrestling-Central-News-61595290838604/" target="_blank" rel="noopener">Facebook</a></footer>
{ad("mobileSticky", "320×50 Mobile", "ad-mobile")}<script src="../story.js"></script></body></html>'''
def build(clusters):
    tmp = SD + ".new"; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    bycat = {}
    for c in clusters: bycat.setdefault(c["categories"][0], []).append(c)
    for c in clusters:
        rel = [r for r in bycat[c["categories"][0]] if r is not c][:6]
        open(os.path.join(tmp, os.path.basename(c["url"])), "w").write(page(c, rel))
    shutil.rmtree(SD, ignore_errors=True); os.replace(tmp, SD)   # only current (<=60 day) stories survive
    sm = [f"<url><loc>{SITE}</loc><changefreq>always</changefreq><priority>1.0</priority></url>"] + \
         [f"<url><loc>{SITE}{c['url']}</loc><lastmod>{iso(c['ts'])}</lastmod></url>" for c in clusters]
    open(os.path.join(PUB, "sitemap.xml"), "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(sm) + "</urlset>")
    open(os.path.join(PUB, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITE}sitemap.xml\n")
