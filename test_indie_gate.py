"""python3 test_indie_gate.py -- AI budget rule (owner 2026-10-24): Indie-only stories get AI rewrites/write-ups only when important."""
import unittest
import indie_gate as g
import llm
def art(raw, src="Fightful", body="", i="x"):
    return {"id": i, "raw_title": raw, "source": src, "body": body, "summary_src": "", "categories": None}
class IndieGate(unittest.TestCase):
    def setUp(self): self._p = llm.pace_ok; llm.pace_ok = lambda margin=0.0, prio=0: prio < 2   # budget tight for Indie/Global work
    def tearDown(self): llm.pace_ok = self._p
    def test_room_in_budget_indie_gets_ai(self):
        llm.pace_ok = lambda margin=0.0, prio=0: True
        self.assertFalse(g.skip_rewrite(art("MLW Fusion On Tubi Preview")))
    def test_routine_indie_skips(self):
        for t in ("MLW Fusion On Tubi Preview", "Josh Bishop in action on MLW Fusion this Thursday", "GCW Announces New Show In Atlanta",
                  "Carlie Bravo: Lee Moriarty Is One Of The Best Wrestlers On Ring of Honor"):
            self.assertTrue(g.skip_rewrite(art(t)), t)
    def test_important_indie_kept(self):
        for t in ("Matt Cardona Wins GCW World Championship", "Effy Signs With MLW", "ROH Star Suffers Torn ACL, Out Of Action",
                  "Nick Gage Hospitalized After GCW Show", "Former ROH Wrestler Dies At 45", "Tony Khan Says ROH Is Thriving",
                  "New GCW Tag Team Champions Crowned", "MLW Star Re-Signs With Promotion"):
            self.assertFalse(g.skip_rewrite(art(t)), t)
    def test_not_indie_untouched(self):
        for t in ("WWE Raw Preview", "AEW Announces Dynamite Card", "Some Wrestler Talks About His Career"):   # last: fallback Indie, AI tags it
            self.assertFalse(g.skip_rewrite(art(t)), t)
    def test_multi_trusted_card_gets_long(self):
        lead = art("GCW Announces New Show In Atlanta", "PWInsider")
        c = {"categories": ["Indie"], "title": lead["raw_title"], "source": "PWInsider", "link": "l", "updates": [{"source": "Fightful", "link": "m"}]}
        self.assertFalse(g.skip_long(c, lead))
        c["updates"] = []
        self.assertTrue(g.skip_long(c, lead))
        c["categories"] = ["AEW", "Indie"]
        self.assertFalse(g.skip_long(c, lead))
if __name__ == "__main__": unittest.main()
