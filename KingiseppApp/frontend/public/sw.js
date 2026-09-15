const CACHE = "kingisepp-shell-v5";
const SHELL = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./brand/header-banner.png",
  "./brand/logo-banner.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))).then(() =>
      self.clients.claim(),
    ),
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/")) {
    return;
  }
  if (event.request.method !== "GET") {
    return;
  }
  // Network-first: иначе после сборки остаётся старый JS/CSS и «ломаются» формы
  event.respondWith(
    fetch(event.request)
      .then((res) => {
        // Добавляем security headers в ответ SW
        const headers = new Headers(res.headers);
        headers.set("X-Content-Type-Options", "nosniff");
        headers.set("X-Frame-Options", "DENY");
        headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
        const enhancedRes = new Response(res.body, {
          status: res.status,
          statusText: res.statusText,
          headers,
        });
        const copy = enhancedRes.clone();
        caches.open(CACHE).then((c) => c.put(event.request, copy));
        return enhancedRes;
      })
      .catch(() => caches.match(event.request)),
  );
});
