(function(){const A=window.ADS_CONFIG;function fill(){if(!A||!A.enabled||!A.publisherId||!(window.wcnConsent&&wcnConsent()))return;
document.querySelectorAll('.ad:not(.live-ad)').forEach(d=>{const id=A.slots[d.dataset.slot]||A.slots.inFeed;d.classList.add('live-ad');d.innerHTML=`<ins class="adsbygoogle" style="display:block;width:100%;height:100%" data-ad-client="${A.publisherId}" data-ad-slot="${id}" data-ad-format="auto" data-full-width-responsive="true"></ins>`;(window.adsbygoogle=window.adsbygoogle||[]).push({})})}
fill();document.addEventListener('wcn-consent',fill);
document.addEventListener('click',e=>{const a=e.target.closest('.rel');if(a&&window.track)track('related_click',{href:a.getAttribute('href')});const s=e.target.closest('.credit a');if(s&&window.track)track('source_click',{source:s.textContent})});
window.track&&track('story_view',{title:document.title})})();
