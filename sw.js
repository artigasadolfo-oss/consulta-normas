/* Service worker de Consulta de normas: guarda la página para que funcione sin conexión.
   Estrategia: responde desde la copia guardada y, si hay red, la actualiza para la próxima vez. */
const CACHE = 'consulta-normas-v1';
const BASE = ['./', 'index.html', 'favicon.png', 'favicon.ico', 'apple-touch-icon.png', 'manifest.webmanifest'];
self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c => Promise.all(BASE.map(u => c.add(u).catch(() => null)))));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const r = e.request;
  if (r.method !== 'GET' || new URL(r.url).origin !== location.origin) return;
  e.respondWith(caches.open(CACHE).then(async c => {
    const hit = await c.match(r, { ignoreSearch: true });
    const red = fetch(r).then(resp => { if (resp && resp.ok) c.put(r, resp.clone()); return resp; }).catch(() => null);
    return hit || (await red) || new Response('Sin conexión y sin copia guardada', { status: 503 });
  }));
});
