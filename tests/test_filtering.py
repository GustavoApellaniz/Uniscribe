from uniscribe.services.filtering import filter_transcript


def test_filter_removes_obvious_noise_but_keeps_academic_signals() -> None:
    source = (
        " Então... hum, uh, a professoressora disse que 2 + 2 = 4. "
        "Isso é muito importante para a prova. "
        "Por exemplo, em 12/05/2026, a equação é E = mc². "
        "Aluno: professor, isso é uma definição? "
        "Talvez seja uma hipótese; não tenho certeza. "
    )

    result = filter_transcript(source)
    text = getattr(result, "text", result)

    assert "Então" not in text
    assert "hum" not in text.lower()
    assert "2 + 2 = 4" in text
    assert "12/05/2026" in text
    assert "E = mc²" in text
    assert "definição" in text.lower()
    assert "hipótese" in text.lower()
    assert "não tenho certeza" in text.lower()


def test_filter_is_stable_for_empty_input() -> None:
    result = filter_transcript("   \n ")
    text = getattr(result, "text", result)
    assert text == ""
