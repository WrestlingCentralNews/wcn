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
        for i, r in enumerate(rs): r["end"] = rs[i + 1]["start"] if i + 1 < len(rs) else None
        out[tid] = {"name": t["name"], "group": t.get("group"), "from": rs[0]["start"], "reigns": rs}
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
        t[tid] = {"n": v["name"], "g": v["group"], "f": v["from"],
                  "r": [[r.get("holder"), r["start"], r.get("end"), "", r.get("photo") or ""] for r in rs]}
    used = {r[4] for v in t.values() for r in v["r"] if r[4]}
    ph = {k: v["file"] for k, v in jload("champion_photos.json", {}).items() if k in used}
    for v in t.values():
        for r in v["r"]:
            if r[4] not in ph: r[4] = ""
    return {"today": now.isoformat(), "titles": t, "photos": ph}
CSS = ("<style>.tl{border:1px solid #8884;border-radius:10px;padding:1rem;margin:1rem 0 2rem}.tl-c{display:flex;flex-wrap:wrap;gap:.5rem;align-items:end}.tl-c label{font-size:.8rem;display:flex;flex-direction:column;gap:.2rem;opacity:.9}"
       ".tl-c select,.tl-c input{font:inherit;padding:.3rem;max-width:100%}.tl-bars{position:relative;height:34px;margin:1rem 0 .3rem;background:#8882;border-radius:6px;overflow:hidden}"
       ".tl-bars span{position:absolute;top:0;bottom:0;border-right:1px solid #fff8;cursor:pointer}.tl-cur{position:absolute;top:-2px;bottom:-2px;width:2px;background:currentColor;pointer-events:none}"
       ".tl-ax{display:flex;justify-content:space-between;font-size:.75rem;opacity:.7}.tl input[type=range]{width:100%;margin:.4rem 0}.tl-card{display:flex;gap:1rem;align-items:center;min-height:96px}"
       ".tl-card img,.tl-ini{width:88px;height:88px;border-radius:50%;object-fit:cover;flex:none;background:#8883;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1.6rem}"
       ".tl-d{font-size:1.1rem;font-weight:700}.tl-n{font-size:1.25rem}.tl-m{font-size:.9rem;opacity:.85}.tl-credits{font-size:.8rem;opacity:.85}.tl-credits li{margin:.15rem 0}</style>")
JS = r"""(function(){var D=JSON.parse(document.getElementById('tl-data').textContent),$=function(i){return document.getElementById(i)};
var DAY=864e5,dn=function(s){var a=s.split('-');return Date.UTC(+a[0],a[1]-1,+a[2])/DAY},ds=function(n){return new Date(n*DAY).toISOString().slice(0,10)};
var fmt=function(s){return new Date(dn(s)*DAY).toLocaleDateString(document.documentElement.lang||'en',{timeZone:'UTC',year:'numeric',month:'short',day:'numeric'})};
var pal=['#c0392b','#2471a3','#229954','#d68910','#7d3c98','#17a589','#a04000','#2e4053'],T,R,lo,hi,today=dn(D.today),seen={};
function pick(rs,day){for(var i=0;i<rs.length;i++){var r=rs[i];if(r[1]<=day&&(!r[2]||day<r[2]))return r}return null}
window.wcnPick=pick;
function ini(n){return (n||'?').replace(/["“”]/g,'').split(/\s+/).filter(Boolean).slice(0,2).map(function(w){return w[0]}).join('').toUpperCase()}
function pre(){R.forEach(function(r){var p=D.photos[r[4]];if(p&&!seen[p]){seen[p]=1;(new Image()).src=p}})}
function draw(){T=D.titles[$('tl-t').value];var y=+$('tl-r').value,f=dn(T.f);lo=Math.max(today-Math.round(y*365.25),f);hi=today;
 R=T.r.filter(function(r){return (r[2]?dn(r[2]):hi+1)>lo});var b=$('tl-bars');b.innerHTML='<i class="tl-cur" id="tl-cur"></i>';var span=Math.max(hi-lo,1);
 R.forEach(function(r,i){if(!r[0])return;var s=Math.max(dn(r[1]),lo),e=r[2]?dn(r[2]):hi+1,el=document.createElement('span');el.style.left=(100*(s-lo)/span)+'%';el.style.width=(100*Math.max(e-s,1)/span)+'%';
  el.style.background=pal[i%pal.length];el.title=r[0]+' ('+r[1]+(r[2]?' – '+r[2]:'')+')';el.onclick=function(){go(s)};b.appendChild(el)});
 $('tl-a0').textContent=fmt(ds(lo));$('tl-a1').textContent=fmt(ds(hi));
 $('tl-hf').textContent=f>today-Math.round(y*365.25)?"History from "+T.f.slice(0,4):'';
 var s=$('tl-s');s.min=lo;s.max=hi;s.step=1;$('tl-q').min=ds(lo);$('tl-q').max=ds(hi);pre();go(Math.min(Math.max(+s.value||hi,lo),hi))}
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
    rng = "".join(f'<option value="{y}"{" selected" if y == 5 else ""}>{lab}</option>' for y, lab in ((1, "Last year"), (5, "Last 5 years"), (10, "Last 10 years"), (20, "Last 20 years")))
    used = {r[4] for v in p["titles"].values() for r in v["r"] if r[4]}
    data = json.dumps(p, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    cr = "".join(f'<li>{e(c["name"])}: photo by {e(c["author"])}, <a href="{e(c["license_url"] or c["source"])}" rel="noopener license" target="_blank">{e(c["license"])}</a>, via <a href="{e(c["source"])}" rel="noopener" target="_blank">Wikimedia Commons</a> (cropped and resized)</li>'
                 for k, c in sorted(credits.items()) if k in used)
    return (CSS + '<section class="tl" aria-labelledby="tl-h"><h2 id="tl-h">Title history timeline</h2>'
            '<p class="note">Pick a title and a time range, then drag the slider day by day or type a date to see who held the belt. Lineages come from the title-history lists on Wikipedia, which cite the promotion or a news report for each reign; the current reign matches the table below.</p>'
            f'<div class="tl-c"><label>Title<select id="tl-t">{opts}</select></label><label>Range<select id="tl-r">{rng}</select></label>'
            '<label>Go to date<input type="date" id="tl-q"></label></div>'
            '<div class="tl-bars" id="tl-bars"></div><div class="tl-ax"><span id="tl-a0"></span><span id="tl-hf"></span><span id="tl-a1"></span></div>'
            '<input type="range" id="tl-s" step="1" aria-label="Date"><div class="tl-d" id="tl-d" aria-live="polite"></div><p class="tl-m" id="tl-msg"></p>'
            '<div class="tl-card" id="tl-card"></div>'
            f'<script type="application/json" id="tl-data">{data}</script><script>{JS}</script>'
            + (f'<details class="tl-credits"><summary>Photo credits</summary><ul>{cr}</ul><p>Wrestlers without a freely licensed photo are shown with their initials.</p></details>' if cr else "")
            + '</section>')
