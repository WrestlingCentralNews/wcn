"""python3 test_breaking.py  -- sample headlines for the 'BREAKING🚨🚨🚨' rule (positives must label, negatives must not)."""
import unittest, breaking
POS = {
 "Bandido, Hangman & Brody King regain AEW Trios titles": "title-change",
 "Knockout Brothers & Jeff Cobb Win NEVER Six-Man Titles": "title-change",
 "Alexa Bliss and Tatum Paxley Win Women's Tag Titles": "title-change",
 "Dominik Mysterio Wins The Intercontinental Championship On Raw": "title-change",
 "New AEW TNT Champion Crowned On Collision": "title-change",
 "Jade Cargill Vacates WWE Women's Tag Team Titles Due To Injury": "title-change",
 "Gunther Dethroned At Crown Jewel": "title-change",
 "PJ Vasa Released by WWE NXT": "release",
 "Carmelo Hayes Has Been Released From WWE": "release",
 "WWE Releases Several Wrestlers Following Raw": "release",
 "AEW Star Fired After Incident In Chicago": "release",
 "Ilja Dragunov Debuts As All Elite At WrestleDream": "debut",
 "AAA on FOX Results: La Catalina Debuts in Tag Title Match": "debut",
 "Mike Bailey Makes His NJPW Debut In Korakuen Hall": "debut",
 "Jay White Returns at AEW WrestleDream": "return",
 "Rhea Ripley Returns to WWE Programming": "return",
 "Will Ospreay returns unannounced to NJPW": "return",
 "Stephanie Vaquer returns at WWE Hawaii house show": "return",
 "Mariah May Makes Shocking Return On Dynamite": "return",
}
NEG = ["Moxley Retains Continental Title Over Davis At WrestleDream", "Mercedes Mone Retains AEW Women's Title at WrestleDream",
 "Nikki Bella earns Women's Title shot by beating Paige", "Trey Miguel earns TNA title shot at Destination X", "Jacy Jayne Describes Out-of-Body Title Win",
 "Drew McIntyre Teases Major WWE Return", "Maya World Cleared To Return To AEW Ring", "Backstage News On Naomi's WWE Return", "Kevin Knight Open To NJPW Return",
 "Kaitlyn Rules Out In-Ring Return", "Corey Graves Medically Cleared for Potential Return", "Tony Khan Updates Mercedes Moné Injury Return",
 "Apollo Crews Open To WWE Return", "MLW Returns To Atlanta Center Stage", "MLW Returns To PPV With November SuperFight", "WWE Stars Promote Return to Australia",
 "WWE Releases SmackDown Videos", "TNA Releases Three Hours Of Leon Slater Matches", "Yota Tsuji Set for MLW Debut", "Sheamus Recalls Nervous WWE ECW Debut",
 "Christyan XO Recalls AEW/ROH Debut Path", "Kofi Calls New Level AEW Debut Worst Kept Secret", "AEW Announces Paris Debut For Grand Slam France",
 "Vietnam's Ares set for NJPW debut in Korakuen Hall tag match", "Drake Maverick Reflects On Surprise Indie Return", "Bully Ray Praises Je'Von Evans' Intense Ambulance Return",
 "Kenny Omega Targets Wrestle Kingdom Title Shot", "AEW World Title Set For Clockwork Carnage At WrestleDream", "Kyle Fletcher Feels Ready For AEW World Title",
 "Rumor: Former WWE Champion Could Return At Survivor Series", "Is Brock Lesnar Returning At WrestleMania?", "Randy Orton Expected To Return Soon",
 "CM Punk Reportedly Set To Return Next Month", "Roman Reigns May Return On SmackDown", "Raw Preview: New Champion To Be Crowned?",
 "Wrestler Requests Release From AEW", "Seth Rollins Fires Back At Critics", "Cody Rhodes Fired Up Ahead Of Crown Jewel",
 "Will Ospreay Will Return At Wrestle Kingdom", "Five wrestlers clash in ladder match for title shot", "Sawyer Defends GCW Title vs Cogar on November 7",
 "Ospreay Retains AEW World Title at All Out", "Hotch vs. Ali 2-Out-Of-3 Falls For TNA International Title", "Raw Returns To Madison Square Garden"]
class T(unittest.TestCase):
    def test_pos(self):
        for h, k in POS.items(): self.assertEqual(breaking.kind(h), k, h)
    def test_neg(self):
        for h in NEG: self.assertIsNone(breaking.kind(h), h)
    def test_quote_never(self): self.assertIsNone(breaking.kind("Jay White Returns at AEW WrestleDream", "quote"))
    def test_x_text(self):
        import x_poster as X
        c = {"id": "t1", "title": "Ilja Dragunov Debuts As All Elite At WrestleDream " + "x" * 200, "summary": "A long summary. " * 20, "categories": ["AEW"], "sources": 9, "trusted": 4, "kind": {"type": "news"}}
        t = X.tweet_text(c); self.assertTrue(t.startswith("BREAKING🚨🚨🚨\n")); self.assertEqual(t.count("🚨"), 3); self.assertLessEqual(X.x_len(t), 280)
        c2 = dict(c, title="Moxley Retains Continental Title Over Davis At WrestleDream", id="t2")
        self.assertNotIn("🚨", X.tweet_text(c2))
    def test_live_text(self):
        import live_x
        st = {"name": "AEW WrestleDream 2026", "brand": "AEW", "tag": "#AEWWrestleDream"}
        t = live_x.match_text(st, {"en": "Bandido, Hangman Page and Brody King defeated Swerve Strickland, Austin Creed and Kofi to win the AEW Trios Titles.", "title": "change"})
        self.assertTrue(t.startswith("BREAKING🚨🚨🚨\n")); self.assertEqual(t.count("🚨"), 3)
        t = live_x.match_text(st, {"en": "Moxley defeated Davis to retain.", "title": "retain"}); self.assertNotIn("🚨", t)
if __name__ == "__main__": unittest.main(verbosity=1)
