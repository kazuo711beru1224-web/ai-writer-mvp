# modules/constitution_ui.py
from __future__ import annotations

from typing import Callable
import streamlit as st


def _safe_msg(e: Exception) -> str:
    """画面表示用：改行や長文を潰して、出し過ぎ事故を防ぐ。"""
    s = str(e) or e.__class__.__name__
    s = s.replace("\r", " ").replace("\n", " ").strip()
    return s[:800]


def stop_with_red_panel(title: str, detail: str) -> None:
    """ベル憲法違反を“赤字で停止”させる最終ゲート。"""
    st.error(title)
    # detail はユーザーの入力やパス等が混ざる可能性があるので整形して表示
    st.code((detail or "").strip(), language="text")
    st.stop()


def run_with_constitution(guard_fn: Callable[[], None]) -> None:
    """
    ベル憲法2（強制装置）：
    - 憲法違反を検知したら、必ず赤字で停止（st.stop）
    - 例外は握り潰さない（続行させない）
    - 画面には安全に整形した情報だけ出す
    """
    try:
        guard_fn()
    except Exception as e:
        detail = f"{e.__class__.__name__}: {_safe_msg(e)}"
        stop_with_red_panel("🚫 ベル憲法違反で停止しました", detail)
