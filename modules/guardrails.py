# modules/guardrails.py
from __future__ import annotations

import importlib
import re
from typing import Callable, List, Optional

from .guardrails_types import Finding, GuardrailResult, max_level_from_list
from .guardrails_taxlaw import evaluate_taxlaw_rules


def _normalize(text: str) -> str:
    if not text:
        return ""
    t = str(text)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("　", " ")
    return t


def _looks_like_taxlaw_topic(body_text: str, suggest_text: str, evidence_text: str) -> bool:
    """
    テーマ判定（最小）：
    税・相続・贈与・控除・申告・基礎控除などが含まれたら税レイヤーを走らせる。
    """
    t = _normalize(body_text) + "\n" + _normalize(suggest_text) + "\n" + _normalize(evidence_text)
    keywords = [
        "相続", "贈与", "相続税", "贈与税", "相続時精算課税",
        "基礎控除", "控除", "軽減", "税務署", "申告", "税率", "課税",
    ]
    return any(k in t for k in keywords)


def _extract_numbers(body_text: str) -> List[str]:
    """
    ざっくり数字抽出（年号含む）。共通フェンスの材料。
    """
    t = _normalize(body_text)

    # 例: 110万円 / 10か月 / 2015 / 令和6年 / 3,000万円 / 2000円 など
    patterns = [
        r"\d[\d,]*\s*万\s*円",
        r"\d+\s*(?:か月|ヶ月|ヵ月|月|年|日|%|％)",  # ★非キャプチャで“数字＋単位”を拾う
        r"(?:令和|平成|昭和)\s*\d+\s*年",
        r"\b(?:19|20)\d{2}\b",
        r"\d[\d,]*\s*円",
    ]

    hits: List[str] = []
    for p in patterns:
        hits.extend(re.findall(p, t))

    # 重複除去（順序保持）
    uniq: List[str] = []
    for x in hits:
        s = str(x).strip()
        if s and s not in uniq:
            uniq.append(s)
    return uniq


def _core_fallback(body_text: str, evidence_text: str, suggest_text: str) -> GuardrailResult:
    """
    guardrails_core が無い場合の最低限フェンス。
    「数字があるのに根拠が空」を止める。
    """
    body = _normalize(body_text)
    evidence = _normalize(evidence_text)

    findings: List[Finding] = []

    numbers = _extract_numbers(body)
    if numbers and not evidence.strip():
        findings.append(
            Finding(
                level="RISK",
                code="EVIDENCE_MISSING",
                message="本文に数字（年号・金額・期限など）が含まれていますが、根拠メモが空です。一次情報（URL/資料名/要点）を入力してください。",
                samples=numbers[:12],
            )
        )

    level = max_level_from_list([f.level for f in findings]) if findings else "SAFE"
    return GuardrailResult(level=level, findings=findings)


def _load_core_evaluator() -> Optional[Callable[[str, str, str], GuardrailResult]]:
    """
    既存の guardrails_core があればそれを使う。
    期待する関数名：
      - evaluate_guardrails_core(body_text, evidence_text, suggest_text) -> GuardrailResult
    """
    try:
        mod = importlib.import_module("modules.guardrails_core")
    except Exception:
        return None

    fn = getattr(mod, "evaluate_guardrails_core", None)
    if callable(fn):
        return fn
    return None


def evaluate_guardrails(body_text: str, evidence_text: str = "", suggest_text: str = "") -> GuardrailResult:
    """
    二段構えの最終入口：
      1) 共通フェンス（guardrails_coreがあれば使用、無ければfallback）
      2) 税・法ルールパック（該当時だけappendして危険度を再計算）
    """
    core_fn = _load_core_evaluator()

    if core_fn is not None:
        core_res = core_fn(body_text, evidence_text, suggest_text)
    else:
        core_res = _core_fallback(body_text, evidence_text, suggest_text)

    findings = list(core_res.findings)

    if _looks_like_taxlaw_topic(body_text, suggest_text, evidence_text):
        findings.extend(evaluate_taxlaw_rules(body_text, evidence_text))

    final_level = max_level_from_list([f.level for f in findings]) if findings else "SAFE"
    return GuardrailResult(level=final_level, findings=findings)