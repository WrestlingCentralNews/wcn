const CATS={WWE:'#e63946',AEW:'#f5c542',TNA:'#4cc9f0',Indie:'#b5179e',Global:'#2ec27e'};
const KEY='wcn_filters';let sel=JSON.parse(localStorage.getItem(KEY)||'null')||Object.keys(CATS);
let items=[],shown=12,lastSeen=+localStorage.getItem('wcn_seen')||0,q='';
const $=s=>document.querySelector(s),esc=s=>(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function ago(t){const m=(Date.now()/1000-t)/60;return m<60?Math.max(1,m|0)+'m ago':m<1440?(m/60|0)+'h ago':(m/1440|0)+'d ago'}
function chips(){$('#filters').innerHTML=Object.entries(CATS).map(([k,c])=>`<button class="chip ${sel.includes(k)?'on':''}" style="--c:${c}" data-k="${k}">${k}<small>${items.filter(i=>i.categories.includes(k)).length}</small></button>`).join('')}
$('#filters').onclick=e=>{const b=e.target.closest('.chip');if(!b)return;const k=b.dataset.k;sel=sel.includes(k)?sel.filter(x=>x!==k):[...sel,k];localStorage.setItem(KEY,JSON.stringify(sel));shown=12;chips();render()};
let qt;$('#q').oninput=e=>{q=e.target.value.toLowerCase();clearTimeout(qt);qt=setTimeout(()=>window.track&&track('search',{search_term:q}),1200);shown=12;render()};
function list(){return items.filter(i=>i.categories.some(c=>sel.includes(c))&&(!q||(i.title+i.summary+i.source+(i.updates||[]).map(u=>u.title).join(' ')).toLowerCase().includes(q)))}
function card(i,n){const c=CATS[i.categories[0]];const img=i.image?`<img loading="lazy" referrerpolicy="no-referrer" src="${esc(i.image)}" alt="" onerror="this.remove()">`:'';
return `<article class="card ${n===0?'hero':''} ${i.kind&&i.kind.type==='quote'?'quote':''}" style="--c:${c}" data-cat="${i.categories[0]}" data-pos="${n}"><div class="img"><div class="ph">${i.categories[0]}</div>${img}</div><div class="body">
<div class="tags">${i.added>lastSeen&&lastSeen?'<span class="tag new">NEW</span>':''}${i.sources>1?`<span class="tag conf">✔ CONFIRMED BY ${i.sources} SOURCES</span>`:''}${(i.updates||[]).length?`<span class="tag dev">DEVELOPING · ${i.updates.length+1} REPORTS</span>`:''}${i.kind&&i.kind.type==='match'?'<span class="tag off">OFFICIAL MATCH</span>':''}${i.categories.map(k=>`<span class="tag" style="--c:${CATS[k]}">${k}</span>`).join('')}</div>
${i.kind&&i.kind.type==='quote'?`<blockquote class="qc"><span class="qm">“</span>${esc(i.kind.quote||i.summary.split(/(?<=[.!?])\s/)[0])}<cite>— ${esc(i.kind.who)}</cite></blockquote>`:''}<h2><a href="${esc(i.link)}" target="_blank" rel="noopener">${esc(i.title)}</a></h2>
<p>${esc(i.summary||`Developing story reported by ${i.source}. Tap through for the full report.`)}</p>
${(i.updates||[]).length?`<details class="upd"><summary>🔄 ${i.updates.length} related update${i.updates.length>1?"s":""} · story timeline</summary><ol>${i.updates.map(u=>`<li><time>${ago(u.ts)}</time><a href="${esc(u.link)}" target="_blank" rel="noopener">${esc(u.title)}</a><span>${esc(u.line)} <em>— ${esc(u.source)}</em></span></li>`).join("")}</ol></details>`:""}<div class="meta"><span>${esc(i.source)} · ${ago(i.ts)}</span><a href="${esc(i.link)}" target="_blank" rel="noopener">Read more →</a></div></div></article>`}
function render(){const L=list(),A=window.ADS_CONFIG||{},every=A.inFeedEvery||4;let h='';
L.slice(0,shown).forEach((i,n)=>{h+=card(i,n);if((n+1)%every===0)h+=`<div class="ad ad-feed" data-slot="inFeed" data-size="Responsive In-Feed"></div>`});
$('#feed').innerHTML=h||'<div class="empty">No stories for these filters yet — pick another promotion.</div>';$('#more').style.display=L.length>shown?'block':'none';
$('#count').textContent=L.length+' stories';observe();fillAds()}
const io=new IntersectionObserver(es=>es.forEach(e=>e.isIntersecting&&(e.target.classList.add('in'),io.unobserve(e.target))),{threshold:.08});
function observe(){document.querySelectorAll('.card:not(.in)').forEach(c=>io.observe(c))}
$('#more').onclick=()=>{shown+=12;render()};
window.onscroll=()=>{$('#toTop').classList.toggle('show',scrollY>800);if(innerHeight+scrollY>document.body.offsetHeight-600&&list().length>shown){shown+=8;render()}};
$('#toTop').onclick=()=>scrollTo({top:0,behavior:'smooth'});
function fillAds(){const A=window.ADS_CONFIG;if(!A||!A.enabled||!(window.wcnConsent&&wcnConsent()))return;
if(!window._ads){window._ads=1;const s=document.createElement('script');s.async=1;s.crossOrigin='anonymous';s.src='https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client='+A.publisherId;document.head.appendChild(s)}
document.querySelectorAll('.ad:not(.live-ad)').forEach(d=>{d.classList.add('live-ad');d.innerHTML=`<ins class="adsbygoogle" style="display:block;width:100%;height:100%" data-ad-client="${A.publisherId}" data-ad-slot="${A.slots[d.dataset.slot]}" data-ad-format="auto" data-full-width-responsive="true"></ins>`;(window.adsbygoogle=window.adsbygoogle||[]).push({})})}
async function load(){try{const d=await (await fetch('news.json?'+Date.now())).json();items=d.items;
$('#updated').textContent='updated '+ago(d.updated);$('#ticker').innerHTML=items.slice(0,15).map(i=>`<span><b>${i.categories[0]}</b> ${esc(i.title)}</span>`).join('');
chips();render();setTimeout(()=>localStorage.setItem('wcn_seen',d.updated),5000)}catch(e){$('#feed').innerHTML='<div class="empty">Could not load news.</div>'}}
load();setInterval(load,15*60*1000);

document.addEventListener('wcn-consent',fillAds);
