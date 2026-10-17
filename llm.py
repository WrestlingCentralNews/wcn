"""xAI Grok rewriting: headline, summary, story type, speaker, promotion. Cached per article; hard monthly budget."""
import os, json, re, time, urllib.request, threading
MODEL = "grok-4.20-0309-non-reasoning"
URL = "https://api.x.ai/v1/chat/completions"
MONTHLY_BUDGET_USD = 9.0     # owner's hard cap for ALL AI spend on the site
SAFETY_USD = 0.40            # hard stop at $8.60 so the cap is never touched
PACE_TARGET_USD = 8.0        # discretionary work (long-form, vision, Spanish long-form) is paced to this monthly total
PACE_BUFFER_USD = 0.35       # allowance ahead of the straight-line pace (absorbs backfills / big show nights)
USAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "llm_usage.json")
CATS = ["WWE", "AEW", "TNA", "Indie", "Global"]
TYPES = ["news", "results", "match", "quote", "opinion", "rumor", "listicle", "off-topic"]
SYS = ("You are the editor of Wrestling Central News. Rewrite a pro-wrestling story in entirely your own words. "
 "Rules: never copy phrases from the source; never invent facts, names, numbers or quotes; no clickbait or questions. "
 "Return JSON: {\"headline\": <=14 words, engaging and accurate>, \"summary\": <2-3 sentences, all key facts, fresh wording>, "
 "\"type\": one of news|results|match|quote|opinion|rumor|listicle|off-topic, \"speaker\": name if type=quote else null, "
 "\"quote\": short exact quote from the text if type=quote else null, \"categories\": subset of [WWE,AEW,TNA,Indie,Global]}. "
 "type guide: results=show/event results or recap; match=a match officially announced; quote=on-record statement by a wrestler/executive/promoter/commentator; "
 "rumor=unconfirmed/speculative/'reportedly could'; opinion=column, grades, predictions, fantasy booking, polls; listicle=ranked or numbered lists; off-topic=not pro wrestling. "
 "Categories: WWE (incl. Raw/SmackDown/NXT), AEW, TNA, Indie (ROH, GCW, MLW, NWA, PWG, US indies), Global (NJPW, Stardom, CMLL, AAA, NOAH, Europe, Australia, etc.). "
 "Tag only promotions the story is about, not ones merely mentioned.")
_lock = threading.Lock()
def _usage():
    m = time.strftime("%Y-%m")
    try: u = json.load(open(USAGE))
    except Exception: u = {}
    if u.get("month") != m: u = {"month": m, "usd": 0.0, "calls": 0}
    if u.get("month") == "2026-10" and not u.get("es_backfill_fix"):   # one-time: first Spanish backfill run (Oct 17) spent $0.19 before usage was saved after build
        u["usd"] += 0.19; u["es_backfill_fix"] = 1
    return u
_U = None
def budget_left():
    global _U
    if _U is None: _U = _usage()
    return MONTHLY_BUDGET_USD - SAFETY_USD - _U["usd"]
def pace_ok(margin=0.0):
    """True while month-to-date spend is under the straight-line pace toward PACE_TARGET_USD (+buffer).
    Discretionary calls check this so spend is spread evenly and the month lands near $8, safely under the $9 cap."""
    import calendar
    budget_left(); t = time.gmtime()
    days = calendar.monthrange(t.tm_year, t.tm_mon)[1]
    frac = (t.tm_mday - 1 + (t.tm_hour * 3600 + t.tm_min * 60) / 86400) / days
    return _U["usd"] + margin < min(PACE_TARGET_USD * frac + PACE_BUFFER_USD, PACE_TARGET_USD)
HDR = lambda key, conv: {"Authorization": "Bearer " + key, "Content-Type": "application/json", "x-grok-conv-id": conv}  # conv id = better prompt-cache hits
def save_usage():
    if _U is not None: json.dump(_U, open(USAGE, "w"))
def rewrite(a):
    key = os.environ.get("AI_API_KEY")
    if not key or budget_left() <= 0: return None
    text = re.sub(r"\s+", " ", (a.get("body") or a.get("summary_src") or ""))[:1100]
    user = f"Source: {a['source']}\nTitle: {a['raw_title']}\nText: {text or '(no text; rely on title only, keep summary to what the title states)'}"
    body = {"model": MODEL, "max_tokens": 260, "temperature": 0.6, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": user}]}
    for attempt in range(2):
        try:
            r = urllib.request.urlopen(urllib.request.Request(URL, data=json.dumps(body).encode(),
                headers=HDR(key, "wcn-rewrite")), timeout=40)
            d = json.load(r)
            cost = d.get("usage", {}).get("cost_in_usd_ticks", 0) / 1e10
            with _lock: _U["usd"] += cost; _U["calls"] += 1
            out = json.loads(d["choices"][0]["message"]["content"])
            if not out.get("headline") or not out.get("summary"): return None
            out["type"] = out.get("type") if out.get("type") in TYPES else "news"
            out["categories"] = [c for c in (out.get("categories") or []) if c in CATS]
            out["model"] = MODEL; out["at"] = int(time.time())
            return out
        except Exception as e:
            err = str(e)[:80]; time.sleep(2)
    print("llm error:", err, flush=True); return None

LONG_SYS = ("You write original articles for Wrestling Central News. From the source text, write 4-6 short paragraphs (2-3 sentences each) "
 "reporting the story entirely in your own words. Facts only: no invented facts, numbers, quotes or names; no speculation, no opinions, "
 "no mention of the source outlet, no calls to action. If the text is thin, write fewer paragraphs (min 2). Return JSON {\"paragraphs\": [..]}.")
def longform(a, headline):
    key = os.environ.get("AI_API_KEY")
    if not key or budget_left() < LONGFORM_RESERVE_USD or not pace_ok(): return None
    text = re.sub(r"\s+", " ", (a.get("body") or a.get("summary_src") or ""))[:2200]
    if len(text) < 200: return None
    body = {"model": MODEL, "max_tokens": 480, "temperature": 0.5, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": LONG_SYS}, {"role": "user", "content": f"Headline: {headline}\nText: {text}"}]}
    try:
        r = urllib.request.urlopen(urllib.request.Request(URL, data=json.dumps(body).encode(),
            headers=HDR(key, "wcn-longform")), timeout=60)
        d = json.load(r)
        with _lock: _U["usd"] += d.get("usage", {}).get("cost_in_usd_ticks", 0) / 1e10; _U["calls"] += 1; _U["long"] = _U.get("long", 0) + 1
        p = [x.strip() for x in json.loads(d["choices"][0]["message"]["content"]).get("paragraphs", []) if isinstance(x, str) and len(x.strip()) > 30]
        return p[:7] or None
    except Exception as e:
        print("llm longform error:", str(e)[:80], flush=True); return None
LONGFORM_RESERVE_USD = 1.0   # keep $1 of the monthly cap for headline/summary rewrites

# ---------- Spanish edition (translation; cached per story by translate.py) ----------
ES_SYS = ("You are a senior editor for the Spanish edition of Wrestling Central News, writing for Latin American and Puerto Rican wrestling fans "
 "(think the voice of Superluchas or ESPN Deportes lucha libre coverage). Rewrite each English item as natural, idiomatic Spanish news copy: "
 "adapt the sentence structure, never translate word for word, and avoid anglicisms that don't exist in Spanish. "
 "Accuracy rules: never add, drop or change facts, names, numbers, dates, results or quotes. "
 "Names: keep ring names, promotion names (WWE, AEW, TNA, NJPW, CMLL, AAA), show names (Raw, SmackDown, NXT, Dynamite, Collision, iMPACT) and "
 "event names (WrestleMania, Crown Jewel, Survivor Series, WrestleDream, Clockwork Carnage...) exactly as in English. "
 "Titles: translate championships the way Spanish-language wrestling media do (Campeonato Mundial Peso Pesado, Campeonato Femenil/Femenino por Parejas, "
 "Campeonato Intercontinental, títulos de tercias/tríos). Keep fan terms used in Spanish: lucha libre, luchador/luchadora, combate/lucha, cartelera, "
 "función, evento, pago por evento (PPV), promo, heel/face (or rudo/técnico), Street Fight, Money in the Bank. Translate legal, medical and business "
 "terms with their proper Spanish equivalents (e.g. assault and battery = agresión y lesiones). "
 "Headlines: natural Spanish news headlines, sentence case, max 14 words, no clickbait, keep the key name first when possible.")
ES_MODEL = MODEL   # chosen after a side-by-side test (see report); cheapest model that reads naturally
def _call(key, conv, system, user, max_tokens, kind, model=None):
    body = {"model": model or ES_MODEL, "max_tokens": max_tokens, "temperature": 0.2, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    r = urllib.request.urlopen(urllib.request.Request(URL, data=json.dumps(body).encode(), headers=HDR(key, conv)), timeout=240)
    d = json.load(r)
    with _lock:
        _U["usd"] += d.get("usage", {}).get("cost_in_usd_ticks", 0) / 1e10; _U["calls"] += 1; _U[kind] = _U.get(kind, 0) + 1
    return json.loads(d["choices"][0]["message"]["content"])
def translate_es(items, model=None):
    """items: [{id, title, summary}] (<=12). Returns {id: {"t": titulo, "s": resumen}}. One call per batch (system prompt amortized)."""
    key = os.environ.get("AI_API_KEY")
    if not key or not items or budget_left() <= 0.2: return {}
    user = ("Translate each item. Return JSON {\"items\": [{\"id\": <same id>, \"titulo\": <Spanish headline>, \"resumen\": <Spanish summary>}]} "
            "with exactly one entry per input id.\n" + json.dumps([{"id": i["id"], "headline": i["title"], "summary": i["summary"]} for i in items], ensure_ascii=False))
    try:
        out = _call(key, "wcn-es", ES_SYS, user, 160 * len(items) + 60, "es", model)
        res = {}
        for x in out.get("items", []):
            if isinstance(x, dict) and x.get("id") and x.get("titulo") and x.get("resumen"):
                res[str(x["id"])] = {"t": str(x["titulo"]).strip(), "s": str(x["resumen"]).strip()}
        return res
    except Exception as ex:
        print("llm es error:", str(ex)[:80], flush=True); return {}
def translate_es_long(paras):
    """Spanish version of a long-form write-up (list of paragraphs). Paced (discretionary)."""
    key = os.environ.get("AI_API_KEY")
    if not key or not paras or budget_left() < LONGFORM_RESERVE_USD or not pace_ok(): return None
    try:
        out = _call(key, "wcn-es-long", ES_SYS, "Translate these paragraphs. Return JSON {\"paragraphs\": [...]} with the same number of paragraphs.\n" + json.dumps(paras, ensure_ascii=False),
                    int(sum(len(p) for p in paras) / 2.6) + 120, "es_long")
        p = [x.strip() for x in out.get("paragraphs", []) if isinstance(x, str) and len(x.strip()) > 30]
        return p if len(p) >= max(1, len(paras) - 1) else None
    except Exception as ex:
        print("llm es long error:", str(ex)[:80], flush=True); return None
