/* Markaz CRM service worker: static fayllar keshdan, sahifalar har doim serverdan.
   Internet yo'q bo'lsa, oflayn sahifa ko'rsatiladi. Shaxsiy ma'lumot keshlanmaydi. */
const V="markaz-v1",OFFLINE="/oflayn/";
self.addEventListener("install",e=>{e.waitUntil(caches.open(V).then(c=>c.addAll([OFFLINE])).then(()=>self.skipWaiting()))});
self.addEventListener("activate",e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==V).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener("fetch",e=>{
  const r=e.request;if(r.method!=="GET")return;
  const u=new URL(r.url);if(u.origin!==location.origin)return;
  if(r.mode==="navigate"){e.respondWith(fetch(r).catch(()=>caches.match(OFFLINE)));return}
  if(u.pathname.startsWith("/static/")){
    e.respondWith(caches.match(r).then(hit=>hit||fetch(r).then(res=>{if(res.ok){const cp=res.clone();caches.open(V).then(c=>c.put(r,cp))}return res})));
  }
});
