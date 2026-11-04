"""Oct 28 2026 Dynamite: 'The Cut defeated Death Riders' must credit Moxley & Garcia from the match header."""
import live, stats_pages
PAGE = """<article><p>Death Riders (AEW Continental Champion Jon Moxley &amp; Daniel Garcia) vs. The Cut (Switchblade Jay White &amp; David Finlay)</p>
<p>Some play by play.</p><p>Match Result: The Cut defeated Death Riders when White pinned Garcia</p>
<p>The Motor City Machine Guns defeated FTR to go up 2-1 in the series</p></article>"""
def test_members_from_header():
    r = live.parse_page(PAGE)
    m = r[0]
    assert m["winner"] == "The Cut (Jay White & David Finlay)"
    assert m["loser"] == "Death Riders (Jon Moxley & Daniel Garcia)"
    assert stats_pages.members(m["loser"]) == ["Jon Moxley", "Daniel Garcia"]
    assert m["who"] == "White pinned Garcia"
    assert r[1]["loser"] == "FTR"
def test_listed_members_untouched():
    assert live.with_members("The Cut (Juice Robinson & The Gunns)", ["The Cut (Jay White & David Finlay)"]) == "The Cut (Juice Robinson & The Gunns)"
    assert live.with_members("Kyle Fletcher", ["Kyle Fletcher", "Jack Perry"]) == "Kyle Fletcher"
def test_three_members_and_tails():
    assert live.with_members("The Cut", ["The Cut (Juice Robinson & Colten Gunn & & Austin Gunn)"]) == "The Cut (Juice Robinson, Colten Gunn & Austin Gunn)"
    assert live.split_method("The Young Bucks pinning Matt & Nick")[0] == "The Young Bucks"
    assert live.split_method("The Creed Brothers in a Quarterfinals Match for the Classic")[0] == "The Creed Brothers"
if __name__ == "__main__":
    test_members_from_header(); test_listed_members_untouched(); test_three_members_and_tails(); print("ok")
