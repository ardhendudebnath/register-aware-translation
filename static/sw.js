/*
 * Service worker: cache the app shell so Setu opens with zero network.
 *
 * This must be a real file served from the origin root — browsers refuse to
 * register a service worker from an inline blob, and a worker served from
 * /static/ could not claim a scope covering the whole app.
 *
 * Strategy:
 *   app shell   cache-first, because it changes only on deploy
 *   /api/*      network-first with a cache fallback, so a repeated translation
 *               still resolves offline from the last response
 *
 * The register layer itself needs none of this — it is pure client-side string
 * processing and re-levelling a cached phrase never touches the network.
 */

// Bump on any change to the shell files below, or a returning visitor keeps
// the cached copy: the app shell is served cache-first, so new markup and a
// new script are invisible until the cache name changes.
const VERSION = "setu-v2";
const SHELL = [
  "/",
  "/static/style.css",
  "/static/app.js",
  "/manifest.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(VERSION)
      // addAll rejects the whole batch if any single request 404s, which would
      // leave the worker permanently uninstalled. Add them individually.
      .then((cache) => Promise.all(SHELL.map((url) => cache.add(url).catch(() => null))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/api/")) {
    event.respondWith(networkFirst(request));
    return;
  }
  event.respondWith(cacheFirst(request));
});

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(VERSION);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const shell = await caches.match("/");
    if (shell) return shell;
    throw err;
  }
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(VERSION);
      cache.put(request, response.clone());
    }
    return response;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;
    return new Response(
      JSON.stringify({
        error: "offline",
        message: "No connection. Cached phrases still work, and any translation already on screen can be re-levelled.",
      }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    );
  }
}
