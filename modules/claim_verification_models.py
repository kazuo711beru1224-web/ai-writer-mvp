from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from hashlib import sha256
from typing import Dict, List, Literal, Optional


GateLevel = Literal["SAFE", "CAUTION", "RISK"]

RuleType = Literal[
    "\u6570\u5b57",
    "\u8a08\u7b97\u5f0f",
    "\u671f\u9650",
    "\u5bfe\u8c61\u8005",
    "\u4f8b\u5916",
]

ContextStatus = Literal["UNREVIEWED", "COMPLETE", "INCOMPLETE"]
MatchStatus = Literal["UNCHECKED", "MATCH", "MISMATCH"]
TimeContext = Literal["CURRENT", "HISTORICAL", "FUTURE"]

ClaimKind = Literal[
    "\u6570\u5b57",
    "\u8a08\u7b97",
    "\u671f\u9650",
    "\u5bfe\u8c61\u6761\u4ef6",
    "\u6cd5\u7684\u30fb\u533b\u7642\u7684\u5224\u65ad",
    "\u305d\u306e\u4ed6\u96d1\u5247\u30fb\u5c0e\u5165\u6587",
]


def sha256_text(text: str) -> str:
    return sha256(str(text or "").encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    url: str
    verifier: str
    doc_name: str
    last_checked_at: date
    review_due_at: date
    raw_text_extract: str
    published_at: Optional[date] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


@dataclass(frozen=True)
class NumberDetail:
    value_str: str
    unit: str
    condition: str

    @property
    def value_decimal(self) -> Decimal:
        return Decimal(self.value_str)


@dataclass(frozen=True)
class FormulaDetail:
    target_object: str
    target_period: str
    aggregation_type: str
    divisor: int
    formula_normalized: str
    variables: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EvidenceRule:
    rule_id: str
    source_id: str
    rule_type: RuleType
    quote_locator: str
    source_quote: str
    condition_scope: str
    rule_hash: str
    context_status: ContextStatus = "UNREVIEWED"
    normalized_number: Optional[NumberDetail] = None
    normalized_formula: Optional[FormulaDetail] = None


@dataclass(frozen=True)
class BodyClaim:
    claim_id: str
    sentence_text: str
    text_hash: str
    start_offset: int
    end_offset: int
    claim_kind: ClaimKind
    requires_verification: bool
    exclusion_reason: Optional[str] = None
    classification_confirmed_at: Optional[date] = None
    time_context: TimeContext = "CURRENT"
    match_status: MatchStatus = "UNCHECKED"
    linked_rule_id: Optional[str] = None
    confirmed_rule_hash: Optional[str] = None
    human_confirmed_at: Optional[date] = None
    normalized_number: Optional[NumberDetail] = None
    normalized_formula: Optional[FormulaDetail] = None


@dataclass(frozen=True)
class ClaimInventory:
    document_hash: str
    claims: List[BodyClaim] = field(default_factory=list)
    claim_inventory_confirmed_at: Optional[date] = None


@dataclass(frozen=True)
class ClaimVerificationFinding:
    level: GateLevel
    code: str
    message: str
    claim_id: Optional[str] = None
    rule_id: Optional[str] = None
    source_id: Optional[str] = None


@dataclass(frozen=True)
class ClaimVerificationResult:
    level: GateLevel
    findings: List[ClaimVerificationFinding] = field(default_factory=list)
