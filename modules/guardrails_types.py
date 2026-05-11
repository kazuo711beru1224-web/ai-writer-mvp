from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal, Optional, Sequence, Tuple


RiskLevel = Literal["SAFE", "CAUTION", "RISK"]


@dataclass(frozen=True)
class Finding:
    """
    検疫ログ1件分の情報を保持する不変オブジェクト。
    - samples は後方互換維持のため Optional。
    - UI/ログ出力で扱いやすいように、受け取った samples は tuple 化して保持する。
    """
    level: RiskLevel
    code: str
    message: str
    samples: Optional[Tuple[str, ...]] = None

    @staticmethod
    def _to_samples(value: Optional[Iterable[object]]) -> Optional[Tuple[str, ...]]:
        if value is None:
            return None
        out: list[str] = []
        for x in value:
            s = str(x).strip()
            if not s:
                continue
            out.append(s)
        return tuple(out) if out else None

    def __post_init__(self) -> None:
        # frozen dataclass なので object.__setattr__ を使う
        object.__setattr__(self, "samples", self._to_samples(self.samples))


@dataclass(frozen=True)
class GuardrailResult:
    """
    検疫結果の集約。
    - level は findings の最大リスク。
    - findings は不変（tuple）で保持し、誤って後から書き換えられないようにする。
    """
    level: RiskLevel
    findings: Tuple[Finding, ...] = ()

    @staticmethod
    def _to_findings(value: Optional[Iterable[Finding]]) -> Tuple[Finding, ...]:
        if not value:
            return ()
        out: list[Finding] = []
        for f in value:
            if isinstance(f, Finding):
                out.append(f)
        return tuple(out)

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", self._to_findings(self.findings))


def max_level_from_list(levels: Sequence[RiskLevel]) -> RiskLevel:
    """
    SAFE < CAUTION < RISK の最大を返す。
    空なら SAFE。
    """
    if not levels:
        return "SAFE"
    if "RISK" in levels:
        return "RISK"
    if "CAUTION" in levels:
        return "CAUTION"
    return "SAFE"