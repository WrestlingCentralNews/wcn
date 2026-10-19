/** Lightweight RSS/Atom item extractor (regex; keeps free-plan CPU under 10ms). */

function decodeEntities(s) {
  return (s || "")
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&apos;/g, "'")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(+n))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCharCode(parseInt(n, 16)));
}

function stripTags(s) {
  return decodeEntities(s).replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
}

function tag(block, name) {
  const m =
    block.match(new RegExp(`<${name}(?:\\s[^>]*)?>([\\s\\S]*?)</${name}>`, "i")) ||
    block.match(new RegExp(`<${name}(?:\\s[^>]*)?/>`, "i"));
  return m ? m[1] ?? "" : "";
}

function linkOf(block) {
  const plain = tag(block, "link");
  if (plain && !/^\s*</.test(plain) && plain.trim()) return stripTags(plain);
  // Atom: <link href="..."/>
  const m = block.match(/<link\b[^>]*\bhref=["']([^"']+)["']/i);
  return m ? m[1].trim() : "";
}

function tsOf(d) {
  if (!d) return null;
  const t = Date.parse(d.trim());
  return Number.isFinite(t) ? t / 1000 : null;
}

/** Parse RSS <item> / Atom <entry> list. Caps at maxItems for CPU. */
export function rssItems(body, maxItems = 40) {
  const text = typeof body === "string" ? body : new TextDecoder().decode(body);
  const out = [];
  const isAtom = /<feed[\s>]/i.test(text) && !/<rss[\s>]/i.test(text);
  const parts = isAtom
    ? text.split(/<entry[\s>]/i).slice(1)
    : text.split(/<item[\s>]/i).slice(1);
  for (const raw of parts) {
    if (out.length >= maxItems) break;
    const end = isAtom ? raw.indexOf("</entry>") : raw.indexOf("</item>");
    const block = end >= 0 ? raw.slice(0, end) : raw.slice(0, 4000);
    const title = stripTags(tag(block, "title"));
    const link = linkOf(block);
    const guid = stripTags(tag(block, isAtom ? "id" : "guid")) || link || title;
    const srcRaw = tag(block, "source");
    const src = srcRaw ? stripTags(srcRaw) : null;
    const pub =
      tag(block, "pubDate") || tag(block, "updated") || tag(block, "published") || "";
    let cleanTitle = title;
    if (src) cleanTitle = title.replace(/\s+-\s+[^-]+$/, "");
    out.push({
      key: guid,
      title: cleanTitle,
      link,
      src,
      ts: tsOf(stripTags(pub)),
    });
  }
  return out;
}

/** Fast FNV-1a 32-bit hex of a string (content change detector). */
export function fnv1a(str) {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16).padStart(8, "0");
}
