"""xAI Grok rewriting: headline, summary, story type, speaker, promotion. Cached per article; hard monthly budget."""
import os, json, re, time, urllib.request, threading
MODEL = "grok-4.20-0309-non-reasoning"
URL = "https://api.x.ai/v1/chat/completions"
MONTHLY_BUDGET_USD = 20.0    # owner's hard cap for ALL AI spend on the site (raised from $9 on 2026-10-25 for longer write-ups)
SAFETY_USD = 0.80            # hard stop at $19.20 so the cap is never touched (same ~4% margin as the old $8.60/$9)
PACE_TARGET_USD = 18.5       # discretionary work (long-form, vision, Spanish long-form) is paced to this monthly total
PACE_BUFFER_USD = 0.80       # allowance ahead of the straight-line pace (absorbs big show nights)
DAILY_MAX_USD = 1.20         # discretionary work stops for the UTC day once the day's total AI spend reaches this (~2x the
                             # straight-line day rate): back-fills spread over days instead of one spike when the line has room
# Throttle order (owner rule 2026-10-25): when the budget is tight, Indie/Global work is cut first, WWE/AEW/TNA last.
# prio 0 = WWE/AEW/TNA new stories + huge news anywhere (title change, death, major signing/release, multi-outlet coverage)
# prio 1 = WWE/AEW/TNA back-fill (older live stories)   prio 2 = Indie/Global new   prio 3 = Indie/Global back-fill
# Each level needs this much room under the monthly pace line (USD) and may use this share of DAILY_MAX_USD:
PRIO_HEADROOM = (0.0, 0.40, 0.80, 1.20)
PRIO_DAY_SHARE = (1.0, 0.60, 0.50, 0.40)
USAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "llm_usage.json")
CATS = ["WWE", "AEW", "TNA", "Indie", "Global"]
TYPES = ["news", "results", "match", "quote", "opinion", "rumor", "listicle", "evergreen", "off-topic"]
SYS = ("You are the editor of Wrestling Central News. Rewrite a pro-wrestling story in entirely your own words. "
 "Rules: never copy phrases from the source; never invent facts, names, numbers or quotes; no clickbait or questions. "
 "Never swap a family member for the famous relative: 'Steve Borden'/'Steven Borden' is Sting's SON, not Sting; a 'Jr.', 'son of X' or 'daughter of X' is never X. Use the name the source uses. "
 "Never upgrade wording: 'appears', 'appearance', 'shows up' or 'is at' is NOT a debut; a 'title match/bout' is NOT a title change. "
 "Keep who chose/signed with which promotion exactly as the source says; never flip 'chose WWE over AEW'. "
 "An interview where someone recalls or explains a past event is not new news: keep the attribution ('X Recalls/Reveals/Says ...') or a time anchor ('in 2024', 'years ago'); never state the past move as if it just happened. "
 "Only say someone debuted, returned, won/lost/vacated a title, or was released/fired if the source title or text states exactly that; otherwise keep the source's own verb. "
 "If the text says the information comes from Fightful Select, credit it as \"per Fightful Select\" (likewise name the Wrestling Observer or PWInsider when it is their report). "
 "Return JSON: {\"headline\": <=14 words, engaging and accurate>, \"summary\": <2-3 sentences, all key facts, fresh wording>, "
 "\"type\": one of news|results|match|quote|opinion|rumor|listicle|evergreen|off-topic, \"speaker\": name if type=quote else null, "
 "\"quote\": short exact quote from the text if type=quote else null, \"categories\": subset of [WWE,AEW,TNA,Indie,Global]}. "
 "type guide: results=show/event results or recap; match=a match officially announced; quote=on-record statement by a wrestler/executive/promoter/commentator; "
 "rumor=unconfirmed/speculative/'reportedly could'; opinion=column, grades, predictions, fantasy booking, polls; listicle=ranked or numbered lists; evergreen=explainer, guide, history, 'what is'/'who is', how something works, look back, flashback, anniversary or 'on this day' piece that reports no new event (a news story with a background paragraph is still news); off-topic=not pro wrestling. "
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
def _today(): return time.strftime("%Y-%m-%d", time.gmtime())
def day_spend():
    budget_left()
    return _U.get("day_usd", 0.0) if _U.get("day") == _today() else 0.0
def add_cost(cost, kind=None):
    """Book one API call (caller holds _lock or is single-threaded): month total, per-kind call count and cost, UTC-day total."""
    budget_left()
    _U["usd"] += cost; _U["calls"] += 1
    if kind:
        _U[kind] = _U.get(kind, 0) + 1
        k = "usd_by_kind"; _U.setdefault(k, {}); _U[k][kind] = round(_U[k].get(kind, 0.0) + cost, 6)
    d = _today()
    if _U.get("day") != d: _U["day"] = d; _U["day_usd"] = 0.0
    _U["day_usd"] += cost
def pace_line():
    """Straight-line month-to-date allowance toward PACE_TARGET_USD (+buffer)."""
    import calendar
    t = time.gmtime(); days = calendar.monthrange(t.tm_year, t.tm_mon)[1]
    frac = (t.tm_mday - 1 + (t.tm_hour * 3600 + t.tm_min * 60) / 86400) / days
    return min(PACE_TARGET_USD * frac + PACE_BUFFER_USD, PACE_TARGET_USD)
def pace_ok(margin=0.0, prio=0):
    """True while discretionary work at this priority may run: month-to-date spend is under the straight-line pace toward
    PACE_TARGET_USD (minus the level's headroom), today's spend is under its share of DAILY_MAX_USD, and the hard stop is far.
    Lower priorities (Indie/Global, back-fill) stop first, so WWE/AEW/TNA and huge news keep their write-ups longest."""
    budget_left()
    p = max(0, min(int(prio or 0), len(PRIO_HEADROOM) - 1))
    if budget_left() < LONGFORM_RESERVE_USD: return False
    if _U["usd"] + margin >= pace_line() - PRIO_HEADROOM[p]: return False
    return day_spend() + margin < DAILY_MAX_USD * PRIO_DAY_SHARE[p]
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
            with _lock: add_cost(cost, "rewrite")
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
def longform(a, headline, prio=0):
    key = os.environ.get("AI_API_KEY")
    if not key or budget_left() < LONGFORM_RESERVE_USD or not pace_ok(prio=prio): return None
    text = re.sub(r"\s+", " ", (a.get("body") or a.get("summary_src") or ""))[:2200]
    if len(text) < 200: return None
    body = {"model": MODEL, "max_tokens": 480, "temperature": 0.5, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": LONG_SYS}, {"role": "user", "content": f"Headline: {headline}\nText: {text}"}]}
    try:
        r = urllib.request.urlopen(urllib.request.Request(URL, data=json.dumps(body).encode(),
            headers=HDR(key, "wcn-longform")), timeout=60)
        d = json.load(r)
        with _lock: add_cost(d.get("usage", {}).get("cost_in_usd_ticks", 0) / 1e10, "long")
        p = [x.strip() for x in json.loads(d["choices"][0]["message"]["content"]).get("paragraphs", []) if isinstance(x, str) and len(x.strip()) > 30]
        return p[:7] or None
    except Exception as e:
        print("llm longform error:", str(e)[:80], flush=True); return None
LONGFORM_RESERVE_USD = 1.0   # keep $1 of the monthly cap for headline/summary rewrites

# ---------- longer write-up (owner 2026-10-25, AdSense 'low value content'): built from ALL trusted reports of the story ----------
LONG2_SYS = ("You write original news articles for Wrestling Central News. You get one or more source reports about ONE story. "
 "Write a 250-400 word article in 4-7 paragraphs of 2-3 sentences each, but ONLY if the reports contain that many distinct facts: "
 "every sentence must state a fact found in the reports (who, what, when, where, the card, results, what was said, what happens next). "
 "If the reports are thin, write fewer paragraphs (minimum 2) - never pad. "
 "Original wording is mandatory: paraphrase everything, restructure the order, never reuse a sentence or any run of 6+ words from the reports. "
 "Direct quotes: at most 2, each under 25 words, copied exactly inside quotation marks; report everything else that was said in indirect speech in your own words. "
 "Forbidden: background or explainer paragraphs the reports do not give, career summaries, filler ('fans will be watching', 'it remains to be seen'), "
 "speculation or predictions ('likely', 'expected to', 'could'), opinions, calls to action, mentioning the outlets or interviewers' outlets. "
 "Never invent facts, names, numbers, dates or quotes. Stick to the wrestlers and promotion of the headline: ignore other news items in the reports (roundups, related links). "
 "Never swap a family member for the famous relative, never upgrade 'appearance' to 'debut' or a title match to a title change, keep who signed with which promotion exactly as reported. "
 "Return JSON {\"paragraphs\": [..]}.")
_QUOTE = re.compile(r"[\"“]([^\"”]{3,})[\"”]")
_NUM = re.compile(r"\d[\d,.:]*\d|\d")
_FILLER = re.compile(r"(?i)\b(?:likely|it remains to be seen|only time will tell|time will tell|fans will (?:be|have)|stay tuned|be sure to|don't miss|"
                     r"expected to|could (?:see|be|lead)|might|perhaps|undoubtedly|without a doubt|in conclusion|overall,)\b")
SHINGLE = 10             # a sentence sharing 10 consecutive words with a report (outside quotes) is copied wording: dropped
                         # (7 caught harmless runs of names/titles like "for the WWE Women's Tag Team Titles")
def _norm(t): return re.sub(r"[^a-z0-9]+", " ", (t or "").lower().replace("’", "'").replace("'", "")).strip()
def _grams(t, n=SHINGLE):
    w = _norm(t).split(); return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}
def grounded(paras, src):
    """No-AI guard on a write-up: drop sentences that quote words not in the reports, state a number the reports don't have,
    copy a run of SHINGLE+ words from the reports outside quotation marks, or are filler/speculation."""
    ns = " " + _norm(src) + " "; nums = {re.sub(r"[,.:]", "", n) for n in _NUM.findall(src or "")}; sg = _grams(src)
    out = []; tot = drop = 0
    for p in paras:
        keep = []
        for s in re.split(r"(?<=[.!?”\"])\s+(?=[A-Z“\"])", p):
            qs = _QUOTE.findall(s)
            if any(_norm(q) and " " + _norm(q) + " " not in ns for q in qs): continue
            if any(re.sub(r"[,.:]", "", n) not in nums for n in _NUM.findall(s)): continue
            if _FILLER.search(_QUOTE.sub(" ", s)): continue
            if _grams(_QUOTE.sub(" | ", s)) & sg: continue
            keep.append(s)
        tot += len(re.split(r"(?<=[.!?\u201d\"])\s+(?=[A-Z\u201c\"])", p)); drop += len(re.split(r"(?<=[.!?\u201d\"])\s+(?=[A-Z\u201c\"])", p)) - len(keep)
        if not out and not keep: return []      # the opening sentence/paragraph failed: the rest would read out of context
        if not out and keep[0] != re.split(r"(?<=[.!?”\"])\s+(?=[A-Z“\"])", p)[0]: return []
        p2 = " ".join(keep).strip()
        if len(p2.split()) >= 8: out.append(p2)
    if tot and drop > tot * 0.25: return []    # too much had to be cut: not trustworthy, keep the story as it was
    return out
def regroup(paras, min_words=40, max_words=90):
    """Join one-sentence paragraphs into readable 2-3 sentence paragraphs (text unchanged)."""
    out = []
    for p in paras or []:
        if out and len(out[-1].split()) < min_words and len(out[-1].split()) + len(p.split()) <= max_words: out[-1] += " " + p
        else: out.append(p)
    if len(out) > 1 and len(out[-1].split()) < 20 and len(out[-2].split()) + len(out[-1].split()) <= max_words + 20:
        out[-2] += " " + out.pop()
    return out
def longform2(headline, reports, prio=0):
    """reports = [source text, ...] (lead first, same story only). -> paragraphs or None. Paced at the given throttle priority."""
    key = os.environ.get("AI_API_KEY")
    if not key or not pace_ok(prio=prio): return None
    parts = []; total = 0
    for i, t in enumerate(reports):
        t = re.sub(r"\s+", " ", t or "")[:2400 if i == 0 else 1500]
        if total + len(t) > 5200: t = t[:max(0, 5200 - total)]
        if len(t) >= 150: parts.append(f"Report {len(parts) + 1}: {t}"); total += len(t)
    if total < 300: return None   # not enough facts for any write-up: keep the summary
    body = {"model": MODEL, "max_tokens": 900, "temperature": 0.6, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": LONG2_SYS}, {"role": "user", "content": f"Headline: {headline}\n" + "\n\n".join(parts)}]}
    try:
        r = urllib.request.urlopen(urllib.request.Request(URL, data=json.dumps(body).encode(), headers=HDR(key, "wcn-long2")), timeout=90)
        d = json.load(r)
        with _lock: add_cost(d.get("usage", {}).get("cost_in_usd_ticks", 0) / 1e10, "long2")
        p = [x.strip() for x in json.loads(d["choices"][0]["message"]["content"]).get("paragraphs", []) if isinstance(x, str) and len(x.strip()) > 30]
        return regroup(grounded(p[:12], " ".join(reports) + " " + headline)) or None
    except Exception as e:
        print("llm long2 error:", str(e)[:80], flush=True); return None

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
        add_cost(d.get("usage", {}).get("cost_in_usd_ticks", 0) / 1e10, kind)
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
def translate_es_long(paras, prio=0):
    """Spanish version of a long-form write-up (list of paragraphs). Paced (discretionary)."""
    key = os.environ.get("AI_API_KEY")
    if not key or not paras or budget_left() < LONGFORM_RESERVE_USD or not pace_ok(prio=prio): return None
    try:
        out = _call(key, "wcn-es-long", ES_SYS, "Translate these paragraphs. Return JSON {\"paragraphs\": [...]} with the same number of paragraphs.\n" + json.dumps(paras, ensure_ascii=False),
                    int(sum(len(p) for p in paras) / 2.6) + 120, "es_long")
        p = [x.strip() for x in out.get("paragraphs", []) if isinstance(x, str) and len(x.strip()) > 30]
        return p if len(p) >= max(1, len(paras) - 1) else None
    except Exception as ex:
        print("llm es long error:", str(ex)[:80], flush=True); return None
