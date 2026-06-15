from __future__ import annotations

from typing import Any, Optional

import streamlit as st


def render_official_procedure_ui(
    logs_dir: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """公式手続きナビの空画面。まだAI生成は行わない。"""

    st.markdown("## 公式手続きナビ（登記・役所・税金）")
    st.write("登記、役所、税金、補助金、法人手続きなど、間違えると困る手続きを整理するための画面です。")
    st.write("この画面では、AIが勝手に断定せず、一次情報・正式な書類名・確認先を分けて表示していきます。")

    st.warning(
        "この画面は、公式手続きを整理するための道案内です。"
        "AIの回答だけで申請や登記を進めないでください。"
        "必ず、公式サイト、管轄窓口、または専門家に確認してください。"
    )

    st.divider()

    st.info("現在は準備中です。まずは画面だけを追加しています。AI生成や自動判定はまだ行いません。")

    st.markdown("### 今後ここに入れる予定の項目")
    st.write("1. 今の状況")
    st.write("2. 知りたいこと")
    st.write("3. 地域・管轄")
    st.write("4. 手続きの種類")
    st.write("5. すでに見つけた公式URL")
    st.write("6. すでに分かっている書類名・検索語")

    st.markdown("### 出力予定")
    st.write("・この手続きは何か")
    st.write("・探すべき書類名・帳票名")
    st.write("・一次情報URL")
    st.write("・提出先")
    st.write("・費用")
    st.write("・専門家に相談する場合")
    st.write("・AIでは断定できないこと")
    st.write("・次にやること")
