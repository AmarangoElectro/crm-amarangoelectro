// sw.js - Service Worker LIMPIO (no cachea nada)
// El anterior guardaba versiones viejas de la app y no dejaba ver los cambios.
// Este se instala, borra todo el caché viejo y deja pasar siempre la versión más nueva.

self.addEventListener('install', function(e){
  self.skipWaiting(); // activarse de inmediato, sin esperar
});

self.addEventListener('activate', function(e){
  e.waitUntil(
    caches.keys().then(function(keys){
      return Promise.all(keys.map(function(k){ return caches.delete(k); }));
    }).then(function(){
      return self.clients.claim();
    })
  );
});

// NO interceptar fetch: siempre va directo a la red (nunca sirve copias viejas)
// (a propósito no hay listener de 'fetch')
