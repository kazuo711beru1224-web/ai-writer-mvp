# modules/consent_admin_ui.py
from __future__ import annotations

from typing import Any
import streamlit as st


def render_consent_admin_ui(**kwargs: Any) -> None:
    _ = kwargs

    st.markdown("## 同意履歴（管理）")
    st.write("この画面では、利用規約に関する確認内容をまとめて表示します。")
    st.write("安心して使い始められるように、利用前に知っておきたいポイントを、ここで整理して確認できます。")

    st.divider()

    st.markdown("#### この画面の役割")
    st.write("・利用規約で伝えている基本的な考え方を、いつでも見直せるようにすること")
    st.write("・どこまでがアプリの役割で、どこからが利用者の判断かを分かりやすく保つこと")
    st.write("・利用前に確認しておきたい内容を、迷わず見直せるようにすること")

    st.divider()

    st.markdown("#### ここで確認できること")
    st.write("・このアプリが、どのような目的のサポートツールか")
    st.write("・生成された文章を使うときに、どのような点に注意すべきか")
    st.write("・利用者が最終的に確認し、判断する範囲がどこか")

    st.divider()

    st.write("利用規約の内容は、「利用規約」の画面でいつでも確認できます。")
    st.write("このアプリは、使い方が分かりやすく、安心して前に進みやすいことを大切にしています。")