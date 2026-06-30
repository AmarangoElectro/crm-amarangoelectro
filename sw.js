// Service Worker - AmarangoElectro CRM
var CACHE='amarango-crm-v1';
var ARCHIVOS=['./index.html','./manifest.json','./icon.png','./icon-192.png'];

self.addEventListener('install', function(e){
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(function(c){return c.addAll(ARCHIVOS).catch(function(){});}));
});
self.addEventListener('activate', function(e){
  e.waitUntil(caches.keys().then(function(ks){return Promise.all(ks.map(function(k){if(k!==CACHE)return caches.delete(k);}));}));
  self.clients.claim();
});
self.addEventListener('fetch', function(e){
  // Para el CRM: red primero (datos frescos), caché como respaldo si no hay internet
  e.respondWith(
    fetch(e.request).then(function(r){
      return caches.open(CACHE).then(function(c){try{c.put(e.request,r.clone());}catch(err){}return r;});
    }).catch(function(){ return caches.match(e.request); })
  );
});
