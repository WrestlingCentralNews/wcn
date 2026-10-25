"""Shared page chrome for generated WCN pages: <head>, header (nav + EN|ES toggle), footer, i18n strings, date helpers."""
import html, json, datetime
from zoneinfo import ZoneInfo
SITE = "https://wrestlingcentralnews.com/"
ET = ZoneInfo("America/New_York")
FB = "https://www.facebook.com/p/Wrestling-Central-News-61595290838604/"
X_URL = "https://x.com/wrestlingWCN"
e = lambda s: html.escape(s or "", quote=True)
# Google tag + Consent Mode v2 (region-aware). Kept identical to the existing GA_HEAD (pages.py re-exports it).
# Owner device opt-out (2026-10-20): ?wcn_me=1 sets localStorage+cookie wcn_me=1 (?wcn_me=0 clears it); while set, gtag.js is not
# loaded (plus GA's official ga-disable flag), analytics.js skips Clarity and shows 'Analytics off on this device' in the footer, and
# the wcnVisits counter (pwa.js/push.js) does not increment. AdSense stays as is (static tag; viewing own pages is allowed, never click).
GA_HEAD = "<script>(function(){var K='wcn_me',on=false,ck=function(){return /(?:^|; )wcn_me=1(?:;|$)/.test(document.cookie)};try{var q=new URLSearchParams(location.search),v=q.get(K);if(v==='1'){localStorage.setItem(K,'1')}else if(v==='0'){localStorage.removeItem(K);document.cookie=K+'=; Max-Age=0; path=/'}on=v!=='0'&&(localStorage.getItem(K)==='1'||ck());if(on){localStorage.setItem(K,'1');document.cookie=K+'=1; Max-Age=63072000; path=/; SameSite=Lax'+(location.protocol==='https:'?'; Secure':'')}if(v!==null){q.delete(K);var s=q.toString();history.replaceState(history.state,'',location.pathname+(s?'?'+s:'')+location.hash)}}catch(e){on=ck()}window.wcnMe=on;if(on)window['ga-disable-G-VXM9BRSC0B']=true})();</script>\n<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}gtag('consent','default',{ad_storage:'denied',analytics_storage:'denied',ad_user_data:'denied',ad_personalization:'denied',wait_for_update:500,region:['AT','BE','BG','HR','CY','CZ','DK','EE','FI','FR','DE','GR','HU','IS','IE','IT','LV','LI','LT','LU','MT','NL','NO','PL','PT','RO','SK','SI','ES','SE','GB','CH']});gtag('consent','default',{ad_storage:'granted',analytics_storage:'granted',ad_user_data:'granted',ad_personalization:'granted'});try{var wc=localStorage.getItem('wcn_consent');if(wc){var wv=wc==='yes'?'granted':'denied';gtag('consent','update',{ad_storage:wv,analytics_storage:wv,ad_user_data:wv,ad_personalization:wv})}}catch(e){}gtag('js',new Date());gtag('config','G-VXM9BRSC0B');</script>\n<script>if(!window.wcnMe){(function(){var s=document.createElement('script');s.async=true;s.src='https://www.googletagmanager.com/gtag/js?id=G-VXM9BRSC0B';document.head.appendChild(s)})()}</script>"
ADSENSE = '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-6049350409363098" crossorigin="anonymous"></script>'
# Language: first-visit client-side redirect to the matching /es/ page when the browser's top preferred language is Spanish.
# Never for bots/headless, never when the reader has a saved choice (wcn_lang) or has visited before; the EN|ES toggle saves the choice.
# Must come AFTER the hreflang <link>s in <head>. Server responses/hreflang are never changed.
LANG_JS = ("<script>(function(){try{var S=localStorage,K='wcn_lang';document.addEventListener('click',function(ev){var a=ev.target.closest&&ev.target.closest('a[data-lang]');"
           "if(a){try{S.setItem(K,a.getAttribute('data-lang'))}catch(x){}}},true);var seen=S.getItem(K)||S.getItem('wcn_v')||S.getItem('wcn_seen')||S.getItem('wcn_consent')||S.getItem('wcn_filters');"
           "S.setItem('wcn_v','1');if(seen||document.documentElement.lang!=='en')return;var n=navigator,ua=n.userAgent||'';"
           "if(n.webdriver||/bot|crawl|spider|slurp|mediapartners|google|bing|yandex|baidu|duckduck|facebookexternal|embedly|preview|lighthouse|headless|pagespeed|validator/i.test(ua))return;"
           "var L=(n.languages&&n.languages.length?n.languages[0]:n.language)||'';if(!/^es(-|$)/i.test(L))return;"
           "var a=document.querySelector('link[rel=alternate][hreflang=es]');if(a&&a.href&&a.href!==location.href)location.replace(a.href)}catch(x){}})();</script>")
ICONS = ('<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png"><link rel="icon" type="image/png" sizes="512x512" href="/favicon-512.png"><link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">'
         '<meta name="theme-color" content="#0a1a18"><link rel="manifest" href="/manifest.webmanifest"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-capable" content="yes">'
         '<meta name="apple-mobile-web-app-status-bar-style" content="black"><meta name="apple-mobile-web-app-title" content="WCN">'
         '<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;600;800&display=swap" rel="stylesheet">')
def hreflang(alts):
    """alts: {'en': abs_url, 'es': abs_url}; emits en, es and x-default (English)."""
    if not alts: return ""
    s = "".join(f'<link rel="alternate" hreflang="{l}" href="{e(u)}">' for l, u in alts.items() if u)
    if alts.get("en"): s += f'<link rel="alternate" hreflang="x-default" href="{e(alts["en"])}">'
    return s
def feeds(lang):
    if lang == "es": return f'<link rel="alternate" type="application/rss+xml" title="Wrestling Central News en español" href="{SITE}es/feed.xml">'
    return f'<link rel="alternate" type="application/rss+xml" title="Wrestling Central News" href="{SITE}feed.xml">'
def head(title, desc, canon, lang="en", alts=None, og_type="website", image=None, ld=None, ads=False, extra="", robots="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1"):
    img = image or SITE + "og-image.jpg"
    lds = "".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in (ld or []))
    loc = "es_LA" if lang == "es" else "en_US"
    return (f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8">\n{GA_HEAD}\n{ADSENSE if ads else ""}'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="{robots}">'
            f'<title>{e(title)}</title><meta name="description" content="{e(desc)}"><link rel="canonical" href="{e(canon)}">{hreflang(alts)}{LANG_JS}{feeds(lang)}'
            f'<meta property="og:type" content="{og_type}"><meta property="og:site_name" content="Wrestling Central News"><meta property="og:locale" content="{loc}"><meta property="og:title" content="{e(title)}">'
            f'<meta property="og:description" content="{e(desc)}"><meta property="og:url" content="{e(canon)}"><meta property="og:image" content="{e(img)}">'
            f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:site" content="@wrestlingWCN"><meta name="twitter:image" content="{e(img)}">{extra}{lds}'
            f'{ICONS}<link rel="stylesheet" href="/style.css"><script src="/ads-config.js"></script><script src="/analytics.js"></script></head>')
T = {
 "en": {"home": "/", "news": "News", "shows": "Shows", "upcoming": "Upcoming", "shows_url": "/shows/", "upcoming_url": "/upcoming/",
        "about": "About", "masthead": "Masthead", "policy": "Editorial & corrections", "contact": "Contact", "privacy": "Privacy Policy", "terms": "Terms of Use", "newsletter": "Newsletter",
        "cookies": "Cookie settings", "follow": "Follow us", "all": "← All news", "lang_label": "Language"},
 "es": {"home": "/es/", "news": "Noticias", "shows": "Programas", "upcoming": "Próximos eventos", "shows_url": "/es/programas/", "upcoming_url": "/es/proximos-eventos/",
        "about": "Quiénes somos", "masthead": "Equipo editorial", "policy": "Política editorial y correcciones", "contact": "Contacto", "privacy": "Política de privacidad (inglés)", "terms": "Términos de uso", "newsletter": "Boletín",
        "cookies": "Configuración de cookies", "follow": "Síguenos", "all": "← Todas las noticias", "lang_label": "Idioma"},
}
STATIC = {  # (en path, es path) for the trust pages, linked from every footer
 "about": ("/about/", "/es/acerca-de/"), "masthead": ("/masthead/", "/es/equipo/"), "policy": ("/editorial-policy/", "/es/politica-editorial/"),
 "contact": ("/contact/", "/es/contacto/"), "terms": ("/terms/", "/es/terminos/"), "staff": ("/authors/wcn-staff/", "/es/autores/redaccion-wcn/"),
}
SOCIAL = (f'<div class="social"><a class="soc soc-x" href="{X_URL}" target="_blank" rel="noopener me" aria-label="Follow WCN on X" title="Follow @wrestlingWCN on X"><svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M18.9 2H22l-7.2 8.2L23.3 22h-6.6l-5.2-6.8L5.5 22H2.4l7.7-8.8L1.9 2h6.8l4.7 6.2L18.9 2zm-1.2 18h1.8L7.4 3.9H5.5L17.7 20z"/></svg></a>'
          f'<a class="soc soc-fb" href="{FB}" target="_blank" rel="noopener me" aria-label="Follow WCN on Facebook" title="Follow WCN on Facebook"><svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M13.5 22v-8.2h2.8l.4-3.2h-3.2V8.5c0-.9.3-1.6 1.6-1.6h1.7V4.1c-.3 0-1.3-.1-2.5-.1-2.5 0-4.2 1.5-4.2 4.3v2.4H7.3v3.2h2.8V22h3.4z"/></svg></a></div>')
def lang_toggle(lang, en_url, es_url):
    """Prominent EN | ES switch; links to the equivalent page (or the other edition's home). Click saves wcn_lang."""
    a = lambda l, u, lab: f'<a href="{e(u)}" hreflang="{l}" lang="{l}" data-lang="{l}"{" class=on aria-current=true" if l == lang else ""}>{lab}</a>'
    return f'<nav class="lang" aria-label="{T[lang]["lang_label"]}">{a("en", en_url or "/", "EN")}<span aria-hidden="true">|</span>{a("es", es_url or "/es/", "ES")}</nav>'
def navlinks(lang, active=None):
    t = T[lang]
    items = [("news", t["home"], t["news"]), ("shows", t["shows_url"], t["shows"]), ("upcoming", t["upcoming_url"], t["upcoming"])]
    return '<nav class="navl" aria-label="Sections">' + "".join(f'<a href="{u}"{" class=on" if k == active else ""}>{lab}</a>' for k, u, lab in items) + "</nav>"
def header(lang, en_url, es_url, active=None, back=False):
    t = T[lang]
    bk = (f'<a class="back" href="{t["home"]}" onclick="if(history.length>1&&document.referrer.indexOf(location.host)>-1){{history.back();return false}}">{t["all"]}</a>' if back else "")
    return (f'<header><div class="bar"><a class="logo" href="{t["home"]}"><img src="/logo-header.png" width="240" height="160" alt="WCN"><span>WRESTLING CENTRAL NEWS</span></a>'
            f'<div class="bar-r">{bk}{lang_toggle(lang, en_url, es_url)}{SOCIAL}</div></div>{navlinks(lang, active)}</header>')
def footer(lang):
    t = T[lang]; i = 1 if lang == "es" else 0
    rss = "/es/feed.xml" if lang == "es" else "/feed.xml"
    nl = "/newsletter/"
    return (f'<footer>© 2026 Wrestling Central News (WCN) · <a href="{STATIC["about"][i]}">{t["about"]}</a> · <a href="{STATIC["masthead"][i]}">{t["masthead"]}</a> · '
            f'<a href="{STATIC["policy"][i]}">{t["policy"]}</a> · <a href="{STATIC["contact"][i]}">{t["contact"]}</a> · <a href="/privacy.html">{t["privacy"]}</a> · <a href="{STATIC["terms"][i]}">{t["terms"]}</a> · '
            f'<a class="nl-link" href="{nl}">{t["newsletter"]}</a> · <a class="rss-link" href="{rss}" type="application/rss+xml">RSS</a> · '
            f'{t["follow"]}: <a href="{X_URL}" target="_blank" rel="noopener">X @wrestlingWCN</a> · <a href="{FB}" target="_blank" rel="noopener">Facebook</a> · '
            f'<a href="#" class="cookie-set" onclick="wcnCookieSettings();return false">{t["cookies"]}</a></footer>')
SCRIPTS = '<script src="/time.js" defer></script><script src="/newsletter.js" defer></script><script src="/pwa.js" defer></script><script src="/push.js" defer></script>'
# ---------- dates ----------
MES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
DIAS_PL = ["los lunes", "los martes", "los miércoles", "los jueves", "los viernes", "los sábados", "los domingos"]
DAYS_PL = ["Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays"]
def dlong(d, lang):   # Oct 19, 2026 / 19 de octubre de 2026
    return f"{d.day} de {MES[d.month-1]} de {d.year}" if lang == "es" else d.strftime("%b %-d, %Y")
def dfull(d, lang):   # Monday, Oct 19, 2026 / lunes 19 de octubre de 2026
    return f"{DIA[d.weekday()]} {dlong(d, lang)}" if lang == "es" else d.strftime("%A, %b %-d, %Y")
def tfmt(hh, mm, lang):
    h12 = hh % 12 or 12; ap = "a.m." if hh < 12 else "p.m."
    return (f"{h12}:{mm:02d} {ap}" if mm else f"{h12} {ap}") + " ET"
def stamp(ts, lang):
    d = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
    return (f"{d.day} de {MES[d.month-1]} de {d.year}, {d:%H:%M} UTC" if lang == "es" else d.strftime("%b %d, %Y · %H:%M UTC"))
def iso(ts): return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat(timespec="seconds")
def breadcrumbs(items):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(items)]}
def crumbs_html(items):
    return '<nav class="crumbs" aria-label="Breadcrumb">' + " › ".join(f'<a href="{e(u.replace(SITE, "/"))}">{e(n)}</a>' for n, u in items[:-1]) + f' › <span>{e(items[-1][0])}</span></nav>'
PUBLISHER = {"@type": "NewsMediaOrganization", "name": "Wrestling Central News", "alternateName": "WCN", "url": SITE,
             "logo": {"@type": "ImageObject", "url": SITE + "logo.png", "width": 600, "height": 399},
             "email": "wcn@mail.grokbot.com", "sameAs": [X_URL, FB],
             "publishingPrinciples": SITE + "editorial-policy/", "correctionsPolicy": SITE + "editorial-policy/#corrections",
             "masthead": SITE + "masthead/", "ethicsPolicy": SITE + "editorial-policy/", "diversityPolicy": None}
PUBLISHER = {k: v for k, v in PUBLISHER.items() if v}
def staff_author(lang="en"):
    return {"@type": "Organization", "name": "WCN Staff" if lang == "en" else "Redacción WCN", "url": SITE + STATIC["staff"][1 if lang == "es" else 0].lstrip("/")}
