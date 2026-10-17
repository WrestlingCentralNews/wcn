(function(){
// Google tag (gtag.js) + Consent Mode v2 defaults are set inline in every page's <head> (GA_HEAD in pages.py), so GA4 fires on page load.
// This file only handles the cookie banner, the "Cookie settings" footer link, and custom events. It never loads gtag.js itself.
const K='wcn_consent';
window.dataLayer=window.dataLayer||[];window.gtag=window.gtag||function(){dataLayer.push(arguments)};
window._ga=1;
window.track=function(n,p){try{gtag('event',n,p||{})}catch(e){}};
// Cheap EEA/UK/CH detection by timezone (over-inclusive on purpose: all Europe/* zones plus EU Atlantic islands).
const TZ=(()=>{try{return Intl.DateTimeFormat().resolvedOptions().timeZone||''}catch(e){return ''}})();
const EU=/^Europe\//.test(TZ)||/^(Atlantic\/(Azores|Madeira|Canary|Reykjavik|Faroe)|Arctic\/Longyearbyen)$/.test(TZ);
window.wcnEU=EU;
function get(){try{return localStorage.getItem(K)}catch(e){return null}}
function apply(c){const v=c==='yes'?'granted':'denied';gtag('consent','update',{ad_storage:v,analytics_storage:v,ad_user_data:v,ad_personalization:v})}
// Ads/analytics allowed: explicit Accept, or no choice yet outside the EEA/UK/CH. An explicit Decline always wins.
window.wcnConsent=()=>{const c=get();return c?c==='yes':!EU};
function banner(){if(document.getElementById('consent'))return;const b=document.createElement('div');b.id='consent';b.innerHTML='<p>We use cookies for analytics and ads to keep WCN free. See our <a href="/privacy.html">Privacy Policy</a>.</p><div><button data-c="no">Decline</button><button data-c="yes" class="ok">Accept</button></div>';
 b.onclick=e=>{const c=e.target.dataset.c;if(!c)return;try{localStorage.setItem(K,c)}catch(x){}apply(c);b.remove();track('consent_choice',{choice:c});document.dispatchEvent(new Event('wcn-consent'))};document.body.appendChild(b)}
window.wcnCookieSettings=banner;
document.addEventListener('DOMContentLoaded',()=>{
 if(EU&&!get())banner();
 const f=document.querySelector('footer');if(f&&!f.querySelector('.cookie-set')){const a=document.createElement('a');a.href='#';a.className='cookie-set';a.textContent='Cookie settings';a.onclick=e=>{e.preventDefault();banner()};f.append(' · ',a)}
});
// scroll depth
const marks=[25,50,75,100],hit=new Set();addEventListener('scroll',()=>{const p=Math.round((scrollY+innerHeight)/document.body.scrollHeight*100);marks.forEach(m=>{if(p>=m&&!hit.has(m)){hit.add(m);track('scroll_depth',{percent:m})}})},{passive:true});
document.addEventListener('click',e=>{const a=e.target.closest('.card a, .upd a');if(a){const c=a.closest('.card');track('story_click',{title:c.querySelector('h2').innerText.slice(0,100),source:a.hostname,category:c.dataset.cat,position:+c.dataset.pos,is_update:!!a.closest('.upd')})}
 const ch=e.target.closest('.chip');if(ch)setTimeout(()=>track('filter_change',{filter:ch.dataset.k,active:ch.classList.contains('on'),selected:document.querySelectorAll('.chip.on').length}),0)});
document.addEventListener('toggle',e=>{if(e.target.classList&&e.target.classList.contains('upd')&&e.target.open)track('timeline_open')},true);
})();
