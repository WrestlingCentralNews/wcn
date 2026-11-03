import chrome
for lang in ("en", "es"):
    h = chrome.footer(lang, "champions")
    assert h.count('<nav class="tabbar"') == 1 and 'aria-label=' in h and 'aria-current=page' in h
    assert h.count("<svg") == 5 and 'id="tb-sheet"' in h and "/history/ple/" in h and "/records/2026/" in h
es = chrome.tabbar("es"); assert "Inicio" in es and "/es/programas/" in es and "/es/proximos-eventos/" in es
css = open("public/style.css").read(); assert "safe-area-inset-bottom" in css and ".navl{display:none!important}" in css
assert "<!--tabbar-->" in open("public/index.html").read()
print("tabbar ok")
