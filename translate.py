"""Spanish edition translations. Each story (cluster id) is translated once: headline + summary in batches of 10
(cheap), plus a Spanish version of the long-form write-up for the most important stories, paced under the AI budget.
Cache: data/translations_es.json {cluster_id: {t, s, h, n, p?, ph?, at}}. Entries for pruned stories are dropped."""
import os, json, re, time, hashlib, unicodedata
from concurrent.futures import ThreadPoolExecutor
import llm
ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, "data", "translations_es.json")
BATCH = 10
MAX_PER_RUN = 400            # headline+summary items per run (initial backfill ~375 stories ≈ $0.15 one-time)
LONG_PER_RUN = 6             # Spanish long-form per run (paced; only important stories)
RETRANSLATE_MAX = 2          # if the English headline/summary changes (new lead report), re-translate at most twice, only while fresh
def h(c): return hashlib.md5((c["title"] + "|" + (c.get("summary") or "")).encode()).hexdigest()[:10]
def slug_es(t):
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", t)).strip("-")[:70].rstrip("-")
# ---------- topic change: the cluster id stayed but the story is a different one (re-clustering / new lead report) ----------
FUNC = set("la el los las un una se ya dos tres cuatro cinco seis the a an new two three four five six avance resultados momentos comienzan funcionario luchadores combate combates evento".split())
def anchors(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    words = re.findall(r"[A-Za-z][A-Za-z'’]+|\d[\d.,]*\d|\d", t)
    out = set()
    for i, w in enumerate(words):
        if w[0].isdigit(): out.add(re.sub(r"[.,]", "", w)); continue
        if w[0].isupper() and w.lower() not in FUNC and (i > 0 or w.isupper() or len(w) > 3): out.add(w.lower())
    return out
def topic_score(a_title, b_title):
    """How strongly two headlines (any language) are about the same story: shared wrestlers count double, plus anchor overlap."""
    import enrich
    pa, pb = enrich.persons(enrich.canon(a_title)), enrich.persons(enrich.canon(b_title))
    a, b = anchors(a_title), anchors(b_title)
    return 2 * len(pa & pb) + (len(a & b) / len(a | b) if a and b else 0)
def changed_topic(es_title, en_title):
    """True if the cached Spanish headline is about a different story than the current English one."""
    import enrich
    pe, pn = enrich.persons(enrich.canon(es_title)), enrich.persons(enrich.canon(en_title))
    if pe & pn: return False
    a, b = anchors(es_title), anchors(en_title)
    if not a or not b: return bool(pe and pn)
    j = len(a & b) / len(a | b)
    return j < 0.2 or (pe and pn and not pe & pn)
def load():
    try: return json.load(open(CACHE))
    except Exception: return {}
def important(c):
    k = (c.get("kind") or {}).get("type")
    return c.get("sources", 1) > 1 or k in ("results", "match") or bool(c.get("hub"))
def run(clusters):
    tr = load(); now = time.time()
    live = {c["id"] for c in clusters}
    tr = {k: v for k, v in tr.items() if k in live}            # same 60-day pruning as the stories
    todo = []; moved = set()
    for c in clusters:
        x = tr.get(c["id"])
        if not x: todo.append(c)
        elif x.get("h") != h(c) and changed_topic(x.get("en") or x["t"], c["title"]):
            todo.append(c); moved.add(c["id"])      # a different story now: always re-translate, new Spanish slug (old one gets a redirect stub)
        elif x.get("h") != h(c) and x.get("n", 1) <= RETRANSLATE_MAX and now - c.get("first_ts", c["ts"]) < 3 * 86400: todo.append(c)
    todo.sort(key=lambda c: c["id"] not in moved)   # topic changes first
    todo = todo[:MAX_PER_RUN]; done = 0; moved_done = []
    if todo and llm.budget_left() > 0.2:
        batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
        def job(b): return b, llm.translate_es([{"id": c["id"], "title": c["title"], "summary": c.get("summary") or ""} for c in b])
        with ThreadPoolExecutor(4) as ex:
            for b, res in ex.map(job, batches):
                for c in b:
                    r = res.get(c["id"])
                    if not r: continue
                    old = tr.get(c["id"], {}); mv = c["id"] in moved
                    tr[c["id"]] = {"t": r["t"], "s": r["s"], "h": h(c), "n": 1 if mv else old.get("n", 0) + 1, "at": int(now), "en": c["title"],
                                   "sl": slug_es(r["t"]) if mv else (old.get("sl") or slug_es(r["t"]))}
                    if mv: moved_done.append(c["id"])
                    if old.get("p") and old.get("ph") == hashlib.md5(json.dumps(c.get("long") or []).encode()).hexdigest()[:10]:
                        tr[c["id"]]["p"], tr[c["id"]]["ph"] = old["p"], old["ph"]
                    done += 1
    # Spanish long-form for important stories (newest first), paced
    lt = [c for c in clusters if c.get("long") and c["id"] in tr and important(c)
          and tr[c["id"]].get("ph") != hashlib.md5(json.dumps(c["long"]).encode()).hexdigest()[:10]
          and now - c.get("first_ts", c["ts"]) < 4 * 86400][:LONG_PER_RUN]
    nl = 0
    if lt and llm.pace_ok():
        with ThreadPoolExecutor(3) as ex:
            for c, p in zip(lt, ex.map(lambda c: llm.translate_es_long(c["long"]), lt)):
                if p: tr[c["id"]]["p"] = p; tr[c["id"]]["ph"] = hashlib.md5(json.dumps(c["long"]).encode()).hexdigest()[:10]; nl += 1
    os.makedirs(os.path.dirname(CACHE), exist_ok=True); json.dump(tr, open(CACHE, "w"), ensure_ascii=False)
    out = {}
    for c in clusters:   # runtime view (not saved): stable URL from the first Spanish slug; long-form only if it matches the current English one
        x = tr.get(c["id"])
        if not x: continue
        ok = x.get("p") and x.get("ph") == hashlib.md5(json.dumps(c.get("long") or []).encode()).hexdigest()[:10]
        out[c["id"]] = {**x, "url": f"es/noticias/{x.get('sl') or slug_es(x['t'])}-{c['id']}.html", "p": x["p"] if ok else None}
    if moved_done: print(f"es: topic changed, new Spanish slug (old URL redirected): {len(moved_done)} {moved_done[:20]}", flush=True)
    print(f"es: translated {done}/{len(todo)}, long {nl}/{len(lt)}, cached {len(tr)}, month spend ${llm._U['usd'] if llm._U else 0:.3f}", flush=True)
    return out
