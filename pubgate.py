"""Pre-publish consistency gate (owner rules 2026-10-21). Runs on every story right before pages/feeds/X/push are built, after
clustering (enrich.cluster already keeps different wrestlers/promotions apart and picks a named, fresh lead). Rules only, no AI.
Fixes what it safely can, HOLDS (does not publish) the rest:
  * headline must name who the story is about: a rewritten headline that dropped the name falls back to the source headline;
    a story whose headlines all hide the name ('TNA Signing Confirmed', 'AAA Star Dealing With Injury') is held;
  * headline and summary must be about the same people and promotion;
  * the promotion tag follows the headline's promotion ('Santino Marella Re-Signs With TNA' is tagged TNA, never WWE);
  * signing stories: new signing vs re-signing must agree between the headline and its sources; if the sources disagree
    (several say 'signs with', several say 're-signs') the story is held;
  * long-form body about other people/another promotion -> dropped (the summary shows instead);
  * photo whose file name names another wrestler / promotion -> the promotion's card (or the WCN card).
Held stories: data/held.json (current holds, for the daily summary) + data/dropped.jsonl."""
import os, json, time, re
import enrich, editorial
ROOT = os.path.dirname(os.path.abspath(__file__))
HELD = os.path.join(ROOT, "data", "held.json")
PROMO_CARD = "https://wrestlingcentralnews.com/img/promo/{}.jpg"
CAT = {"wwe": "WWE", "aew": "AEW", "tna": "TNA", "njpw": "Global", "cmll": "Global", "aaa": "Global", "stardom": "Global",
       "mlw": "Indie", "gcw": "Indie", "nwa": "Indie"}
def _art(c): return {"raw_title": c.get("raw_title") or "", "title": c.get("title") or ""}
def names_in(t, names):
    low = enrich.canon(t or "").lower()
    def one(n):
        if re.search(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", low): return True
        last = re.sub(r"s$", "", n.split()[-1])                      # 'the hardys' ~ 'Jeff Hardy', 'dragon lee' ~ 'Lee'
        return len(last) >= 3 and re.search(r"(?<![a-z])" + re.escape(last) + r"s?(?![a-z])", low) is not None
    return any(one(n) for n in names)
def kinds(c, bylink):
    out = []
    for l in [c["link"]] + [u["link"] for u in c.get("updates", [])]:
        a = bylink.get(l)
        if a:
            k = enrich.kind_of(a)
            if k: out.append(k)
    return out
def gate(c, bylink):
    fixes, holds = [], []
    # 1. the headline names the person
    T = lambda x: enrich.teaser({"raw_title": x or "", "title": x or ""})
    if T(c.get("title")):
        if enrich.subjects(c.get("raw_title") or ""):          # the rewrite dropped the name the source headline has
            new = enrich.headline(c["raw_title"], (c.get("kind") or {}).get("type"))
            fixes.append(f"nameless headline '{c['title']}' -> '{new}'"); c["title"] = new
        elif T(c.get("raw_title")): holds.append("headline doesn't name who it is about")
    t = c.get("title") or ""; s = c.get("summary") or ""
    pt = enrich.subjects(t)
    # 2. headline vs summary
    if pt and enrich.subjects(s) and not names_in(s, pt): holds.append("headline names " + ", ".join(sorted(pt)) + "; summary is about someone else")
    ft, fs = enrich.promos(t), enrich.promos(s)
    if ft and fs and not ft & fs and not (pt and names_in(s, pt)): holds.append("headline and summary are about different promotions")
    # 3. tag follows the headline
    want = sorted({CAT[p] for p in ft if p in CAT}, key=["WWE", "AEW", "TNA", "Indie", "Global"].index)
    if want and not set(want) & set(c.get("categories") or []):
        fixes.append(f"tag {c.get('categories')} -> {want}"); c["categories"] = want
    # 4. new signing vs re-signing
    ks = kinds(c, bylink); tk = enrich.signing_kind(t) or enrich.signing_kind(c.get("raw_title") or "")
    n, r = ks.count("new"), ks.count("re-sign")
    if n >= 2 and r >= 2 and min(n, r) >= 0.4 * max(n, r): holds.append(f"sources disagree: {n} say new signing, {r} say re-signing")
    elif tk in ("new", "re-sign"):
        opp = "re-sign" if tk == "new" else "new"
        if ks.count(opp) >= 2 and ks.count(opp) > 2 * ks.count(tk): holds.append(f"headline says {tk} but most sources say {opp}")
    # 5. body
    if c.get("long") and enrich.long_mismatch(_art(c), c["long"]): c["long"] = None; fixes.append("long-form about another story dropped")
    # 6. photo
    u = c.get("image")
    if u and "wrestlingcentralnews.com/img/" not in u and c.get("image_status") != "override" and enrich.img_clash(u, pt, ft):
        p = sorted(ft)[0] if ft else None
        c["image"] = PROMO_CARD.format(p) if p else None; c["image_status"] = "gate:" + (p or "wcn-card"); c["image_credit"] = None
        c.pop("img_w", None); c.pop("img_h", None); fixes.append("photo names another wrestler/promotion -> " + (c["image"] or "WCN card"))
    return not holds, fixes, holds
def run(clusters, bylink, log=print):
    keep, held = [], {}
    for c in clusters:
        ok, fixes, holds = gate(c, bylink)
        if fixes: log(f"gate: fixed {c['id']} '{c['title'][:70]}': " + "; ".join(fixes))
        if ok: keep.append(c); continue
        held[c["id"]] = {"title": c["title"], "link": c["link"], "source": c["source"], "why": holds, "at": int(time.time())}
        editorial.log_drop({"raw_title": c["raw_title"], "source": c["source"], "link": c["link"]}, "consistency hold: " + "; ".join(holds))
        log(f"gate: HOLD {c['id']} '{c['title'][:70]}': " + "; ".join(holds))
    try: os.makedirs(os.path.dirname(HELD), exist_ok=True); json.dump(held, open(HELD, "w"), indent=1)
    except Exception: pass
    return keep
