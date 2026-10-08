"""Safety classifier: keyword rules must fire without an LLM."""

from backend.services.safety import classify


def test_passport_withheld_is_safeguarding():
    result = classify("My employer withheld my passport and I cannot leave the house.")
    assert result.triggered
    assert result.category == "safeguarding_exploitation"
    assert "999" in result.message or any("999" in r for r in result.resources)


def test_visa_advice_is_signposted():
    result = classify("Please advise me on my visa application and asylum claim.")
    assert result.triggered
    assert result.category == "immigration_legal"
    assert "cannot" in result.message.lower() or "GOV.UK" in result.message


def test_fabricate_request_refused():
    result = classify("Can you fake a certificate and lie on my CV that I worked at the NHS?")
    assert result.triggered
    assert result.category == "fabricate_credentials"


def test_ordinary_career_question_passes():
    result = classify("I was a nurse in Kyiv. What UK jobs could fit me?")
    assert result.triggered is False
