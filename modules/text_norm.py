# modules/text_norm.py
from __future__ import annotations

import re
from typing import List


_CODE_FENCE_OPEN_RE = re.compile(r"^\s*```([a-zA-Z0-9_-]+)?\s*$")


def strip_outer_code_fence(text: str) -> str:
    """
    入力が
    ```markdown
    ...
    ```
    のような「外側のコードフェンス」で包まれている時だけ剥がす。

    - 先頭が ``` で始まらなければ何もしない
    - 3行未満なら何もしない
    - 1行目が ``` / ```markdown 等に一致しなければ何もしない
    - 最終行が ``` 単独でなければ何もしない

    ※中身の ``` は触らない（安全第一）
    """
    if not text:
        return ""

    s = text.strip()
    if not s.startswith("```"):
        return text

    lines = s.splitlines()
    if len(lines) < 3:
        return text

    if not _CODE_FENCE_OPEN_RE.match(lines[0].strip()):
        return text

    if lines[-1].strip() != "```":
        return text

    inner = "\n".join(lines[1:-1]).strip("\n")
    return inner


def normalize_lines(text: str) -> str:
    """改行の揺れなど最低限の正規化（必要最小限）"""
    if not text:
        return ""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def build_ai_meta(main_kw: str, sub_kws: List[str], user_refs: str, user_suggest: str) -> dict:
    """
    「AIが参考にしたもの」を、アプリとして“透明性”を持って保存・表示するためのメタ情報。

    ここで言う「参考にした」は、
    - 外部検索ではなく
    - “AIに渡した根拠（入力）” と “AIに渡した関連KW（入力＋自動）”
    を指す（ベル憲法：嘘をつかない）。
    """
    main_kw = (main_kw or "").strip()
    sub_clean = [s.strip() for s in (sub_kws or []) if s and s.strip()]

    refs_clean = normalize_lines(user_refs or "").strip()
    suggest_clean = normalize_lines(user_suggest or "").strip()

    # 自動サジェスト（最低限）：メインKW＋サブKW
    auto_suggest = [main_kw] if main_kw else []
    auto_suggest += sub_clean

    # 表示用：入力＋自動 を合成（重複は潰す）
    merged = []
    if suggest_clean:
        for line in suggest_clean.splitlines():
            t = line.strip()
            if t:
                merged.append(t)
    for t in auto_suggest:
        if t and t not in merged:
            merged.append(t)

    return {
        "refs_used": refs_clean,               # AIに渡した根拠（入力）
        "suggest_used": "\n".join(merged),     # AIに渡した関連KW（入力＋自動）
    }
