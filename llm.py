"""xAI Grok rewriting: headline, summary, story type, speaker, promotion. Cached per article; hard monthly budget."""
import os, json, re, time, urllib.request, threading
MODEL = "grok-4.20-0309-non-reasoning"
URL = "https://api.x.ai/v1/chat/completions"
MONTHLY_BUDGET_USD = 9.0
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
    return u
_U = None
def budget_left():
    global _U
    if _U is None: _U = _usage()
    return MONTHLY_BUDGET_USD - _U["usd"]
def save_usage():
    if _U is not None: json.dump(_U, open(USAGE, "w"))
def rewrite(a):
    key = os.environ.get("AI_API_KEY")
    if not key or budget_left() <= 0: return None
    text = re.sub(r"\s+", " ", (a.get("body") or a.get("summary_src") or ""))[:1300]
    user = f"Source: {a['source']}\nTitle: {a['raw_title']}\nText: {text or '(no text; rely on title only, keep summary to what the title states)'}"
    body = {"model": MODEL, "max_tokens": 260, "temperature": 0.6, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": user}]}
    for attempt in range(2):
        try:
            r = urllib.request.urlopen(urllib.request.Request(URL, data=json.dumps(body).encode(),
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}), timeout=40)
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
    if not key or budget_left() < LONGFORM_RESERVE_USD: return None
    text = re.sub(r"\s+", " ", (a.get("body") or a.get("summary_src") or ""))[:2600]
    if len(text) < 200: return None
    body = {"model": MODEL, "max_tokens": 480, "temperature": 0.5, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": LONG_SYS}, {"role": "user", "content": f"Headline: {headline}\nText: {text}"}]}
    try:
        r = urllib.request.urlopen(urllib.request.Request(URL, data=json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}), timeout=60)
        d = json.load(r)
        with _lock: _U["usd"] += d.get("usage", {}).get("cost_in_usd_ticks", 0) / 1e10; _U["calls"] += 1; _U["long"] = _U.get("long", 0) + 1
        p = [x.strip() for x in json.loads(d["choices"][0]["message"]["content"]).get("paragraphs", []) if isinstance(x, str) and len(x.strip()) > 30]
        return p[:7] or None
    except Exception as e:
        print("llm longform error:", str(e)[:80], flush=True); return None
LONGFORM_RESERVE_USD = 1.0   # keep $1 of the monthly cap for headline/summary rewrites
