from modules.guardrails_core import evaluate_guardrails


def test_promotion_pop_is_not_treated_as_latest_news_or_forecast():
    text = (
        "店頭POPです。"
        "お客様におにぎりと温かい飲み物をおすすめすることが重要です。"
        "今後の売り場作りにも必要です。"
    )

    result = evaluate_guardrails(
        body_text=text,
        evidence_text="",
        suggest_text="店頭 POP 販促 おにぎり",
    )

    codes = [f.code for f in result.findings]

    assert "最新情報は最終確認前提" not in codes
    assert "ニュース系の断定調注意" not in codes
    assert result.level == "SAFE"


def test_real_news_still_gets_latest_news_caution():
    text = "速報です。政府は本日、法改正に関する声明を出しました。今後の対応が必要です。"

    result = evaluate_guardrails(
        body_text=text,
        evidence_text="政府発表 速報 法改正 声明",
        suggest_text="ニュース 政府 法改正",
    )

    codes = [f.code for f in result.findings]

    assert "最新情報は最終確認前提" in codes
