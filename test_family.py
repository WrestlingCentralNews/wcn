import aliases
def test_sting_son():
    src = "Steve Borden Returns To AEW To Make Blood & Guts Challenge"
    body = "The son of wrestling legend Sting was injured during his debut match alongside Allin at AEW All Out."
    assert aliases.family_mixup("Sting Returns To AEW For Blood & Guts Challenge", src, body) == "Sting"
    assert aliases.family_mixup("Sting Returns On AEW Dynamite", "Steven Borden Returns, Issues Blood & Guts Challenge To Don Callis Family", "") == "Sting"
    assert aliases.family_mixup("Sting's Son Steve Borden Returns On Dynamite", src, body) is None
    assert aliases.family_mixup("Sting Inducted Into Hall Of Fame", "Sting Inducted Into Hall Of Fame", "") is None
    assert aliases.family_mixup("Sting Praises Son", "Steve Borden Sr. Praises Son", "") is None
    for n in ("Steve Borden", "Steven Borden", "Borden Jr.", "Sting's son"):
        assert "Sting" not in aliases.canon(n).replace("Sting's", "")
def test_generic_jr():
    assert aliases.family_mixup("Dusty Rhodes Returns", "Dusty Rhodes Jr. Returns", "") == "Dusty Rhodes"
    assert aliases.family_mixup("Rey Mysterio Wins", "Dominik Mysterio Wins", "") == "Rey Mysterio"
