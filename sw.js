/* Mastering Epistemology — offline support.

   Pages, styles and scripts come from the network when there is one (so updates
   show at once) and from the cache when there is not. Images and fonts come from
   the cache first. "Save the whole guide for offline reading" in the reading
   settings sends a message here to fetch everything listed in offline.json.
   Audio is never cached: the files are large and are streamed in ranges. */

const CACHE = "epis-v1";
const BASE = new URL("./", self.location).href;

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET" || req.headers.has("range")) return;
  const url = new URL(req.url);
  if (!url.href.startsWith(BASE) || /\.(mp3|epub)$/i.test(url.pathname)) return;
  if (/\.(jpe?g|png|webp|svg|woff2)$/i.test(url.pathname)) event.respondWith(cacheFirst(req, url));
  else event.respondWith(networkFirst(req));
});

async function networkFirst(req) {
  const cache = await caches.open(CACHE);
  try {
    const res = await fetch(req);
    if (res.ok && res.type === "basic") cache.put(req, res.clone());
    return res;
  } catch (err) {
    const hit = await cache.match(req, { ignoreSearch: true });
    if (hit) return hit;
    if (req.mode === "navigate") {
      return new Response(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">' +
        '<title>Offline</title><body style="font:18px/1.6 Georgia,serif;max-width:32rem;margin:15vh auto;padding:0 20px;color:#1B2730;background:#F6F3EC">' +
        "<h1>You are offline</h1><p>This page hasn't been saved on this device yet. Open the reading settings (Aa) " +
        "and choose <b>Save the whole guide for offline reading</b> next time you are online.</p>" +
        '<p><a href="' + BASE + '">Go to the start page</a></p></body>',
        { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } });
    }
    throw err;
  }
}

async function cacheFirst(req, url) {
  const cache = await caches.open(CACHE);
  const hit = await cache.match(req);
  if (hit) return hit;
  try {
    const res = await fetch(req);
    if (res.ok && res.type === "basic") cache.put(req, res.clone());
    return res;
  } catch (err) {
    // Artwork comes in several widths; offline, any saved width will do.
    const m = url.pathname.match(/^(.*\/assets\/art\/[\w-]+?)(?:-(?:640|1200|2000|thumb))?\.jpg$/);
    if (m) {
      for (const suffix of ["-1200", "-640", "-2000", "-thumb", ""]) {
        const other = await cache.match(url.origin + m[1] + suffix + ".jpg");
        if (other) return other;
      }
    }
    throw err;
  }
}

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "save-offline" && event.ports[0]) event.waitUntil(saveAll(event.ports[0]));
});

async function saveAll(port) {
  try {
    const list = await (await fetch(BASE + "offline.json", { cache: "no-store" })).json();
    const cache = await caches.open(CACHE);
    const queue = list.slice();
    let n = 0;
    const worker = async () => {
      while (queue.length) {
        const path = queue.shift();
        try {
          const res = await fetch(BASE + path, { cache: "no-cache" });
          if (res.ok) await cache.put(BASE + path, res);
        } catch (e) { /* skip this one */ }
        n += 1;
        if (n % 8 === 0 || n === list.length) port.postMessage({ n, of: list.length });
      }
    };
    await Promise.all([worker(), worker(), worker(), worker()]);
    port.postMessage({ done: true });
  } catch (err) {
    port.postMessage({ error: String(err) });
  }
}
