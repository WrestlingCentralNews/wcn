import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { rssItems, fnv1a } from "../src/rss.js";
import { pageLinks } from "../src/pages.js";
import { tier, verdict } from "../src/editorial.js";
import { sourcesForCycle, allSources } from "../src/sources.js";
import { poll, maybeDispatch } from "../src/index.js";

describe("rssItems", () => {
  it("parses RSS 2.0 items", () => {
    const xml = `<?xml version="1.0"?><rss><channel>
      <item><title>Roman Reigns Returns To SmackDown</title>
        <link>https://example.com/a</link><guid>g1</guid>
        <pubDate>Mon, 19 Oct 2026 12:00:00 GMT</pubDate></item>
      <item><title>Opinion: Top 10 Moments</title><link>https://example.com/b</link><guid>g2</guid></item>
    </channel></rss>`;
    const items = rssItems(xml);
    assert.equal(items.length, 2);
    assert.equal(items[0].title, "Roman Reigns Returns To SmackDown");
    assert.equal(items[0].key, "g1");
    assert.ok(items[0].ts > 1e9);
  });

  it("parses Atom entries and source element", () => {
    const xml = `<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Fightful - Big News</title><id>id1</id>
        <link href="https://fightful.com/x"/>
        <source>Fightful</source>
        <updated>2026-10-19T12:00:00Z</updated></entry>
    </feed>`;
    const items = rssItems(xml);
    assert.equal(items.length, 1);
    assert.equal(items[0].src, "Fightful");
    assert.equal(items[0].link, "https://fightful.com/x");
  });

  it("fnv1a is stable", () => {
    assert.equal(fnv1a("hello"), fnv1a("hello"));
    assert.notEqual(fnv1a("hello"), fnv1a("world"));
  });
});

describe("editorial", () => {
  it("tiers trusted sources", () => {
    assert.equal(tier("Fightful"), 1);
    assert.equal(tier("Bleacher Report"), 2);
    assert.equal(tier("Random Blog"), 3);
  });

  it("drops listicles and keeps news", () => {
    assert.equal(verdict("10 Reasons Why Roman Reigns Is The Best"), "listicle");
    assert.equal(verdict("Will CM Punk Win At WrestleMania?"), "question headline (speculative)");
    assert.equal(verdict("AEW Dynamite Results: Hangman Retains"), null);
    assert.equal(verdict("Carmelo Hayes And Kelani Jordan Marry"), null);
  });
});

describe("pageLinks", () => {
  it("extracts WWE.com article links", () => {
    const html = `
      <a href="/article/carmelo-hayes-kelani-jordan-wedding-news">x</a>
      <a href="/videos/something">no</a>
      <a href="https://www.wwe.com/article/another-long-enough-slug-here">y</a>`;
    const ls = pageLinks("WWE.com", html);
    assert.ok(ls.some((l) => l.includes("carmelo-hayes")));
    assert.ok(ls.every((l) => /\/article\//.test(l)));
  });
});

describe("sourcesForCycle", () => {
  it("always includes priority feeds and rotates google", () => {
    const a = sourcesForCycle(0).map((s) => s.name);
    const b = sourcesForCycle(1).map((s) => s.name);
    assert.ok(a.includes("Fightful"));
    assert.ok(b.includes("Fightful"));
    assert.ok(a.includes("Wrestling Observer"));
    // Google buckets differ
    const ag = a.filter((n) => n.startsWith("Google News") || n.startsWith("Official"));
    const bg = b.filter((n) => n.startsWith("Google News") || n.startsWith("Official"));
    assert.ok(ag.length && bg.length);
    assert.notDeepEqual(ag.sort(), bg.sort());
    assert.ok(allSources().length >= 26);
  });
});

describe("poll + maybeDispatch", () => {
  it("baselines then triggers on new trusted item", async () => {
    const bodies = {
      "https://www.fightful.com/rss.xml": `<?xml version="1.0"?><rss><channel>
        <item><title>Old Story Already On Feed</title><link>https://f/1</link><guid>old</guid>
          <pubDate>Mon, 19 Oct 2026 10:00:00 GMT</pubDate></item>
      </channel></rss>`,
    };
    const fetchOne = async (url, meta) => {
      if (!(url in bodies)) return { code: 404, body: null, meta };
      return { code: 200, body: bodies[url], meta: { etag: '"v1"' } };
    };
    const S = { feeds: {}, titles: {}, cycle: 0, pending: [] };
    // Force only Fightful by stubbing cycle sources — poll uses sourcesForCycle;
    // Fightful is always in priority set. First pass = baseline.
    const r1 = await poll(S, fetchOne);
    assert.equal(r1.newItems.length, 0);
    assert.equal(S.feeds.Fightful.baseline, true);

    bodies["https://www.fightful.com/rss.xml"] = `<?xml version="1.0"?><rss><channel>
      <item><title>Old Story Already On Feed</title><link>https://f/1</link><guid>old</guid>
        <pubDate>Mon, 19 Oct 2026 10:00:00 GMT</pubDate></item>
      <item><title>New Signing Confirmed By AEW</title><link>https://f/2</link><guid>new</guid>
        <pubDate>${new Date().toUTCString()}</pubDate></item>
    </channel></rss>`;
    const r2 = await poll(S, fetchOne);
    assert.ok(r2.newItems.some((i) => i.title.includes("New Signing")));
  });

  it("maybeDispatch respects covering run and hourly cap", async () => {
    const now = Math.floor(Date.now() / 1000);
    const S = {
      pending: [{ title: "X", seen_at: now - 30, link: "https://x" }],
    };
    const calls = [];
    const env = {
      GITHUB_TOKEN: "test-token",
      // monkeypatch via module is hard; test the pure decision with a fake by
      // importing and stubbing fetch globally.
    };
    const orig = globalThis.fetch;
    globalThis.fetch = async (url, opts) => {
      calls.push({ url: String(url), method: opts?.method || "GET" });
      if (String(url).includes("/runs?") && !String(url).includes("event=")) {
        return new Response(
          JSON.stringify({
            workflow_runs: [
              {
                id: 99,
                status: "in_progress",
                event: "workflow_dispatch",
                created_at: new Date((now - 10) * 1000).toISOString(),
              },
            ],
          }),
          { status: 200 },
        );
      }
      if (String(url).includes("event=workflow_dispatch")) {
        return new Response(JSON.stringify({ workflow_runs: [] }), { status: 200 });
      }
      return new Response("", { status: 204 });
    };
    try {
      const r = await maybeDispatch(S, env);
      assert.equal(r.reason, "covered");
      assert.equal(S.pending.length, 0);
      assert.ok(!calls.some((c) => c.method === "POST"));
    } finally {
      globalThis.fetch = orig;
    }
  });

  it("dispatches when clear", async () => {
    const now = Math.floor(Date.now() / 1000);
    const S = { pending: [{ title: "Y", seen_at: now - 30, link: "https://y" }] };
    const env = { GITHUB_TOKEN: "test-token" };
    const orig = globalThis.fetch;
    let posted = false;
    globalThis.fetch = async (url, opts) => {
      if (String(url).includes("/dispatches") && opts?.method === "POST") {
        posted = true;
        return new Response(null, { status: 204 });
      }
      return new Response(JSON.stringify({ workflow_runs: [] }), { status: 200 });
    };
    try {
      const r = await maybeDispatch(S, env);
      assert.equal(r.dispatched, true);
      assert.equal(posted, true);
      assert.equal(S.pending.length, 0);
      assert.equal(S.last_trigger.mode, "dispatched");
    } finally {
      globalThis.fetch = orig;
    }
  });
});
