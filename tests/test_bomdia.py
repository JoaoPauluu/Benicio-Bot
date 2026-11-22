from whatsapp_bot.commands.bomdia import parse_quotes, pick_for_day

HTML = """
<div class="thought-card"><p class="frase fr">Bom dia, mundo!</p><span class="author-name">Fulano</span></div>
<div class="thought-card"><p class="frase fr">Outra frase</p></div>
<div class="other"><p class="frase">fora do card</p></div>
"""


def test_parse_quotes():
    assert parse_quotes(HTML) == [("Bom dia, mundo!", "Fulano"), ("Outra frase", "")]


def test_pick_is_stable_per_day():
    q = parse_quotes(HTML)
    assert pick_for_day(q, "2026-11-22") == pick_for_day(q, "2026-11-22")
