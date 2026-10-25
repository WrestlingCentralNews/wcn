"""No-AI sanity check of Spanish translations: names / promotions / numbers must come from the English story."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import translate, pages

SEM = {"id": "caade68cbcbb3", "title": "Motor City Machine Guns to Host Seminar at FLEX Wrestling", "categories": ["Indies"],
       "summary": "FLEX Wrestling in New York will hold a pro wrestling seminar with the Motor City Machine Guns at the LECOM Event Center.",
       "long": ["FLEX Wrestling in New York will hold a special pro wrestling seminar featuring the Motor City Machine Guns at the LECOM Event Center. " * 3]}

class T(unittest.TestCase):
    def test_mcmg_seminar_mistranslation_flagged(self):
        bad = {"t": "FTR vs MCMG: serie al mejor de 5", "s": "FTR y Motor City Machine Guns se enfrentan en una serie al mejor de cinco."}
        r = translate.es_issues(SEM, bad)
        self.assertTrue(any("ftr" in x.lower() for x in r), r)
        self.assertTrue(pages.noindex(SEM, "es", bad)); self.assertFalse(pages.noindex(SEM, "en"))
    def test_good_translation_passes(self):
        ok = {"t": "Motor City Machine Guns impartirán seminario en FLEX Wrestling",
              "s": "FLEX Wrestling en Nueva York realizará un seminario con Motor City Machine Guns en el LECOM Event Center."}
        self.assertEqual(translate.es_issues(SEM, ok), []); self.assertFalse(pages.noindex(SEM, "es", ok))
    def test_surname_or_first_name_counts(self):
        c = {"title": "Ric Flair's Daughter Charlotte Gives Health Latest", "summary": "Charlotte gave an update on her father."}
        self.assertEqual(translate.es_issues(c, {"t": "Charlotte Flair actualiza el estado de salud de Ric Flair", "s": ""}), [])
    def test_numbers(self):
        c = {"title": "NXT Viewership Rises To 732,000 For October 13 Episode", "summary": "NXT drew 732,000 viewers. Starts 8 PM."}
        self.assertEqual(translate.es_issues(c, {"t": "WWE NXT alcanza 732.000 espectadores el 13 de octubre", "s": "A las 8:00 p.m."}), [])
        self.assertTrue(translate.es_issues(c, {"t": "WWE NXT alcanza 950.000 espectadores", "s": ""}))
        c2 = {"title": "Jerry Lynn Recalls The 1990s", "summary": "Lynn on the 1990s."}
        self.assertEqual(translate.es_issues(c2, {"t": "Jerry Lynn recuerda los años 90", "s": ""}), [])
    def test_promotion(self):
        c = {"title": "Shotzi Blackheart Signs With TNA", "summary": "TNA signs Shotzi Blackheart."}
        self.assertTrue(translate.es_issues(c, {"t": "Shotzi Blackheart firma con AEW", "s": ""}))
        self.assertEqual(translate.es_issues(c, {"t": "Shotzi Blackheart firma con TNA", "s": ""}), [])
    def test_summary_needs_two_extra_names(self):
        c = {"title": "Cody Rhodes Talks Crown Jewel", "summary": "Cody Rhodes discussed Crown Jewel."}
        self.assertEqual(translate.es_issues(c, {"t": "Cody Rhodes habla de Crown Jewel", "s": "Cody Rhodes, como Randy Orton, habló."}), [])
        self.assertTrue(translate.es_issues(c, {"t": "Cody Rhodes habla de Crown Jewel", "s": "Randy Orton y Roman Reigns hablaron."}))
    def test_missing_translation(self):
        self.assertEqual(translate.es_issues(SEM, None), [])

if __name__ == "__main__": unittest.main()
