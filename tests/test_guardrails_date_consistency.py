import datetime

from modules.guardrails_core import (
    _future_tense_past_date_findings,
    evaluate_guardrails_core,
)


FIXED_TODAY = datetime.date(2026, 7, 6)


def test_past_date_future_tense_is_caution():
    body = "この制度は2024年3月31日に終了します。"

    findings = _future_tense_past_date_findings(body, today=FIXED_TODAY)

    assert len(findings) == 1
    assert findings[0].code == "時系列不一致"
    assert findings[0].level == "CAUTION"
    assert "2024年3月31日" in findings[0].samples[0]

    # 根拠欄に本文と同じ数字を入れて「根拠未入力」RISKが別途立たない状態にし、
    # 日付矛盾チェック単体がCAUTIONとして反映されることを確認する。
    result = evaluate_guardrails_core(
        body_text=body,
        evidence_text="2024年3月31日に制度が終了することが決まっている。",
    )
    codes = [f.code for f in result.findings]
    assert "時系列不一致" in codes
    assert result.level == "CAUTION"


def test_future_date_future_tense_has_no_warning():
    body = "この制度は2099年3月31日に終了します。"

    findings = _future_tense_past_date_findings(body, today=FIXED_TODAY)

    assert findings == []

    result = evaluate_guardrails_core(body_text=body)
    codes = [f.code for f in result.findings]
    assert "時系列不一致" not in codes


def test_no_fixed_date_has_no_warning():
    body = "この制度は今後見直される可能性があります。"

    findings = _future_tense_past_date_findings(body, today=FIXED_TODAY)

    assert findings == []

    result = evaluate_guardrails_core(body_text=body)
    codes = [f.code for f in result.findings]
    assert "時系列不一致" not in codes


def test_default_today_uses_asia_tokyo_timezone():
    # today を指定しない場合は ZoneInfo("Asia/Tokyo") の現在日付が使われる。
    # 未来日付にしておけば、実行日に関わらず警告が出ないことで
    # 本番のデフォルト経路（壁時計依存）を安全に確認できる。
    body = "この制度は2999年12月31日に終了します。"

    findings = _future_tense_past_date_findings(body)

    assert findings == []
