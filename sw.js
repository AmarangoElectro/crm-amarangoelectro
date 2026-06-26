/* Service Worker - Amarango / AmarangoElectro
   Permite que el CRM se instale como app y muestre notificaciones. */

const CACHE = 'amarango-v1';

// Instalación: activar de inmediato
self.addEventListener('install', (e) => {
  self.skipWaiting();
});

// Activación: tomar control de las pestañas abiertas
self.addEventListener('activate', (e) => {
  e.waitUntil(self.clients.claim());
});

// Al tocar una notificación, abrir / enfocar el CRM
self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  e.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((cs) => {
      for (const c of cs) {
        if ('focus' in c) return c.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow('.');
    })
  );
});

// Soporte para notificaciones push (si en el futuro se usan)
self.addEventListener('push', (e) => {
  let data = { title: 'Amarango 🐝', body: 'Tenés una novedad' };
  try { if (e.data) data = e.data.json(); } catch (err) {}
  e.waitUntil(
    self.registration.showNotification(data.title || 'Amarango 🐝', {
      body: data.body || '',
      tag: 'ae-msg',
      renotify: true
    })
  );
});
