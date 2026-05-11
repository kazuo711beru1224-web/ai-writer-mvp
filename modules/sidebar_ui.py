# modules/sidebar_ui.py
from __future__ import annotations

import streamlit as st


def render_sidebar_ui(
    *,
    app_title: str,
    outputs_dir: str,
    logs_dir: str,
    current_menu: str,
    current_has_key: bool,
) -> tuple[str, str]:
    st.sidebar.markdown(f"## {app_title}")
    st.sidebar.markdown("### 🔐 APIキー（本生成用）")

    # ✅ ここは key のみ。value/index は渡さない（警告・Wクリック系の温床を潰す）
    api_key = st.sidebar.text_input(
        "OpenAI APIキー",
        type="password",
        key="sidebar__api_key_widget",
        help="この画面を開いている間だけ使われます。アプリ側に保存しません。",
    )

    st.sidebar.caption(f"現在：{'本生成（APIキーあり）' if current_has_key else 'デモ生成（APIキーなし）'}")
    st.sidebar.caption(f"outputs_dir: {outputs_dir}")
    st.sidebar.caption(f"logs_dir: {logs_dir}")
    st.sidebar.divider()

    st.sidebar.markdown("### メニュー")

    menu_options = [
        "ホーム",
        "記事モード（SEOライティング）",
        "文章チェック（手動入力）",
        "生成履歴",
        "⚙ アプリ情報",
    ]

    # ✅ state が壊れてたら救済（選択肢外を防ぐ）
    if st.session_state.get("sidebar__menu_widget") not in menu_options:
        st.session_state["sidebar__menu_widget"] = "ホーム"

    # ✅ ここも key のみ（index/value を渡さない）
    menu = st.sidebar.radio(
        "メニュー",
        options=menu_options,
        key="sidebar__menu_widget",
    )

    return menu, api_key
