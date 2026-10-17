/* WCN service worker. Generated into public/sw.js by pages.py; VERSION changes whenever static assets change. */
const VERSION = "__VERSION__";
const STATIC = "wcn-static-" + VERSION, PAGES = "wcn-pages-v1", FONTS = "wcn-fonts-v1";
const KEEP = [STATIC, PAGES, FONTS];
const PRECACHE = __PRECACHE__;
const OFFLINE = "/offline.html", MAX_PAGES = 80;
// Never touched by the SW (always straight to network): ads, analytics, consent, config, RSS feeds/sitemap (*.xml).
const BYPASS = /^\/push\/|\.xml$|\/(analytics|ads-config)\.js$|\/ads\.txt$|\/sw\.js$|\/manifest\.webmanifest$/;
const STATIC_EXT = /\.(css|js|png|jpe?g|webp|gif|svg|ico|woff2?)$/i;

self.addEventListener("install", ev => {
  ev.waitUntil(caches.open(STATIC).then(c => c.addAll(PRECACHE.map(u => new Request(u, {cache: "reload"})))).then(() => self.skipWaiting()));
});
self.addEventListener("activate", ev => {
  ev.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith("wcn-") && !KEEP.includes(k)).map(k => caches.delete(k))))
    .then(() => self.registration.navigationPreload && self.registration.navigationPreload.enable().catch(() => {}))
    .then(() => self.clients.claim()));
});

async function trim(cache) {
  const ks = await cache.keys();
  for (let i = 0; i < ks.length - MAX_PAGES; i++) await cache.delete(ks[i]);
}
// Network-first: always fresh when online; cached copy only if the network actually fails.
async function networkFirst(ev, key) {
  const cache = await caches.open(PAGES);
  try {
    const res = (ev.preloadResponse && await ev.preloadResponse) || await fetch(ev.request, {cache: "no-cache"});
    if (res && res.ok && res.type === "basic") { cache.put(key, res.clone()).then(() => trim(cache)); }
    return res;
  } catch (err) {
    const hit = await cache.match(key, {ignoreSearch: true}) || await caches.match(key, {ignoreSearch: true});
    if (hit) return hit;
    if (ev.request.mode === "navigate") return (await caches.match(OFFLINE)) || Response.error();
    throw err;
  }
}
async function cacheFirst(req, name) {
  const hit = await caches.match(req, {ignoreSearch: name !== FONTS});
  if (hit) return hit;
  const res = await fetch(req);
  if (res && (res.ok || res.type === "opaque")) { const c = await caches.open(name); c.put(req, res.clone()); }
  return res;
}

self.addEventListener("fetch", ev => {
  const req = ev.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin === location.origin) {
    if (BYPASS.test(url.pathname)) return;
    if (req.mode === "navigate" || url.pathname.endsWith(".html") || url.pathname === "/") {
      const key = new URL(url.pathname === "/" ? "/index.html" : url.pathname, location.origin).href;
      return ev.respondWith(networkFirst(ev, key));
    }
    if (url.pathname.endsWith(".json")) return ev.respondWith(networkFirst(ev, new URL(url.pathname, location.origin).href));
    if (STATIC_EXT.test(url.pathname)) return ev.respondWith(cacheFirst(req, STATIC));
    return;
  }
  // Google Fonts only; every other cross-origin request (AdSense, analytics, OneSignal cdn/api, story images) is left alone.
  if (url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com") return ev.respondWith(cacheFirst(req, FONTS));
});
