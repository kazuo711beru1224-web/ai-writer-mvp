from modules.guardrails_core import evaluate_guardrails_core


def test_body_non_padded_day_matches_evidence_zero_padded_day():
    body = "会員登録の受付は2025年12月2日から開始します。"
    evidence = "会員登録の受付は2025年12月02日から開始する。"

    result = evaluate_guardrails_core(body_text=body, evidence_text=evidence)

    samples = [s for f in result.findings for s in (f.samples or ())]
    assert "2日" not in samples
    assert result.level == "SAFE"


def test_body_zero_padded_day_matches_evidence_non_padded_day():
    body = "会員登録の受付は2025年12月02日から開始します。"
    evidence = "会員登録の受付は2025年12月2日から開始する。"

    result = evaluate_guardrails_core(body_text=body, evidence_text=evidence)

    samples = [s for f in result.findings for s in (f.samples or ())]
    assert "02日" not in samples
    assert result.level == "SAFE"


def test_body_only_date_is_still_detected_as_missing():
    body = "2025年12月2日以降は、マイナ保険証または資格確認書を提示してください。"
    evidence = "マイナンバーカードを健康保険証として利用できます。"

    result = evaluate_guardrails_core(body_text=body, evidence_text=evidence)

    codes = [f.code for f in result.findings]
    samples = [s for f in result.findings for s in (f.samples or ())]
    assert "根拠に数字未記載" in codes
    assert "2日" in samples


def test_amount_mismatch_is_still_detected():
    body = "基礎控除額は3000万円です。"
    evidence = "基礎控除額は3600万円です。"

    result = evaluate_guardrails_core(body_text=body, evidence_text=evidence)

    codes = [f.code for f in result.findings]
    samples = [s for f in result.findings for s in (f.samples or ())]
    assert "根拠に数字未記載" in codes
    assert "3000万円" in samples


def test_percentage_mismatch_is_still_detected():
    body = "税率は15%です。"
    evidence = "税率は10%です。"

    result = evaluate_guardrails_core(body_text=body, evidence_text=evidence)

    codes = [f.code for f in result.findings]
    samples = [s for f in result.findings for s in (f.samples or ())]
    assert "根拠に数字未記載" in codes
    assert "15%" in samples


def test_age_mismatch_is_still_detected():
    body = "対象は65歳以上です。"
    evidence = "対象は70歳以上です。"

    result = evaluate_guardrails_core(body_text=body, evidence_text=evidence)

    codes = [f.code for f in result.findings]
    samples = [s for f in result.findings for s in (f.samples or ())]
    assert "根拠に数字未記載" in codes
    assert "65歳" in samples


def test_duration_kagetsu_is_not_affected_by_zero_padding_alias():
    # 「3か月」は月トークン（^\d+月$）ではないため、ゼロ埋めエイリアスの対象外のまま。
    body = "申告期限は死亡から10か月です。"
    evidence = "申告期限は死亡から3か月です。"

    result = evaluate_guardrails_core(body_text=body, evidence_text=evidence)

    codes = [f.code for f in result.findings]
    samples = [s for f in result.findings for s in (f.samples or ())]
    assert "根拠に数字未記載" in codes
    assert "10か月" in samples
