from modules.guardrails_core import (
    _maybe_missing_exception_or_alternative_findings,
    evaluate_guardrails_core,
)


EVIDENCE_WITH_TEMPORARY_MEASURE = (
    "従来の健康保険証の有効期限は2025年12月1日で終了する。"
    "2025年12月2日以降は、マイナ保険証または資格確認書を提示する。"
    "有効期限切れに気付かず従来の健康保険証を持参した場合の暫定対応は"
    "2026年7月31日で終了する。"
)


def test_strong_negation_without_rescue_nearby_is_caution():
    body = "従来の健康保険証を提示しても診察や薬の処方を受けることができません。"

    findings = _maybe_missing_exception_or_alternative_findings(
        body, EVIDENCE_WITH_TEMPORARY_MEASURE
    )

    assert len(findings) == 1
    assert findings[0].code == "例外条件の落とし込み不足"
    assert findings[0].level == "CAUTION"
    assert "受けることができません" in findings[0].samples[0]


def test_distant_paragraph_rescue_word_does_not_suppress_warning():
    # 「ただし」は本文にあるが、強い否定文から離れた別段落にしかない。
    body = (
        "従来の健康保険証を提示しても診察や薬の処方を受けることができません。"
        "医療機関の受付時間は通常どおりです。"
        "会計窓口の混雑状況も普段と変わりません。"
        "なお、当院の駐車場は台数に限りがあります。"
        "ただし、休日は別の駐車場を利用できます。"
    )

    findings = _maybe_missing_exception_or_alternative_findings(
        body, EVIDENCE_WITH_TEMPORARY_MEASURE
    )

    assert len(findings) == 1
    assert findings[0].code == "例外条件の落とし込み不足"


def test_rescue_sentence_immediately_after_negation_suppresses_warning():
    body = (
        "従来の健康保険証を提示しても診察や薬の処方を受けることができません。"
        "ただし、有効期限切れに気付かなかった場合の暫定対応があります。"
    )

    findings = _maybe_missing_exception_or_alternative_findings(
        body, EVIDENCE_WITH_TEMPORARY_MEASURE
    )

    assert findings == []


def test_rescue_sentence_immediately_before_negation_suppresses_warning():
    body = (
        "有効期限切れに気付かなかった場合は、暫定対応の期間内であれば引き続き利用できます。"
        "その暫定対応の期間を過ぎると、従来の健康保険証では受けることができません。"
    )

    findings = _maybe_missing_exception_or_alternative_findings(
        body, EVIDENCE_WITH_TEMPORARY_MEASURE
    )

    assert findings == []


def test_alternative_option_dropped_is_caution():
    evidence = "本人確認は運転免許証またはマイナンバーカードのどちらかを提示してください。"
    body = "本人確認書類として運転免許証の提示が必要です。それ以外の方法では確認できません。"

    findings = _maybe_missing_exception_or_alternative_findings(body, evidence)

    assert len(findings) == 1
    assert findings[0].code == "例外条件の落とし込み不足"


def test_no_exception_or_alternative_words_in_evidence_has_no_warning():
    evidence = "運転免許証を提示してください。"
    body = "運転免許証がないと本人確認できません。"

    findings = _maybe_missing_exception_or_alternative_findings(body, evidence)

    assert findings == []


def test_blank_evidence_has_no_warning():
    body = "従来の健康保険証を提示しても診察や薬の処方を受けることができません。"

    findings = _maybe_missing_exception_or_alternative_findings(body, "")

    assert findings == []


def test_evaluate_guardrails_core_surfaces_exception_finding_as_caution():
    body = "従来の健康保険証を提示しても診察や薬の処方を受けることができません。"

    result = evaluate_guardrails_core(
        body_text=body,
        evidence_text=EVIDENCE_WITH_TEMPORARY_MEASURE,
    )

    codes = [f.code for f in result.findings]
    assert "例外条件の落とし込み不足" in codes
    assert result.level == "CAUTION"
