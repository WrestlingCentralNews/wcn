"""WCN original pieces library (/originals/). Source files: originals/*.md (front matter + markdown).
Permanent URLs /originals/<slug>/ -- never pruned by 48h/stale/cleanup logic, index tier always strong.
GATED: nothing is written to public/ unless ORIGINALS_LIVE is True; drafts (status: draft) never publish."""
import os, re, json, glob, datetime, html, markdown
import chrome
from chrome import SITE, e

COLUMN_NAME = "GONEdii Gazette G."          # ONE place to change the column brand / byline
COLUMN_SHORT = "GG"
DISCLOSURE = "Drafted with AI from WCN's confirmed records, then edited and fact-checked by our team."
COLUMN_SLUG = "gonedii-gazette"            # column page: /originals/<COLUMN_SLUG>/ (keep stable once live)
ORIGINALS_LIVE = True                       # owner approved Nov 5 2026 (t643u)
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "originals")
CATC = {"WWE": "#f26a14", "AEW": "#7cd618", "TNA": "#4ea8ff", "NXT": "#f5c518", "AAA": "#2fd3b4", "Global": "#2fd3b4", "Indie": "#f05fc1"}
PROMO_RX = [(re.compile(r"\bAEW\b|Continental|Dynamite|Collision"), "AEW"), (re.compile(r"\bNXT\b"), "NXT"),
            (re.compile(r"\bAAA\b"), "AAA"), (re.compile(r"\bTNA\b|Knockouts"), "TNA"), (re.compile(r"WWE|Raw|SmackDown|WrestleMania"), "WWE")]

def load(path):
    raw = open(path, encoding="utf-8").read()
    _, fm, body = raw.split("---", 2)
    meta = {}
    for ln in fm.strip().splitlines():
        k, v = ln.split(":", 1); v = v.strip()
        meta[k.strip()] = json.loads(v) if v[:1] in '"[{' else v
    meta["body"] = body.strip(); meta["d"] = datetime.date.fromisoformat(meta["date"])
    meta["url"] = f"/originals/{meta['slug']}/"
    if meta.get("published"): meta["ts"] = datetime.datetime.fromisoformat(meta["published"]).timestamp()
    meta["mins"] = max(1, round(len(re.findall(r"\w+", body)) / 230))
    return meta

def pieces(include_drafts=False):
    ps = [load(p) for p in glob.glob(os.path.join(SRC, "*.md"))]
    ps = [p for p in ps if include_drafts or p.get("status") == "published"]
    return sorted(ps, key=lambda p: p["d"], reverse=True)

def _promo_of(text):
    for rx, p in PROMO_RX:
        if rx.search(text): return p
    return None

def render_body(p):
    h = markdown.markdown(p["body"], extensions=["tables"])
    for phrase, url in (p.get("links") or {}).items():          # link existing phrases only (first hit)
        h = h.replace(phrase, f'<a href="{url}">{phrase}</a>', 1)
    # promotion-colored rows in tables
    def row(m):
        promo = _promo_of(m.group(1)) or p.get("promo")
        return f'<tr style="--c:{CATC.get(promo, "#7cd618")}">{m.group(1)}</tr>'
    h = re.sub(r"<tr>(\s*<td>.*?)</tr>", row, h, flags=re.S)
    h = h.replace("<table>", '<div class="og-tbl"><table>').replace("</table>", "</table></div>")
    h = re.sub(r"<h2>(.*?)</h2>", r'<h2 class="og-h"><span></span>\1</h2>', h)
    # stat callout after the 3rd paragraph
    if p.get("stats"):
        cells = "".join(f'<div><b>{e(n)}</b><small>{e(l)}</small></div>' for n, l in (s.split("|", 1) for s in p["stats"]))
        box = f'<aside class="og-stats" aria-label="Key numbers">{cells}</aside>'
        parts = h.split("</p>", 3)
        if len(parts) == 4: h = "</p>".join(parts[:3]) + "</p>" + box + parts[3]
    for q in p.get("pullquotes") or []:                            # repeat an existing sentence as a pull quote
        i = h.find(q)
        if i > -1:
            j = h.find("</p>", i) + 4
            h = h[:j] + f'<blockquote class="og-pq"><p>“{e(q)}.”</p><cite>— {e(COLUMN_NAME)}</cite></blockquote>' + h[j:]
    h = re.sub(r"<hr\s*/?>\s*<p><em>(.*?)</em></p>", r'<div class="og-method"><b>How we built this</b><p>\1</p></div>', h, flags=re.S)
    return h

CSS = """
.og-wrap{max-width:820px;margin:0 auto;padding:0 18px 60px;position:relative;z-index:1}
.og-hero{position:relative;margin:26px -18px 30px;padding:46px 34px 34px;border-radius:22px;overflow:hidden;border:1px solid var(--line);
 background:radial-gradient(circle at 85% 15%,color-mix(in srgb,var(--c) 35%,transparent),transparent 55%),linear-gradient(160deg,#123a33,#0a1a18 70%)}
.og-hero svg.og-bg{position:absolute;right:-40px;top:-30px;width:360px;opacity:.16;pointer-events:none}
.og-kick{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:16px}
.og-col{font-family:'Bebas Neue';letter-spacing:3px;font-size:18px;color:var(--acc)}
.og-pill{font-family:'Bebas Neue';letter-spacing:1.5px;font-size:16px;padding:3px 14px;border-radius:999px;background:var(--c);color:#000;box-shadow:0 0 18px -4px var(--c)}
.og-orig{font-size:11px;letter-spacing:1.5px;text-transform:uppercase;border:1px solid var(--line);border-radius:999px;padding:4px 10px;color:var(--soft)}
.og-hero h1{font-family:'Bebas Neue';font-weight:400;font-size:clamp(40px,6vw,66px);line-height:.98;letter-spacing:1px;margin:0 0 14px;text-shadow:0 0 30px rgba(124,214,24,.18)}
.og-dek{font-size:19px;color:var(--soft);line-height:1.5;margin:0 0 24px;max-width:640px}
.og-by{display:flex;align-items:center;gap:14px;padding-top:18px;border-top:1px solid var(--line)}
.og-mono{width:50px;height:50px;border-radius:14px;display:grid;place-items:center;font-family:'Bebas Neue';font-size:26px;letter-spacing:1px;color:#000;background:linear-gradient(135deg,var(--acc),#c7ff6b);box-shadow:0 0 22px -4px var(--acc)}
.og-by a{color:var(--txt);font-weight:800;text-decoration:none}.og-by small{display:block;color:var(--mut);font-size:13px;margin-top:3px}
.og-body{font-size:18.5px;line-height:1.75;color:#e9f2ef}
.og-body p{margin:0 0 1.15em}.og-body strong{color:#fff;background:linear-gradient(transparent 62%,rgba(124,214,24,.28) 0)}
.og-body a{color:var(--acc);text-decoration:none;border-bottom:1px solid rgba(124,214,24,.4)}
.og-body>p:first-of-type::first-letter{font-family:'Bebas Neue';float:left;font-size:84px;line-height:.8;padding:6px 10px 0 0;color:var(--acc)}
.og-h{font-family:'Bebas Neue';font-weight:400;font-size:36px;letter-spacing:1.5px;margin:1.6em 0 .5em;display:flex;align-items:center;gap:12px}
.og-h span{width:28px;height:6px;border-radius:3px;background:var(--c);box-shadow:0 0 14px var(--c)}
.og-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:28px 0}
.og-stats div{background:linear-gradient(160deg,var(--card),#0e231f);border:1px solid var(--line);border-top:3px solid var(--c);border-radius:16px;padding:18px 16px;text-align:center}
.og-stats b{display:block;font-family:'Bebas Neue';font-weight:400;font-size:58px;line-height:1;color:var(--c);text-shadow:0 0 24px color-mix(in srgb,var(--c) 50%,transparent)}
.og-stats small{color:var(--soft);font-size:13px;letter-spacing:.5px;text-transform:uppercase}
.og-tbl{overflow-x:auto;margin:22px 0 28px;border-radius:16px;border:1px solid var(--line);background:#0d211d}
.og-tbl table{border-collapse:collapse;width:100%;font-size:15px;line-height:1.4}
.og-tbl th{font-family:'Bebas Neue';font-weight:400;letter-spacing:1.5px;font-size:17px;text-align:left;padding:12px 14px;color:var(--acc);background:#10302a;white-space:nowrap}
.og-tbl td{padding:12px 14px;border-top:1px solid var(--line)}
.og-tbl tr td:first-child{border-left:4px solid var(--c);font-weight:800}
.og-tbl tbody tr:nth-child(odd){background:rgba(255,255,255,.02)}
.og-tbl td:last-child{font-variant-numeric:tabular-nums}
.og-body ul{list-style:none;padding:0;margin:0 0 1.2em}.og-body li{position:relative;padding:10px 14px 10px 38px;margin-bottom:8px;background:var(--card);border:1px solid var(--line);border-radius:12px}
.og-body li::before{content:"";position:absolute;left:15px;top:20px;width:10px;height:10px;border-radius:50%;background:var(--c);box-shadow:0 0 10px var(--c)}
.og-pq{margin:34px 0;padding:8px 0 8px 26px;border-left:5px solid var(--acc2)}
.og-pq p{font-family:'Bebas Neue';font-size:clamp(30px,4.4vw,42px);line-height:1.05;letter-spacing:1px;margin:0 0 8px;color:#fff}
.og-pq cite{font-style:normal;color:var(--acc2);font-size:13px;letter-spacing:1.5px;text-transform:uppercase}
.og-method{margin-top:36px;padding:18px 20px;border-radius:14px;background:#0d211d;border:1px dashed var(--line);font-size:14.5px;color:var(--soft)}
.og-method b{font-family:'Bebas Neue';font-weight:400;font-size:20px;letter-spacing:1.5px;color:var(--acc)}.og-method p{margin:6px 0 0}
.og-more{display:flex;gap:10px;flex-wrap:wrap;margin-top:26px}.og-more a{padding:10px 16px;border-radius:999px;background:var(--card);border:1px solid var(--line);color:var(--txt);text-decoration:none;font-weight:600;font-size:14px}
.og-list{display:grid;gap:16px}.og-card{display:block;padding:22px;border-radius:18px;background:var(--card);border:1px solid var(--line);border-left:5px solid var(--c);color:var(--txt);text-decoration:none}
.og-card h2{font-family:'Bebas Neue';font-weight:400;font-size:32px;margin:8px 0 6px;letter-spacing:1px}.og-card p{color:var(--soft);margin:0}
@media(max-width:600px){.og-hero{padding:34px 20px 24px;border-radius:0}.og-stats{grid-template-columns:1fr}.og-stats div{display:flex;align-items:center;gap:14px;text-align:left}.og-stats b{font-size:46px}.og-body{font-size:17.5px}}
"""
BELT_SVG = ('<svg class="og-bg" viewBox="0 0 200 120" aria-hidden="true"><g fill="none" stroke="currentColor" stroke-width="3" style="color:var(--c)">'
            '<rect x="4" y="38" width="192" height="44" rx="10"/><ellipse cx="100" cy="60" rx="46" ry="52"/><ellipse cx="100" cy="60" rx="32" ry="38"/>'
            '<circle cx="34" cy="60" r="12"/><circle cx="166" cy="60" r="12"/><path d="M84 60l10 10 22-24"/></g></svg>')

def article_ld(p):
    col = {"@type": "Organization", "name": COLUMN_NAME, "url": SITE + f"originals/{COLUMN_SLUG}/", "parentOrganization": {"@type": "NewsMediaOrganization", "name": "Wrestling Central News", "url": SITE}}
    return {"@context": "https://schema.org", "@type": "AnalysisNewsArticle", "headline": p["title"], "description": p.get("dek", ""),
            "datePublished": p.get("published") or p["d"].isoformat(), "dateModified": p.get("updated", p["date"]), "mainEntityOfPage": SITE + p["url"].lstrip("/"),
            "author": col, "publisher": chrome.PUBLISHER, "isAccessibleForFree": True, "inLanguage": "en", "image": SITE + "og-image.jpg"}

def render_piece(p, draft=False):
    c = CATC.get(p.get("promo"), "#7cd618"); canon = SITE + p["url"].lstrip("/")
    robots = "noindex,nofollow" if draft else "index,follow,max-image-preview:large,max-snippet:-1"
    ld = [article_ld(p), chrome.breadcrumbs([("WCN", SITE), ("Originals", SITE + "originals/"), (p["title"], canon)])]
    hero = (f'<header class="og-hero">{BELT_SVG}<div class="og-kick"><span class="og-col">{e(COLUMN_NAME)}</span>'
            f'<span class="og-pill">{e(p.get("promo",""))}</span><span class="og-orig">WCN Original · Analysis</span></div>'
            f'<h1>{e(p["title"])}</h1><p class="og-dek">{e(p.get("dek",""))}</p>'
            f'<div class="og-by"><span class="og-mono">{COLUMN_SHORT}</span><div>By <a href="/originals/{COLUMN_SLUG}/">{e(COLUMN_NAME)}</a>'
            f'<small class="og-disc">{e(DISCLOSURE)}</small><small><time datetime="{p["d"].isoformat()}">{chrome.dlong(p["d"], "en")}</time> · {p["mins"]} min read</small></div></div></header>')
    more = ('<nav class="og-more" aria-label="Related"><a href="/champions/">Current champions</a><a href="/shows/">Results &amp; shows</a>'
            '<a href="/upcoming/">Upcoming events</a><a href="/originals/">More WCN Originals</a></nav>')
    return (chrome.head(p["title"] + " | WCN Originals", p.get("dek", ""), canon, "en", og_type="article", ld=ld, robots=robots, extra=f"<style>{CSS}</style>")
            + f'<body><div class="spot s1"></div><div class="spot s2"></div>{chrome.header("en", p["url"], None, active="originals")}'
            f'<main class="og-wrap" style="--c:{c}"><article>{hero}<div class="og-body">{render_body(p)}</div></article>{more}</main>{chrome.footer("en")}{chrome.SCRIPTS}</body></html>')

def render_index(ps):
    cards = "".join(f'<a class="og-card" style="--c:{CATC.get(p.get("promo"), "#7cd618")}" href="{p["url"]}"><span class="og-pill">{e(p.get("promo",""))}</span>'
                    f'<h2>{e(p["title"])}</h2><p>{e(p.get("dek",""))}</p><p><small>{chrome.dlong(p["d"],"en")} · {p["mins"]} min read</small></p></a>' for p in ps)
    return (chrome.head("WCN Originals: analysis from Wrestling Central News", f"Original analysis by {COLUMN_NAME}, built on WCN's own champions and results data.", SITE + "originals/", "en", extra=f"<style>{CSS}</style>")
            + f'<body>{chrome.header("en", "/originals/", None, active="originals")}<main class="og-wrap"><header class="og-hero" style="--c:#7cd618"><h1>WCN Originals</h1>'
            f'<p class="og-dek">Analysis columns by <a href="/originals/{COLUMN_SLUG}/">{e(COLUMN_NAME)}</a>. Every piece stays here permanently.</p></header><div class="og-list">{cards}</div></main>{chrome.footer("en")}</body></html>')

def render_column():
    body = (f"<p><strong>By {e(COLUMN_NAME)} {e(DISCLOSURE)}</strong></p><p>{e(COLUMN_NAME)} is the name of WCN's original analysis column. It is not a person. Pieces are built from WCN's own champions board and confirmed results pages. Every result we cite is backed by a trusted source "
            "(Wrestling Observer, Wrestling Inc or Fightful), and each piece is reviewed before it is published.</p>"
            "<p>Corrections follow our <a href=\"/editorial-policy/#corrections\">editorial policy</a>. Contact: wcn@mail.grokbot.com.</p>")
    ld = [{"@context": "https://schema.org", "@type": "Organization", "name": COLUMN_NAME, "url": SITE + f"originals/{COLUMN_SLUG}/", "parentOrganization": chrome.PUBLISHER}]
    return (chrome.head(f"{COLUMN_NAME} | WCN Originals", f"How WCN's {COLUMN_NAME} column is made.", SITE + f"originals/{COLUMN_SLUG}/", "en", ld=ld, extra=f"<style>{CSS}</style>")
            + f'<body>{chrome.header("en", "/originals/", None, active="originals")}<main class="og-wrap"><header class="og-hero" style="--c:#7cd618"><h1>{e(COLUMN_NAME)}</h1></header>'
            f'<div class="og-body">{body}</div></main>{chrome.footer("en")}</body></html>')

def sitemap_urls():
    """Published pieces + index + column page; empty until ORIGINALS_LIVE. Always strong index tier."""
    if not ORIGINALS_LIVE: return []
    ps = pieces(); return ([SITE + "originals/", SITE + f"originals/{COLUMN_SLUG}/"] + [SITE + p["url"].lstrip("/") for p in ps]) if ps else []

def news_entries(hours=48, now=None):
    """[(url, 'en', title, ts)] for published pieces first published within `hours` (Google News sitemap rule)."""
    import time
    if not ORIGINALS_LIVE: return []
    now = now or time.time(); out = []
    for p in pieces():
        ts = p.get("ts")
        if ts and now - ts <= hours * 3600: out.append((SITE + p["url"].lstrip("/"), "en", p["title"], ts))
    return out

def is_original(path): return path.startswith("/originals/") or "/originals/" in path   # for stale/cleanup/index_tier guards

def build(public_dir):
    """Call from the site build. No-op until ORIGINALS_LIVE; drafts never written."""
    if not ORIGINALS_LIVE: return 0
    ps = pieces()
    def w(rel, s):
        d = os.path.join(public_dir, rel); os.makedirs(d, exist_ok=True); open(os.path.join(d, "index.html"), "w").write(s)
    w("originals", render_index(ps)); w(f"originals/{COLUMN_SLUG}", render_column())
    for p in ps: w(p["url"].strip("/"), render_piece(p))
    return len(ps)

def preview(out_dir):
    ps = pieces(include_drafts=True); os.makedirs(out_dir, exist_ok=True)
    for p in ps: open(os.path.join(out_dir, p["slug"] + ".html"), "w").write(render_piece(p, draft=True))
    return ps
