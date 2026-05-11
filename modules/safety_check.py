# modules/safety_check.py
# ✅ v2026-01-19-SAFETY-GATE

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Dict


DANGER_CATEGORIES = {
    "金融": [
        "保険", "NISA", "iDeCo", "年金", "税", "非課税", "控除", "利回り", "投資", "株", "債券",
        "金利", "ローン", "クレジット", "金融庁", "国税庁", "為替", "円建て", "外貨建て",
    ],
    "医療": [
        "治る", "治療", "薬", "副作用", "病気", "医師", "診断", "症状", "手術",
        "厚労省", "ガイドライン", "臨床", "予防", "効果", "改善",
    ],
    "法律": [
        "違法", "合法", "弁護士", "訴訟", "契約", "罰", "刑", "民事", "裁判",
        "法務省", "判例", "規約", "条例",
    ],
}

# 断定・煽り・誇張（危険）
BANNED_WORDS = [
    "必ず", "絶対", "100%", "１００％", "確実", "保証", "誰でも", "完全に", "魔法", "一発で",
    "最強", "絶対に損しない", "確実に儲かる", "必勝",
]

# 「一般化しすぎ」注意
GENERALIZING_WORDS = [
    "多くの", "一般に", "たいてい", "みんな", "ほとんど", "誰もが",
]

# 数字検出（％、円、日、倍、年、回など）
NUMERIC_PATTERN = re.compile(
    r"(\d+(\.\d+)?)\s*(%|％|円|日|週間|ヶ月|か月|年|倍|回|人|万円|千円|円台)"
)

# URLっぽいもの
URL_PATTERN = re.compile(r"(https?://[^\s\)）]+)")


@dataclass
class GateResult:
    danger_category: str  # "金融"/"医療"/"法律"/"一般"
    banned_hits: List[str]
    general_hits: List[str]
    numeric_hits: List[str]
    url_hits: List[str]
    requires_sources: bool
    passed: bool
    reasons: List[str]


def detect_category(text: str) -> str:
    t = text or ""
    for cat, kws in DANGER_CATEGORIES.items():
        for kw in kws:
            if kw in t:
                return cat
    return "一般"


def analyze(text: str) -> GateResult:
    text = text or ""
    cat = detect_category(text)

    banned_hits = [w for w in BANNED_WORDS if w in text]
    general_hits = [w for w in GENERALIZING_WORDS if w in text]

    numeric_hits = []
    for m in NUMERIC_PATTERN.finditer(text):
        numeric_hits.append(m.group(0))

    url_hits = []
    for m in URL_PATTERN.finditer(text):
        url_hits.append(m.group(1))

    # 危険カテゴリ or 数字/固有名詞っぽい（ここでは数字で代用）なら出典必須
    requires_sources = (cat in ("金融", "医療", "法律")) or (len(numeric_hits) > 0)

    reasons: List[str] = []
    passed = True

    # 断定語は即NG（危険カテゴリは厳格）
    if banned_hits:
        passed = False
        reasons.append("断定・誇張語が含まれています（修正必須）")

    # 一般化語は警告（危険カテゴリではNG扱い）
    if general_hits and cat in ("金融", "医療", "法律"):
        passed = False
        reasons.append("一般化表現が含まれています（危険カテゴリでは修正必須）")

    # 出典が必要なのにURL/資料名が無い場合はNG（URLがない＝一次情報が無い可能性）
    # ※ここは「一次情報URL or 資料名」を最終的に fact_table で埋める想定
    if requires_sources and len(url_hits) == 0:
        # ただし、記事本文にURLがなくても「根拠表」で資料名を出せればOKなので、
        # ここでは「仮NG」にせず、check_ui側の根拠表ゲートで確定判定する
        reasons.append("危険カテゴリ/数字あり：根拠（一次情報URL/資料名）が必要です")

    return GateResult(
        danger_category=cat,
        banned_hits=banned_hits,
        general_hits=general_hits,
        numeric_hits=numeric_hits,
        url_hits=url_hits,
        requires_sources=requires_sources,
        passed=passed,
        reasons=reasons,
    )
