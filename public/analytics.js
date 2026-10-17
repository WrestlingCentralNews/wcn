(function(){
const ID=(window.ANALYTICS_CONFIG||{}).measurementId, K='wcn_consent';
window.track=function(n,p){if(window._ga)gtag('event',n,p||{})};
// Consent Mode v2: everything denied by default until the visitor accepts.
window.dataLayer=window.dataLayer||[];window.gtag=window.gtag||function(){dataLayer.push(arguments)};
gtag('consent','default',{ad_storage:'denied',analytics_storage:'denied',ad_user_data:'denied',ad_personalization:'denied',wait_for_update:500});
function loadGA(){if(!ID||window._ga)return;window._ga=1;
 gtag('consent','update',{ad_storage:'granted',analytics_storage:'granted',ad_user_data:'granted',ad_personalization:'granted'});
 gtag('js',new Date());gtag('config',ID);const s=document.createElement('script');s.async=1;s.src='https://www.googletagmanager.com/gtag/js?id='+ID;document.head.appendChild(s)}
function banner(){const b=document.createElement('div');b.id='consent';b.innerHTML='<p>We use cookies for analytics and ads to keep WCN free. See our <a href="/privacy.html">Privacy Policy</a>.</p><div><button data-c="no">Decline</button><button data-c="yes" class="ok">Accept</button></div>';
 b.onclick=e=>{const c=e.target.dataset.c;if(!c)return;localStorage.setItem(K,c);b.remove();if(c==='yes')loadGA();document.dispatchEvent(new Event('wcn-consent'))};document.body.appendChild(b)}
const c=localStorage.getItem(K);if(c==='yes')loadGA();else if(!c)document.addEventListener('DOMContentLoaded',banner);
window.wcnConsent=()=>localStorage.getItem(K)==='yes';
// scroll depth
const marks=[25,50,75,100],hit=new Set();addEventListener('scroll',()=>{const p=Math.round((scrollY+innerHeight)/document.body.scrollHeight*100);marks.forEach(m=>{if(p>=m&&!hit.has(m)){hit.add(m);track('scroll_depth',{percent:m})}})},{passive:true});
document.addEventListener('click',e=>{const a=e.target.closest('.card a, .upd a');if(a){const c=a.closest('.card');track('story_click',{title:c.querySelector('h2').innerText.slice(0,100),source:a.hostname,category:c.dataset.cat,position:+c.dataset.pos,is_update:!!a.closest('.upd')})}
 const ch=e.target.closest('.chip');if(ch)setTimeout(()=>track('filter_change',{filter:ch.dataset.k,active:ch.classList.contains('on'),selected:document.querySelectorAll('.chip.on').length}),0)});
document.addEventListener('toggle',e=>{if(e.target.classList&&e.target.classList.contains('upd')&&e.target.open)track('timeline_open')},true);
})();
