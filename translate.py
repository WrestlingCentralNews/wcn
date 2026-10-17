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
    todo = []
    for c in clusters:
        x = tr.get(c["id"])
        if not x: todo.append(c)
        elif x.get("h") != h(c) and x.get("n", 1) <= RETRANSLATE_MAX and now - c.get("first_ts", c["ts"]) < 3 * 86400: todo.append(c)
    todo = todo[:MAX_PER_RUN]; done = 0
    if todo and llm.budget_left() > 0.2:
        batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
        def job(b): return b, llm.translate_es([{"id": c["id"], "title": c["title"], "summary": c.get("summary") or ""} for c in b])
        with ThreadPoolExecutor(4) as ex:
            for b, res in ex.map(job, batches):
                for c in b:
                    r = res.get(c["id"])
                    if not r: continue
                    old = tr.get(c["id"], {})
                    tr[c["id"]] = {"t": r["t"], "s": r["s"], "h": h(c), "n": old.get("n", 0) + 1, "at": int(now), "sl": old.get("sl") or slug_es(r["t"])}
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
    print(f"es: translated {done}/{len(todo)}, long {nl}/{len(lt)}, cached {len(tr)}, month spend ${llm._U['usd'] if llm._U else 0:.3f}", flush=True)
    return out
