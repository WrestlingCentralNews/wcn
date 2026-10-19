/* WCN PWA: service worker registration, install button (Android/desktop), one-time iOS hint, offline notice.
   Install bar and iOS hint only from a reader's 2nd visit (wcnVisits). */
(function(){
  if ('serviceWorker' in navigator) addEventListener('load', function(){ navigator.serviceWorker.register('/sw.js', {scope: '/'}).catch(function(e){ console.warn('WCN SW', e); }); });
  var LS = window.localStorage, K = 'wcn_install_dismissed', IOS = 'wcn_ios_hint_shown';
  // Visit counter (owner rule 2026-10-19): no install / alerts prompts on a reader's first visit, only from the 2nd visit on.
  // A visit = a browser session (sessionStorage flag); readers from before the counter existed count as returning.
  // Shared with push.js (whichever runs first counts the visit; the other reuses it).
  window.wcnVisits = window.wcnVisits || function(){ try { var S = localStorage, s = sessionStorage, n = +S.getItem('wcn_visits') || 0;
    if (!s.getItem('wcn_vs')) { if (!n && (S.getItem('wcn_seen') || S.getItem('wcn_consent') || S.getItem('wcn_filters') || S.getItem('wcn_lang') || S.getItem('wcn_install_dismissed') || S.getItem('wcn_ios_hint_shown'))) n = 1;
      n++; S.setItem('wcn_visits', String(n)); s.setItem('wcn_vs', '1'); }
    return n; } catch (e) { return 1; } };
  var returning = wcnVisits() >= 2;
  var standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  function get(k){ try { return LS.getItem(k); } catch(e){ return null; } }
  function set(k){ try { LS.setItem(k, String(Date.now())); } catch(e){} }
  function bar(html, cls){
    var d = document.createElement('div'); d.className = 'pwa-bar ' + (cls||''); d.setAttribute('role', 'dialog'); d.setAttribute('aria-label', 'Install WCN app');
    d.innerHTML = html + '<button class="pwa-x" aria-label="Dismiss">×</button>'; document.body.appendChild(d);
    requestAnimationFrame(function(){ d.classList.add('in'); }); return d;
  }
  function track(n, p){ try { if (window.gtag) gtag('event', n, p || {}); } catch (e) {} }
  var installed = false;
  function close(d, key){ d.classList.remove('in'); setTimeout(function(){ d.remove(); }, 300); if (key) set(key); }
  if (!standalone && returning) {   // first visit: no install bar / iOS hint (the service worker still registers above)
    var deferred = null;
    addEventListener('beforeinstallprompt', function(e){
      e.preventDefault(); deferred = e;
      var ts = +get(K) || 0; if (Date.now() - ts < 30 * 864e5) return;   // dismissed: stay quiet for 30 days
      (function show(){ if ((window.wcnEU && !get('wcn_consent')) || document.getElementById('consent')) return setTimeout(show, 5000); if (document.querySelector('.pwa-bar')) return;
        track('pwa_prompt_shown', {prompt_type: 'install_bar'});
        var d = bar('<img src="/pwa/icon-192.png" alt="" width="34" height="34"><span><b>Get the WCN app</b><small>Breaking wrestling news, one tap away</small></span><button class="pwa-go">Install</button>');
        d.querySelector('.pwa-x').onclick = function(){ close(d, K); };
        d.querySelector('.pwa-go').onclick = function(){ if (!deferred) return close(d); deferred.prompt(); deferred.userChoice.then(function(ch){ var o = ch && ch.outcome; if (o === 'accepted') { installed = true; track('pwa_install', {method: 'install_prompt'}); } else track('pwa_install_dismissed', {method: 'install_prompt'}); deferred = null; close(d, K); }); };
      })();
    });
    addEventListener('appinstalled', function(){ if (!installed) { installed = true; track('pwa_install', {method: 'appinstalled'}); } set(K); var d = document.querySelector('.pwa-bar'); if (d) close(d); });
    var ua = navigator.userAgent, isIOS = /iphone|ipad|ipod/i.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    var safari = isIOS && /safari/i.test(ua) && !/crios|fxios|edgios|gsa\//i.test(ua);
    if (safari && !get(IOS)) (function show(){ if ((window.wcnEU && !get('wcn_consent')) || document.getElementById('consent')) return setTimeout(show, 5000);
      set(IOS);   // shown at most once
      track('pwa_ios_hint_shown', {prompt_type: 'ios_add_to_home'});
      var d = bar('<img src="/pwa/icon-192.png" alt="" width="34" height="34"><span><b>Add WCN to your Home Screen</b><small>Tap <svg viewBox="0 0 24 24" width="14" height="14" aria-label="Share"><path fill="currentColor" d="M12 2l4 4h-3v8h-2V6H8l4-4zm-7 9h3v2H6v7h12v-7h-2v-2h3a1 1 0 011 1v9a1 1 0 01-1 1H5a1 1 0 01-1-1v-9a1 1 0 011-1z"/></svg> Share → Add to Home Screen</small></span>', 'ios');
      d.querySelector('.pwa-x').onclick = function(){ close(d); };
      setTimeout(function(){ if (d.isConnected) close(d); }, 15000);
    })();
  }
  function net(){
    var n = document.getElementById('pwa-offline');
    if (navigator.onLine) { if (n) n.remove(); return; }
    if (!n) { n = document.createElement('div'); n.id = 'pwa-offline'; n.textContent = "You're offline — showing saved stories"; document.body.prepend(n); }
  }
  addEventListener('online', net); addEventListener('offline', net); if (document.readyState !== 'loading') net(); else addEventListener('DOMContentLoaded', net);
})();
