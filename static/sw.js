/* JARVIS Service Worker — caches app shell for offline & fast load */
const CACHE = 'jarvis-v3';
const SHELL = ['/android', '/app', '/static/android_manifest.json', '/static/manifest.json'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c =>
      Promise.allSettled(SHELL.map(u => c.add(u)))
    ).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/ws')) return;
  e.respondWith(
    fetch(e.request).then(r => {
      if (r && r.status === 200) {
        const clone = r.clone();
        caches.open(CACHE).then(c => c.put(e.request, clone));
      }
      return r;
    }).catch(() => caches.match(e.request))
  );
});

/* Push notification handler */
self.addEventListener('push', e => {
  const data = e.data?.json() || { title: 'JARVIS', body: 'New message' };
  e.waitUntil(
    self.registration.showNotification(data.title || 'JARVIS', {
      body: data.body || '',
      icon: '/static/icon-192.png',
      badge: '/static/icon-192.png',
      vibrate: [200, 100, 200],
      tag: 'jarvis',
      renotify: true,
      data: { url: data.url || '/android' },
    })
  );
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(clients.openWindow(e.notification.data?.url || '/android'));
});
