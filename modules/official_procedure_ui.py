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

    st.info("現在は入力欄だけを追加しています。AI生成や自動判定はまだ行いません。")

    st.markdown("### 1. 今の状況")
    st.caption("現在の状況を書いてください。実名や個人情報は、必要がなければ入れないでください。")
    st.text_area(
        "今の状況",
        placeholder=(
            "例：合同会社の代表社員を、現在の代表者から別の社員へ変更したい。\n"
            "会社は東京都〇〇区にある。\n"
            "必要な登記書類、費用、相談先を知りたい。"
        ),
        height=130,
        key="official__current_situation",
        label_visibility="collapsed",
    )

    st.markdown("### 2. 知りたいこと")
    st.caption("何を知りたいかを書いてください。")
    st.text_area(
        "知りたいこと",
        placeholder=(
            "例：代表社員の変更に必要な申請書名、添付書類、提出先、登録免許税、相談先を知りたい。\n"
            "自分で手続きできるのか、専門家に頼んだ方がよいのかも知りたい。"
        ),
        height=130,
        key="official__question",
        label_visibility="collapsed",
    )

    st.markdown("### 3. 地域・管轄")
    st.caption("都道府県、市区町村、管轄が分かれば書いてください。分からなければ空欄で大丈夫です。")
    st.text_input(
        "地域・管轄",
        placeholder="例：東京都〇〇区 / 管轄法務局は未確認",
        key="official__jurisdiction",
        label_visibility="collapsed",
    )

    st.markdown("### 4. 手続きの種類")
    st.caption("分かる範囲で選んでください。迷う場合は「その他」で大丈夫です。")
    st.radio(
        "手続きの種類",
        [
            "法人登記",
            "個人の行政手続き",
            "税金",
            "社会保険・年金",
            "補助金・助成金",
            "許認可",
            "相続・戸籍",
            "その他",
        ],
        key="official__procedure_type",
        label_visibility="collapsed",
    )

    st.markdown("### 5. すでに見つけた公式URL")
    st.caption("公式ページを見つけている場合はURLを貼ってください。分からなければ空欄で大丈夫です。")
    st.text_input(
        "すでに見つけた公式URL",
        placeholder="例：https://www.moj.go.jp/ または https://houmukyoku.moj.go.jp/",
        key="official__official_url",
        label_visibility="collapsed",
    )

    st.markdown("### 6. すでに分かっている書類名・検索語")
    st.caption("分かっている書類名や、検索した言葉があれば書いてください。")
    st.text_area(
        "すでに分かっている書類名・検索語",
        placeholder=(
            "例：合同会社変更登記申請書\n"
            "例：代表社員の交代に必要な登記書類\n"
            "例：法人登記 代表者変更 合同会社"
        ),
        height=120,
        key="official__known_docs",
        label_visibility="collapsed",
    )

    st.divider()

    st.markdown("### 出力予定")
    st.write("・この手続きは何か")
    st.write("・探すべき書類名・帳票名")
    st.write("・一次情報URL")
    st.write("・提出先")
    st.write("・費用")
    st.write("・専門家に相談する場合")
    st.write("・AIでは断定できないこと")
    st.write("・次にやること")
