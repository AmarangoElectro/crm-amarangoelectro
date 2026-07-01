// Service Worker - Calculadora AmarangoElectro
// v2: RED PRIMERO para el HTML (siempre trae la última versión), caché solo de respaldo.
var CACHE='amarango-calc-v2';
var ARCHIVOS=['./calculadora.html','./manifest.json','./icon.png','./icon-192.png'];

self.addEventListener('install', function(e){
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(function(c){return c.addAll(ARCHIVOS).catch(function(){});}));
});

self.addEventListener('activate', function(e){
  e.waitUntil(
    caches.keys().then(function(claves){
      return Promise.all(claves.map(function(k){ if(k!==CACHE)return caches.delete(k); }));
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', function(e){
  var req=e.request;
  // Para el HTML y JS: RED PRIMERO (siempre lo último). Si no hay internet, uso el caché.
  var esDocumento = req.mode==='navigate' || (req.url.indexOf('.html')>-1);
  if(esDocumento){
    e.respondWith(
      fetch(req).then(function(r){
        return caches.open(CACHE).then(function(c){ try{c.put(req,r.clone());}catch(err){} return r; });
      }).catch(function(){ return caches.match(req).then(function(x){ return x || caches.match('./calculadora.html'); }); })
    );
    return;
  }
  // Para imágenes/íconos: caché primero (no cambian casi nunca)
  e.respondWith(
    caches.match(req).then(function(resp){
      return resp || fetch(req).then(function(r){
        return caches.open(CACHE).then(function(c){ try{c.put(req,r.clone());}catch(err){} return r; });
      }).catch(function(){ return resp; });
    })
  );
});
