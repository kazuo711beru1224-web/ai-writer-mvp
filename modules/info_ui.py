from __future__ import annotations

import os
import glob
import streamlit as st


def render_info_ui(outputs_dir: str, logs_dir: str, openai_api_key: str) -> None:
    st.markdown("## ⚙ アプリ情報")
    st.write("動作モードや保存状況を確認できます。")
    st.divider()

    use_real_api = bool(openai_api_key and openai_api_key.strip())

    st.markdown("### 動作モード")
    st.write(f"現在：{'本生成（API使用）' if use_real_api else 'デモ生成（API未使用）'}")

    st.divider()
    st.markdown("### 保存状況")

    files = glob.glob(os.path.join(outputs_dir, "output_*.md"))
    st.write(f"保存された文章（テキスト）：{len(files)} 件")

    # ★ベル憲法：保存場所（パス）や内部情報は購入者に出さない
