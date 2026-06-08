from modules.style_checker import _check_convenient_phrases


def test_check_convenient_phrases_detects_expected_terms():
    text = (
        "商品の特徴を確認することは重要です。\n"
        "この部分は必要です。\n"
        "正しく使えば、サービスがより可能になります。\n"
        "ただし、表現によっては読みづらさが出ることがあります。"
    )

    findings = _check_convenient_phrases(text)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.code == "便利表現チェック"
    assert set(finding.samples) >= {"重要です", "必要です", "可能になります"}
