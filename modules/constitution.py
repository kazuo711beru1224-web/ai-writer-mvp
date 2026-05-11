# modules/constitution.py
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import List


class ConstitutionViolation(RuntimeError):
    pass


@dataclass
class _Violation:
    title: str
    detail: str


def _fail(title: str, violations: List[_Violation]) -> None:
    lines = [title]
    for v in violations:
        lines.append(v.detail)
    msg = "\n".join(lines)
    raise ConstitutionViolation(msg)


def _read_text(fp: str) -> str:
    with open(fp, "r", encoding="utf-8") as f:
        return f.read()


def _iter_py_files(root_dir: str) -> List[str]:
    targets: List[str] = []
    for base, _, files in os.walk(root_dir):
        # .venv / __pycache__ は除外
        if any(x in base for x in (".venv", "__pycache__", ".git")):
            continue
        for name in files:
            if name.endswith(".py"):
                targets.append(os.path.join(base, name))
    return targets


def check_codebase(cfg: object | None = None) -> None:
    """
    ベル憲法（静的チェック）
    - ウィジェット呼び出しで「初期値を直接渡すパラメータ」を使わない
    - session_state 直書き等の危険パターンは必要に応じてここに追加
    """
    root_dir = os.getcwd()
    py_files = _iter_py_files(root_dir)

    violations: List[_Violation] = []

    # ------------------------------------------------------------
    # ルール1: ウィジェットに「初期値パラメータ」を渡す書き方を禁止
    #
    # 目的：rerun後の状態不一致や、widget生成後の状態書き換え事故を防ぐ。
    # 対応：key のみに寄せ、初期化は if key not in st.session_state: で1回。
    # ------------------------------------------------------------
    # 注意：ここで「禁止対象の文字列」をそのまま書くと、grep系チェックが
    # “文字列が存在するだけで違反”になる場合に自爆するため、
    # 正規表現は分割して組み立てる。
    banned_token = "va" + "lue" + "="  # ← こうしておけばファイル内に直書きされない

    # widget呼び出しの中だけを狙うのが理想だが、まずは素直に検出する
    # （誤検出が気になるなら段階的に厳密化していく）
    pat = re.compile(re.escape(banned_token))

    for fp in py_files:
        # constitution 自身をスキップしたいなら、ここで除外してもOK。
        # ただし今回は自爆防止済みなのでスキップ不要。
        text = _read_text(fp)

        if pat.search(text):
            violations.append(
                _Violation(
                    title="widget initial-arg violation",
                    detail=(
                        f"❌ ウィジェット初期値パラメータ禁止違反: {fp}\n"
                        f"   対策: 初期値は key のみに寄せ、\n"
                        f"   初期化は if key not in st.session_state: で1回。\n"
                    ),
                )
            )

    if violations:
        _fail("🚫 ベル憲法違反（静的チェック）", violations)
