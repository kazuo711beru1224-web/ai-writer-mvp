from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Dict, List, Optional

from modules.claim_verification_models import (
    BodyClaim,
    ClaimInventory,
    ClaimVerificationFinding,
    ClaimVerificationResult,
    EvidenceRule,
    EvidenceSource,
    FormulaDetail,
    GateLevel,
    NumberDetail,
    sha256_text,
)


UNSUPPORTED_SAFE_RULE_TYPES = {
    "\u671f\u9650",
    "\u5bfe\u8c61\u8005",
    "\u4f8b\u5916",
}


def _finding(
    *,
    level: GateLevel,
    code: str,
    message: str,
    claim_id: Optional[str] = None,
    rule_id: Optional[str] = None,
    source_id: Optional[str] = None,
) -> ClaimVerificationFinding:
    return ClaimVerificationFinding(
        level=level,
        code=code,
        message=message,
        claim_id=claim_id,
        rule_id=rule_id,
        source_id=source_id,
    )


def _claim_text_changed(*, document_text: str, claim: BodyClaim) -> bool:
    if sha256_text(claim.sentence_text) != claim.text_hash:
        return True

    if claim.start_offset < 0 or claim.end_offset < claim.start_offset:
        return True

    if claim.end_offset > len(document_text):
        return True

    return document_text[claim.start_offset:claim.end_offset] != claim.sentence_text


def _number_conflicts(claim_number: Optional[NumberDetail], rule_number: Optional[NumberDetail]) -> bool:
    if claim_number is None or rule_number is None:
        return False

    return (
        claim_number.value_decimal != rule_number.value_decimal
        or claim_number.unit != rule_number.unit
        or claim_number.condition != rule_number.condition
    )


def _formula_conflicts(claim_formula: Optional[FormulaDetail], rule_formula: Optional[FormulaDetail]) -> bool:
    if claim_formula is None or rule_formula is None:
        return False

    return (
        claim_formula.target_object != rule_formula.target_object
        or claim_formula.target_period != rule_formula.target_period
        or claim_formula.aggregation_type != rule_formula.aggregation_type
        or claim_formula.divisor != rule_formula.divisor
        or claim_formula.formula_normalized.strip() != rule_formula.formula_normalized.strip()
    )


def _date_outside_effective_range(
    *,
    evaluation_date: date,
    source: EvidenceSource,
) -> bool:
    if source.effective_from is not None and evaluation_date < source.effective_from:
        return True

    if source.effective_to is not None and evaluation_date > source.effective_to:
        return True

    return False


def _current_rule_for_claim(
    *,
    claim: BodyClaim,
    rules_by_id: Dict[str, EvidenceRule],
) -> Optional[EvidenceRule]:
    if not claim.linked_rule_id:
        return None

    return rules_by_id.get(claim.linked_rule_id)


def reconcile_claim_inventory(
    *,
    document_text: str,
    inventory: ClaimInventory,
    rules_by_id: Dict[str, EvidenceRule],
) -> ClaimInventory:
    document_changed = sha256_text(document_text) != inventory.document_hash
    claims: List[BodyClaim] = []

    for claim in inventory.claims:
        rule = _current_rule_for_claim(claim=claim, rules_by_id=rules_by_id)
        rule_changed = (
            rule is not None
            and claim.confirmed_rule_hash is not None
            and rule.rule_hash != claim.confirmed_rule_hash
        )

        claim_changed = _claim_text_changed(document_text=document_text, claim=claim)

        if document_changed or claim_changed or rule_changed:
            claims.append(
                replace(
                    claim,
                    match_status="UNCHECKED",
                    confirmed_rule_hash=None,
                    human_confirmed_at=None,
                )
            )
        else:
            claims.append(claim)

    return replace(
        inventory,
        claim_inventory_confirmed_at=None if document_changed else inventory.claim_inventory_confirmed_at,
        claims=claims,
    )


def evaluate_claim_verification(
    *,
    evaluation_date: date,
    document_text: str,
    inventory: ClaimInventory,
    sources_by_id: Dict[str, EvidenceSource],
    rules_by_id: Dict[str, EvidenceRule],
) -> ClaimVerificationResult:
    risk_findings: List[ClaimVerificationFinding] = []
    caution_findings: List[ClaimVerificationFinding] = []

    if sha256_text(document_text) != inventory.document_hash:
        caution_findings.append(
            _finding(
                level="CAUTION",
                code="\u672c\u6587\u30cf\u30c3\u30b7\u30e5\u4e0d\u4e00\u81f4",
                message="\u672c\u6587\u304c\u4e3b\u5f35\u4e00\u89a7\u306e\u78ba\u5b9a\u5f8c\u306b\u5909\u66f4\u3055\u308c\u3066\u3044\u307e\u3059\u3002",
            )
        )

    if inventory.claim_inventory_confirmed_at is None:
        caution_findings.append(
            _finding(
                level="CAUTION",
                code="\u4e3b\u5f35\u4e00\u89a7\u672a\u78ba\u5b9a",
                message="\u672c\u6587\u304b\u3089\u306e\u91cd\u8981\u4e3b\u5f35\u306e\u6d17\u3044\u51fa\u3057\u304c\u4eba\u9593\u306b\u3088\u3063\u3066\u672a\u78ba\u5b9a\u3067\u3059\u3002",
            )
        )

    for claim in inventory.claims:
        rule = _current_rule_for_claim(claim=claim, rules_by_id=rules_by_id)
        source = sources_by_id.get(rule.source_id) if rule is not None else None

        if claim.requires_verification and claim.match_status == "MISMATCH":
            risk_findings.append(
                _finding(
                    level="RISK",
                    code="\u4e3b\u5f35\u4e0d\u4e00\u81f4",
                    message="\u672c\u6587\u306e\u4e3b\u5f35\u304c\u6839\u62e0\u30eb\u30fc\u30eb\u3068\u77db\u76fe\u3057\u3066\u3044\u307e\u3059\u3002",
                    claim_id=claim.claim_id,
                    rule_id=claim.linked_rule_id,
                    source_id=source.source_id if source is not None else None,
                )
            )

        if claim.requires_verification and rule is not None and source is not None:
            if claim.time_context == "CURRENT" and _date_outside_effective_range(
                evaluation_date=evaluation_date,
                source=source,
            ):
                risk_findings.append(
                    _finding(
                        level="RISK",
                        code="\u9069\u7528\u671f\u9593\u5916",
                        message="\u73fe\u5728\u306e\u4e3b\u5f35\u306b\u5bfe\u3057\u3001\u6839\u62e0\u306e\u9069\u7528\u671f\u9593\u304c\u5916\u308c\u3066\u3044\u307e\u3059\u3002",
                        claim_id=claim.claim_id,
                        rule_id=rule.rule_id,
                        source_id=source.source_id,
                    )
                )

            if _number_conflicts(claim.normalized_number, rule.normalized_number):
                risk_findings.append(
                    _finding(
                        level="RISK",
                        code="\u6570\u5024\u4e0d\u4e00\u81f4",
                        message="\u672c\u6587\u306e\u6570\u5024\u304c\u6839\u62e0\u30eb\u30fc\u30eb\u3068\u77db\u76fe\u3057\u3066\u3044\u307e\u3059\u3002",
                        claim_id=claim.claim_id,
                        rule_id=rule.rule_id,
                        source_id=source.source_id,
                    )
                )

            if _formula_conflicts(claim.normalized_formula, rule.normalized_formula):
                risk_findings.append(
                    _finding(
                        level="RISK",
                        code="\u8a08\u7b97\u5f0f\u4e0d\u4e00\u81f4",
                        message="\u672c\u6587\u306e\u8a08\u7b97\u5f0f\u304c\u6839\u62e0\u30eb\u30fc\u30eb\u3068\u77db\u76fe\u3057\u3066\u3044\u307e\u3059\u3002",
                        claim_id=claim.claim_id,
                        rule_id=rule.rule_id,
                        source_id=source.source_id,
                    )
                )

        if _claim_text_changed(document_text=document_text, claim=claim):
            caution_findings.append(
                _finding(
                    level="CAUTION",
                    code="\u4e3b\u5f35\u30cf\u30c3\u30b7\u30e5\u4e0d\u4e00\u81f4",
                    message="\u539f\u5b50\u7684\u4e3b\u5f35\u306e\u6587\u9762\u307e\u305f\u306f\u672c\u6587\u4e0a\u306e\u7bc4\u56f2\u304c\u5909\u66f4\u3055\u308c\u3066\u3044\u307e\u3059\u3002",
                    claim_id=claim.claim_id,
                    rule_id=claim.linked_rule_id,
                )
            )

        if claim.classification_confirmed_at is None:
            caution_findings.append(
                _finding(
                    level="CAUTION",
                    code="\u4e3b\u5f35\u5206\u985e\u672a\u78ba\u5b9a",
                    message="\u4e3b\u5f35\u306e\u7a2e\u5225\u3068\u7167\u5408\u8981\u5426\u304c\u4eba\u9593\u306b\u3088\u3063\u3066\u672a\u78ba\u5b9a\u3067\u3059\u3002",
                    claim_id=claim.claim_id,
                )
            )

        if not claim.requires_verification:
            if not claim.exclusion_reason:
                caution_findings.append(
                    _finding(
                        level="CAUTION",
                        code="\u7167\u5408\u9664\u5916\u7406\u7531\u306a\u3057",
                        message="\u7167\u5408\u4e0d\u8981\u3068\u3059\u308b\u7406\u7531\u304c\u672a\u8a18\u5165\u3067\u3059\u3002",
                        claim_id=claim.claim_id,
                    )
                )
            continue

        if rule is None:
            caution_findings.append(
                _finding(
                    level="CAUTION",
                    code="\u6839\u62e0\u672a\u7d10\u4ed8\u3051",
                    message="\u7167\u5408\u5fc5\u9808\u306e\u4e3b\u5f35\u306b\u6839\u62e0\u30eb\u30fc\u30eb\u304c\u7d10\u4ed8\u3044\u3066\u3044\u307e\u305b\u3093\u3002",
                    claim_id=claim.claim_id,
                    rule_id=claim.linked_rule_id,
                )
            )
            continue

        if source is None:
            caution_findings.append(
                _finding(
                    level="CAUTION",
                    code="\u6839\u62e0\u5143\u4e0d\u660e",
                    message="\u6839\u62e0\u30eb\u30fc\u30eb\u306b\u5bfe\u5fdc\u3059\u308b\u4e00\u6b21\u60c5\u5831\u5143\u304c\u898b\u3064\u304b\u308a\u307e\u305b\u3093\u3002",
                    claim_id=claim.claim_id,
                    rule_id=rule.rule_id,
                    source_id=rule.source_id,
                )
            )
            continue

        if claim.confirmed_rule_hash != rule.rule_hash:
            caution_findings.append(
                _finding(
                    level="CAUTION",
                    code="\u6839\u62e0\u30cf\u30c3\u30b7\u30e5\u4e0d\u4e00\u81f4",
                    message="\u6839\u62e0\u30eb\u30fc\u30eb\u304c\u78ba\u8a8d\u5f8c\u306b\u5909\u66f4\u3055\u308c\u3066\u3044\u307e\u3059\u3002",
                    claim_id=claim.claim_id,
                    rule_id=rule.rule_id,
                    source_id=source.source_id,
                )
            )

        if claim.match_status == "UNCHECKED" or claim.human_confirmed_at is None:
            caution_findings.append(
                _finding(
                    level="CAUTION",
                    code="\u4e3b\u5f35\u672a\u7167\u5408",
                    message="\u7167\u5408\u5fc5\u9808\u306e\u4e3b\u5f35\u304c\u672a\u78ba\u8a8d\u3067\u3059\u3002",
                    claim_id=claim.claim_id,
                    rule_id=rule.rule_id,
                    source_id=source.source_id,
                )
            )

        if rule.rule_type in UNSUPPORTED_SAFE_RULE_TYPES:
            caution_findings.append(
                _finding(
                    level="CAUTION",
                    code="\u672a\u5bfe\u5fdc\u30eb\u30fc\u30eb\u7a2e\u5225",
                    message="\u671f\u9650\u30fb\u5bfe\u8c61\u8005\u30fb\u4f8b\u5916\u306f\u73fe\u884c\u306e\u81ea\u52d5\u7167\u5408\u3067\u306fSAFE\u306b\u3067\u304d\u307e\u305b\u3093\u3002",
                    claim_id=claim.claim_id,
                    rule_id=rule.rule_id,
                    source_id=source.source_id,
                )
            )

        if rule.context_status != "COMPLETE":
            caution_findings.append(
                _finding(
                    level="CAUTION",
                    code="\u6839\u62e0\u6587\u8108\u672a\u5b8c\u7d50",
                    message="\u6839\u62e0\u30eb\u30fc\u30eb\u306e\u5bfe\u8c61\u6761\u4ef6\u30fb\u4f8b\u5916\u30fb\u6642\u70b9\u304c\u81ea\u5df1\u5b8c\u7d50\u3057\u3066\u3044\u307e\u305b\u3093\u3002",
                    claim_id=claim.claim_id,
                    rule_id=rule.rule_id,
                    source_id=source.source_id,
                )
            )

        if evaluation_date > source.review_due_at:
            caution_findings.append(
                _finding(
                    level="CAUTION",
                    code="\u78ba\u8a8d\u671f\u9650\u5207\u308c",
                    message="\u4e00\u6b21\u60c5\u5831\u306e\u518d\u78ba\u8a8d\u671f\u9650\u3092\u904e\u304e\u3066\u3044\u307e\u3059\u3002",
                    claim_id=claim.claim_id,
                    rule_id=rule.rule_id,
                    source_id=source.source_id,
                )
            )

    if risk_findings:
        return ClaimVerificationResult(level="RISK", findings=risk_findings + caution_findings)

    if caution_findings:
        return ClaimVerificationResult(level="CAUTION", findings=caution_findings)

    return ClaimVerificationResult(level="SAFE", findings=[])
