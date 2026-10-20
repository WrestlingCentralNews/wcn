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
// Microsoft Clarity (heatmaps + session recordings). Loaded ONLY when analytics consent is granted
// (default outside EEA/UK/CH, or after Accept in the banner). Consent is passed with Clarity's consentv2 API;
// a later Decline revokes it (Clarity deletes its cookies) and stops recording; the tag is not loaded on later pages.
// NEVER pass a 'source' key: it is reserved for Microsoft-issued CMP IDs, and an unknown value made p.clarity.ms/collect
// answer 400 to the session's first upload, so Clarity recorded 0 sessions (Oct 17-19 2026).
const CLARITY_ID='yzbrkdw45p';let clarityOn=false;
window.clarity=window.clarity||function(){(window.clarity.q=window.clarity.q||[]).push(arguments)};
function clarityConsent(ok){const v=ok?'granted':'denied';try{clarity('consentv2',{ad_Storage:'denied',analytics_Storage:v})}catch(e){}}
function loadClarity(){if(clarityOn)return;clarityOn=true;clarityConsent(true);try{clarity('set','page_type',pt())}catch(e){}
 const t=document.createElement('script');t.async=1;t.src='https://www.clarity.ms/tag/'+CLARITY_ID;const f=document.getElementsByTagName('script')[0];(f&&f.parentNode?f.parentNode:document.head).insertBefore(t,f||null)}
function clearClarity(){const h=location.hostname,ds=['',h,'.'+h.replace(/^www\./,'')];['_clck','_clsk'].forEach(n=>ds.forEach(d=>{document.cookie=n+'=; Max-Age=0; path=/'+(d?'; domain='+d:'')}))}
// Owner device opt-out (?wcn_me=1, set by the inline head script as window.wcnMe): never load Clarity on that device.
function syncClarity(){if(window.wcnMe)return;if(window.wcnConsent())loadClarity();else if(clarityOn){clarityConsent(false);clarityOn=false;setTimeout(()=>{try{clarity('stop')}catch(e){}clearClarity()},300)}}
document.addEventListener('wcn-consent',syncClarity);
document.addEventListener('DOMContentLoaded',()=>{
 if(EU&&!get())banner();
 const f=document.querySelector('footer');if(f&&!f.querySelector('.cookie-set')){const a=document.createElement('a');a.href='#';a.className='cookie-set';a.textContent='Cookie settings';a.onclick=e=>{e.preventDefault();banner()};f.append(' · ',a)}
 if(window.wcnMe&&f&&!f.querySelector('.wcn-me')){const m=document.createElement('a');m.href='?wcn_me=0';m.className='wcn-me';m.title='Owner device: GA4 and Clarity are not loaded here. Tap to turn analytics back on.';m.textContent='Analytics off on this device';m.style.opacity='.7';f.append(' · ',m)}
});
// scroll depth
const marks=[25,50,75,100],hit=new Set();addEventListener('scroll',()=>{const p=Math.round((scrollY+innerHeight)/document.body.scrollHeight*100);marks.forEach(m=>{if(p>=m&&!hit.has(m)){hit.add(m);track('scroll_depth',{percent:m})}})},{passive:true});
// Behavior events (all via gtag, so Consent Mode applies exactly as for page_view). Enhanced measurement already covers page_view/scroll.
const slug=h=>{const m=(h||'').match(/story\/([^\/?#]+?)(?:-[0-9a-f]{6,})?\.html/);return m?m[1].slice(0,100):''};
const host=a=>(a.hostname||'').replace(/^www\./,'');
const place=a=>a.closest('header')?'header':a.closest('footer')?'footer':'body';
const pt=()=>document.body&&document.body.classList.contains('story-page')?'story':/\/newsletter\//.test(location.pathname)?'newsletter':'home';
document.addEventListener('click',e=>{const t=e.target;if(!t.closest)return;
 const ch=t.closest('.chip');if(ch){setTimeout(()=>{const b=document.querySelector('.chip[data-k="'+ch.dataset.k+'"]');track('filter_click',{brand:ch.dataset.k,active:!!(b&&b.classList.contains('on')),selected_count:document.querySelectorAll('.chip.on').length})},0);return}
 const a=t.closest('a[href]');if(!a)return;const ext=host(a)&&host(a)!==location.hostname.replace(/^www\./,'');
 const so=/(^|\.)(x|twitter)\.com$/.test(host(a))?'x':/(^|\.)facebook\.com$/.test(host(a))?'facebook':'';
 if(so&&/wrestlingWCN|Wrestling-Central-News/i.test(a.href)){track('social_click',{network:so,placement:place(a),page_type:pt()});return}
 const c=a.closest('.card'),rel=a.closest('.rel'),ns=a.closest('.nl-sample');
 if(c||rel||ns){const u=!!a.closest('.upd'),list=c?(u?'feed_update':c.closest('#lead')?'top':'feed'):rel?'related':'newsletter_sample';
  const items=rel?[...document.querySelectorAll('.rel')]:ns?[...ns.querySelectorAll('a')]:null;
  track('story_click',{story_title:((c?c.querySelector('h2'):a).innerText||'').trim().slice(0,100),story_slug:slug(a.href),brand:c?c.dataset.cat:rel?((document.querySelector('.story .tag:not(.conf)')||{}).textContent||''):((a.nextElementSibling||{}).textContent||''),position:c?+c.dataset.pos+1:items.indexOf(rel||a)+1,list,link_type:a.classList.contains('img')?'image':a.closest('.meta')?'read_more':'headline',outbound:ext,page_type:pt()})}
 if(ext&&(c||a.closest('.credit,.pcredit')))track('source_click',{source_domain:host(a),link_type:a.closest('.pcredit')?'image_credit':c?'feed_card':'source_link',story_slug:slug(location.pathname),page_type:pt()});
});
syncClarity();
document.addEventListener('toggle',e=>{if(e.target.classList&&e.target.classList.contains('upd')&&e.target.open)track('timeline_open')},true);
})();
