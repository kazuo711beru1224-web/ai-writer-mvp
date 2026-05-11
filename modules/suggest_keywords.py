# modules/suggest_keywords.py
# ✅ v2026-01-20-SUGGEST
# 全部コピペで新規作成

from __future__ import annotations

from typing import List


def _uniq(seq: List[str]) -> List[str]:
    seen = set()
    out = []
    for s in seq:
        s = (s or "").strip()
        if not s:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def build_suggest_keywords(main_kw: str, sub_kws: List[str], topic: str = "") -> List[str]:
    """
    外部APIなしで「材料の見える化」用にキーワード候補を組み立てる。
    ※本物のサジェスト取得は別途APIが必要。MVPは透明性目的で十分。
    """
    main_kw = (main_kw or "").strip()
    topic = (topic or "").strip()
    sub_kws = _uniq([k.strip() for k in (sub_kws or []) if k.strip()])

    base = []
    if main_kw:
        base.append(main_kw)
    base += sub_kws
    if topic:
        base.append(topic)

    # ざっくり「よく使われる関連語」を付け足す（透明性・材料提示用）
    suffixes = [
        "とは",
        "意味",
        "やり方",
        "使い方",
        "コツ",
        "注意点",
        "初心者",
        "上達",
        "練習方法",
        "効果",
        "メリット",
        "デメリット",
        "比較",
        "おすすめ",
        "よくある質問",
    ]

    out = []
    for k in base:
        out.append(k)
        for s in suffixes:
            if len(k) >= 2:
                out.append(f"{k} {s}")

    return _uniq(out)[:40]
