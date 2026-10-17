(function(){const A=window.ADS_CONFIG;function fill(){if(!A||!A.enabled||!A.publisherId||!(window.wcnConsent&&wcnConsent()))return;
document.querySelectorAll('.ad:not(.live-ad)').forEach(d=>{const id=A.slots[d.dataset.slot]||A.slots.inFeed;d.classList.add('live-ad');d.innerHTML=`<ins class="adsbygoogle" style="display:block;width:100%;height:100%" data-ad-client="${A.publisherId}" data-ad-slot="${id}" data-ad-format="auto" data-full-width-responsive="true"></ins>`;(window.adsbygoogle=window.adsbygoogle||[]).push({})})}
fill();document.addEventListener('wcn-consent',fill);
// related/source clicks are tracked in analytics.js (story_click / source_click)
window.track&&track('story_view',{brand:((document.querySelector('.story .tag:not(.conf)')||{}).textContent||''),story_slug:(location.pathname.match(/story\/([^\/]+?)(?:-[0-9a-f]{6,})?\.html/)||[])[1]||''})})();
