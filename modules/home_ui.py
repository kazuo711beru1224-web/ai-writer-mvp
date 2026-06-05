from __future__ import annotations

from typing import Any
import streamlit as st


def render_home_ui(use_real_api: bool = False, **kwargs: Any) -> None:
    _ = kwargs

    st.markdown("## AIライティング自動化アプリ - 明元楽市版")
    st.write("SEO記事の下書きを、迷わず作るためのアプリです。")
    st.write("このアプリは、記事の下書きづくりを助ける道具です。")
    st.write("AIにすべてを任せるのではなく、作者ご自身が確認しながら文章を整えます。")
    st.write("書き出しで止まる時間を減らし、公開前の不安を確認しやすくします。")

    st.divider()

    st.markdown("### このアプリでできること")
    st.write("・SEO記事の下書きを作れます。")
    st.write("・文章の見直しポイントを確認できます。")
    st.write("・公開前に気になる表現をチェックできます。")
    st.write("・作った文章をあとで見直せます。")

    st.divider()

    st.markdown("### 🔐 AI下書き作成について")
    st.write("AIで下書きを作成するには、利用者ご自身のOpenAI APIキーが必要です。")
    st.write("入力したAPIキーは、AIによる下書き作成のためだけに使います。")
    st.write("人に見せたり、LINEやメールで送ったりしないでください。")

    if use_real_api:
        st.write("現在：AIで下書きを作成できます")

    st.divider()

    st.markdown("### 安心して使うためのポイント")
    st.write("・入力内容は保存され、途中から続けられます。")
    st.write("・生成結果は保存できるので、あとで見直せます。")
    st.write("・AIの文章は下書きです。公開前に作者ご自身で確認してください。")

    st.divider()

    st.markdown("### 使い方（最短ルート）")
    st.write("1. 『記事モード』で、書きたいテーマやキーワードを入れます。")
    st.write("2. まずは下書きを作り、全体の流れをつかみます。")
    st.write("3. 『文章チェック』で、気になる点を確認します。")
    st.write("4. 必要なところだけ直して、公開できる形へ近づけます。")

    st.divider()

