"""Builds title_lineage.json (owner pt596u) from Wikipedia title-history lists (PWtitlereign rows, each citing its own source).
Accuracy guard: a title keeps its imported history only if the newest Wikipedia reign matches champions.json (holder + date);
otherwise only the current reign is kept ('history from <since>'). Run by hand: python3 tools/build_lineage.py <dir with <id>.txt raw wikitext> <pages.txt>"""
import re, sys, json, os, datetime, unicodedata
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def fold(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()
def blocks(txt):
    out, i = [], 0
    while True:
        i = txt.find("{{PWtitlereign", i)
        if i < 0: return out
        d, j = 0, i
        while j < len(txt):
            if txt.startswith("{{", j): d += 1; j += 2; continue
            if txt.startswith("}}", j):
                d -= 1; j += 2
                if d == 0: break
                continue
            j += 1
        out.append(txt[i:j]); i = j
def fields(b):
    body, f, d, cur = b[2:-2], {}, 0, ""
    parts = []
    for k, ch in enumerate(body):
        if body.startswith("{{", k) or body.startswith("[[", k): d += 1
        if body.startswith("}}", k) or body.startswith("]]", k): d -= 1
        if ch == "|" and d <= 0 and not (k and body[k-1] in "{["): parts.append(cur); cur = ""
        else: cur += ch
    parts.append(cur)
    for p in parts[1:]:
        if "=" in p: k, v = p.split("=", 1); f[k.strip()] = v.strip()
    return f
def date_of(v):
    m = re.search(r"\{\{dts\|([^}]*)\}\}", v or "")
    s = (m.group(1) if m else v or "").replace("|", " ")
    s = re.sub(r"\s+", " ", re.sub(r"<[^>]*>|\{\{[^}]*\}\}", "", s)).strip()
    s = re.sub(r"\s+,", ",", s); s = re.sub(r"^Between (.+?) and .*?(,\s*\d{4})?$", lambda m: m.group(1) if re.search(r"\d{4}", m.group(1)) else m.group(1) + (m.group(2) or ""), s)
    s = re.sub(r"(\d+)\s*[–-]\s*\d+,", r"\1,", s)
    for fmt in ("%B %d, %Y", "%B %d %Y", "%Y %m %d", "%Y-%m-%d", "%d %B %Y"):
        try: return datetime.datetime.strptime(s, fmt).date().isoformat()
        except Exception: pass
    return None
def holder(v):
    v = re.split(r"<br\s*/?>|\n", v or "")[0]
    m = re.search(r"\{\{sortname\|([^|}]*)\|([^|}]*)(?:\|([^|}]*))?[^}]*\}\}", v)
    link = None
    if m:
        name = f"{m.group(1)} {m.group(2)}".strip(); g3 = (m.group(3) or "").strip()
        link = f"{name} ({g3.split('=',1)[1]})" if g3.startswith("dab=") else (g3 or name)
    else:
        l = re.search(r"\[\[([^|\]]*)(?:\|([^\]]*))?\]\]", v)
        if l: link = l.group(1).strip(); name = (l.group(2) or l.group(1)).strip()
        else: name = v
    name = re.sub(r"<ref.*|\{\{[^}]*\}\}|'''?|\[\[|\]\]", "", name).strip(" ()")
    return name, link
def parse(txt):
    rows = []
    for b in blocks(txt):
        f = fields(b); d = date_of(f.get("date"))
        typ = (f.get("type") or "").lower()
        if typ in ("promotion", "brand", "title name", "name") or (typ and not d): continue
        if not d: return None
        url = re.search(r"\|\s*url\s*=\s*(https?://[^|\s}]+)", f.get("ref", ""))
        if typ or not f.get("champion"):
            rows.append({"holder": None, "start": d, "note": typ or "vacant"})
        else:
            n, link = holder(f["champion"])
            if not n: return None
            rows.append({"holder": n, "wiki": link, "start": d, "source": url.group(1) if url else None})
    return rows
def main(dirp, pages):
    cfg = json.load(open(os.path.join(ROOT, "champions.json")))
    pg = dict(l.strip().split("|", 1) for l in open(pages) if "|" in l)
    out, report = {}, {}
    for t in cfg["titles"]:
        wp = "https://en.wikipedia.org/wiki/" + pg.get(t["id"], "")
        cur = {"holder": t["champion"], "start": t["since"], "source": t["source"]}
        try: rows = parse(open(os.path.join(dirp, t["id"] + ".txt")).read())
        except Exception: rows = None
        ok = bool(rows) and all(rows[i]["start"] <= rows[i+1]["start"] for i in range(len(rows)-1))
        if ok:
            last = rows[-1]
            hn = fold(last.get("holder")); cn = fold(t["champion"]); mem = [fold(x) for x in (t.get("members") or [])]
            ok = last["start"] == t["since"] and bool(hn) and (hn == cn or hn in cn or cn in hn or (mem and all(m in fold(t["champion"] + " " + hn) or m in hn for m in mem[:1])))
        if ok:
            for r in rows:
                r["source"] = r.get("source") or wp
            rows[-1].update(holder=t["champion"], source=t["source"])
            reigns = rows
        else:
            reigns = [cur]
        for i, r in enumerate(reigns): r["end"] = reigns[i+1]["start"] if i + 1 < len(reigns) else None
        out[t["id"]] = {"name": t["name"], "promo": t["promo"], "list_source": wp if ok else t["source"], "history_from": reigns[0]["start"], "reigns": reigns}
        report[t["id"]] = (ok, reigns[0]["start"], len(reigns))
    json.dump({"_note": "Built by tools/build_lineage.py from Wikipedia title-history lists (each reign keeps the source Wikipedia cites); only kept when the newest reign matches champions.json. stats_pages.py extends it automatically from champions.json.", "titles": out},
              open(os.path.join(ROOT, "title_lineage.json"), "w"), indent=0, ensure_ascii=False)
    for k, v in report.items(): print(k, *v)
if __name__ == "__main__": main(sys.argv[1], sys.argv[2])
