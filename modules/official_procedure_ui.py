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
    st.caption("公式ページを見つけている場合はURLを貼ってください。分からなければ空欄で大丈夫です。次の段階で、AIが公式ページの候補を探します。")
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

    current_situation = str(st.session_state.get("official__current_situation", "") or "").strip()
    question = str(st.session_state.get("official__question", "") or "").strip()
    jurisdiction = str(st.session_state.get("official__jurisdiction", "") or "").strip()
    procedure_type = str(st.session_state.get("official__procedure_type", "") or "").strip()
    official_url = str(st.session_state.get("official__official_url", "") or "").strip()
    known_docs = str(st.session_state.get("official__known_docs", "") or "").strip()

    st.markdown("### 7. 入力内容の確認")
    st.caption("ここでは、今入力した内容を確認します。まだAI生成や自動判定は行いません。")

    with st.expander("入力した内容を見る", expanded=True):
        st.markdown("**1. 今の状況**")
        st.write(current_situation if current_situation else "未入力です。")

        st.markdown("**2. 知りたいこと**")
        st.write(question if question else "未入力です。")

        st.markdown("**3. 地域・管轄**")
        st.write(jurisdiction if jurisdiction else "未入力です。")

        st.markdown("**4. 手続きの種類**")
        st.write(procedure_type if procedure_type else "未選択です。")

        st.markdown("**5. すでに見つけた公式URL**")
        if official_url:
            st.write(official_url)
        else:
            st.write("未入力です。公式URLが分からない場合は、空欄で大丈夫です。次の段階で、AIが公式ページの候補を探します。")

        st.markdown("**6. すでに分かっている書類名・検索語**")
        st.write(known_docs if known_docs else "未入力です。")

    st.divider()

    st.markdown("### 8. 次に確認すること")
    st.caption("ここでは、入力内容をもとに、次に確認した方がよい点を整理します。まだAI生成や自動判定は行いません。")

    check_items = []

    if not current_situation:
        check_items.append("今の状況が未入力です。まず、何をしたいのかを短く書いてください。")

    if not question:
        check_items.append("知りたいことが未入力です。必要書類、費用、提出先、相談先など、知りたい内容を書いてください。")

    if not jurisdiction:
        check_items.append("地域・管轄が未入力です。分からなければ空欄でも大丈夫ですが、都道府県や市区町村があると整理しやすくなります。")

    if not official_url:
        check_items.append("公式URLは未入力です。分からなくても大丈夫です。次の段階で、AIが公式ページの候補を探します。")

    if not known_docs:
        check_items.append("書類名・検索語が未入力です。分かる言葉だけで大丈夫です。例：変更登記、申請書、代表者変更など。")

    if not check_items:
        check_items.append("入力内容はそろっています。次の段階で、公式ページ候補や探すべき書類名を整理します。")

    for i, item in enumerate(check_items, start=1):
        st.write(f"{i}. {item}")

    st.divider()

    st.markdown("### 9. 公式ページ候補を探す")
    st.caption("正式な書類名や公式URLが分からなくても大丈夫です。ここでは、次の段階で探す準備をします。")

    if "official_procedure_show_search_panel" not in st.session_state:
        st.session_state["official_procedure_show_search_panel"] = False

    if st.button("公式ページ候補を探す準備をする", type="primary"):
        st.session_state["official_procedure_show_search_panel"] = True

    if st.session_state.get("official_procedure_show_search_panel"):
        st.info(
            "次の段階で、手続きの内容・地域・分かっている言葉をもとに、"
            "公式ページ候補を探します。\n\n"
            "検索結果は必ず公式サイトを確認してください。"
        )

        st.markdown("#### 検索に使う材料")

        st.write("1. 手続きの内容")
        st.write(current_situation if current_situation else "未入力です。何をしたいのかを短く書くと探しやすくなります。")

        st.write("2. 知りたいこと")
        st.write(question if question else "未入力です。必要書類、費用、提出先などを知りたい場合は書いてください。")

        st.write("3. 地域・管轄")
        st.write(jurisdiction if jurisdiction else "未入力です。分からなければ空欄で大丈夫です。")

        st.write("4. 分かっている言葉")
        st.write(known_docs if known_docs else "未入力です。正式な書類名が分からなくても大丈夫です。")

        st.markdown("#### 優先して確認する公式サイト候補")
        st.write("1. 法務局")
        st.write("2. 市区町村")
        st.write("3. 都道府県")
        st.write("4. 税務署")
        st.write("5. 年金事務所")
        st.write("6. その他の公的機関")

        st.markdown("#### 検索語候補")
        st.caption("正式な書類名が分からなくても、手続きの内容や分かっている言葉から検索候補を作ります。")

        base_words = []
        if procedure_type:
            base_words.append(procedure_type)
        if current_situation:
            base_words.append(current_situation)
        if question:
            base_words.append(question)
        if jurisdiction:
            base_words.append(jurisdiction)
        if known_docs:
            base_words.append(known_docs)

        if base_words:
            joined_words = " ".join(base_words)
            search_candidates = [
                f"{joined_words} 公式",
                f"{joined_words} 申請書",
                f"{joined_words} 必要書類",
                f"{joined_words} 管轄 窓口",
                f"{joined_words} 費用",
            ]
        else:
            search_candidates = [
                "手続き名 公式",
                "手続き名 申請書",
                "手続き名 必要書類",
                "手続き名 管轄 窓口",
                "手続き名 費用",
            ]

        for i, candidate in enumerate(search_candidates, start=1):
            st.write(f"{i}. {candidate}")

        st.markdown("#### コピー用検索語")
        st.caption("下の枠をコピーして、Google検索や公式サイト内検索に貼り付けられます。")

        copy_text = "\n".join(search_candidates)
        st.text_area(
            "コピー用",
            value=copy_text,
            height=150,
            key="official_procedure_search_terms_copy",
        )

        st.caption(
            "この段階では、まだ検索は実行しません。"
            "次の段階で、上の検索語候補をもとに公式ページ候補を整理します。"
        )

        st.markdown("#### AI整理用の下書き")
        st.caption(
            "次の段階でAIに整理させるための下書きです。"
            "URLや書類名は、まだ確定情報として扱いません。"
        )

        draft_lines = [
            "【目的】",
            "公式手続きに関する情報を、一次情報確認前の候補として整理する。",
            "",
            "【手続きの種類】",
            procedure_type if procedure_type else "未入力",
            "",
            "【今の状況】",
            current_situation if current_situation else "未入力",
            "",
            "【知りたいこと】",
            question if question else "未入力",
            "",
            "【地域・管轄】",
            jurisdiction if jurisdiction else "未入力",
            "",
            "【分かっている書類名・検索語】",
            known_docs if known_docs else "未入力",
            "",
            "【検索語候補】",
        ]

        draft_lines.extend([f"- {candidate}" for candidate in search_candidates])

        draft_lines.extend([
            "",
            "【確認ルール】",
            "- AIの回答だけで申請・登記・届出を進めない。",
            "- URLは必ず公式サイトを開いて確認する。",
            "- 書類名・費用・提出先は、管轄窓口で最終確認する。",
            "- AIが断定できないことは「未確認」として扱う。",
            "- 判断に迷う場合は、専門家または管轄窓口へ相談する。",
            "",
            "【AIに期待する整理】",
            "- この手続きが何に当たるかを候補として整理する。",
            "- 探すべき書類名・帳票名を候補として整理する。",
            "- 一次情報として確認すべき公式サイトの種類を整理する。",
            "- 提出先、費用、相談先を確認項目として整理する。",
            "- 不明点や断定できない点を「未確認」として分ける。",
        ])

        draft_text = "\n".join(draft_lines)

        st.text_area(
            "AI整理用下書き",
            value=draft_text,
            height=360,
            key="official_procedure_ai_draft",
        )

    st.divider()

    st.markdown("### 10. 確認ルール")
    st.warning(
        "公式手続きは、AIの回答だけで進めないでください。"
        "必ず公式サイト、管轄窓口、または専門家に確認してください。"
    )

    st.write("1. AIの回答だけで申請・登記・届出を進めない")
    st.write("2. URLは必ず公式サイトを開いて確認する")
    st.write("3. 書類名・費用・提出先は、管轄窓口で最終確認する")
    st.write("4. AIが断定できないことは「未確認」として扱う")
    st.write("5. 判断に迷う場合は、専門家または管轄窓口へ相談する")

    st.divider()

    st.markdown("### 11. 出力予定")
    st.write("1. この手続きは何か")
    st.write("2. 探すべき書類名・帳票名")
    st.write("3. 一次情報URL")
    st.write("4. 提出先")
    st.write("5. 費用")
    st.write("6. 専門家に相談する場合")
    st.write("7. AIでは断定できないこと")
    st.write("8. 次にやること")
