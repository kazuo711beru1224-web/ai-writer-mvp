from __future__ import annotations

import re
from typing import List

from .guardrails_types import Finding


def _normalize(text: str) -> str:
    if not text:
        return ""
    t = text
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("　", " ")
    t = t.replace("，", ",").replace("．", ".")
    return t


def _split_paragraphs(text: str) -> List[str]:
    t = _normalize(text)
    parts = re.split(r"\n\s*\n+", t)
    return [p.strip() for p in parts if p.strip()]


def _has_all(text: str, patterns: List[str]) -> bool:
    return all(re.search(p, text) for p in patterns)


def _window_hits(text: str, patterns: List[str], window: int = 260, step: int = 60) -> bool:
    t = _normalize(text)
    if len(t) <= window:
        return _has_all(t, patterns)
    for i in range(0, len(t) - window + 1, step):
        chunk = t[i : i + window]
        if _has_all(chunk, patterns):
            return True
    return False


def evaluate_taxlaw_rules(body_text: str, evidence_text: str = "") -> List[Finding]:
    """
    税・法専用の検疫レイヤー。
    「制度Aの数字を制度Bに貼る」混同ペアを拾って RISK/CAUTION を返す。
    """
    body = _normalize(body_text)
    paras = _split_paragraphs(body)

    findings: List[Finding] = []

    # -------------------------
    # ルールA：110万円 × 相続税/基礎控除（混同）
    # -------------------------
    ptn_110 = r"110\s*万\s*円"
    ptn_sozoku = r"相続税"
    ptn_kiso = r"基礎控除"

    hit_a = any(_has_all(p, [ptn_110, f"({ptn_sozoku}|{ptn_kiso})"]) for p in paras)
    if not hit_a:
        hit_a = _window_hits(body, [ptn_110, f"({ptn_sozoku}|{ptn_kiso})"])

    if hit_a:
        findings.append(
            Finding(
                level="RISK",
                code="MIXUP_110_SOUZOKU",
                message=(
                    "「110万円」と「相続税/基礎控除」が近接しています。"
                    "110万円は相続時精算課税（贈与税側）の基礎控除として扱われる数字で、"
                    "相続税の基礎控除とは分けて説明する必要があります。"
                ),
            )
        )

    # -------------------------
    # ルールB：配偶者控除/軽減 × 4,000万円（古い数字疑い）
    # -------------------------
    ptn_spouse = r"配偶者"
    ptn_koujo = r"(控除|軽減)"
    ptn_4000 = r"4\s*,?\s*000\s*万\s*円"

    hit_b = any(_has_all(p, [ptn_spouse, ptn_koujo, ptn_4000]) for p in paras)
    if hit_b:
        findings.append(
            Finding(
                level="RISK",
                code="SPOUSE_4000_OLD",
                message=(
                    "「配偶者の控除/軽減」に「4,000万円」が出ています。"
                    "制度説明として古い表現の可能性が高いので、一次情報で確認し、"
                    "現在の説明軸（法定相続分・一定額など）に合わせて書き直してください。"
                ),
            )
        )

    # -------------------------
    # ルールC：相続税の基礎控除に触れているのに 3,000万/600万がゼロ
    # -------------------------
    talks_kiso = bool(re.search(r"相続税", body) and re.search(r"基礎控除", body))
    has_3000 = bool(re.search(r"3\s*,?\s*000\s*万\s*円", body))
    has_600 = bool(re.search(r"600\s*万\s*円", body))

    if talks_kiso and (not has_3000) and (not has_600):
        findings.append(
            Finding(
                level="CAUTION",
                code="SOZOKU_KISO_NUM_MISSING",
                message=(
                    "本文で「相続税の基礎控除」に触れていますが、代表的な計算要素"
                    "（3,000万円・600万円など）が本文にありません。"
                    "数字を出すなら一次情報で確認して追記するか、一般論に留めてください。"
                ),
            )
        )

    return findings