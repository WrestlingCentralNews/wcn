const CATS={WWE:'#f26a14',AEW:'#7cd618',TNA:'#4ea8ff',Indie:'#f05fc1',Global:'#2fd3b4'};
const LANG=document.documentElement.lang==='es'?'es':'en';
const TX={en:{conf:n=>`✔ CONFIRMED BY ${n} SOURCES`,dev:n=>`DEVELOPING · ${n} REPORTS`,off:'OFFICIAL MATCH',nw:'NEW',dflt:s=>`Developing story reported by ${s}. Tap through for the full report.`,upd:n=>`🔄 ${n} related update${n>1?'s':''} · story timeline`,more:'Read more →',stories:'stories',updated:'updated ',none:'No stories for these filters yet — pick another promotion.',fail:'Could not load news.',first:'first reported ',upd2:'updated ',top:'Top Stories',brk:'BREAKING'},
es:{conf:n=>`✔ CONFIRMADO POR ${n} FUENTES`,dev:n=>`EN DESARROLLO · ${n} REPORTES`,off:'COMBATE OFICIAL',nw:'NUEVO',dflt:s=>`Noticia en desarrollo reportada por ${s}. Toca para ver el reporte completo.`,upd:n=>`🔄 ${n} actualización${n>1?'es':''} relacionada${n>1?'s':''} · cronología`,more:'Leer más →',stories:'noticias',updated:'actualizado ',none:'Todavía no hay noticias con estos filtros. Elige otra empresa.',fail:'No se pudieron cargar las noticias.',first:'publicado ',upd2:'actualizado ',top:'Lo más importante',brk:'ÚLTIMA HORA'}}[LANG];
const KEY='wcn_filters';let sel=JSON.parse(localStorage.getItem(KEY)||'null')||Object.keys(CATS);{const P=new URLSearchParams(location.search).get('promo');if(P&&CATS[P])sel=[P]}
let items=[],shown=12,lastSeen=+localStorage.getItem('wcn_seen')||0,q='';
const $=s=>document.querySelector(s),esc=s=>(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function ago(t){const m=(Date.now()/1000-t)/60,v=m<60?Math.max(1,m|0)+(LANG==='es'?' min':'m'):m<1440?(m/60|0)+'h':(m/1440|0)+'d';return LANG==='es'?'hace '+v:v+' ago'}
// cards are sorted by latest activity (ts); show when the story was first reported too, so a long-running story never looks brand new
function when(i){const f=i.first_ts||i.ts;return (i.updates||[]).length&&i.ts-f>300?TX.first+ago(f)+' · '+TX.upd2+ago(i.ts):ago(f)}
function chips(){$('#filters').innerHTML=Object.entries(CATS).map(([k,c])=>`<button class="chip ${sel.includes(k)?'on':''}" style="--c:${c}" data-k="${k}">${k}<small>${items.filter(i=>i.categories.includes(k)).length}</small></button>`).join('')}
$('#filters').onclick=e=>{const b=e.target.closest('.chip');if(!b)return;const k=b.dataset.k;sel=sel.includes(k)?sel.filter(x=>x!==k):[...sel,k];localStorage.setItem(KEY,JSON.stringify(sel));shown=12;chips();render()};
let qt;$('#q').oninput=e=>{q=e.target.value.toLowerCase();clearTimeout(qt);qt=setTimeout(()=>window.track&&track('search',{search_term:q}),1200);shown=12;render()};
function list(){return items.filter(i=>i.categories.some(c=>sel.includes(c))&&(!q||(i.title+i.summary+i.source+(i.updates||[]).map(u=>u.title).join(' ')).toLowerCase().includes(q)))}
// photo fallback (2026-10-22): a photo that fails to load removes only itself and the blurred copy, never the promotion placeholder under it
const FGERR="var b=this.parentNode&&this.parentNode.querySelector('img.bg');b&&b.remove();this.remove()";
function pic(i){const u=(i.image_local||i.image||'').trim();return /^(https?:)?\/\//.test(u)||u.startsWith('/')?u:''}
function card(i,n,hero){const c=CATS[i.categories[0]]||'#2fd3b4',im=pic(i);const ld=hero?'fetchpriority="high"':'loading="lazy"',wh=i.img_w&&i.img_h?` width="${i.img_w}" height="${i.img_h}"`:'';const img=im?`<img class="bg" ${ld} referrerpolicy="no-referrer" src="${esc(im)}" alt="" aria-hidden="true" onerror="this.remove()"><img class="fg${i.img_w&&i.img_h&&i.img_w/i.img_h>=1.6&&i.img_w/i.img_h<=2.1?' fill':''}" ${ld}${wh} referrerpolicy="no-referrer" src="${esc(im)}" alt="" onerror="${FGERR}">`:'';
return `<article class="card ${hero?'hero in':''} ${i.kind&&i.kind.type==='quote'?'quote':''}" style="--c:${c}" data-cat="${i.categories[0]}" data-pos="${n}"><a class="img" href="${esc(i.url||i.link)}" aria-hidden="true" tabindex="-1"><div class="ph">${i.categories[0]}</div>${img}</a><div class="body">
<div class="tags">${hero&&i.brk?`<span class="tag brk">${TX.brk}</span>`:''}${i.added>lastSeen&&lastSeen?`<span class="tag new">${TX.nw}</span>`:''}${i.sources>1?`<span class="tag conf">${TX.conf(i.sources)}</span>`:''}${(i.updates||[]).length?`<span class="tag dev">${TX.dev(i.updates.length+1)}</span>`:''}${i.kind&&i.kind.type==='match'?`<span class="tag off">${TX.off}</span>`:''}${i.categories.map(k=>`<span class="tag" style="--c:${CATS[k]}">${k}</span>`).join('')}</div>
${i.kind&&i.kind.type==='quote'?`<blockquote class="qc"><span class="qm">“</span>${esc(i.kind.quote||i.summary.split(/(?<=[.!?])\s/)[0])}<cite>— ${esc(i.kind.who)}</cite></blockquote>`:''}<h2><a href="${esc(i.url||i.link)}">${esc(i.title)}</a></h2>
<p>${esc(i.summary||TX.dflt(i.source))}</p>
${(i.updates||[]).length?`<details class="upd"><summary>${TX.upd(i.updates.length)}</summary><ol>${i.updates.map(u=>`<li><time>${ago(u.ts)}</time><a href="${esc(i.url||u.link)}">${esc(u.title)}</a><span>${esc(u.line)} <em>— ${esc(u.source)}</em></span></li>`).join("")}</ol></details>`:""}<div class="meta"><span>${esc(i.source)} · ${when(i)}</span><a href="${esc(i.url||i.link)}">${TX.more}</a></div></div></article>`}
// Top stories (mirrors toppick.py): importance (news.json 'imp', BREAKING bonus included) minus age; lead needs a photo
const TP={fresh:24,decay:.75,old:.15,n:5,bump:48};
// photo(): 2 = real photo with a measured size (it loaded for the site), 1 = promotion card / unmeasured photo, 0 = none
function photo(i){const u=pic(i);return !u?0:!/\/img\/promo\//.test(u)&&i.img_w?2:1}
function topPick(L){const now=Date.now()/1000;if(L.length<TP.n+3)return[];const act=i=>Math.min(i.ts,(i.first_ts||i.ts)+TP.bump*3600);let pool=L.filter(i=>now-act(i)<TP.fresh*3600);if(pool.length<TP.n)pool=L.slice(0,40);
 const v=i=>(i.imp||0)-TP.decay*Math.max(0,now-act(i))/3600-TP.old*Math.max(0,act(i)-(i.first_ts||i.ts))/3600;
 const r=pool.map(i=>[v(i),i]).sort((a,b)=>b[0]-a[0]).map(x=>x[1]),nq=i=>!(i.kind&&i.kind.type==='quote'),pin=L.filter(i=>i.lead_until>now&&photo(i)===2).sort((a,b)=>a.lead_until-b.lead_until)[0],lead=pin||r.find(i=>photo(i)===2&&nq(i))||r.find(i=>photo(i)&&nq(i))||r[0],rest=r.filter(i=>i!==lead);
 let sec=rest.filter(i=>photo(i)).slice(0,TP.n-1);sec=sec.concat(rest.filter(i=>!sec.includes(i)).slice(0,TP.n-1-sec.length));sec.sort((a,b)=>rest.indexOf(a)-rest.indexOf(b));return[lead,...sec]}
function mini(i,n){const c=CATS[i.categories[0]]||'#2fd3b4',u=esc(i.url||i.link),im=pic(i);const img=im?`<img class="fg" loading="lazy" referrerpolicy="no-referrer" src="${esc(im)}" alt="" onerror="this.remove()">`:'';
return `<article class="card mini in" style="--c:${c}" data-cat="${i.categories[0]}" data-pos="${n}"><a class="img" href="${u}" aria-hidden="true" tabindex="-1"><div class="ph">${i.categories[0]}</div>${img}</a><div class="body"><div class="tags">${i.brk?`<span class="tag brk">${TX.brk}</span>`:''}<span class="tag" style="--c:${c}">${i.categories[0]}</span></div><h2><a href="${u}">${esc(i.title)}</a></h2><div class="meta"><span>${ago(i.ts)}</span></div></div></article>`}
function render(){const L=list(),A=window.ADS_CONFIG||{},every=A.inFeedEvery||4;let h='';
const T=q?[]:topPick(L),F=T.length?L.filter(i=>!T.includes(i)):L,top=$('#lead');
if(top){top.classList.remove('wait');top.innerHTML=T.length?`<h2 class="top-h">${TX.top}</h2>${card(T[0],0,1)}<div class="minis">${T.slice(1).map((i,k)=>mini(i,k+1)).join('')}</div>`:''}
const o=top&&T.length?T.length:0;
F.slice(0,shown).forEach((i,n)=>{h+=card(i,n+o,!top&&n===0);if((n+1)%every===0)h+=`<div class="ad ad-feed" data-slot="inFeed" data-size="Responsive In-Feed"></div>`});
$('#feed').innerHTML=h||'<div class="empty">'+TX.none+'</div>';$('#more').style.display=F.length>shown?'block':'none';
$('#count').textContent=L.length+' '+TX.stories;observe();fillAds()}
const io=new IntersectionObserver(es=>es.forEach(e=>e.isIntersecting&&(e.target.classList.add('in'),io.unobserve(e.target))),{threshold:.08});
function observe(){document.querySelectorAll('.card:not(.in)').forEach(c=>io.observe(c))}
$('#more').onclick=()=>{shown+=12;render()};
window.onscroll=()=>{$('#toTop').classList.toggle('show',scrollY>800);if(innerHeight+scrollY>document.body.offsetHeight-600&&list().length-($('#lead')&&!q?TP.n:0)>shown){shown+=8;render()}};
$('#toTop').onclick=()=>scrollTo({top:0,behavior:'smooth'});
function fillAds(){const A=window.ADS_CONFIG;if(!A||!A.enabled||!A.publisherId||!(window.wcnConsent&&wcnConsent()))return;
document.querySelectorAll('.ad:not(.live-ad)').forEach(d=>{d.classList.add('live-ad');d.innerHTML=`<ins class="adsbygoogle" style="display:block;width:100%;height:100%" data-ad-client="${A.publisherId}" data-ad-slot="${A.slots[d.dataset.slot]}" data-ad-format="auto" data-full-width-responsive="true"></ins>`;(window.adsbygoogle=window.adsbygoogle||[]).push({})})}
async function load(){try{const d=await (await fetch('news.json?'+Date.now())).json();items=d.items;
$('#updated').innerHTML='<span class="upd-p">'+TX.updated+'</span>'+ago(d.updated);if($('#updated-m'))$('#updated-m').textContent=ago(d.updated);$('#ticker').innerHTML=items.slice(0,15).map(i=>`<span><b>${i.categories[0]}</b> ${esc(i.title)}</span>`).join('');
chips();render();restore();setTimeout(()=>localStorage.setItem('wcn_seen',d.updated),5000)}catch(e){$('#feed').innerHTML='<div class="empty">'+TX.fail+'</div>'}}
load();setInterval(load,15*60*1000);
async function liveBar(){try{const d=await (await fetch('/live.json?'+Date.now())).json(),L=d.live||[];let b=document.getElementById('livebar');if(!L.length){b&&b.remove();return}
if(!b){b=document.createElement('div');b.id='livebar';b.className='livebar';const f=$('.rail')||$('#filters');f.parentNode.insertBefore(b,f);b.onclick=e=>{const a=e.target.closest('a');a&&window.track&&track('live_banner_click',{story_slug:a.dataset.live})}}
b.innerHTML=L.map(x=>`<a href="/${esc(LANG==='es'?(x.es||x.en):x.en)}" data-live="${esc(x.key)}"><span class="live-badge">${LANG==='es'?'EN VIVO':'LIVE NOW'}</span> <b>${esc(x.name)}</b> <span>${LANG==='es'?'Resultados en vivo, combate por combate':'Match-by-match live results'} →</span></a>`).join('')}catch(e){}}
liveBar();setInterval(liveBar,3*60*1000);

document.addEventListener('wcn-consent',fillAds);

// remember feed position so Back returns to the same story
document.addEventListener('click',e=>{const a=e.target.closest('.card a');if(a&&/^(story|noticias)\//.test(a.getAttribute('href')))sessionStorage.setItem('wcn_scroll',JSON.stringify({y:scrollY,shown,q,sel}))});
let _restored=0;function restore(){if(_restored++)return;const s=JSON.parse(sessionStorage.getItem('wcn_scroll')||'null');if(!s)return;shown=Math.max(shown,s.shown||12);render();
 document.querySelectorAll('.card').forEach(c=>c.classList.add('in'));requestAnimationFrame(()=>scrollTo(0,s.y));sessionStorage.removeItem('wcn_scroll')}
if('scrollRestoration' in history)history.scrollRestoration='manual';
addEventListener('pageshow',e=>{if(e.persisted){}});
