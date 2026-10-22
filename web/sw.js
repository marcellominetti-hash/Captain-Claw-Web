const CACHE='corsair-cat-v2';
const ASSETS=['./','./index.html','./styles.css?v=2','./game.js?v=2','./input-fix.js?v=2','./manifest.webmanifest?v=2'];

self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE).then(c=>c.addAll(ASSETS)).then(()=>self.skipWaiting()));
});

self.addEventListener('activate',event=>{
  event.waitUntil(
    caches.keys()
      .then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k))))
      .then(()=>self.clients.claim())
  );
});

self.addEventListener('fetch',event=>{
  if(event.request.method!=='GET') return;
  const url=new URL(event.request.url);
  if(url.origin!==self.location.origin) return;

  // Network-first for app code so mobile users do not get stuck on stale JS.
  if(/\.(?:html|js|css|webmanifest)$/.test(url.pathname) || url.pathname.endsWith('/')){
    event.respondWith(
      fetch(event.request)
        .then(resp=>{
          const copy=resp.clone();
          caches.open(CACHE).then(c=>c.put(event.request,copy));
          return resp;
        })
        .catch(()=>caches.match(event.request).then(r=>r||caches.match('./index.html')))
    );
    return;
  }

  event.respondWith(caches.match(event.request).then(cached=>cached||fetch(event.request)));
});
