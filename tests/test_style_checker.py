from modules.style_checker import _check_convenient_phrases


def test_check_convenient_phrases_reports_remaining_sentence_only():
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
    assert len(finding.samples) == 1
    assert finding.samples[0].endswith("\u53ef\u80fd\u306b\u306a\u308a\u307e\u3059\u3002")
