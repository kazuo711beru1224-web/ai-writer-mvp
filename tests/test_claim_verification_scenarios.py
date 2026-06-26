from __future__ import annotations

from datetime import date

from modules.claim_verification_core import evaluate_claim_verification, reconcile_claim_inventory
from modules.claim_verification_models import (
    BodyClaim,
    ClaimInventory,
    EvidenceRule,
    EvidenceSource,
    FormulaDetail,
    sha256_text,
)


EVAL_DATE = date(2026, 6, 25)
CONFIRMED_AT = date(2026, 6, 1)


def _source(*, effective_from=None, effective_to=None, review_due_at=date(2027, 1, 1)):
    return EvidenceSource(
        source_id="SRC-001",
        url="https://example.test/source",
        verifier="\u65e5\u672c\u5e74\u91d1\u6a5f\u69cb",
        doc_name="\u5728\u8077\u8001\u9f62\u5e74\u91d1\u306e\u8aac\u660e",
        last_checked_at=CONFIRMED_AT,
        review_due_at=review_due_at,
        raw_text_extract="\u305d\u306e\u6708\u4ee5\u524d1\u5e74\u9593\u306e\u6a19\u6e96\u8cde\u4e0e\u984d\u306e\u5408\u8a08\u00f712\u3002",
        effective_from=effective_from,
        effective_to=effective_to,
    )


def _formula(divisor=12):
    return FormulaDetail(
        target_object="\u6a19\u6e96\u8cde\u4e0e\u984d",
        target_period="\u305d\u306e\u6708\u4ee5\u524d1\u5e74\u9593",
        aggregation_type="\u5408\u8a08",
        divisor=divisor,
        formula_normalized=f"sum(standard_bonus) / {divisor}",
        variables={"\u6a19\u6e96\u8cde\u4e0e\u984d": "\u904e\u53bb1\u5e74\u9593\u306e\u8cde\u4e0e"},
    )


def _rule(*, rule_hash="RULE-HASH-1", formula=None, rule_type="\u8a08\u7b97\u5f0f"):
    return EvidenceRule(
        rule_id="RULE-001",
        source_id="SRC-001",
        rule_type=rule_type,
        quote_locator="\u5728\u8077\u8001\u9f62\u5e74\u91d1\u306e\u8a08\u7b97\u8aac\u660e",
        source_quote="\u305d\u306e\u6708\u4ee5\u524d1\u5e74\u9593\u306e\u6a19\u6e96\u8cde\u4e0e\u984d\u306e\u5408\u8a08\u00f712",
        condition_scope="\u8cde\u4e0e\u304c\u3042\u308b\u5834\u5408",
        rule_hash=rule_hash,
        context_status="COMPLETE",
        normalized_formula=formula or _formula(),
    )


def _claim(sentence, *, formula=None, match_status="MATCH", human_confirmed_at=CONFIRMED_AT):
    return BodyClaim(
        claim_id="CLM-001",
        sentence_text=sentence,
        text_hash=sha256_text(sentence),
        start_offset=0,
        end_offset=len(sentence),
        claim_kind="\u8a08\u7b97",
        requires_verification=True,
        classification_confirmed_at=CONFIRMED_AT,
        time_context="CURRENT",
        match_status=match_status,
        linked_rule_id="RULE-001",
        confirmed_rule_hash="RULE-HASH-1",
        human_confirmed_at=human_confirmed_at,
        normalized_formula=formula or _formula(),
    )


def _inventory(document_text, claim, *, inventory_confirmed_at=CONFIRMED_AT):
    return ClaimInventory(
        document_hash=sha256_text(document_text),
        claims=[claim],
        claim_inventory_confirmed_at=inventory_confirmed_at,
    )


def _evaluate(document_text, inventory, source=None, rule=None):
    return evaluate_claim_verification(
        evaluation_date=EVAL_DATE,
        document_text=document_text,
        inventory=inventory,
        sources_by_id={"SRC-001": source or _source()},
        rules_by_id={"RULE-001": rule or _rule()},
    )


def test_safe_when_all_claims_are_matched_and_human_confirmed():
    document_text = "\u6a19\u6e96\u8cde\u4e0e\u984d\u306e\u5408\u8a08\u309212\u3067\u5272\u308a\u307e\u3059\u3002"
    claim = _claim(document_text)
    inventory = _inventory(document_text, claim)

    result = _evaluate(document_text, inventory)

    assert result.level == "SAFE"
    assert result.findings == []


def test_caution_when_human_confirmation_is_missing():
    document_text = "\u6a19\u6e96\u8cde\u4e0e\u984d\u306e\u5408\u8a08\u309212\u3067\u5272\u308a\u307e\u3059\u3002"
    claim = _claim(document_text, human_confirmed_at=None)
    inventory = _inventory(document_text, claim)

    result = _evaluate(document_text, inventory)

    assert result.level == "CAUTION"
    assert "\u4e3b\u5f35\u672a\u7167\u5408" in {finding.code for finding in result.findings}


def test_risk_when_formula_conflicts_with_rule():
    document_text = "\u8cde\u4e0e\u306e\u7dcf\u984d\u3092\u652f\u7d66\u56de\u6570\u3067\u5272\u308a\u307e\u3059\u3002"
    claim = _claim(document_text, formula=_formula(divisor=2))
    inventory = _inventory(document_text, claim)

    result = _evaluate(document_text, inventory)

    assert result.level == "RISK"
    assert "\u8a08\u7b97\u5f0f\u4e0d\u4e00\u81f4" in {finding.code for finding in result.findings}


def test_reconcile_resets_confirmation_when_document_changes():
    document_text = "\u6a19\u6e96\u8cde\u4e0e\u984d\u306e\u5408\u8a08\u309212\u3067\u5272\u308a\u307e\u3059\u3002"
    changed_document = document_text + "\u8ffd\u8a18\u3002"
    claim = _claim(document_text)
    inventory = _inventory(document_text, claim)

    reconciled = reconcile_claim_inventory(
        document_text=changed_document,
        inventory=inventory,
        rules_by_id={"RULE-001": _rule()},
    )
    result = _evaluate(changed_document, reconciled)

    assert reconciled.claim_inventory_confirmed_at is None
    assert reconciled.claims[0].match_status == "UNCHECKED"
    assert reconciled.claims[0].confirmed_rule_hash is None
    assert reconciled.claims[0].human_confirmed_at is None
    assert result.level == "CAUTION"


def test_reconcile_resets_confirmation_when_rule_hash_changes():
    document_text = "\u6a19\u6e96\u8cde\u4e0e\u984d\u306e\u5408\u8a08\u309212\u3067\u5272\u308a\u307e\u3059\u3002"
    claim = _claim(document_text)
    inventory = _inventory(document_text, claim)
    changed_rule = _rule(rule_hash="RULE-HASH-2")

    reconciled = reconcile_claim_inventory(
        document_text=document_text,
        inventory=inventory,
        rules_by_id={"RULE-001": changed_rule},
    )
    result = _evaluate(document_text, reconciled, rule=changed_rule)

    assert reconciled.claims[0].match_status == "UNCHECKED"
    assert reconciled.claims[0].confirmed_rule_hash is None
    assert reconciled.claims[0].human_confirmed_at is None
    assert result.level == "CAUTION"
    assert "\u6839\u62e0\u30cf\u30c3\u30b7\u30e5\u4e0d\u4e00\u81f4" in {finding.code for finding in result.findings}


def test_none_effective_dates_do_not_cause_risk_by_themselves():
    document_text = "\u6a19\u6e96\u8cde\u4e0e\u984d\u306e\u5408\u8a08\u309212\u3067\u5272\u308a\u307e\u3059\u3002"
    claim = _claim(document_text)
    inventory = _inventory(document_text, claim)
    source = _source(effective_from=None, effective_to=None)

    result = _evaluate(document_text, inventory, source=source)

    assert result.level == "SAFE"


def test_caution_when_claim_inventory_is_not_confirmed():
    document_text = "\u6a19\u6e96\u8cde\u4e0e\u984d\u306e\u5408\u8a08\u309212\u3067\u5272\u308a\u307e\u3059\u3002"
    claim = _claim(document_text)
    inventory = _inventory(document_text, claim, inventory_confirmed_at=None)

    result = _evaluate(document_text, inventory)

    assert result.level == "CAUTION"
    assert "\u4e3b\u5f35\u4e00\u89a7\u672a\u78ba\u5b9a" in {finding.code for finding in result.findings}


def test_caution_when_claim_classification_is_not_confirmed():
    document_text = "\u6a19\u6e96\u8cde\u4e0e\u984d\u306e\u5408\u8a08\u309212\u3067\u5272\u308a\u307e\u3059\u3002"
    claim = BodyClaim(
        claim_id="CLM-001",
        sentence_text=document_text,
        text_hash=sha256_text(document_text),
        start_offset=0,
        end_offset=len(document_text),
        claim_kind="\u8a08\u7b97",
        requires_verification=True,
        classification_confirmed_at=None,
        time_context="CURRENT",
        match_status="MATCH",
        linked_rule_id="RULE-001",
        confirmed_rule_hash="RULE-HASH-1",
        human_confirmed_at=CONFIRMED_AT,
        normalized_formula=_formula(),
    )
    inventory = _inventory(document_text, claim)

    result = _evaluate(document_text, inventory)

    assert result.level == "CAUTION"
    assert "\u4e3b\u5f35\u5206\u985e\u672a\u78ba\u5b9a" in {finding.code for finding in result.findings}


def test_caution_when_excluded_claim_has_no_reason():
    document_text = "\u3053\u306e\u8a18\u4e8b\u3067\u306f\u5728\u8077\u8001\u9f62\u5e74\u91d1\u3092\u308f\u304b\u308a\u3084\u3059\u304f\u8aac\u660e\u3057\u307e\u3059\u3002"
    claim = BodyClaim(
        claim_id="CLM-INTRO",
        sentence_text=document_text,
        text_hash=sha256_text(document_text),
        start_offset=0,
        end_offset=len(document_text),
        claim_kind="\u305d\u306e\u4ed6\u96d1\u5247\u30fb\u5c0e\u5165\u6587",
        requires_verification=False,
        exclusion_reason=None,
        classification_confirmed_at=CONFIRMED_AT,
        time_context="CURRENT",
    )
    inventory = _inventory(document_text, claim)

    result = _evaluate(document_text, inventory)

    assert result.level == "CAUTION"
    assert "\u7167\u5408\u9664\u5916\u7406\u7531\u306a\u3057" in {finding.code for finding in result.findings}


def test_caution_when_rule_type_is_unsupported_for_safe():
    document_text = "\u7533\u8acb\u671f\u9650\u306f3\u670831\u65e5\u3067\u3059\u3002"
    rule = _rule(rule_type="\u671f\u9650")
    claim = BodyClaim(
        claim_id="CLM-DEADLINE",
        sentence_text=document_text,
        text_hash=sha256_text(document_text),
        start_offset=0,
        end_offset=len(document_text),
        claim_kind="\u671f\u9650",
        requires_verification=True,
        classification_confirmed_at=CONFIRMED_AT,
        time_context="CURRENT",
        match_status="MATCH",
        linked_rule_id="RULE-001",
        confirmed_rule_hash="RULE-HASH-1",
        human_confirmed_at=CONFIRMED_AT,
    )
    inventory = _inventory(document_text, claim)

    result = _evaluate(document_text, inventory, rule=rule)

    assert result.level == "CAUTION"
    assert "\u672a\u5bfe\u5fdc\u30eb\u30fc\u30eb\u7a2e\u5225" in {finding.code for finding in result.findings}


def test_risk_when_current_claim_is_outside_effective_period():
    document_text = "\u6a19\u6e96\u8cde\u4e0e\u984d\u306e\u5408\u8a08\u309212\u3067\u5272\u308a\u307e\u3059\u3002"
    claim = _claim(document_text)
    inventory = _inventory(document_text, claim)
    source = _source(effective_from=date(2025, 4, 1), effective_to=date(2026, 3, 31))

    result = _evaluate(document_text, inventory, source=source)

    assert result.level == "RISK"
    assert "\u9069\u7528\u671f\u9593\u5916" in {finding.code for finding in result.findings}


def test_caution_when_source_review_due_date_has_passed():
    document_text = "\u6a19\u6e96\u8cde\u4e0e\u984d\u306e\u5408\u8a08\u309212\u3067\u5272\u308a\u307e\u3059\u3002"
    claim = _claim(document_text)
    inventory = _inventory(document_text, claim)
    source = _source(review_due_at=date(2026, 6, 24))

    result = _evaluate(document_text, inventory, source=source)

    assert result.level == "CAUTION"
    assert "\u78ba\u8a8d\u671f\u9650\u5207\u308c" in {finding.code for finding in result.findings}


def test_caution_when_rule_context_is_not_complete():
    document_text = "\u6a19\u6e96\u8cde\u4e0e\u984d\u306e\u5408\u8a08\u309212\u3067\u5272\u308a\u307e\u3059\u3002"
    claim = _claim(document_text)
    inventory = _inventory(document_text, claim)
    rule = EvidenceRule(
        rule_id="RULE-001",
        source_id="SRC-001",
        rule_type="\u8a08\u7b97\u5f0f",
        quote_locator="\u5728\u8077\u8001\u9f62\u5e74\u91d1\u306e\u8a08\u7b97\u8aac\u660e",
        source_quote="\u305d\u306e\u6708\u4ee5\u524d1\u5e74\u9593\u306e\u6a19\u6e96\u8cde\u4e0e\u984d\u306e\u5408\u8a08\u00f712",
        condition_scope="\u8cde\u4e0e\u304c\u3042\u308b\u5834\u5408",
        rule_hash="RULE-HASH-1",
        context_status="INCOMPLETE",
        normalized_formula=_formula(),
    )

    result = _evaluate(document_text, inventory, rule=rule)

    assert result.level == "CAUTION"
    assert "\u6839\u62e0\u6587\u8108\u672a\u5b8c\u7d50" in {finding.code for finding in result.findings}


def test_caution_when_source_for_linked_rule_is_missing():
    document_text = "\u6a19\u6e96\u8cde\u4e0e\u984d\u306e\u5408\u8a08\u309212\u3067\u5272\u308a\u307e\u3059\u3002"
    claim = _claim(document_text)
    inventory = _inventory(document_text, claim)

    result = evaluate_claim_verification(
        evaluation_date=EVAL_DATE,
        document_text=document_text,
        inventory=inventory,
        sources_by_id={},
        rules_by_id={"RULE-001": _rule()},
    )

    assert result.level == "CAUTION"
    assert "\u6839\u62e0\u5143\u4e0d\u660e" in {finding.code for finding in result.findings}


def test_caution_when_required_claim_has_no_linked_rule():
    document_text = "\u6a19\u6e96\u8cde\u4e0e\u984d\u306e\u5408\u8a08\u309212\u3067\u5272\u308a\u307e\u3059\u3002"
    claim = BodyClaim(
        claim_id="CLM-NO-RULE",
        sentence_text=document_text,
        text_hash=sha256_text(document_text),
        start_offset=0,
        end_offset=len(document_text),
        claim_kind="\u8a08\u7b97",
        requires_verification=True,
        classification_confirmed_at=CONFIRMED_AT,
        time_context="CURRENT",
        match_status="MATCH",
        linked_rule_id=None,
        confirmed_rule_hash=None,
        human_confirmed_at=CONFIRMED_AT,
        normalized_formula=_formula(),
    )
    inventory = _inventory(document_text, claim)

    result = evaluate_claim_verification(
        evaluation_date=EVAL_DATE,
        document_text=document_text,
        inventory=inventory,
        sources_by_id={"SRC-001": _source()},
        rules_by_id={},
    )

    assert result.level == "CAUTION"
    assert "\u6839\u62e0\u672a\u7d10\u4ed8\u3051" in {finding.code for finding in result.findings}
