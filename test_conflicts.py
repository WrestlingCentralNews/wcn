"""python3 test_conflicts.py -- /live priority: every rank pair, unresolved pairs, overrides."""
import unittest, itertools, conflicts as C
S = {1: {"key": "2026-11-07-wwe-crown-jewel", "slug": "wwe-crown-jewel", "name": "WWE Crown Jewel 2026", "brand": "WWE", "kind": "ppv", "date": "2026-11-07"},
     2: {"key": "2026-11-07-aew-collision", "slug": "aew-collision", "name": "AEW Collision", "brand": "AEW", "kind": "weekly", "date": "2026-11-07"},
     3: {"key": "2026-11-07-aaa-heroes", "slug": "aaa-heroes", "name": "AAA Héroes Inmortales 2026", "brand": "Global", "kind": "ppv", "date": "2026-11-07"},
     4: {"key": "2026-11-07-wwe-nxt-halloween-havoc", "slug": "wwe-nxt-halloween-havoc", "name": "NXT Halloween Havoc 2026", "brand": "WWE", "kind": "ppv", "date": "2026-11-07"},
     5: {"key": "2026-11-07-tna-impact", "slug": "tna-impact", "name": "TNA iMPACT!", "brand": "TNA", "kind": "weekly", "date": "2026-11-07"}}
RAW = {"key": "2026-11-07-wwe-raw", "slug": "wwe-raw", "name": "WWE Raw", "brand": "WWE", "kind": "weekly", "date": "2026-11-07"}
NJPW = {"key": "2026-11-07-njpw-x", "slug": "njpw-x", "name": "NJPW Power Struggle", "brand": "Global", "kind": "ppv", "date": "2026-11-07"}
def w(s, last): return dict(s, last=last)
class T(unittest.TestCase):
    def test_ranks(self):
        for r, s in S.items(): self.assertEqual(C.rank(s), r, s["name"])
        self.assertIsNone(C.rank(RAW)); self.assertIsNone(C.rank(NJPW))
        self.assertEqual(C.rank({"slug": "aew-wrestledream", "brand": "AEW", "kind": "ppv", "name": "AEW WrestleDream"}), 2)
        self.assertEqual(C.rank({"slug": "wwe-nxt", "brand": "WWE", "kind": "weekly", "name": "WWE NXT"}), 4)
        self.assertEqual(C.rank({"slug": "tna-bound-for-glory", "brand": "TNA", "kind": "ppv", "name": "TNA Bound for Glory"}), 5)
    def test_every_rank_pair(self):   # higher priority wins even when the lower one has the newer result
        for a, b in itertools.combinations(range(1, 6), 2):
            c, how = C.choose([w(S[a], 100), w(S[b], 200)], "2026-11-07", ovr={})
            self.assertEqual((c["key"], how), (S[a]["key"], "priority"), f"{a} vs {b}")
    def test_unresolved(self):
        for x, y in ((RAW, S[2]), (RAW, S[1]), (NJPW, S[5]), (dict(S[5], key="k2", slug="tna-other"), S[5])):   # unranked or same rank
            c, how = C.choose([w(x, 100), w(y, 200)], "2026-11-07", ovr={})
            self.assertEqual(how, "unresolved-default"); self.assertEqual(c["key"], y["key"])           # most recent confirmed result
            c, how = C.choose([w(x, 300), w(y, 200)], "2026-11-07", ovr={}); self.assertEqual(c["key"], x["key"])
    def test_override_wins(self):
        c, how = C.choose([w(S[1], 100), w(S[5], 50)], "2026-11-07", ovr={"2026-11-07": "tna-impact"}); self.assertEqual((c["key"], how), (S[5]["key"], "override"))
        c, how = C.choose([w(RAW, 100), w(S[2], 200)], "2026-11-07", ovr={"2026-11-07": "2026-11-07-wwe-raw"}); self.assertEqual((c["key"], how), (RAW["key"], "override"))
        c, how = C.choose([w(S[1], 100), w(S[2], 200)], "2026-11-07", ovr={"2026-11-08": "aew-collision"}); self.assertEqual(how, "priority")   # other night's override ignored
        c, how = C.choose([w(S[1], 100), w(S[2], 200)], "2026-11-07", ovr={"2026-11-07": "not-on-tonight"}); self.assertEqual(how, "priority")
    def test_single(self): self.assertEqual(C.choose([w(RAW, 1)], "2026-11-07", ovr={})[1], "only")
    def test_three_way(self):
        c, how = C.choose([w(S[5], 300), w(S[3], 200), w(S[4], 100)], "2026-11-07", ovr={}); self.assertEqual((c["key"], how), (S[3]["key"], "priority"))
        self.assertEqual(C.choose([w(S[1], 1), w(S[2], 2), w(RAW, 3)], "2026-11-07", ovr={})[1], "unresolved-default")
if __name__ == "__main__": unittest.main(verbosity=1)
