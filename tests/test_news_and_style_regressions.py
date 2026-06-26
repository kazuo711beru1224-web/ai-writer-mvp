from modules.guardrails_core import evaluate_guardrails
from modules.style_checker import check_style


def _codes(result):
    return {finding.code for finding in result.findings}


def test_legal_procedure_words_do_not_trigger_news_cautions():
    result = evaluate_guardrails(
        body_text=(
            "\u5408\u540c\u4f1a\u793e\u306e\u4ee3\u8868\u793e\u54e1\u304c\u6b7b\u4ea1\u3057\u305f\u5f8c\u306f\u3001"
            "\u767b\u8a18\u624b\u7d9a\u304d\u304c\u5fc5\u8981\u3067\u3059\u3002"
            "\u4eca\u5f8c\u306e\u624b\u7d9a\u304d\u306f\u3001\u6cd5\u52d9\u5c40\u306e\u6848\u5185\u3068\u5c02\u9580\u5bb6\u3078\u306e\u78ba\u8a8d\u3092\u901a\u3058\u3066\u6574\u7406\u3057\u307e\u3059\u3002"
        ),
        evidence_text="",
    )
    codes = _codes(result)
    assert "\u30cb\u30e5\u30fc\u30b9\u7cfb\u306e\u65ad\u5b9a\u8abf\u6ce8\u610f" not in codes
    assert "\u6700\u65b0\u60c5\u5831\u306f\u6700\u7d42\u78ba\u8a8d\u524d\u63d0" not in codes


def test_ordinary_necessary_and_important_are_not_convenient_phrases():
    result = check_style(
        text="\u767b\u8a18\u624b\u7d9a\u304d\u306e\u78ba\u8a8d\u304c\u5fc5\u8981\u3067\u3059\u3002\u4e8b\u5b9f\u95a2\u4fc2\u306e\u6574\u7406\u306f\u91cd\u8981\u3067\u3059\u3002"
    )
    assert "\u4fbf\u5229\u8868\u73fe\u30c1\u30a7\u30c3\u30af" not in _codes(result)


def test_remaining_convenient_phrase_reports_the_full_sentence():
    sentence = "\u3053\u308c\u306b\u3088\u308a\u3001\u78ba\u8a8d\u306e\u9806\u756a\u304c\u5206\u304b\u308a\u307e\u3059\u3002"
    result = check_style(text=sentence)
    finding = next(f for f in result.findings if f.code == "\u4fbf\u5229\u8868\u73fe\u30c1\u30a7\u30c3\u30af")
    assert finding.samples == (sentence,)


def test_clear_news_keeps_latest_information_caution():
    result = evaluate_guardrails(
        body_text="\u672c\u65e5\u3001\u653f\u5e9c\u306f\u4f1a\u898b\u3067\u65b0\u305f\u306a\u65b9\u91dd\u3092\u767a\u8868\u3057\u307e\u3057\u305f\u3002",
        evidence_text="",
    )
    assert "\u6700\u65b0\u60c5\u5831\u306f\u6700\u7d42\u78ba\u8a8d\u524d\u63d0" in _codes(result)


def test_latest_news_caution_prompts_date_issuer_and_multiple_sources():
    result = evaluate_guardrails(
        body_text="\u672c\u65e5\u3001\u653f\u5e9c\u306f\u4f1a\u898b\u3067\u65b0\u305f\u306a\u65b9\u91dd\u3092\u767a\u8868\u3057\u307e\u3057\u305f\u3002",
        evidence_text="",
    )
    finding = next(
        item
        for item in result.findings
        if item.code == "\u6700\u65b0\u60c5\u5831\u306f\u6700\u7d42\u78ba\u8a8d\u524d\u63d0"
    )
    assert "\u53c2\u7167\u65e5" in finding.message
    assert "\u767a\u8868\u5143" in finding.message
    assert "\u8907\u6570\u306e\u78ba\u8a8d\u5148" in finding.message



def test_bonus_payment_count_formula_is_risk_when_evidence_says_divide_by_twelve():
    evidence = (
        "日本年金機構。その月以前1年間の"
        "標準賞与額の合計÷12。"
    )
    result = evaluate_guardrails(
        body_text="賞与の総額を支給回数で割ります。",
        evidence_text=evidence,
    )
    assert "根拠式との不一致" in _codes(result)
    assert result.level == "RISK"


def test_correct_bonus_formula_is_caution_until_claim_matching_exists():
    evidence = (
        "日本年金機構。その月以前1年間の"
        "標準賞与額の合計÷12。"
    )
    result = evaluate_guardrails(
        body_text="在職老齢年金で、標準賞与額の合計を12で割ります。",
        evidence_text=evidence,
    )
    codes = _codes(result)
    assert "根拠式との不一致" not in codes
    assert "重要主張の照合未完了" in codes
    assert result.level == "CAUTION"


def test_pension_possibility_is_not_treated_as_news_forecast():
    result = evaluate_guardrails(
        body_text=(
            "\u5728\u8077\u8001\u9f62\u5e74\u91d1\u3067\u3001\u7d66\u4e0e\u3068\u8cde\u4e0e\u306b\u3088\u3063\u3066"
            "\u5e74\u91d1\u304c\u6e1b\u308b\u53ef\u80fd\u6027\u3092\u78ba\u8a8d\u3057\u305f\u3044\u3067\u3059\u3002"
        ),
        evidence_text="",
    )
    codes = _codes(result)
    assert "\u30cb\u30e5\u30fc\u30b9\u7cfb\u306e\u65ad\u5b9a\u8abf\u6ce8\u610f" not in codes
    assert "\u6700\u65b0\u60c5\u5831\u306f\u6700\u7d42\u78ba\u8a8d\u524d\u63d0" not in codes


def test_pension_future_word_is_not_treated_as_news_forecast():
    result = evaluate_guardrails(
        body_text=(
            "\u5c06\u6765\u306e\u751f\u6d3b\u8cbb\u306b\u4e0d\u5b89\u304c\u3042\u308b\u305f\u3081\u3001"
            "\u7d66\u4e0e\u3068\u8cde\u4e0e\u3067\u5e74\u91d1\u304c\u6e1b\u308b\u53ef\u80fd\u6027\u3092\u78ba\u8a8d\u3057\u305f\u3044\u3067\u3059\u3002"
        ),
        evidence_text="",
    )
    codes = _codes(result)
    assert "\u30cb\u30e5\u30fc\u30b9\u7cfb\u306e\u65ad\u5b9a\u8abf\u6ce8\u610f" not in codes
    assert "\u6700\u65b0\u60c5\u5831\u306f\u6700\u7d42\u78ba\u8a8d\u524d\u63d0" not in codes
