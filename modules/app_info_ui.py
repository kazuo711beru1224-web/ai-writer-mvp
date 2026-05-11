# modules/app_info_ui.py（完成版：丸ごと置換）

import streamlit as st


def render_app_info_ui(
    outputs_dir: str,
    logs_dir: str,
    openai_api_key: str,
    use_real_api: bool,
) -> None:
    st.markdown("## ⚙ アプリ情報")
    st.write("動作モードや保存状況を確認できます。")

    st.divider()

    st.markdown("### 動作モード")
    st.write(f"現在：{'本生成' if use_real_api else 'デモ生成'}")

    # 参考：APIキーの有無を“表示”したい場合（キーそのものは絶対に表示しない）
    st.caption(f"APIキー：{'あり（入力済み）' if (openai_api_key and str(openai_api_key).strip()) else 'なし'}")

    st.divider()

    st.markdown("### 保存状況")
    # 件数表示は、ここでは“確実に落ちない”ように簡易版
    # ※ 既に別モジュールで正確な集計関数があるなら、そちらに差し替えOK
    st.write("保存された文章（テキスト）：（件数は生成履歴で確認できます）")

    st.divider()

    st.markdown("### 上級者向け：保存場所を確認する（必要な人だけ）")
    st.write("ふだんは見なくて大丈夫です。トラブル調査などで使います。")

    st.write("作った文章が入る場所（表示）")
    st.code(outputs_dir)

    st.write("動作記録（トラブル調査用）が入る場所")
    st.code(logs_dir)
