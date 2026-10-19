/** Snapshot of aggregator.FEEDS + pagesrc.LISTINGS (keep in sync when those change). */
const G = (q) =>
  "https://news.google.com/rss/search?q=" + encodeURIComponent(q) + "&hl=en-US&gl=US&ceid=US:en";

/** Direct RSS feeds the site's aggregator reads. */
export const FEEDS = {
  "Wrestling Inc": "https://www.wrestlinginc.com/feed/",
  Fightful: "https://www.fightful.com/rss.xml",
  "Google News: PWInsider": G("site:pwinsider.com"),
  "Cageside Seats": "https://www.cagesideseats.com/rss/index.xml",
  "POST Wrestling": "https://www.postwrestling.com/feed/",
  "Wrestling Observer": "https://www.f4wonline.com/feed",
  "Ringside News": "https://www.ringsidenews.com/feed/",
  "Sportskeeda Wrestling": "https://www.sportskeeda.com/feed/wwe",
  "Google News: WWE": G("WWE wrestling"),
  "Google News: AEW": G("AEW wrestling"),
  "Google News: TNA": G("TNA wrestling"),
  "Google News: Indie": G('GCW OR PWG OR MLW OR "Ring of Honor" wrestling'),
  "Official: WWE.com": G("site:wwe.com when:7d"),
  "Official: AEW": G("site:allelitewrestling.com when:7d"),
  "Official: TNA": G("site:tnawrestling.com when:7d"),
  "Official: NJPW": G("site:njpw1972.com when:7d"),
  "PWInsider (via Google)": G("site:pwinsider.com when:7d"),
  "Google News: Global": G('NJPW OR Stardom OR CMLL OR "Lucha Libre AAA" OR wXw OR RevPro wrestling'),
  AEW: "https://www.allelitewrestling.com/blog-feed.xml",
  MLW: "https://mlw.com/feed/",
  "Google News: AAA": G('"Lucha Libre AAA" OR "AAA Worldwide" when:7d'),
};

/** No-RSS news listing pages (pagesrc.LISTINGS). value: [url, pathRegex, slugOkRegex|null] */
export const LISTINGS = {
  PWInsider: ["https://www.pwinsider.com/", /\/article\/\d+\/[a-z0-9-]+\.html/, null],
  "WWE.com": ["https://www.wwe.com/news", /\/article\/[a-z0-9-]{12,}/, null],
  "TNA Wrestling": ["https://tnawrestling.com/news/", /\/news\/[a-z0-9-]{12,}/, null],
  STARDOM: ["https://wwr-stardom.com/en/news/", /\/en\/news\/\d{6,8}[a-z0-9-]*\//, null],
  "Bleacher Report": [
    "https://bleacherreport.com/wrestling",
    /\/articles\/\d+-[a-z0-9-]+/,
    /wwe|aew|tna|nxt|\braw\b|-raw-|smackdown|wrestlemania|summerslam|royal-rumble|survivor-series|crown-jewel|wrestledream|full-gear|all-in|dynamite|collision|njpw|-roh-|stardom|aaa|cmll|pro-wrestling|wrestling-/,
  ],
};

/** Heavy pages: only every Nth cycle (matches box watcher EVERY). */
export const EVERY = { "Bleacher Report": 3 };

/** All (name, url, kind) tuples. */
export function allSources() {
  const out = [];
  for (const [n, u] of Object.entries(FEEDS)) out.push({ name: n, url: u, kind: "rss" });
  for (const [n, v] of Object.entries(LISTINGS)) out.push({ name: n, url: v[0], kind: "page" });
  return out;
}

/**
 * Free-plan CPU is 10ms. Rotate Google News / heavy sources across cycles so a
 * burst of 200s never parses every body in one invocation. Priority (direct
 * tier-1 RSS + listing pages) is checked every cycle.
 */
export function sourcesForCycle(cycle) {
  const all = allSources();
  const priority = [];
  const rotate = [];
  for (const s of all) {
    if (s.url.includes("news.google.com") || s.name === "Bleacher Report" || s.name === "Ringside News" || s.name === "Sportskeeda Wrestling") {
      rotate.push(s);
    } else {
      priority.push(s);
    }
  }
  // Two rotate buckets: even cycles get bucket 0, odd get bucket 1.
  const bucket = cycle % 2;
  const half = rotate.filter((_, i) => i % 2 === bucket);
  return priority.concat(half);
}
