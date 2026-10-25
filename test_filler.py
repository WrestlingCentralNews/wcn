"""Conservative 'link-only' filler filter (editorial.filler_notice): pure video / stream / how-to-watch link headlines go,
real news that merely mentions 'full match', 'live stream' or 'how to watch' stays."""
import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import enrich, editorial   # enrich first (editorial.filler_notice uses its roster name list)

T = editorial.FILLER_FROM + 60
BLOCK = ["FULL MATCH: Cruz Montana vs. Dion Lennox: NXT highlights, Oct. 20, 2026 - WWE",
         "FULL MATCH: CM Punk vs. Johnny Gargano | WWE Title Match: SmackDown highlights, Sept. 4, 2026",
         "Full Match: Seth Rollins vs. Gunther", "Watch: FULL EPISODE: Lucha Libre AAA, Oct. 17, 2026",
         "Watch: AEW WrestleDream BUY IN", "Watch: AAA Héroes Inmortales: October 24, 2026", "AEW WrestleDream live stream: The Buy In",
         "How to Watch AEW 'WrestleDream' 2026", "Here’s How to Watch WWE Money in the Bank 2026 Live Online",
         "Where to Watch WWE Premium Live Events, Raw, SmackDown, NXT and more - WWE", "Watch AEW WrestleDream: Orlando Live Stream Online | DAZN US"]
KEEP = ["WATCH: WWE Crown Jewel Stadium Construction Underway in Saudi Arabia Amid Security Concerns",
        "How to watch WWE Crown Jewel 2026: start time, card",
        "How to Watch WWE Crown Jewel 2026: Date, Special Start Time, Match Card, Location & Live Stream",
        "Cody Rhodes vs Randy Orton full match set for Crown Jewel", "AEW secures live stream deal with Tubi",
        "AEW WrestleDream 2026: Full match card, start time, everything to know about Clockwork Carnage",
        "WWE SmackDown Spoiler Lineup for October 16, 2026: Full Match Card and Backstage Notes Revealed",
        "AEW Dynamite/Collision Preview (10/14/26): Start Time, Match Card, How To Watch & Live Stream",
        "Watch: Cody Rhodes Attacks Randy Orton After SmackDown", "Watch: WWE star Cody Rhodes attacks Randy Orton",
        "Watch: #ThickBrother floor-presses 455 pounds at the Performance Center", "WWE Raw Full Match Card Revealed",
        "Netflix Confirms How To Watch WWE Raw In Canada Starting January", "Watch: Bayley Returns On Raw",
        "Watch: Roman Reigns vs. Bronson Reed full match set for Crown Jewel", "How To Watch AEW All In 2027 After Major TV Deal Change",
        "WWE Raw live stream numbers hit record on Netflix", "Watch: Liv Morgan Wins Women's World Title",
        "AEW WrestleDream Live Results", "WWE Raw Results: Full Match Results From Netflix Episode"]

class T_(unittest.TestCase):
    def test_blocks_link_only(self):
        for t in BLOCK: self.assertEqual(editorial.filler_notice({"raw_title": t, "ts": T}), "link-only notice", t)
    def test_keeps_real_news(self):
        for t in KEEP: self.assertIsNone(editorial.filler_notice({"raw_title": t, "ts": T}), t)
    def test_body_with_named_matches_stays(self):   # Fightful's 'Watch: AAA Héroes Inmortales' post listed the card -> became 'Card Revealed'
        a = {"raw_title": "Watch: AAA Héroes Inmortales: October 24, 2026", "ts": T,
             "summary_src": "Lucha Libre AAA presents Héroes Inmortales featuring Mr. Iguana, Psycho Clown and Pagano in title matches."}
        self.assertIsNone(editorial.filler_notice(a))
        self.assertEqual(editorial.filler_notice({**a, "summary_src": "Watch the show here."}), "link-only notice")
        self.assertEqual(editorial.filler_notice({"raw_title": BLOCK[0], "ts": T, "body": "Cruz Montana vs. Dion Lennox full match."}), "link-only notice")
    def test_dated_gate(self):   # stories already published keep their ids
        self.assertIsNone(editorial.filler_notice({"raw_title": BLOCK[0], "ts": T - 3600}))

if __name__ == "__main__": unittest.main()
