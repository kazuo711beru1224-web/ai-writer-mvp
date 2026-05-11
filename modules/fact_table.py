# modules/fact_table.py
from __future__ import annotations

import re
from typing import Any, Dict

import pandas as pd


RISK_KEYWORDS = {
    "政治": ["選挙", "首相", "政党", "内閣", "与党", "野党", "公約", "国会"],
    "法律": ["違法", "合法", "罰", "訴訟", "契約", "法律", "弁護士"],
    "医療": ["病気", "治る", "薬", "診断", "症状", "治療", "副作用"],
    "金融": ["投資", "株", "利回り", "NISA", "FX", "暗号資産", "保険", "ローン"],
}

RISK_ORDER = ["政治", "法律", "医療", "金融"]


def judge_risk_category(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return "一般"

    for cat in RISK_ORDER:
        kws = RISK_KEYWORDS.get(cat, [])
        for kw in kws:
            if kw in t:
                return cat

    return "一般"


def _extract_claims(text: str, n: int = 5) -> list[str]:
    parts = re.split(r"[。\n]+", text)
    parts = [p.strip() for p in parts if p.strip()]
    parts = sorted(parts, key=len, reverse=True)
    return parts[:n] if parts else []


def build_fact_table(
    text: str,
    user_references_text: str = "",
    **kwargs,
) -> Dict[str, Any]:
    claims = _extract_claims(text, n=5)

    rows = []
    has_refs = bool(user_references_text.strip())
    for c in claims:
        rows.append(
            {
                "claim": c,
                "source": "ユーザー入力の根拠あり" if has_refs else "要一次情報",
            }
        )

    df = pd.DataFrame(rows)
    return {"df": df, "claims": claims}
