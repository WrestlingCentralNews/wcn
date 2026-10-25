"""Longer write-ups + $20 AI budget throttle (owner 2026-10-25)."""
import time, unittest
import llm, longer, indie_gate

def usage(usd=5.0, day_usd=0.0):
    llm._U = {"month": time.strftime("%Y-%m"), "usd": usd, "calls": 0, "day": llm._today(), "day_usd": day_usd}

class Budget(unittest.TestCase):
    def setUp(self): self._u = llm._U; self._pl = llm.pace_line; llm.pace_line = lambda: 10.0
    def tearDown(self): llm._U = self._u; llm.pace_line = self._pl
    def test_numbers(self):
        self.assertEqual(llm.MONTHLY_BUDGET_USD, 20.0)
        self.assertAlmostEqual(llm.MONTHLY_BUDGET_USD - llm.SAFETY_USD, 19.2)
        self.assertEqual(llm.PACE_TARGET_USD, 18.5)
    def test_priority_order_under_month_pace(self):
        usage(usd=9.0)          # 1.0 under the pace line: Indie/Global back-fill (headroom 1.2) is cut first
        self.assertEqual([llm.pace_ok(prio=p) for p in range(4)], [True, True, True, False])
        usage(usd=9.5)
        self.assertEqual([llm.pace_ok(prio=p) for p in range(4)], [True, True, False, False])
        usage(usd=9.9)
        self.assertEqual([llm.pace_ok(prio=p) for p in range(4)], [True, False, False, False])
        usage(usd=10.1)
        self.assertFalse(llm.pace_ok(prio=0))
    def test_daily_cap_spreads_backfill(self):
        usage(usd=1.0, day_usd=0.65)
        self.assertEqual([llm.pace_ok(prio=p) for p in range(4)], [True, True, False, False])
        usage(usd=1.0, day_usd=1.25)
        self.assertFalse(llm.pace_ok(prio=0))
    def test_day_rolls_over(self):
        llm._U = {"month": time.strftime("%Y-%m"), "usd": 1.0, "calls": 0, "day": "2000-01-01", "day_usd": 5.0}
        self.assertEqual(llm.day_spend(), 0.0)
        llm.add_cost(0.01, "long2")
        self.assertAlmostEqual(llm.day_spend(), 0.01); self.assertAlmostEqual(llm._U["usd"], 1.01)
        self.assertEqual(llm._U["long2"], 1)
    def test_hard_stop(self):
        llm.pace_line = lambda: 30.0
        usage(usd=19.19)
        self.assertFalse(llm.pace_ok(prio=0))

class Grounded(unittest.TestCase):
    SRC = 'Cody Rhodes said he loves acting and that "wrestling is my life". He has held 2 titles since 2024 at WWE.'
    def test_clean_kept(self):
        p = ["Cody Rhodes opened up about his work outside the ring and his love for acting.",
             'He also stressed that "wrestling is my life" when asked about his priorities.']
        self.assertEqual(llm.grounded(p, self.SRC), p)
    def test_invented_number_quote_filler_dropped(self):
        p = ["Cody Rhodes opened up about his work outside the ring and his love for acting.",
             "He has held 3 titles across his career so far in the company. He talked about his family at length."]
        out = " ".join(llm.grounded(p, self.SRC))
        self.assertNotIn("3 titles", out)
        p2 = ['Cody Rhodes opened up about his work outside the ring and his love for acting.', 'He said "I will never leave" to the crowd tonight here.']
        self.assertNotIn("never leave", " ".join(llm.grounded(p2, self.SRC)))
        p3 = ["Cody Rhodes opened up about his work outside the ring and his love for acting.", "It remains to be seen what comes next for the star."]
        self.assertNotIn("remains", " ".join(llm.grounded(p3, self.SRC)))
    def test_copied_run_dropped(self):
        p = ["Cody Rhodes spoke about his career outside the ring at length this week.",
             "Cody Rhodes said he loves acting and that wrestling is my life, he noted."]
        self.assertNotIn("loves acting and", " ".join(llm.grounded(p, self.SRC)))
    def test_regroup(self):
        p = ["One two three four five six seven eight nine ten.", "Eleven twelve thirteen fourteen fifteen sixteen seventeen.", "A " * 85]
        r = llm.regroup(p)
        self.assertEqual(len(r), 2); self.assertEqual(" ".join(r).split(), " ".join(p).split())
    def test_bad_opening_rejects_all(self):
        p = ["Cody Rhodes has held 7 titles over 9 years with the company.", "He talked about acting a lot in the new interview."]
        self.assertEqual(llm.grounded(p, self.SRC), [])

def card(i, cats, age_h, words=40, llm_long=None, **kw):
    now = time.time()
    c = {"id": f"c{i}", "link": f"l{i}", "title": f"Story {i}", "categories": cats, "first_ts": now - age_h * 3600, "ts": now,
         "summary": " ".join(["w"] * words), "updates": [], "source": "Fightful", "sources": 1}
    c.update(kw)
    m = {"id": f"a{i}", "link": f"l{i}", "llm": {"t": "x"}, "body": "Body " * 80, "source": "Fightful", "raw_title": f"Story {i}"}
    if llm_long: m["llm_long"] = llm_long
    return c, m

class Plan(unittest.TestCase):
    def setUp(self):
        self._g = (indie_gate.multi_trusted, indie_gate.important_title, indie_gate.important)
        indie_gate.multi_trusted = lambda c: False; indie_gate.important_title = lambda t: "dies" in (t or ""); indie_gate.important = lambda a: False
    def tearDown(self): indie_gate.multi_trusted, indie_gate.important_title, indie_gate.important = self._g
    def test_order_and_eligibility(self):
        cs = [card(1, ["Indie"], 2), card(2, ["WWE"], 99), card(3, ["AEW"], 1), card(4, ["Global"], 200),
              card(5, ["Indie"], 100, title="Indie legend dies"), card(6, ["WWE"], 1, words=300), card(7, ["TNA"], 1, card={"x": 1})]
        clusters = [c for c, m in cs]; bylink = {m["link"]: m for c, m in cs}
        order = [x[2]["id"] for x in longer.plan(clusters, bylink)]
        self.assertEqual(order, ["c3", "c2", "c5", "c1", "c4"])   # new big, then back-fill big + huge, then Indie/Global new, back-fill last
        self.assertNotIn("c6", order); self.assertNotIn("c7", order)
    def test_tried_not_repaid(self):
        c, m = card(1, ["WWE"], 2); bylink = {m["link"]: m}
        m["llm_long2"] = {"sig": longer.sig(longer.reports(c, m, bylink)), "n": 1, "v": longer.V}
        self.assertEqual(longer.plan([c], bylink), [])
        m["llm_long2"] = {"sig": longer.sig(longer.reports(c, m, bylink)), "n": 1}          # rejected by the v1 guard: one fresh try
        self.assertEqual(len(longer.plan([c], bylink)), 1)
        m["llm_long2"] = {"sig": longer.sig(longer.reports(c, m, bylink)), "n": 1, "w1": 120}  # kept by v1: not paid again
        self.assertEqual(longer.plan([c], bylink), [])

class Run(unittest.TestCase):
    def setUp(self):
        self._f = (llm.longform2, llm.longform, llm.pace_ok)
        llm.pace_ok = lambda margin=0.0, prio=0: True; llm.longform = lambda *a, **k: None
    def tearDown(self): llm.longform2, llm.longform, llm.pace_ok = self._f
    def test_keep_only_real_gain(self):
        old = ["one two three four five six seven eight nine ten " * 6]
        c1, m1 = card(1, ["WWE"], 2, llm_long=old); c2, m2 = card(2, ["WWE"], 2, llm_long=old)
        long_p = ["Story one gets a fuller account with plenty of new facts drawn from the reports " * 6]
        llm.longform2 = lambda h, rs, prio=0: long_p if h == "Story 1" else ["Short version of the second story only."]
        r = longer.run([c1, c2], {m1["link"]: m1, m2["link"]: m2})
        self.assertEqual((r["done"], r["kept"]), (2, 1))
        self.assertEqual(m1["llm_long"], long_p); self.assertEqual(m2["llm_long"], old)
        self.assertIn("w1", m1["llm_long2"]); self.assertNotIn("w1", m2["llm_long2"])
    def test_throttled_no_calls(self):
        llm.pace_ok = lambda margin=0.0, prio=0: prio < 2
        calls = []
        llm.longform2 = lambda h, rs, prio=0: calls.append(h) or None
        c, m = card(1, ["Indie"], 100)
        r = longer.run([c], {m["link"]: m})
        self.assertEqual((r["done"], calls), (0, []))
        self.assertNotIn("llm_long2", m)

if __name__ == "__main__": unittest.main()
