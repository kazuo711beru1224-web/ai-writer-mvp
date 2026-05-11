# modules/quality_gate.py
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Tuple


@dataclass
class GateResult:
    ok: bool
    score: int
    issues: List[str]
    notes: List[str]


def _count_chars(text: str) -> int:
    return len(text or "")


def _has_title_like(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    # 先頭行がタイトルっぽい
    first = t.splitlines()[0].strip()
    if not first:
        return False
    # Markdownの # か、日本語タイトルっぽさ
    if first.startswith("#"):
        return True
    if "【タイトル】" in first or "タイトル" in first:
        return True
    # 1行目が短めならタイトルとみなす（雑だけど実用）
    return len(first) <= 80


def _has_h2_or_heading(text: str) -> bool:
    # Markdown見出し or "H2："表記
    return bool(re.search(r"(^|\n)##\s+.+", text)) or ("H2" in text)


def _has_faq(text: str) -> bool:
    return "FAQ" in text or "よくある質問" in text


def _has_refs(refs: str) -> bool:
    return bool((refs or "").strip())


def judge_quality(text: str, refs: str = "", suggest: str = "") -> GateResult:
    """
    ✅ MVP品質ゲート（まずは壊れない・分かりやすい判定）
    - 文字数
    - タイトル
    - 見出し
    - FAQ（推奨）
    - 根拠欄（推奨）
    """
    issues: List[str] = []
    notes: List[str] = []

    n = _count_chars(text)

    # ---- 必須（落第条件）----
    if n < 600:
        issues.append("文字数が少なすぎます（目安：600文字以上）。")
    if not _has_title_like(text):
        issues.append("タイトルが見つかりません（先頭行をタイトルにしてください）。")
    if not _has_h2_or_heading(text):
        issues.append("見出し（H2/##）が見つかりません。構造が弱いです。")

    # ---- 推奨（警告）----
    if n < 1500:
        notes.append("文字数がやや少なめです（目安：1500文字以上だと安定）。")
    if not _has_faq(text):
        notes.append("FAQがありません（あると読者満足とSEOに有利になりやすい）。")
    if not _has_refs(refs):
        notes.append("参考URL/資料名が未入力です（事実系の記事は根拠を入れると安全）。")
    if not (suggest or "").strip():
        notes.append("サジェスト/関連KWが未入力です（材料が残ると再現性が上がります）。")

    score = 100
    score -= 25 * len(issues)
    score -= 5 * len(notes)
    score = max(0, score)

    ok = len(issues) == 0
    return GateResult(ok=ok, score=score, issues=issues, notes=notes)


def append_quality_log(logs_dir: str, result: GateResult, meta: dict) -> None:
    """
    logs/quality_log.csv に追記（MVP）
    """
    out_dir = Path(logs_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "quality_log.csv"

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = [
        ts,
        "OK" if result.ok else "NG",
        str(result.score),
        meta.get("title", ""),
        str(meta.get("chars", "")),
        " / ".join(result.issues) if result.issues else "",
        " / ".join(result.notes) if result.notes else "",
    ]
    header = "datetime,status,score,title,chars,issues,notes\n"
    row = ",".join([_escape_csv(x) for x in line]) + "\n"

    if not path.exists():
        path.write_text(header, encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write(row)


def _escape_csv(s: str) -> str:
    s = (s or "").replace('"', '""')
    if any(c in s for c in [",", "\n", "\r"]):
        return f'"{s}"'
    return s
