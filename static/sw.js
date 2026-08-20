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

// Bumping this is no longer how a change reaches people — the shell refreshes
// itself, see staleWhileRevalidate below. Change it only to discard everything
// cached under the old name, which is worth doing when the shape of what is
// cached changes rather than its contents.
const VERSION = "setu-v3";
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
  event.respondWith(staleWhileRevalidate(request, event));
});

/*
 * Serve the cached shell immediately, then refresh it in the background.
 *
 * This was cache-first with no revalidation, which meant the shell froze the
 * moment it was cached and stayed frozen until VERSION changed by hand. That
 * is a worse trap than it sounds: bumping the version does not fix it either,
 * because the new cache fills on the next load and then freezes in turn. A
 * whole afternoon of edits can be invisible while every file on disk is
 * correct — which is exactly how this comment came to be written.
 *
 * Stale-while-revalidate keeps the instant open and the offline behaviour, and
 * a change lands on the following load without anyone remembering to bump
 * anything.
 */
async function staleWhileRevalidate(request, event) {
  const cache = await caches.open(VERSION);
  const cached = await cache.match(request);

  const network = fetch(request)
    .then((response) => {
      if (response.ok) cache.put(request, response.clone());
      return response;
    })
    .catch(() => null);

  // Keep the worker alive for the background refresh; returning the cached
  // copy resolves respondWith, and the browser is then free to kill us.
  if (event) event.waitUntil(network);

  if (cached) return cached;

  const response = await network;
  if (response) return response;

  const shell = await cache.match("/");
  if (shell) return shell;
  throw new Error("offline, and this was never cached");
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
