import { LISTINGS } from "./sources.js";

function absUrl(base, href) {
  try {
    return new URL(href, base).href.split("?")[0];
  } catch {
    return null;
  }
}

function hostTail(u) {
  try {
    return new URL(u).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

/** Extract article links from a listing page HTML (pagesrc.links). */
export function pageLinks(name, html) {
  const entry = LISTINGS[name];
  if (!entry) return [];
  const [base, rx, slugOk] = entry;
  const baseHost = hostTail(base);
  const out = [];
  const seen = new Set();
  const re = /href="([^"#]+)"/gi;
  let m;
  while ((m = re.exec(html))) {
    const l = absUrl(base, m[1].replace(/&amp;/g, "&"));
    if (!l) continue;
    let path;
    try {
      path = new URL(l).pathname;
    } catch {
      continue;
    }
    if (!rx.test(path)) continue;
    if (!hostTail(l).endsWith(baseHost)) continue;
    if (slugOk) {
      const slug = l.split("/").pop() || "";
      if (!slugOk.test(slug) && !slugOk.test(l)) continue;
    }
    if (seen.has(l)) continue;
    seen.add(l);
    out.push(l);
  }
  return out;
}
