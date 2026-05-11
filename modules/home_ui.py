from __future__ import annotations

from typing import Any
import streamlit as st


def render_home_ui(use_real_api: bool = False, **kwargs: Any) -> None:
    _ = kwargs

    st.markdown("## AIライティング自動化アプリ - 明元楽市版")
    st.markdown("### 書き出しで止まりにくくするためのアプリ")

    st.write("このアプリは、SEO文書の下書きづくりを前に進めやすくするための道具です。")
    st.write("AIに任せきるのではなく、作者ご自身が判断しやすい形で文章づくりを支えます。")
    st.write("何を書けばよいか迷う時間を減らし、発信を積み上げやすくします。")

    st.divider()

    st.markdown("### このアプリで目指せること")
    st.write("・何を書けばよいか迷いにくくなります。")
    st.write("・下書きづくりの負担を減らせます。")
    st.write("・公開前の不安を確認しやすくなります。")
    st.write("・発信を続けやすくなります。")

    st.divider()

    st.markdown("### 🔐 AI下書き作成について")
    st.write("AIで下書きを作成するには、利用者ご自身のAPIキーが必要です。")
    st.write("入力したAPIキーは、AIによる下書き作成のためだけに利用します。")

    if use_real_api:
        st.write("現在：AIで下書きを作成できます")
    else:
        st.write("現在：デモで下書きを試せます")

    st.divider()

    st.markdown("### 使い方（最短ルート）")
    st.write("1. 『記事モード』で、書きたいテーマやキーワードを入れます。")
    st.write("2. まずは下書きを作り、全体の流れをつかみます。")
    st.write("3. 『文章チェック』で、気になる点を確認します。")
    st.write("4. 必要なところだけ直して、公開できる形へ近づけます。")

    st.divider()

    st.markdown("### 安心して進めるためのポイント")
    st.write("✅ 入力内容はページを移動しても残りやすく、途中から続けやすい設計です。")
    st.write("✅ 生成結果は保存できるので、あとで見直したり戻したりしやすくなっています。")
    st.write("✅ APIキーがなくても、まずはデモ生成で流れを試せます。")
    st.write("✅ このアプリは、書き出しで迷いやすい場面に寄り添い、『何を書けばよいか分からない時間』を減らして、発信を続けやすくすることを目指しています。")