from modules.guardrails_core import evaluate_guardrails

_CLAIM_PENDING_CODE = "重要主張の照合未完了"


def _codes(result):
    return {finding.code for finding in result.findings}


def test_fee_keyword_triggers_claim_alignment_pending_caution():
    body = "継続手数料である可能性が高く、対象者の条件を確認する必要があります。"
    evidence = "この記事の根拠となる会員規約の一般的な説明を記載しています。"

    result = evaluate_guardrails(body_text=body, evidence_text=evidence)

    assert _CLAIM_PENDING_CODE in _codes(result)


def test_card_keyword_with_amount_triggers_claim_alignment_pending_caution():
    body = "カードの年会費2200円が引き落とされました。"
    evidence = "この記事の根拠となる会員規約には、年会費は2200円と明記されています。"

    result = evaluate_guardrails(body_text=body, evidence_text=evidence)

    assert _CLAIM_PENDING_CODE in _codes(result)
    assert result.level == "CAUTION"


def test_refund_keyword_with_condition_word_triggers_claim_alignment_pending_caution():
    body = "特定の条件を満たしていない場合、返金を受けられる可能性があります。対象者に該当するかご確認ください。"
    evidence = "会員規約に基づいて返金条件を一般的に説明しています。"

    result = evaluate_guardrails(body_text=body, evidence_text=evidence)

    assert _CLAIM_PENDING_CODE in _codes(result)


def test_cancellation_contract_terms_trigger_claim_alignment_pending_caution():
    body = "解約や契約内容については、規約の対象者条件を確認する必要があります。"
    evidence = "会員規約に基づいて解約条件を一般的に説明しています。"

    result = evaluate_guardrails(body_text=body, evidence_text=evidence)

    assert _CLAIM_PENDING_CODE in _codes(result)


def test_claim_alignment_pending_caution_is_not_added_when_evidence_is_blank():
    body = "継続手数料である可能性が高く、対象者の条件を確認する必要があります。"

    result = evaluate_guardrails(body_text=body, evidence_text="")

    assert _CLAIM_PENDING_CODE not in _codes(result)


def test_claim_alignment_pending_caution_is_not_added_for_ordinary_topic():
    body = "今日は天気が良いので、近所の公園を散歩しました。気持ちがいい一日でした。"
    evidence = "天気予報によると明日も晴れの予定です。"

    result = evaluate_guardrails(body_text=body, evidence_text=evidence)

    assert _CLAIM_PENDING_CODE not in _codes(result)


def test_existing_high_impact_topics_still_trigger_claim_alignment_pending_caution():
    body = "医療保険の給付金は基準額に応じて計算されます。"
    evidence = "保険会社のパンフレットに基づく一般的な説明です。"

    result = evaluate_guardrails(body_text=body, evidence_text=evidence)

    assert _CLAIM_PENDING_CODE in _codes(result)


def test_bare_high_impact_topic_sentences_without_numbers_trigger_claim_alignment_pending_caution():
    evidence = "カード会社の公式カスタマーサポートページを確認した。"
    bodies = [
        "継続手数料である可能性が高い。",
        "未利用の期間が続いた際に請求されることがある。",
        "返金を受けられる場合がある。",
        "特定の条件を満たしていない場合に手数料が発生する。",
        "カード契約や規約を確認する必要がある。",
    ]

    for body in bodies:
        result = evaluate_guardrails(body_text=body, evidence_text=evidence)
        assert _CLAIM_PENDING_CODE in _codes(result), body


def test_formula_mismatch_still_suppresses_claim_alignment_pending_caution():
    body = "賞与の総額を支給回数で割ります。カードの契約とは関係ありません。"
    evidence = "日本年金機構。その月以前1年間の標準賞与額の合計÷12。"

    result = evaluate_guardrails(body_text=body, evidence_text=evidence)

    codes = _codes(result)
    assert "根拠式との不一致" in codes
    assert _CLAIM_PENDING_CODE not in codes
