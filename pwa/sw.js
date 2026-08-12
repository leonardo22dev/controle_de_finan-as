/* Service worker: guarda o app em cache para funcionar offline.
   Os DADOS não passam por aqui — ficam no localStorage do aparelho. */

/* IMPORTANTE: suba esta versão a cada alteração em HTML/CSS/JS.
   A estratégia é cache-first, então sem trocar o nome do cache o aparelho
   continua servindo os arquivos antigos indefinidamente. O activate abaixo
   apaga os caches de versões anteriores. */
const CACHE = 'gastos-v2';

const ARQUIVOS = [
  './',
  './index.html',
  './styles.css',
  './parser.js',
  './app.js',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE)
      // addAll é tudo-ou-nada: um 404 aborta a instalação inteira.
      .then((c) => Promise.allSettled(ARQUIVOS.map((a) => c.add(a))))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((nomes) => Promise.all(
        nomes.filter((n) => n !== CACHE).map((n) => caches.delete(n)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;

  // Cache primeiro: o app é estático e precisa abrir sem rede.
  e.respondWith(
    caches.match(e.request).then((resposta) => {
      if (resposta) return resposta;
      return fetch(e.request)
        .then((r) => {
          if (r.ok && new URL(e.request.url).origin === location.origin) {
            const copia = r.clone();
            caches.open(CACHE).then((c) => c.put(e.request, copia));
          }
          return r;
        })
        .catch(() => caches.match('./index.html'));
    }),
  );
});
