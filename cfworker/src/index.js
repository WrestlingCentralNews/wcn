/**
 * WCN always-on source poller (Cloudflare Worker).
 * Cron every 2 minutes: conditional-GET sources, detect new trusted items, dispatch
 * update.yml when the box watcher may be paused. Coordinates with the box via
 * the GitHub Actions API (active runs + shared 20/hour workflow_dispatch cap).
 */
import { EVERY, sourcesForCycle } from "./sources.js";
import { tier, verdict } from "./editorial.js";
import { rssItems, fnv1a } from "./rss.js";
import { pageLinks } from "./pages.js";
import { activeRuns, recentDispatches, dispatchUpdate } from "./github.js";

const UA =
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36 WCN-cfworker/1.0";
const STATE_KEY = "watcher";
const MAX_PER_HOUR = 20;
const MIN_GAP_S = 60;
const FRESH_H = 6;
const GOOGLE_BACKOFF_S = 15 * 60;
const FETCH_TIMEOUT_MS = 12000;
const MAX_BODY = 2_000_000;
const MAX_PARSE_PER_RUN = 4; // free-plan CPU budget: parse at most this many changed bodies per tick
const SEEN_CAP = 400;

async function loadState(env) {
  const raw = await env.STATE.get(STATE_KEY, "json");
  return raw && typeof raw === "object"
    ? raw
    : { feeds: {}, titles: {}, cycle: 0, pending: [], google_backoff_until: 0 };
}

async function saveState(env, S) {
  await env.STATE.put(STATE_KEY, JSON.stringify(S));
}

function titleId(title) {
  const s = (title || "").toLowerCase().replace(/\W/g, "");
  // md5 not in Workers crypto for sync; use fnv of normalized title (dedup across feeds is best-effort)
  return fnv1a(s).slice(0, 12);
}

async function cget(url, meta) {
  const h = { "User-Agent": UA, Accept: "*/*", "Accept-Encoding": "identity" };
  if (meta?.etag) h["If-None-Match"] = meta.etag;
  if (meta?.lm) h["If-Modified-Since"] = meta.lm;
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), FETCH_TIMEOUT_MS);
  try {
    const r = await fetch(url, { headers: h, signal: ac.signal, redirect: "follow" });
    if (r.status === 304) return { code: 304, body: null, meta };
    if (!r.ok) return { code: r.status, body: null, meta };
    const buf = await r.arrayBuffer();
    const slice = buf.byteLength > MAX_BODY ? buf.slice(0, MAX_BODY) : buf;
    const body = new TextDecoder("utf-8", { fatal: false }).decode(slice);
    const next = {};
    const et = r.headers.get("ETag");
    const lm = r.headers.get("Last-Modified");
    if (et) next.etag = et;
    if (lm) next.lm = lm;
    return { code: 200, body, meta: next };
  } catch {
    return { code: 0, body: null, meta };
  } finally {
    clearTimeout(t);
  }
}

function pruneSeen(seen, now) {
  const entries = Object.entries(seen || {});
  if (entries.length <= SEEN_CAP) return seen || {};
  entries.sort((a, b) => b[1] - a[1]);
  return Object.fromEntries(entries.slice(0, SEEN_CAP));
}

function pruneTitles(T, now) {
  const entries = Object.entries(T || {});
  if (entries.length <= 4000) return T || {};
  entries.sort((a, b) => b[1] - a[1]);
  return Object.fromEntries(entries.slice(0, 3000));
}

/** Core poll: returns { newItems, dirty, stats }. Mutates S. */
export async function poll(S, fetchOne = cget) {
  const now = Math.floor(Date.now() / 1000);
  const cycle = S.cycle || 0;
  const srcs = sourcesForCycle(cycle).filter((s) => {
    if (EVERY[s.name] && cycle % EVERY[s.name]) return false;
    if (s.url.includes("news.google.com") && now < (S.google_backoff_until || 0)) return false;
    return true;
  });

  const F = S.feeds || (S.feeds = {});
  const T = S.titles || (S.titles = {});
  const stats = { "200": 0, "304": 0, err: 0, parsed: 0, skipped_cpu: 0 };
  const newItems = [];
  let dirty = false;
  let parseLeft = MAX_PARSE_PER_RUN;

  const results = await Promise.all(
    srcs.map(async (s) => {
      const m = F[s.name]?.meta || {};
      const res = await fetchOne(s.url, m);
      return { s, ...res };
    }),
  );

  for (const { s, code, body, meta } of results) {
    const f = F[s.name] || (F[s.name] = { seen: {}, baseline: false });
    if (code === 304) {
      stats["304"]++;
      continue;
    }
    if (code !== 200 || !body) {
      stats.err++;
      f.last_code = code;
      dirty = true;
      if (s.url.includes("news.google.com") && (code === 429 || code === 503)) {
        S.google_backoff_until = now + GOOGLE_BACKOFF_S;
      }
      continue;
    }
    stats["200"]++;
    const hash = fnv1a(body);
    const metaChanged =
      (meta?.etag && meta.etag !== f.meta?.etag) ||
      (meta?.lm && meta.lm !== f.meta?.lm) ||
      hash !== f.hash;
    f.meta = meta || {};
    f.last_code = 200;
    if (!metaChanged && f.baseline) {
      // identical body; nothing to do
      continue;
    }
    if (parseLeft <= 0) {
      // Defer parsing to a later cycle; drop validators so we re-fetch.
      f.meta = {};
      f.hash = null;
      stats.skipped_cpu++;
      dirty = true;
      continue;
    }
    parseLeft--;
    stats.parsed++;
    f.hash = hash;
    dirty = true;

    let items;
    try {
      if (s.kind === "rss") items = rssItems(body);
      else
        items = pageLinks(s.name, body).map((l) => ({
          key: l,
          title: l.split("/").filter(Boolean).pop() || l,
          link: l,
          src: null,
          ts: null,
        }));
    } catch {
      continue;
    }

    const fresh = items.filter((i) => i.key && !(i.key in (f.seen || {})));
    for (const i of items) {
      if (i.key) f.seen[i.key] = now;
    }
    f.seen = pruneSeen(f.seen, now);

    if (!f.baseline) {
      f.baseline = true;
      continue;
    }

    for (const i of fresh) {
      const tid = titleId(i.title);
      if (s.kind === "rss" && T[tid]) continue; // already seen via another feed
      if (s.kind === "rss") T[tid] = now;
      const src = i.src || s.name;
      if (tier(src) > 2) continue;
      if (i.ts && i.ts < now - FRESH_H * 3600) continue;
      const why = s.kind === "rss" ? verdict(i.title) : null;
      if (why) continue;
      newItems.push({
        feed: s.name,
        source: src,
        title: (i.title || "").slice(0, 140),
        link: i.link || "",
        ts: i.ts,
        seen_at: now,
      });
    }
  }

  S.titles = pruneTitles(T, now);
  S.cycle = cycle + 1;
  S.last_run = new Date().toISOString();
  S.last_poll_stats = stats;
  return { newItems, dirty: dirty || newItems.length > 0, stats };
}

/** Decide whether to workflow_dispatch. Mutates S. Uses GitHub as shared coordinator. */
export async function maybeDispatch(S, env) {
  const P = S.pending || (S.pending = []);
  if (!P.length) return { dispatched: false, reason: "empty" };
  const token = env.GITHUB_TOKEN;
  if (!token) return { dispatched: false, reason: "no_token" };

  const now = Math.floor(Date.now() / 1000);
  let act, recent;
  try {
    [act, recent] = await Promise.all([activeRuns(token), recentDispatches(token, 3600)]);
  } catch (e) {
    return { dispatched: false, reason: "gh_error:" + String(e.message || e).slice(0, 80) };
  }

  const oldest = Math.min(...P.map((p) => p.seen_at));
  const covering = act.filter((r) => r.created >= oldest - 5);
  if (covering.length) {
    S.pending = [];
    S.last_trigger = {
      at: new Date().toISOString(),
      n: P.length,
      mode: "covered",
      run: covering[0].id,
      titles: P.map((p) => p.title).slice(0, 5),
    };
    return { dispatched: false, reason: "covered", run: covering[0].id };
  }
  const queued = act.filter((r) => r.status !== "in_progress");
  if (queued.length) return { dispatched: false, reason: "already_queued" };
  if (recent.length >= MAX_PER_HOUR) return { dispatched: false, reason: "hourly_cap" };
  if (recent.length) {
    const latest = Math.max(...recent.map((r) => r.created));
    if (now - latest < MIN_GAP_S) return { dispatched: false, reason: "min_gap" };
  }

  try {
    await dispatchUpdate(token);
  } catch (e) {
    return { dispatched: false, reason: "dispatch_fail:" + String(e.message || e).slice(0, 80) };
  }

  S.last_trigger = {
    at: new Date().toISOString(),
    n: P.length,
    mode: "dispatched",
    titles: P.map((p) => p.title).slice(0, 5),
  };
  S.pending = [];
  return { dispatched: true, reason: "ok", n: P.length };
}

async function runOnce(env) {
  const S = await loadState(env);
  const beforePending = (S.pending || []).length;
  const { newItems, dirty: pollDirty, stats } = await poll(S);
  if (newItems.length) {
    S.pending = (S.pending || []).concat(newItems);
  }
  let dispatchResult = { dispatched: false, reason: "skipped" };
  let dispatchDirty = false;
  if ((S.pending || []).length) {
    dispatchResult = await maybeDispatch(S, env);
    dispatchDirty = true; // pending cleared or last_trigger set
  }
  // Always refresh last_run on a successful cycle; only KV-put when something changed
  // or we have never written (so /health works after first run).
  const mustWrite =
    pollDirty ||
    dispatchDirty ||
    newItems.length ||
    beforePending !== (S.pending || []).length ||
    !S._written;
  S._written = true;
  if (mustWrite) await saveState(env, S);
  else {
    // still persist last_run occasionally: at most once per 30 min via a cheap touch flag
    const lastTouch = S._touch_at || 0;
    const now = Math.floor(Date.now() / 1000);
    if (now - lastTouch > 1800) {
      S._touch_at = now;
      S.last_run = new Date().toISOString();
      await saveState(env, S);
    }
  }
  return { stats, newItems: newItems.length, dispatch: dispatchResult, wrote: mustWrite };
}

function healthPayload(S) {
  return {
    ok: true,
    service: "wcn-watcher",
    last_run: S?.last_run || null,
    last_trigger: S?.last_trigger || null,
    cycle: S?.cycle || 0,
    pending: (S?.pending || []).length,
    last_poll_stats: S?.last_poll_stats || null,
    feeds_tracked: Object.keys(S?.feeds || {}).length,
  };
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(
      runOnce(env).catch((e) => {
        console.error("scheduled error", String(e).slice(0, 200));
      }),
    );
  },

  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/health" || url.pathname === "/") {
      let S = null;
      try {
        S = await loadState(env);
      } catch {
        S = {};
      }
      return new Response(JSON.stringify(healthPayload(S), null, 2), {
        headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
      });
    }
    if (url.pathname === "/run" && request.method === "POST") {
      // Manual kick (no auth beyond knowing the workers.dev URL; harmless: same as cron).
      const result = await runOnce(env);
      return new Response(JSON.stringify(result, null, 2), {
        headers: { "content-type": "application/json; charset=utf-8" },
      });
    }
    return new Response("WCN watcher\n", { status: 404 });
  },
};
