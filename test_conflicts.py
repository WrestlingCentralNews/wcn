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
    def test_needs_user(self):   # two IMPORTANT non-ranked shows (PPVs/specials): owner decides; temp default = newest result
        ROH = {"key": "k-roh", "slug": "roh-final-battle", "name": "ROH Final Battle", "brand": "AEW", "kind": "ppv", "date": "2026-11-07"}
        ROH["brand"] = "Global"
        for x, y in ((NJPW, ROH), (NJPW, dict(NJPW, key="k-gcw", slug="gcw-x", name="GCW Fight Club")), (dict(NJPW, key="k-st", slug="stardom-x", name="Stardom Dream Queendom"), ROH)):
            self.assertTrue(C.needs_user([x, y]), (x["name"], y["name"]))
            c, how = C.choose([w(x, 100), w(y, 200)], "2026-11-07", ovr={}); self.assertEqual((c["key"], how), (y["key"], "unresolved-default"))
            c, how = C.choose([w(x, 300), w(y, 200)], "2026-11-07", ovr={}); self.assertEqual(c["key"], x["key"])
        self.assertTrue(C.needs_user([S[1], NJPW, ROH]))   # ranked show present but two important non-ranked ones too
        h = C.reach_hint([ROH, NJPW]); self.assertEqual(h[0]["promotion"], "njpw")
    def test_minor_auto_reach(self):   # minor overlaps auto-resolve by reach, then newest result
        SD = dict(RAW, key="k-sd", slug="wwe-smackdown", name="WWE SmackDown")
        c, how = C.choose([w(RAW, 100), w(S[2], 200)], "2026-11-07", ovr={}); self.assertEqual((c["key"], how), (RAW["key"], "reach"))   # WWE > AEW weekly
        self.assertFalse(C.needs_user([RAW, S[2]]))
        c, how = C.choose([w(RAW, 100), w(SD, 200)], "2026-11-07", ovr={}); self.assertEqual((c["key"], how), ("k-sd", "reach"))       # same tier: newest
        c, how = C.choose([w(NJPW, 100), w(S[5], 200)], "2026-11-07", ovr={}); self.assertEqual((c["key"], how), (NJPW["key"], "reach"))  # one important only: reach (NJPW 6 > TNA 5)
        CM = {"key": "k-cmll", "slug": "cmll-viernes", "name": "CMLL Viernes Espectacular", "brand": "Global", "kind": "weekly", "date": "2026-11-07"}
        STP = {"key": "k-stp", "slug": "stardom-x", "name": "Stardom Big Show", "brand": "Global", "kind": "ppv", "date": "2026-11-07"}
        c, how = C.choose([w(CM, 200), w(STP, 100)], "2026-11-07", ovr={}); self.assertEqual(c["key"], "k-stp")   # PPV beats weekly in the same tier
        I1 = {"key": "k-i1", "slug": "beyond-x", "name": "Beyond Wrestling", "brand": "Indie", "kind": "weekly"}; I2 = dict(I1, key="k-i2", slug="wrestling-open")
        c, how = C.choose([w(I1, 100), w(I2, 200)], "2026-11-07", ovr={}); self.assertEqual((c["key"], how), ("k-i2", "reach"))
        self.assertEqual(C.choose([w(dict(S[5], key="k2", slug="tna-other"), 100), w(S[5], 200)], "2026-11-07", ovr={})[0]["key"], S[5]["key"])   # same rank: newest
    def test_override_wins(self):
        c, how = C.choose([w(S[1], 100), w(S[5], 50)], "2026-11-07", ovr={"2026-11-07": "tna-impact"}); self.assertEqual((c["key"], how), (S[5]["key"], "override"))
        c, how = C.choose([w(RAW, 100), w(S[2], 200)], "2026-11-07", ovr={"2026-11-07": "2026-11-07-wwe-raw"}); self.assertEqual((c["key"], how), (RAW["key"], "override"))
        c, how = C.choose([w(S[1], 100), w(S[2], 200)], "2026-11-07", ovr={"2026-11-08": "aew-collision"}); self.assertEqual(how, "priority")   # other night's override ignored
        c, how = C.choose([w(S[1], 100), w(S[2], 200)], "2026-11-07", ovr={"2026-11-07": "not-on-tonight"}); self.assertEqual(how, "priority")
    def test_single(self): self.assertEqual(C.choose([w(RAW, 1)], "2026-11-07", ovr={})[1], "only")
    def test_three_way(self):
        c, how = C.choose([w(S[5], 300), w(S[3], 200), w(S[4], 100)], "2026-11-07", ovr={}); self.assertEqual((c["key"], how), (S[3]["key"], "priority"))
        self.assertEqual(C.choose([w(S[1], 1), w(S[2], 2), w(RAW, 3)], "2026-11-07", ovr={})[1], "reach")
if __name__ == "__main__": unittest.main(verbosity=1)
