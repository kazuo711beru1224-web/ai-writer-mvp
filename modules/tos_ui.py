from __future__ import annotations

import streamlit as st
from typing import List, Dict, Any

from modules.tos import (
    DEFAULT_TOS_VERSION,
    get_or_create_client_id,
    append_agreement,
    load_agreements,
    is_agreed_latest,
)

# =========================
# ベル憲法3（外向き短い約束）
# =========================
OUTWARD_PROMISE = (
    "本アプリは、高リスクジャンルのAI文章について、"
    "事故リスクを検出し、編集者の確認ポイントを可視化する支援ツールです。"
)

# ここは将来ファイルから読む形にしてもOK（MVPは直書きでよい）
TOS_TITLE = "利用規約（抜粋）"
TOS_BODY = """\
### 0. 存在理由
本アプリは、高リスクジャンルにおけるAI文章の事故リスクを検出し、編集者の確認ポイントを可視化する支援ツールです。

### 1. 本アプリが約束すること
- 根拠と不一致の数字・年号・固有名詞を検出します。
- 制度名や概念の混同が疑われる組み合わせ（混同ペア）を検出します。
- 危険度を SAFE / CAUTION / RISK の3段階で表示します。
- 危険度が高い場合は、強制ストッパー（本文非表示・再生成/手動修正の促し等）を発動します。

### 2. 本アプリが約束しないこと
- 完成原稿としての品質・完成度の保証
- 法的・医療的・投資的その他専門領域の最終的な正確性の保証
- 専門家による判断の代替

※ 最終的な内容の確認・判断はユーザー自身の責任で行ってください。
"""


def render_tos_page() -> None:
    st.markdown("## 利用規約")
    st.info(OUTWARD_PROMISE)
    st.markdown(TOS_BODY)


def render_agreement_gate(
    logs_dir: str,
    app_version: str,
    tos_version: str = DEFAULT_TOS_VERSION,
) -> bool:
    """
    同意済みなら True、未同意なら False。
    未同意の場合は、同意UIを表示して、同意ボタンを押すまで進ませない想定。
    """
    st.markdown("## 利用開始の同意")
    st.warning("このアプリは「完成原稿」を保証しません。事故リスク検出の支援ツールです。")

    client_id = get_or_create_client_id(logs_dir)

    st.caption(f"規約バージョン：{tos_version} / アプリ：{app_version}")
    with st.expander("利用規約（抜粋）を読む", expanded=True):
        st.markdown(TOS_BODY)

    col1, col2 = st.columns([1, 1])
    with col1:
        agree = st.button("同意して利用を開始する", use_container_width=True, key="btn_tos_agree")
    with col2:
        st.button("同意しない（アプリを閉じる）", use_container_width=True, key="btn_tos_decline")

    if agree:
        append_agreement(
            logs_dir=logs_dir,
            client_id=client_id,
            tos_version=tos_version,
            app_version=app_version,
            source="first_launch",
        )
        st.success("同意を記録しました。メニューから利用を開始できます。")
        return True

    st.stop()
    return False


def render_agreement_history(logs_dir: str) -> None:
    st.markdown("## 同意履歴（管理）")
    rows = load_agreements(logs_dir)
    if not rows:
        st.info("同意履歴はまだありません。")
        return

    # 表示用に軽く整形
    # Streamlitのst.dataframeでそのまま出す（MVP優先）
    st.dataframe(rows, use_container_width=True)
    st.caption("※MVPでは端末識別＝client_id（ローカルUUID）です。")