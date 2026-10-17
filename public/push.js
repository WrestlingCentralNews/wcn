/* WCN breaking-news web push (OneSignal v16, Custom Code). Never auto-prompts: the header bell asks only on tap.
   OneSignal's worker lives at /push/onesignal/ (its own scope) so the PWA sw.js keeps '/'. */
(function(){
  var APP_ID = '50ded3cc-5465-43f5-9e31-4c229a84abde';
  var ua = navigator.userAgent, isIOS = /iphone|ipad|ipod/i.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  var standalone = matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
  var iosNeedsInstall = isIOS && !standalone;              // iOS only allows web push from a Home Screen app
  var canPush = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  if (!canPush && !iosNeedsInstall) return;               // unsupported browser: no bell at all
  var OS = null, ready = false;
  window.OneSignalDeferred = window.OneSignalDeferred || [];
  if (canPush) {
    var s = document.createElement('script'); s.src = 'https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.page.js'; s.defer = true; document.head.appendChild(s);
    OneSignalDeferred.push(async function(OneSignal){
      try {
        await OneSignal.init({appId: APP_ID, serviceWorkerPath: 'push/onesignal/OneSignalSDKWorker.js', serviceWorkerParam: {scope: '/push/onesignal/'},
          showCredit: false, autoResubscribe: true, requiresUserPrivacyConsent: true, notifyButton: {enable: false}, promptOptions: {slidedown: {prompts: []}}});
        OS = OneSignal; ready = true;
        if (Notification.permission === 'granted') OneSignal.setConsentGiven(true);   // already opted in earlier
        OneSignal.User.PushSubscription.addEventListener('change', paint);
        OneSignal.Notifications.addEventListener('permissionChange', paint);
        paint();
      } catch (e) { console.warn('WCN push init', e); }
    });
  }
  var BELL = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22zm7-6V11a7 7 0 0 0-5.5-6.84V3.5a1.5 1.5 0 0 0-3 0v.66A7 7 0 0 0 5 11v5l-2 2v1h18v-1l-2-2z"/></svg>';
  var btn;
  function subscribed(){ return ready && OS.User.PushSubscription.optedIn && Notification.permission === 'granted'; }
  function paint(){
    if (!btn) return;
    var on = subscribed();
    btn.classList.toggle('on', on);
    btn.title = on ? 'Breaking news alerts are on (tap to turn off)' : 'Get breaking news alerts';
    btn.setAttribute('aria-label', btn.title); btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    var l = btn.querySelector('.lbl'); if (l) l.textContent = on ? 'Alerts on' : 'Get breaking news alerts';
  }
  function toast(html, cls, ms){
    var old = document.querySelector('.push-toast'); if (old) old.remove();
    var d = document.createElement('div'); d.className = 'pwa-bar push-toast ' + (cls||''); d.setAttribute('role', 'status');
    d.innerHTML = '<img src="/pwa/icon-192.png" alt="" width="34" height="34"><span>' + html + '</span><button class="pwa-x" aria-label="Dismiss">×</button>';
    document.body.appendChild(d); requestAnimationFrame(function(){ d.classList.add('in'); });
    var close = function(){ d.classList.remove('in'); setTimeout(function(){ d.remove(); }, 300); };
    d.querySelector('.pwa-x').onclick = close; setTimeout(close, ms || 9000);
  }
  function track(n, p){ try { if (window.gtag) gtag('event', n, p || {}); } catch (e) {} }
  async function onTap(){
    if (iosNeedsInstall) { track('push_prompt_shown', {prompt_type: 'ios_install_required'}); return toast('<b>Alerts need the WCN app on iPhone</b><small>Tap Share → <b>Add to Home Screen</b>, open WCN from your Home Screen, then tap the bell.</small>', 'ios', 15000); }
    if (!ready) return toast('<b>One moment…</b><small>Alerts are still loading. Try again in a few seconds.</small>', '', 4000);
    if (Notification.permission === 'denied') { track('push_prompt_shown', {prompt_type: 'blocked_hint'}); return toast('<b>Notifications are blocked</b><small>Allow notifications for wrestlingcentralnews.com in your browser\'s site settings, then tap the bell again.</small>', 'ios', 12000); }
    try {
      if (subscribed()) { await OS.User.PushSubscription.optOut(); track('push_optout', {method: 'bell'}); toast('<b>Alerts turned off</b><small>Tap the bell any time to turn them back on.</small>', '', 5000); }
      else {
        OS.setConsentGiven(true);                      // tapping the bell = consent to push only (separate from ad/analytics cookies)
        var asked = Notification.permission === 'default'; if (asked) track('push_prompt_shown', {prompt_type: 'browser_permission'});
        await OS.User.PushSubscription.optIn();        // shows the browser permission prompt if needed
        if (Notification.permission === 'granted') track('push_optin', {method: 'bell', prompted: asked}); else track('push_prompt_declined', {result: Notification.permission});
        if (Notification.permission === 'granted') toast('<b>You\'re in!</b><small>We\'ll only ping you for big breaking wrestling news (max 3 a day).</small>', '', 7000);
      }
    } catch (e) { console.warn('WCN push', e); }
    paint();
  }
  function mount(){
    var soc = document.querySelector('.social'); if (!soc || document.querySelector('.soc-bell')) return;
    btn = document.createElement('button'); btn.type = 'button'; btn.className = 'soc soc-bell';
    btn.innerHTML = BELL + '<span class="lbl">Get breaking news alerts</span>'; btn.onclick = onTap; soc.prepend(btn); paint();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
