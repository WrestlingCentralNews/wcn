"""Spanish home (/es/), trust pages (about, masthead, editorial & corrections policy, contact, staff byline pages; EN + ES),
sitemaps (sitemap.xml, es/sitemap.xml, sitemap-news.xml) and robots.txt."""
import os, re, json, time, html
import chrome as C, imgmeta
from chrome import e, SITE
ROOT = os.path.dirname(os.path.abspath(__file__)); PUB = os.path.join(ROOT, "public")
CATC = {"WWE": "#f26a14", "AEW": "#7cd618", "TNA": "#4ea8ff", "Indie": "#f05fc1", "Global": "#2fd3b4"}
EMAIL = "wcn@mail.grokbot.com"   # the ONLY public contact; never the owner's personal details
def write(rel, s):
    full = os.path.join(PUB, rel, "index.html") if rel.endswith("/") else os.path.join(PUB, rel)
    os.makedirs(os.path.dirname(full), exist_ok=True); open(full, "w").write(s)
def simple(rel, lang, title, desc, h1, body, alt_rel, ld=None, active=None):
    url = SITE + rel; other = SITE + alt_rel
    alts = {"en": url, "es": other} if lang == "en" else {"en": other, "es": url}
    en_u, es_u = ("/" + rel, "/" + alt_rel) if lang == "en" else ("/" + alt_rel, "/" + rel)
    write(rel, C.head(title, desc, url, lang, alts=alts, ld=ld or []) +
          f'<body><div class="spot s1"></div><div class="spot s2"></div>{C.header(lang, en_u, es_u, active)}<main class="nl-page legal-page"><h1>{h1}</h1>{body}</main>{C.footer(lang)}{C.SCRIPTS}</body></html>')
    return [rel]
TRUST = {
"about": {
 "en": ("About Wrestling Central News", "Wrestling Central News (WCN) covers WWE, AEW, TNA, the independents and wrestling around the world, updated around the clock.", "About <b>WCN</b>",
  f"""<p class="lede">Wrestling Central News (WCN) is an independent pro wrestling news site covering WWE, AEW, TNA, the independent scene and promotions around the world, in English and Spanish.</p>
<h2>What we do</h2><p>We monitor official promotion announcements and established wrestling news outlets around the clock and publish a refreshed feed every 15 minutes. Each WCN story has an original headline and summary written in our own words, says when the story was first reported and last updated, and links to the original report so readers can go to the source.</p>
<h2>How stories are produced</h2><p>WCN uses automated tools, including AI writing assistance, to draft headlines, summaries, Spanish translations and longer write-ups from the reporting of trusted outlets. Editorial rules decide what gets published: we prioritise official sources and outlets with a strong track record, we flag stories confirmed by several outlets, we hold back single-source reports from low-trust sites, and we don't publish rumor roundups, opinion columns or listicles as news. Read our <a href="/editorial-policy/">editorial and corrections policy</a>.</p>
<h2>Shows and events</h2><p>Our <a href="/shows/">show pages</a> collect the card, results and news for every episode of WWE Raw, SmackDown, NXT, AEW Dynamite, AEW Collision and TNA iMPACT, plus premium live events and PPVs. See the <a href="/upcoming/">upcoming events</a> schedule.</p>
<h2>Contact</h2><p>Tips, corrections and business enquiries: <a href="mailto:{EMAIL}">{EMAIL}</a>. More on our <a href="/contact/">contact page</a>.</p>"""),
 "es": ("Quiénes somos: Wrestling Central News", "Wrestling Central News (WCN) cubre WWE, AEW, TNA, las independientes y la lucha libre de todo el mundo, las 24 horas.", "Quiénes <b>somos</b>",
  f"""<p class="lede">Wrestling Central News (WCN) es un sitio independiente de noticias de lucha libre que cubre WWE, AEW, TNA, la escena independiente y empresas de todo el mundo, en inglés y en español.</p>
<h2>Qué hacemos</h2><p>Seguimos las 24 horas los anuncios oficiales de las empresas y a los medios de lucha libre más reconocidos, y actualizamos las noticias cada 15 minutos. Cada noticia de WCN tiene un titular y un resumen propios, indica cuándo se publicó y cuándo se actualizó, y enlaza al reporte original.</p>
<h2>Cómo producimos las noticias</h2><p>WCN utiliza herramientas automatizadas, incluida la asistencia de inteligencia artificial, para redactar titulares, resúmenes, traducciones al español y artículos más extensos a partir de la información de medios confiables. Nuestras reglas editoriales deciden qué se publica: damos prioridad a las fuentes oficiales y a los medios con buena trayectoria, señalamos las noticias confirmadas por varios medios, no publicamos reportes de una sola fuente poco confiable y no presentamos rumores, columnas de opinión ni listas como noticias. Lee nuestra <a href="/es/politica-editorial/">política editorial y de correcciones</a>.</p>
<h2>Programas y eventos</h2><p>En nuestras <a href="/es/programas/">páginas de programas</a> reunimos la cartelera, los resultados y las noticias de cada episodio de WWE Raw, SmackDown, NXT, AEW Dynamite, AEW Collision y TNA iMPACT, además de los eventos premium y PPV. Consulta los <a href="/es/proximos-eventos/">próximos eventos</a>.</p>
<h2>Contacto</h2><p>Datos, correcciones y consultas comerciales: <a href="mailto:{EMAIL}">{EMAIL}</a>. Más en nuestra <a href="/es/contacto/">página de contacto</a>.</p>""")},
"masthead": {
 "en": ("Masthead | Wrestling Central News", "Who publishes Wrestling Central News and how to reach the WCN Staff editorial team.", "Masthead",
  f"""<p class="lede">Wrestling Central News is published by WCN. All stories are produced by the <a href="/authors/wcn-staff/">WCN Staff</a> editorial team under our <a href="/editorial-policy/">editorial policy</a>.</p>
<dl class="facts"><div><dt>Publication</dt><dd>Wrestling Central News (WCN)</dd></div><div><dt>Editions</dt><dd>English (<a href="/">wrestlingcentralnews.com</a>) and Spanish (<a href="/es/">/es/</a>)</dd></div>
<div><dt>Editorial team</dt><dd>WCN Staff</dd></div><div><dt>Coverage</dt><dd>WWE, AEW, TNA, independent wrestling, NJPW, CMLL, AAA, Stardom and global promotions</dd></div>
<div><dt>Editorial contact &amp; corrections</dt><dd><a href="mailto:{EMAIL}">{EMAIL}</a></dd></div><div><dt>Follow</dt><dd><a href="{C.X_URL}" rel="noopener">X @wrestlingWCN</a> · <a href="{C.FB}" rel="noopener">Facebook</a></dd></div></dl>"""),
 "es": ("Equipo editorial | Wrestling Central News", "Quién publica Wrestling Central News y cómo contactar al equipo de Redacción WCN.", "Equipo editorial",
  f"""<p class="lede">Wrestling Central News es publicado por WCN. Todas las noticias las produce el equipo de <a href="/es/autores/redaccion-wcn/">Redacción WCN</a> según nuestra <a href="/es/politica-editorial/">política editorial</a>.</p>
<dl class="facts"><div><dt>Publicación</dt><dd>Wrestling Central News (WCN)</dd></div><div><dt>Ediciones</dt><dd>Inglés (<a href="/">wrestlingcentralnews.com</a>) y español (<a href="/es/">/es/</a>)</dd></div>
<div><dt>Equipo editorial</dt><dd>Redacción WCN</dd></div><div><dt>Cobertura</dt><dd>WWE, AEW, TNA, lucha independiente, NJPW, CMLL, AAA, Stardom y empresas de todo el mundo</dd></div>
<div><dt>Contacto editorial y correcciones</dt><dd><a href="mailto:{EMAIL}">{EMAIL}</a></dd></div><div><dt>Síguenos</dt><dd><a href="{C.X_URL}" rel="noopener">X @wrestlingWCN</a> · <a href="{C.FB}" rel="noopener">Facebook</a></dd></div></dl>""")},
"policy": {
 "en": ("Editorial & Corrections Policy | Wrestling Central News", "How Wrestling Central News chooses sources, writes stories, uses AI, labels updates and corrects mistakes.", "Editorial &amp; corrections policy",
  f"""<p class="lede">These are the standards behind every WCN story.</p>
<h2>Sourcing</h2><p>We report from official promotion announcements and established wrestling news outlets. Sources are ranked by track record; stories reported only by low-trust sites and not confirmed elsewhere are not published. When several outlets confirm a story we say so on the card ("Confirmed by N sources"). Every story names and links its source.</p>
<h2>Original writing and AI use</h2><p>Headlines, summaries and write-ups are written in our own words; we don't copy other outlets' text. WCN uses AI writing assistance to draft that text and the Spanish translations, under strict instructions: no invented facts, names, numbers, quotes, match results or dates. Show and event pages only list matches and results that appear in reports from trusted outlets, and dates come from official or trusted announcements.</p>
<h2>What we don't publish as news</h2><p>Rumor roundups, speculation, opinion columns, predictions, grades and listicles are filtered out of the news feed.</p>
<h2>Dates and updates</h2><p>Each story shows when it was first reported and, for developing stories, when it was last updated, with a timeline of follow-up reports.</p>
<h2 id="corrections">Corrections</h2><p>If we get something wrong, we fix it. Email <a href="mailto:{EMAIL}?subject=Correction">{EMAIL}</a> with the story link and what needs correcting. Verified errors are corrected promptly, and the story's "updated" time changes. Stories that turn out to be false are removed.</p>
<h2>Images</h2><p>Photos come from the source report or from freely licensed collections such as Wikimedia Commons, with credit shown where required.</p>
<h2>Independence</h2><p>WCN is supported by advertising. Advertisers have no say over our coverage.</p>"""),
 "es": ("Política editorial y de correcciones | Wrestling Central News", "Cómo Wrestling Central News elige sus fuentes, redacta las noticias, usa la IA, marca las actualizaciones y corrige errores.", "Política editorial y de correcciones",
  f"""<p class="lede">Estos son los criterios detrás de cada noticia de WCN.</p>
<h2>Fuentes</h2><p>Informamos a partir de anuncios oficiales de las empresas y de medios de lucha libre reconocidos. Clasificamos las fuentes según su trayectoria; no publicamos noticias que solo reporta un sitio poco confiable sin confirmación de otros medios. Cuando varios medios confirman una noticia, lo indicamos ("Confirmado por N fuentes"). Cada noticia nombra y enlaza su fuente.</p>
<h2>Redacción propia e inteligencia artificial</h2><p>Los titulares, resúmenes y artículos están redactados con nuestras propias palabras; no copiamos textos de otros medios. WCN utiliza asistencia de IA para redactar esos textos y las traducciones al español, con instrucciones estrictas: nada de hechos, nombres, cifras, citas, resultados ni fechas inventados. Las páginas de programas y eventos solo incluyen combates y resultados que aparecen en reportes de medios confiables, y las fechas provienen de anuncios oficiales o confiables.</p>
<h2>Lo que no publicamos como noticia</h2><p>Recopilaciones de rumores, especulación, columnas de opinión, predicciones, calificaciones y listas quedan fuera del feed de noticias.</p>
<h2>Fechas y actualizaciones</h2><p>Cada noticia indica cuándo se publicó y, si está en desarrollo, cuándo se actualizó por última vez, con una cronología de los reportes posteriores.</p>
<h2 id="correcciones">Correcciones</h2><p>Si nos equivocamos, lo corregimos. Escribe a <a href="mailto:{EMAIL}?subject=Correcci%C3%B3n">{EMAIL}</a> con el enlace de la noticia y lo que hay que corregir. Los errores verificados se corrigen de inmediato y cambia la hora de "actualizado". Las noticias que resulten falsas se eliminan.</p>
<h2>Imágenes</h2><p>Las fotos provienen del reporte original o de colecciones con licencia libre, como Wikimedia Commons, con el crédito correspondiente.</p>
<h2>Independencia</h2><p>WCN se financia con publicidad. Los anunciantes no influyen en nuestra cobertura.</p>""")},
"contact": {
 "en": ("Contact Wrestling Central News", "How to contact Wrestling Central News: news tips, corrections, advertising and partnerships.", "Contact <b>WCN</b>",
  f"""<p class="lede">The best way to reach the WCN Staff is by email: <a href="mailto:{EMAIL}">{EMAIL}</a>.</p>
<ul class="nl-perks"><li><b>News tips</b>Send the link or details; we publish only what trusted outlets or official sources can confirm.</li>
<li><b>Corrections</b>Include the story link and what's wrong. See our <a href="/editorial-policy/#corrections">corrections policy</a>.</li>
<li><b>Advertising &amp; partnerships</b>Use the same address with "Advertising" in the subject.</li></ul>
<p>You can also message us on <a href="{C.X_URL}" rel="noopener">X @wrestlingWCN</a> or <a href="{C.FB}" rel="noopener">Facebook</a>.</p>"""),
 "es": ("Contacto | Wrestling Central News", "Cómo contactar a Wrestling Central News: datos, correcciones, publicidad y alianzas.", "Contacto",
  f"""<p class="lede">La mejor forma de contactar a la Redacción WCN es por correo: <a href="mailto:{EMAIL}">{EMAIL}</a>.</p>
<ul class="nl-perks"><li><b>Datos y noticias</b>Envía el enlace o los detalles; solo publicamos lo que confirman medios confiables o fuentes oficiales.</li>
<li><b>Correcciones</b>Incluye el enlace de la noticia y el error. Consulta nuestra <a href="/es/politica-editorial/#correcciones">política de correcciones</a>.</li>
<li><b>Publicidad y alianzas</b>Usa la misma dirección con "Publicidad" en el asunto.</li></ul>
<p>También puedes escribirnos en <a href="{C.X_URL}" rel="noopener">X @wrestlingWCN</a> o <a href="{C.FB}" rel="noopener">Facebook</a>.</p>""")},
}
def build_trust(clusters, tr):
    out = []
    org_ld = dict(C.PUBLISHER, **{"@context": "https://schema.org"})
    for key, langs in TRUST.items():
        en_rel, es_rel = C.STATIC[key][0].lstrip("/"), C.STATIC[key][1].lstrip("/")
        for lang, (title, desc, h1, body) in langs.items():
            rel, alt = (en_rel, es_rel) if lang == "en" else (es_rel, en_rel)
            typ = {"about": "AboutPage", "contact": "ContactPage"}.get(key, "WebPage")
            ld = [{"@context": "https://schema.org", "@type": typ, "name": title, "url": SITE + rel, "inLanguage": lang, "publisher": C.PUBLISHER}]
            if key == "about": ld.append(org_ld)
            out += simple(rel, lang, title, desc, h1, body, alt, ld)
    # staff byline pages with the latest stories
    for lang in ("en", "es"):
        rel = C.STATIC["staff"][1 if lang == "es" else 0].lstrip("/"); alt = C.STATIC["staff"][0 if lang == "es" else 1].lstrip("/")
        if lang == "en":
            items = [(c["title"], c["url"], c) for c in clusters[:30]]
            title, desc, h1 = "WCN Staff | Wrestling Central News", "Stories by the WCN Staff, the editorial team of Wrestling Central News.", "WCN Staff"
            intro = f'<p class="lede">WCN Staff is the editorial team behind Wrestling Central News. Stories are produced under our <a href="/editorial-policy/">editorial policy</a>, with original headlines and summaries and a link to every source. Contact: <a href="mailto:{EMAIL}">{EMAIL}</a>.</p><h2>Latest stories</h2>'
        else:
            items = [(tr[c["id"]]["t"], tr[c["id"]]["url"], c) for c in clusters if c["id"] in tr][:30]
            title, desc, h1 = "Redacción WCN | Wrestling Central News", "Noticias de la Redacción WCN, el equipo editorial de Wrestling Central News.", "Redacción WCN"
            intro = f'<p class="lede">Redacción WCN es el equipo editorial de Wrestling Central News. Las noticias se producen según nuestra <a href="/es/politica-editorial/">política editorial</a>, con titulares y resúmenes propios y el enlace a cada fuente. Contacto: <a href="mailto:{EMAIL}">{EMAIL}</a>.</p><h2>Últimas noticias</h2>'
        lis = "".join(f'<li><a href="/{e(u)}">{e(t)}</a><span><time datetime="{C.iso(c.get("first_ts", c["ts"]))}">{C.stamp(c.get("first_ts", c["ts"]), lang)}</time></span></li>' for t, u, c in items)
        ld = [{"@context": "https://schema.org", "@type": "ProfilePage", "url": SITE + rel, "inLanguage": lang, "mainEntity": dict(C.staff_author(lang), description=desc, parentOrganization=C.PUBLISHER)}]
        out += simple(rel, lang, title, desc, h1, intro + f'<ol class="stafflist">{lis}</ol>', alt, ld)
    return out
# ---------- Spanish home ----------
BRK_ES = '<span class="tag brk">ÚLTIMA HORA</span>'
# a photo that fails to load removes itself and its blurred copy, never the promotion placeholder (.ph) under it (mirrors app.js)
FGERR = "var b=this.parentNode&&this.parentNode.querySelector('img.bg');b&&b.remove();this.remove()"
def card_html(c, L, n, hero=False):
    col = CATC.get(c["categories"][0]); img = c.get("image") or ""
    ld = 'fetchpriority="high"' if hero else 'loading="lazy"'   # lead card is the LCP image: load it first, never lazily
    wh = f' width="{c["img_w"]}" height="{c["img_h"]}"' if c.get("img_w") and c.get("img_h") else ""
    im = (f'<img class="bg" {ld} referrerpolicy="no-referrer" src="{e(img)}" alt="" aria-hidden="true" onerror="this.remove()"><img class="fg{imgmeta.fill_cls(c.get('img_w'), c.get('img_h'))}" {ld}{wh} referrerpolicy="no-referrer" src="{e(img)}" alt="" onerror="{FGERR}">' if img else "")
    u = L["url"][3:]   # relative to /es/
    return (f'<article class="card {"hero" if hero else ""} in" style="--c:{col}" data-cat="{c["categories"][0]}" data-pos="{n}"><a class="img" href="{e(u)}" aria-hidden="true" tabindex="-1"><div class="ph">{c["categories"][0]}</div>{im}</a><div class="body">'
            f'<div class="tags">{BRK_ES if hero and c.get("brk") else ""}{"".join(f"<span class=tag style=--c:{CATC[k]}>{k}</span>" for k in c["categories"])}</div><h2><a href="{e(u)}">{e(L["t"])}</a></h2><p>{e(L["s"])}</p>'
            f'<div class="meta"><span>{e(c["source"])}</span><a href="{e(u)}">Leer más →</a></div></div></article>')
def _ago_es(t):   # same wording as app.js ago() (es); app.js re-renders it on load
    m = max(0, time.time() - int(t)) / 60
    return "hace " + (f"{max(1, int(m))} min" if m < 60 else f"{int(m // 60)}h" if m < 1440 else f"{int(m // 1440)}d")
def mini_html(c, L, n):
    col = CATC.get(c["categories"][0]); img = c.get("image") or ""; u = L["url"][3:]
    im = f'<img class="fg" loading="lazy" referrerpolicy="no-referrer" src="{e(img)}" alt="" onerror="this.remove()">' if img else ""
    return (f'<article class="card mini in" style="--c:{col}" data-cat="{c["categories"][0]}" data-pos="{n}"><a class="img" href="{e(u)}" aria-hidden="true" tabindex="-1"><div class="ph">{c["categories"][0]}</div>{im}</a><div class="body">'
            f'<div class="tags">{BRK_ES if c.get("brk") else ""}<span class="tag" style="--c:{col}">{c["categories"][0]}</span></div><h2><a href="{e(u)}">{e(L["t"])}</a></h2><div class="meta"><span>{_ago_es(c["ts"])}</span></div></div></article>')
def top_html(items):
    """Top stories block (lead + 4), same pick as app.js for the default all-promotions view."""
    import toppick
    lead, sec = toppick.pick([c for c, L in items])
    if not lead: return "", items
    T = [lead] + sec; Lm = {id(c): L for c, L in items}
    h = f'<h2 class="top-h">Lo más importante</h2>{card_html(lead, Lm[id(lead)], 0, True)}<div class="minis">{"".join(mini_html(c, Lm[id(c)], k + 1) for k, c in enumerate(sec))}</div>'
    return h, [(c, L) for c, L in items if all(c is not t for t in T)]
def build_es_home(clusters, tr):
    items = [(c, tr[c["id"]]) for c in clusters if c["id"] in tr]
    title = "Noticias de lucha libre: WWE, AEW, TNA y más | Wrestling Central News en español"
    desc = "Noticias de lucha libre en español: WWE, AEW, TNA, la escena independiente, CMLL, AAA y NJPW. Resultados de Raw, SmackDown, Dynamite y más, actualizados cada 15 minutos."
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": "Wrestling Central News en español", "url": SITE + "es/", "inLanguage": "es", "publisher": C.PUBLISHER},
          {"@context": "https://schema.org", "@type": "ItemList", "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": SITE + L["url"]} for i, (c, L) in enumerate(items[:20])]}]
    top, rest = top_html(items); o = 5 if top else 0
    first = "".join(card_html(c, L, i + o, hero=not top and i == 0) for i, (c, L) in enumerate(rest[:12]))
    tick = "".join(f'<span><b>{c["categories"][0]}</b> {e(L["t"])}</span>' for c, L in items[:15])
    s = (C.head(title, desc, SITE + "es/", "es", alts={"en": SITE, "es": SITE + "es/"}, ld=ld, ads=True) +
         f'''<body><div class="spot s1"></div><div class="spot s2"></div>
{C.header("es", "/", "/es/", "news").replace('<nav class="navl"', '<div class="rail"><nav class="navl"', 1).replace('</header>', '<nav class="filters" id="filters"></nav></div><div class="tools"><input id="q" placeholder="Busca luchadores, programas, empresas…" aria-label="Buscar"><span id="count"></span><span class="live" style="margin-left:auto"><i></i> EN VIVO · <span id="updated">cargando…</span></span></div></header>')}
<div class="ad ad-leader" data-slot="leaderboard" data-size="728×90 Leaderboard"></div>
<div class="ticker"><div id="ticker">{tick}</div></div>
<h1 class="es-h1">Noticias de lucha libre en español</h1>
<main class="layout"><aside class="side"><div class="ad ad-sky" data-slot="leftSkyscraper" data-size="300×600 Half-page"></div></aside>
<div class="mid"><section id="lead" class="lead" aria-label="Lo más importante">{top}</section><section id="feed" class="feed">{first}</section></div>
<aside class="side"><div class="ad ad-sky" data-slot="rightSkyscraper" data-size="300×600 Half-page"></div></aside></main>
<button id="more" class="more">Cargar más noticias</button>
<div class="ad ad-footer" data-slot="footer" data-size="970×90 Footer Banner"></div>
{__import__("pages").nl_block("footer-home-es", base="/", lang="es")}
{C.footer("es")}
<div class="ad ad-mobile" data-slot="mobileSticky" data-size="320×50 Mobile"></div>
<button id="toTop" title="Volver arriba">▲</button>
<script src="/app.js"></script>{C.SCRIPTS}</body></html>''')
    write("es/", s)
    # Spanish feed data for app.js (urls relative to /es/)
    es_items = []
    for c, L in items:
        x = {k: v for k, v in c.items() if k not in ("long", "raw_title", "_hot")}
        x["title"], x["summary"], x["url"] = L["t"], L["s"], L["url"][3:]
        x["updates"] = [{"ts": u["ts"], "source": u["source"], "link": u["link"], "title": f"Reporte de {u['source']}", "line": ""} for u in c.get("updates", [])]
        es_items.append(x)
    json.dump({"updated": int(time.time()), "count": len(es_items), "items": es_items}, open(os.path.join(PUB, "es", "news.json"), "w"), ensure_ascii=False)
    return ["es/"]
# ---------- sitemaps ----------
def urlset(entries, alts=False):
    ns = ' xmlns:xhtml="http://www.w3.org/1999/xhtml"' if alts else ""
    body = ""
    for loc, lastmod, alt in entries:
        body += f"<url><loc>{html.escape(loc)}</loc>" + (f"<lastmod>{lastmod}</lastmod>" if lastmod else "")
        if alt:
            for l, u in alt.items(): body += f'<xhtml:link rel="alternate" hreflang="{l}" href="{html.escape(u)}"/>'
            body += f'<xhtml:link rel="alternate" hreflang="x-default" href="{html.escape(alt["en"])}"/>'
        body += "</url>"
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"{ns}>{body}</urlset>'
def news_sitemap(clusters, tr, hours=48):
    cut = time.time() - hours * 3600; out = []
    for c in clusters:
        if c.get("first_ts", c["ts"]) < cut: continue
        out.append((SITE + c["url"], "en", c["title"], c.get("first_ts", c["ts"])))
        if c["id"] in tr: out.append((SITE + tr[c["id"]]["url"], "es", tr[c["id"]]["t"], c.get("first_ts", c["ts"])))
    body = "".join(f"<url><loc>{html.escape(u)}</loc><news:news><news:publication><news:name>Wrestling Central News</news:name><news:language>{l}</news:language></news:publication>"
                   f"<news:publication_date>{C.iso(ts)}</news:publication_date><news:title>{html.escape(t)}</news:title></news:news></url>" for u, l, t, ts in out[:1000])
    open(os.path.join(PUB, "sitemap-news.xml"), "w").write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
                                                          'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">' + body + "</urlset>")
    return len(out)
def robots():
    open(os.path.join(PUB, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\nSitemap: {SITE}sitemap.xml\nSitemap: {SITE}es/sitemap.xml\nSitemap: {SITE}sitemap-news.xml\n")
