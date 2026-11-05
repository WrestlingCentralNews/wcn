"""Dry run: python3 tools/index_tier_dryrun.py news.json out.md [days] -- tier of every story from the last N days (default 3)."""
import sys, os, json, time, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import index_tier
src, out = sys.argv[1], sys.argv[2]; days = float(sys.argv[3]) if len(sys.argv) > 3 else 3
it = [c for c in json.load(open(src))["items"] if c.get("first_ts", c["ts"]) >= time.time() - days * 86400]
rows = [(c, *index_tier.tier(c)) for c in sorted(it, key=lambda c: -c.get("first_ts", c["ts"]))]
n = collections.Counter(r[1] for r in rows); why = collections.Counter((r[1], r[2].split(" (")[0]) for r in rows)
L = [f"# Index tier dry run (last {days:g} days, {len(rows)} stories) — NOT enabled", "",
     f"**INDEX: {n['index']}  |  NOINDEX: {n['noindex']}**", "", "| Tier | Reason | Count |", "|---|---|---|"]
L += [f"| {t} | {r} | {k} |" for (t, r), k in sorted(why.items(), key=lambda x: (x[0][0], -x[1]))]
L += ["", "| Tier | Promo | Type | Imp | Headline | Reason |", "|---|---|---|---|---|---|"]
for c, t, r in rows:
    L.append(f"| {t.upper()} | {'/'.join(c.get('categories') or [])} | {(c.get('kind') or {}).get('type','news')} | {c.get('imp')} | {c['title'].replace('|','/')} | {r} |")
open(out, "w").write("\n".join(L) + "\n"); print(dict(n)); [print(k, v) for k, v in why.most_common()]
