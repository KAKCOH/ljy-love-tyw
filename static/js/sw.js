const CACHE = 'lovetimeline-v2';
const ASSETS = [
  '/',
  '/static/css/style.css',
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/manifest.json',
  '/login'
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(ASSETS).catch(() => {}))
  );
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE).map(k => caches.delete(k))
    ))
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;

  // Network-first for HTML pages, cache-first for static assets
  if (e.request.mode === 'navigate' || e.request.headers.get('accept')?.includes('text/html')) {
    e.respondWith(
      fetch(e.request)
        .then(res => {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
          return res;
        })
        .catch(() => caches.match(e.request) || caches.match('/'))
    );
  } else {
    e.respondWith(
      caches.match(e.request).then(cached => cached || fetch(e.request).then(res => {
        const clone = res.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
        return res;
      }))
    );
  }
});

self.addEventListener('push', e => {
  let data = {};
  if (e.data) {
    try { data = e.data.json(); } catch (_) { data = { body: e.data.text() }; }
  }
  e.waitUntil(
    self.registration.showNotification(data.title || 'Love Timeline', {
      body: data.body || '',
      icon: '/static/icon-192.png',
      badge: '/static/icon-192.png',
      vibrate: [200, 100, 200],
      tag: data.tag || 'msg',
      renotify: true,
      data: { url: '/messages' }
    })
  );
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(windows => {
      const url = (e.notification.data && e.notification.data.url) || '/messages';
      for (const w of windows) {
        if (w.url.includes(url)) { w.focus(); return; }
      }
      if (clients.openWindow) clients.openWindow(url);
    })
  );
});
