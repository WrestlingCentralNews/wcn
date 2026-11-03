"""Title-history timeline on /champions/ (owner pt596u). Data: title_lineage.json (Wikipedia title-history lists, guarded by
tools/build_lineage.py) + champion_photos.json (Wikimedia Commons, freely licensed, hosted under /img/champions/).
Auto-update: lineage() closes the last reign and appends the current one whenever champions.json / WCN results show a new champion.
A reign covers start <= day < next start, so the new champion shows exactly on the day of the title change."""
import os, json, html, datetime
ROOT = os.path.dirname(os.path.abspath(__file__))
e = lambda s: html.escape(s or "", quote=True)
YEARS = 20
def jload(p, d):
    try: return json.load(open(os.path.join(ROOT, p)))
    except Exception: return d
def norm(s): return " ".join((s or "").lower().replace("’", "'").split())
def lineage(champ, data=None):
    """champ = {id: current state dict (champion, since, source)}. Returns {id: {name, from, reigns:[{h,s,e,src,p}]}}."""
    data = data if data is not None else jload("title_lineage.json", {}).get("titles", {})
    out = {}
    for tid, t in champ.items():
        rs = [dict(r) for r in (data.get(tid) or {}).get("reigns", [])]
        cur = {"holder": t["champion"], "start": t["since"], "source": t.get("source")}
        if rs and rs[-1]["start"] == cur["start"]: rs[-1].update(holder=cur["holder"], source=cur["source"] or rs[-1].get("source"))
        elif rs and rs[-1]["start"] < cur["start"]:
            if norm(rs[-1].get("holder")) == norm(cur["holder"]) and not rs[-1].get("end"): pass   # same reign, nothing new
            else: rs.append(cur)
        else: rs = [cur]
        full = len(rs) > 1 or bool((data.get(tid) or {}).get("created"))
        for i, r in enumerate(rs): r["end"] = rs[i + 1]["start"] if i + 1 < len(rs) else None
        out[tid] = {"name": t["name"], "group": t.get("group"), "from": rs[0]["start"], "created": full, "reigns": rs}
    return out
def champion_on(reigns, day):
    """Reign in force on ISO date `day` (start <= day < end); None before history or during a vacancy."""
    for r in reigns:
        if r["start"] <= day and (r.get("end") is None or day < r["end"]): return r
    return None
def payload(lin, now):
    cut = (now.replace(year=now.year - YEARS) if not (now.month == 2 and now.day == 29) else now.replace(year=now.year - YEARS, day=28)).isoformat()
    t = {}
    for tid, v in lin.items():
        rs = [r for r in v["reigns"] if (r.get("end") or "9999") > cut]
        t[tid] = {"n": v["name"], "g": v["group"], "f": v["from"], "c": 1 if v.get("created") else 0,
                  "r": [[r.get("holder"), r["start"], r.get("end"), "", r.get("photo") or ""] for r in rs]}
    used = {r[4] for v in t.values() for r in v["r"] if r[4]}
    ph = {k: v["file"] for k, v in jload("champion_photos.json", {}).items() if k in used}
    for v in t.values():
        for r in v["r"]:
            if r[4] not in ph: r[4] = ""
    return {"today": now.isoformat(), "titles": t, "photos": ph}
CSS = ("<style>.tl{background:var(--card,#13302c);border:1px solid var(--line,#24443e);border-radius:16px;padding:18px;margin:4px 0 8px;color:var(--txt,#fff)}"
       ".tl h2{margin:0 0 6px}.tl .note{margin:0 0 12px;color:var(--soft,#d3e0dc)}"
       ".tl-c{display:grid;grid-template-columns:2fr 1fr 1fr;gap:12px}.tl-c label{display:flex;flex-direction:column;gap:6px;font:700 12px/1.2 Inter,system-ui,sans-serif;text-transform:uppercase;letter-spacing:.5px;color:var(--mut,#9fb1ad);min-width:0}"
       ".tl-c select,.tl-c input{-webkit-appearance:none;appearance:none;width:100%;min-width:0;box-sizing:border-box;min-height:44px;padding:10px 38px 10px 12px;border-radius:10px;border:1px solid var(--line,#24443e);"
       "background:var(--bg2,#0f2a26);color:var(--txt,#fff);font:600 15px/1.2 Inter,system-ui,sans-serif;text-overflow:ellipsis;white-space:nowrap;overflow:hidden;color-scheme:dark}"
       ".tl-c select{background-image:url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8'%3E%3Cpath d='M1 1l5 5 5-5' fill='none' stroke='%237cd618' stroke-width='2'/%3E%3C/svg%3E\");background-repeat:no-repeat;background-position:right 14px center}"
       ".tl-c input{padding-right:12px}.tl-c select:focus,.tl-c input:focus{outline:2px solid var(--acc,#7cd618);outline-offset:1px;border-color:var(--acc,#7cd618)}"
       ".tl-bars{position:relative;height:40px;margin:16px 0 6px;background:var(--bg,#0a1a18);border:1px solid var(--line,#24443e);border-radius:8px;overflow:hidden}"
       ".tl-bars span{position:absolute;top:0;bottom:0;border-right:2px solid var(--bg,#0a1a18);cursor:pointer;box-sizing:border-box}.tl-cur{position:absolute;top:0;bottom:0;width:3px;margin-left:-1px;background:#fff;box-shadow:0 0 6px #000;z-index:2;pointer-events:none}"
       ".tl-ax{display:flex;justify-content:space-between;gap:8px;font-size:12px;color:var(--mut,#9fb1ad)}.tl-ax #tl-a0,.tl-ax #tl-hf{color:var(--acc,#7cd618);font-weight:700;text-align:center}"
       ".tl input[type=range]{width:100%;height:44px;margin:4px 0;accent-color:var(--acc,#7cd618);background:transparent}"
       ".tl-d{font:400 30px/1 'Bebas Neue',Inter,sans-serif;letter-spacing:1px;color:var(--acc,#7cd618)}.tl-msg{margin:4px 0;font-size:14px;color:var(--soft,#d3e0dc)}.tl-msg:empty{display:none}"
       ".tl-card{display:flex;gap:16px;align-items:center;min-height:104px;padding:12px;margin-top:8px;border-radius:12px;background:var(--bg2,#0f2a26)}"
       ".tl-card img,.tl-ini{width:92px;height:92px;border-radius:50%;object-fit:cover;flex:none;border:3px solid var(--acc,#7cd618);background:var(--card2,#1a2b33);display:flex;align-items:center;justify-content:center;font:700 28px/1 Inter,sans-serif;color:#fff;box-sizing:border-box}"
       ".tl-n{font-size:22px;font-weight:800}.tl-m{font-size:14px;color:var(--soft,#d3e0dc)}.tl-credits{margin-top:12px;font-size:12px;color:var(--mut,#9fb1ad)}.tl-credits summary{cursor:pointer;min-height:32px}.tl-credits a{color:var(--soft,#d3e0dc)}"
       "@media(max-width:600px){.tl{padding:14px;border-radius:14px}.tl-c{grid-template-columns:1fr 1fr}.tl-c label:first-child{grid-column:1/-1}.tl-card{flex-direction:column;text-align:center}.tl-ax{font-size:11px}}"
       "@media(max-width:340px){.tl-c{grid-template-columns:1fr}}</style>")
JS = r"""(function(){var D=JSON.parse(document.getElementById('tl-data').textContent),$=function(i){return document.getElementById(i)};
var DAY=864e5,dn=function(s){var a=s.split('-');return Date.UTC(+a[0],a[1]-1,+a[2])/DAY},ds=function(n){return new Date(n*DAY).toISOString().slice(0,10)};
var fmt=function(s){return new Date(dn(s)*DAY).toLocaleDateString(document.documentElement.lang||'en',{timeZone:'UTC',year:'numeric',month:'short',day:'numeric'})};
var pal=['#7cd618','#f26a14','#2bb3a3','#4a90e2','#e6b422','#9b6ce0','#e0598b','#6fa8b8'],hc=function(n){var h=0;for(var i=0;i<n.length;i++)h=(h*31+n.charCodeAt(i))|0;return pal[Math.abs(h)%pal.length]},T,R,lo,hi,today=dn(D.today),seen={};
function pick(rs,day){for(var i=0;i<rs.length;i++){var r=rs[i];if(r[1]<=day&&(!r[2]||day<r[2]))return r}return null}
window.wcnPick=pick;
function ini(n){return (n||'?').replace(/["“”]/g,'').split(/\s+/).filter(Boolean).slice(0,2).map(function(w){return w[0]}).join('').toUpperCase()}
function pre(){R.forEach(function(r){var p=D.photos[r[4]];if(p&&!seen[p]){seen[p]=1;(new Image()).src=p}})}
function draw(){T=D.titles[$('tl-t').value];var y=+$('tl-r').value,f=dn(T.f);lo=Math.max(today-Math.round(y*365.25),f);hi=today;
 R=T.r.filter(function(r){return (r[2]?dn(r[2]):hi+1)>lo});var b=$('tl-bars');b.innerHTML='<i class="tl-cur" id="tl-cur"></i>';var span=Math.max(hi-lo,1);
 R.forEach(function(r,i){if(!r[0])return;var s=Math.max(dn(r[1]),lo),e=r[2]?dn(r[2]):hi+1,el=document.createElement('span');el.style.left=(100*(s-lo)/span)+'%';el.style.width=(100*Math.max(e-s,1)/span)+'%';
  el.style.background=hc(r[0]);el.title=r[0]+' ('+r[1]+(r[2]?' – '+r[2]:'')+')';el.onclick=function(){go(s)};b.appendChild(el)});
 var yng=f>today-Math.round(y*365.25);$('tl-a0').textContent=(yng&&T.c?'Title created ':'')+fmt(ds(lo));$('tl-a1').textContent=fmt(ds(hi));
 $('tl-hf').textContent=yng&&!T.c?'History from '+T.f.slice(0,4):'';
 var s=$('tl-s');s.min=lo;s.max=hi;s.step=1;$('tl-q').min=ds(lo);$('tl-q').max=ds(hi);pre();go(s.dataset.on?Math.min(Math.max(+s.value,lo),hi):hi);s.dataset.on=1}
function go(n){var s=$('tl-s');n=Math.round(n);s.value=n;var d=ds(n),r=pick(T.r,d);$('tl-cur').style.left=(100*(n-lo)/Math.max(hi-lo,1))+'%';$('tl-d').textContent=fmt(d);$('tl-q').value=d;show(r,d)}
function show(r,d){var c=$('tl-card'),ph=r&&D.photos[r[4]];
 if(!r||!r[0]){c.innerHTML='<div class="tl-ini">–</div><div><div class="tl-n">'+(d<T.f?'No champion on record for this title on that date. Our history for it starts '+fmt(T.f)+'.':'The title was vacant on this date.')+'</div></div>';return}
 c.innerHTML=(ph?'<img src="'+ph+'" alt="'+r[0].replace(/"/g,'&quot;')+'" width="88" height="88">':'<div class="tl-ini" aria-hidden="true">'+ini(r[0])+'</div>')+
 '<div><div class="tl-n"><strong></strong></div><div class="tl-m"></div></div>';c.querySelector('strong').textContent=r[0];
 c.querySelector('.tl-m').textContent='Reign: '+fmt(r[1])+' – '+(r[2]?fmt(r[2]):'present')}
$('tl-t').onchange=draw;$('tl-r').onchange=draw;$('tl-s').addEventListener('input',function(){go(+this.value)});
$('tl-q').addEventListener('change',function(){var v=this.value;if(!/^\d{4}-\d\d-\d\d$/.test(v))return;var n=dn(v);
 if(n>today){$('tl-msg').textContent='That date is in the future, so here is today.';n=today}
 else if(n<lo){var y=$('tl-r');if(n>=dn(T.f)){y.value=20;draw()}
  if(n<lo){$('tl-msg').textContent=v<T.f?'Our history for the '+T.n+' starts '+fmt(T.f)+', so here is the first champion on record.':'That date is outside the range shown, so here is the earliest date available.';n=lo}else $('tl-msg').textContent=''}
 else $('tl-msg').textContent='';go(n)});
draw()})();"""
def html_block(lin, now, credits=None):
    p = payload(lin, now); credits = credits if credits is not None else jload("champion_photos.json", {})
    opts = "".join(f'<option value="{e(k)}">{e(v["g"] + ": " if v.get("g") else "")}{e(v["n"])}</option>' for k, v in p["titles"].items())
    rng = "".join(f'<option value="{y}"{" selected" if y == 5 else ""}>{lab}</option>' for y, lab in ((1, "1 year"), (5, "5 years"), (10, "10 years"), (20, "20 years")))
    used = {r[4] for v in p["titles"].values() for r in v["r"] if r[4]}
    data = json.dumps(p, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    cr = "".join(f'<li>{e(c["name"])}: photo by {e(c["author"])}, <a href="{e(c["license_url"] or c["source"])}" rel="noopener license" target="_blank">{e(c["license"])}</a>, via <a href="{e(c["source"])}" rel="noopener" target="_blank">Wikimedia Commons</a> (cropped and resized)</li>'
                 for k, c in sorted(credits.items()) if k in used)
    return (CSS + '<section class="tl" aria-labelledby="tl-h"><h2 id="tl-h">Title history timeline</h2>'
            '<p class="note">Pick a title and a time range, then drag the slider day by day or type a date to see who held the belt. Lineages come from the title-history lists on Wikipedia, which cite the promotion or a news report for each reign; the current reign matches the table below.</p>'
            f'<div class="tl-c"><label>Title<select id="tl-t">{opts}</select></label><label>Range<select id="tl-r">{rng}</select></label>'
            '<label>Go to date<input type="date" id="tl-q"></label></div>'
            '<div class="tl-bars" id="tl-bars"></div><div class="tl-ax"><span id="tl-a0"></span><span id="tl-hf"></span><span id="tl-a1"></span></div>'
            '<input type="range" id="tl-s" step="1" aria-label="Date"><div class="tl-d" id="tl-d" aria-live="polite"></div><p class="tl-msg" id="tl-msg"></p>'
            '<div class="tl-card" id="tl-card"></div>'
            f'<script type="application/json" id="tl-data">{data}</script><script>{JS}</script>'
            + (f'<details class="tl-credits"><summary>Photo credits</summary><ul>{cr}</ul><p>Wrestlers without a freely licensed photo are shown with their initials.</p></details>' if cr else "")
            + '</section>')
