import inspect

import streamlit as st

import app
import modules.article_ui as article_ui
from modules.article_ui import (
    _build_article_scroll_restore_script_html,
    _build_article_scroll_tracker_script_html,
    _classify_question_type,
    _render_large_text_preview,
    _render_reference_hint_section,
    get_article_persist_keys,
    render_article_ui,
    ARTICLE_ACTIVE_PAGE_KEY,
    ARTICLE_PAGE_BASIC,
    ARTICLE_PAGE_KEYWORD,
    ARTICLE_PAGE_OFFICIAL,
    ARTICLE_PAGE_STYLE,
    ARTICLE_PAGE_DRAFT,
    ARTICLE_PAGE_PRECHECK,
    ARTICLE_SCROLL_STORAGE_KEY,
    ARTICLE_TOP_ANCHOR_ID,
    KEYS,
    REFERENCE_HINT_OPEN_KEY,
    UI_FLAG_KEYS,
)


def _reset_session_state():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def test_promotion_context_is_not_latest_news():
    text = (
        "近くにドラッグストアができてから、コンビニの来店客数が少し減っています。"
        "店頭POPの文章を考えたいです。"
    )
    assert _classify_question_type(text) != "latest_news"


def test_reference_hint_open_key_is_a_ui_flag():
    # 確認先の探し方ヒントの開閉は、_evidence_inputs_are_thin()に連動しない
    # 独立フラグで管理する。UI_FLAG_KEYS経由で初期化・リセットされることを確認する。
    assert REFERENCE_HINT_OPEN_KEY in UI_FLAG_KEYS


def test_reference_hint_open_key_is_not_a_persisted_data_key():
    # 表示のON/OFFはUI状態であり、記事データそのものではないため、
    # 自動保存の作業内容判定（WORK_SIG_KEYS相当）には含めない設計であることを確認する。
    assert REFERENCE_HINT_OPEN_KEY not in get_article_persist_keys()


def test_render_reference_hint_section_runs_without_error_when_closed():
    _reset_session_state()
    st.session_state[REFERENCE_HINT_OPEN_KEY] = False
    _render_reference_hint_section()


def test_render_reference_hint_section_runs_without_error_when_open():
    _reset_session_state()
    st.session_state[REFERENCE_HINT_OPEN_KEY] = True
    _render_reference_hint_section()


def test_large_text_preview_shows_placeholder_code_block_when_empty(monkeypatch):
    # 空欄時に「（未入力）」の1行だけ→反映後にcode blockが丸ごと出現、という
    # 高さ差が反映ボタン押下時のスクロールずれの原因だったため、
    # empty_placeholderを渡した場合は空欄でも同じ構造(caption+code)になることを確認する。
    calls = {"caption": [], "code": []}
    monkeypatch.setattr(st, "caption", lambda text: calls["caption"].append(text))
    monkeypatch.setattr(st, "code", lambda text, **kwargs: calls["code"].append(text))

    _render_large_text_preview(
        title="生成に使う要点",
        body="",
        show_key="dummy_show_key",
        preview_chars=700,
        empty_placeholder="まだ反映されていません。",
    )

    assert calls["caption"] == ["文字数：0"]
    assert calls["code"] == ["まだ反映されていません。"]


def test_large_text_preview_falls_back_to_caption_only_when_no_placeholder_given(monkeypatch):
    # empty_placeholderを渡さない既存の呼び出し元は、従来通り「（未入力）」の
    # 1行キャプションのみで、st.codeは呼ばれないことを回帰確認する。
    calls = {"caption": [], "code": []}
    monkeypatch.setattr(st, "caption", lambda text: calls["caption"].append(text))
    monkeypatch.setattr(st, "code", lambda text, **kwargs: calls["code"].append(text))

    _render_large_text_preview(
        title="根拠",
        body="",
        show_key="dummy_show_key_2",
        preview_chars=700,
    )

    assert calls["caption"] == ["（未入力）"]
    assert calls["code"] == []


def test_scroll_tracker_script_guards_against_duplicate_listener_registration():
    html_out = _build_article_scroll_tracker_script_html()

    assert "<script>" in html_out
    assert "__aiWriterArticleScrollInit" in html_out
    assert "sessionStorage" in html_out
    assert ARTICLE_SCROLL_STORAGE_KEY in html_out


def test_scroll_tracker_script_only_saves_while_article_anchor_present():
    # 記事モード用アンカー(#article-top)が無いとき（＝他モード表示中）は
    # 保存しないことのガード条件がスクリプトに含まれることを確認する。
    html_out = _build_article_scroll_tracker_script_html()

    assert ARTICLE_TOP_ANCHOR_ID in html_out
    assert "getElementById(ANCHOR_ID)" in html_out


def test_scroll_tracker_script_rechecks_anchor_inside_debounce_timeout():
    # 記事モードを離れた直後にscroll debounceタイマー（150ms）が残っている
    # と、発火時点では他モードに切り替わっていることがある。保存イベント
    # 発生時だけでなく、setTimeoutコールバック内の保存直前にも
    # getElementById(ANCHOR_ID)を再チェックし、他モードのscrollTopが
    # article用sessionStorageへ紛れ込まないことを確認する。
    html_out = _build_article_scroll_tracker_script_html()

    setTimeout_idx = html_out.index("win.setTimeout(function()")
    set_item_idx = html_out.index("sessionStorage.setItem")
    recheck_idx = html_out.index(
        "if (!doc.getElementById(ANCHOR_ID)) { return; }", setTimeout_idx
    )

    assert setTimeout_idx < recheck_idx < set_item_idx
    assert html_out.count("getElementById(ANCHOR_ID)") >= 2


def test_scroll_tracker_script_listens_on_document_capture_phase():
    # section.stMain がStreamlitの再描画で入れ替わっても捕捉し続けられるよう、
    # documentのキャプチャフェーズでリッスンしていることを確認する。
    html_out = _build_article_scroll_tracker_script_html()

    assert "addEventListener('scroll'" in html_out
    assert html_out.strip().endswith("</script>")
    assert ", true)" in html_out


def test_scroll_restore_script_skips_when_url_hash_present():
    # 画面移動サポートのアンカーリンクなど、URL hashがあるときは
    # ユーザーの操作を優先し、sessionStorageからの復元をしないことを確認する。
    html_out = _build_article_scroll_restore_script_html(nonce="1")

    assert "window.location" in html_out or "win.location" in html_out
    assert "location.hash" in html_out


def test_scroll_restore_script_clears_any_hash_while_in_article_mode():
    # Streamlit本体の見出しアンカー機能（script完了300ms後のscrollIntoView）を
    # 空振りさせるため、記事モード表示中（ANCHOR_IDがDOMに存在する）なら、
    # 既知アンカーかどうかに関わらずhashをhistory.replaceStateで消費して
    # クリアすることを確認する。
    html_out = _build_article_scroll_restore_script_html(nonce="1")

    assert "history.replaceState" in html_out
    hash_block_idx = html_out.index("if (hashId) {")
    anchor_check_idx = html_out.index(
        "if (doc.getElementById(ANCHOR_ID)) {", hash_block_idx
    )
    replace_state_idx = html_out.index("history.replaceState", anchor_check_idx)

    assert hash_block_idx < anchor_check_idx < replace_state_idx


def test_scroll_restore_script_hash_clear_is_scoped_to_article_anchor_presence():
    # hashクリアはANCHOR_ID(article-top)がDOM上に存在するとき（＝記事モード
    # 表示中）に限定し、他モードの画面移動サポートのhashを誤って消費しない
    # よう防御していることを確認する。
    html_out = _build_article_scroll_restore_script_html(nonce="1")

    assert ARTICLE_TOP_ANCHOR_ID in html_out
    assert "var ANCHOR_ID" in html_out


def test_scroll_restore_script_returns_after_hash_clear_by_default():
    # restore_even_if_hash_consumed未指定（既定False）のときは、hashクリア後も
    # 従来通りreturnし、その回はsessionStorage復帰を行わないことを確認する。
    # 他モードから記事モードへ戻るjust_entered_menu側の呼び出しはこの既定の
    # ままにして、直前の画面移動サポートのアンカー移動を一度だけ尊重する。
    html_out = _build_article_scroll_restore_script_html(nonce="1")

    hash_block_idx = html_out.index("if (hashId) {")
    close_brace_idx = html_out.index("\n    }\n\n    var KEY", hash_block_idx)
    hash_block = html_out[hash_block_idx:close_brace_idx]

    assert "RESTORE_EVEN_IF_HASH_CONSUMED = false" in html_out
    assert "if (!RESTORE_EVEN_IF_HASH_CONSUMED) { return; }" in hash_block


def test_scroll_restore_script_continues_to_session_storage_when_hash_consumed_flag_set():
    # restore_even_if_hash_consumed=Trueのときは、hashクリア後もreturnせず
    # sessionStorage復帰処理へ続けることを確認する（反映ボタン押下側の呼び出し用）。
    html_out = _build_article_scroll_restore_script_html(
        nonce="1", restore_even_if_hash_consumed=True
    )

    assert "RESTORE_EVEN_IF_HASH_CONSUMED = true" in html_out

    hash_block_idx = html_out.index("if (hashId) {")
    session_storage_idx = html_out.index("sessionStorage.getItem", hash_block_idx)
    return_idx = html_out.find("if (!RESTORE_EVEN_IF_HASH_CONSUMED) { return; }", hash_block_idx)

    # ガード自体はJS内に存在するが、フラグがtrueのため実行時にはreturnせず
    # sessionStorage復帰コードへ到達できる並び（return文がguardの中に留まり、
    # sessionStorage.getItemがそれより後方に存在する）になっていることを確認する。
    assert 0 <= return_idx < session_storage_idx


def test_scroll_restore_script_pauses_tracker_saves_after_running():
    # 復帰スクリプトがscrollTopを動かした直後、trackerがそのプログラム由来の
    # 位置を保存し直さないよう、一時停止フラグを立てることを確認する。
    html_out = _build_article_scroll_restore_script_html(nonce="1")

    assert "__aiWriterArticleScrollPauseUntil" in html_out


def test_scroll_restore_script_reads_the_same_storage_key_as_tracker():
    html_out = _build_article_scroll_restore_script_html(nonce="1")

    assert ARTICLE_SCROLL_STORAGE_KEY in html_out
    assert "sessionStorage.getItem" in html_out


def test_scroll_restore_script_differs_by_nonce_to_force_iframe_reload():
    html_1 = _build_article_scroll_restore_script_html(nonce="1")
    html_2 = _build_article_scroll_restore_script_html(nonce="2")

    assert html_1 != html_2


def test_scroll_tracker_script_skips_save_while_restore_pause_is_active():
    # 復帰スクリプトが立てた一時停止フラグの間は、tracker側がsessionStorageへの
    # 保存をスキップすることを確認する。
    html_out = _build_article_scroll_tracker_script_html()

    assert "__aiWriterArticleScrollPauseUntil" in html_out
    assert "Date.now() < win.__aiWriterArticleScrollPauseUntil" in html_out


def test_scroll_restore_script_escapes_nonce_value():
    html_out = _build_article_scroll_restore_script_html(nonce='"; alert(1); //')

    assert "<script>alert(1)" not in html_out


def _active_code_lines(source: str) -> str:
    # コメントアウトされた呼び出し（無効化した保険コード）を除外し、
    # 実際に実行されるコード行だけを対象に文字列アサーションするための補助。
    return "\n".join(
        line for line in source.splitlines() if not line.strip().startswith("#")
    )


def test_render_article_ui_does_not_call_scroll_tracker():
    # 自動スクロール保存（tracker）は、入力・クリック等の通常操作で発生する
    # 意図しないscrollイベントまで保存してしまい、本番Streamlit Cloudで
    # 位置が勝手に動く不安定要因になっていたため、呼び出しをいったん停止する。
    # 関数本体は削除せず残すが、render_article_ui()からは呼ばれないことを
    # 回帰確認する（コメントアウトされた呼び出しは対象外）。
    active_source = _active_code_lines(inspect.getsource(render_article_ui))

    assert "_render_article_scroll_tracker()" not in active_source


def test_render_article_ui_calls_scroll_restore_only_for_hash_clear_on_menu_entry():
    # hash残留対策として、他モードから記事モードへ入り直した直後
    # （just_entered_menu）にだけ、hashクリア専用の呼び出し
    # （restore_even_if_hash_consumed=False）を行うことを確認する。
    # sessionStorageによる位置復元（True側）は本番Streamlit Cloudで
    # 不安定要因になったため、引き続き呼ばない。
    active_source = _active_code_lines(inspect.getsource(render_article_ui))

    assert "_render_article_scroll_restore(restore_even_if_hash_consumed=False)" in active_source
    assert "restore_even_if_hash_consumed=True" not in active_source
    assert "if just_entered_menu:" in active_source


def test_official_info_page_does_not_auto_call_scroll_restore_after_apply():
    # 「この確認先を下書きに反映する」ボタン後の復帰呼び出しも停止されている
    # ことを確認する（コメントアウトされた呼び出しは対象外）。
    active_source = _active_code_lines(
        inspect.getsource(article_ui._render_page_3_official_info)
    )

    assert "_render_article_scroll_restore(" not in active_source


def test_render_article_ui_does_not_use_scroll_into_view():
    # 画面移動サポートはscrollIntoViewをやめ、active_page切替のみで行う
    # ようにしたため、render_article_ui()はscrollIntoView・one-shotの
    # スクロールリクエストのどちらも一切使わないことを回帰確認する。
    source = inspect.getsource(render_article_ui)

    assert "scrollIntoView" not in source
    assert "ARTICLE_SCROLL_REQUEST_KEY" not in source


def test_official_info_page_has_no_url_hash_or_scroll_markup():
    # 公式情報・確認先ページ自体にも、URL hashやscrollIntoViewに関する
    # マークアップが残っていないことを確認する。
    source = inspect.getsource(article_ui._render_page_3_official_info)

    assert "scrollIntoView" not in source
    assert 'href="#' not in source
    assert "data-ai-scroll-target" not in source


def test_render_article_ui_renders_article_top_anchor(monkeypatch):
    # hashクリア処理は、id="article-top"がDOM上に存在するときだけ
    # 「今は記事モード表示中」と判定してhashを消費する設計のため、
    # このアンカー自体が実際に描画されることを回帰確認する
    # （アンカーが無いとhashクリアが常に空振りする）。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC

    markdown_calls = []
    monkeypatch.setattr(st, "markdown", lambda text, **kwargs: markdown_calls.append(text))

    render_article_ui(**_common_kwargs())

    assert any(f'id="{ARTICLE_TOP_ANCHOR_ID}"' in text for text in markdown_calls)


# =========================
# 記事モードのページ区切り型UI（6ページ）
# =========================

def _common_kwargs():
    return dict(outputs_dir="out", logs_dir="logs", openai_api_key="", use_real_api=False)


def test_article_active_page_key_is_not_a_persisted_data_key():
    # ページ表示は画面状態であり記事データではないため、自動保存対象
    # （get_article_persist_keys）には含めない設計であることを確認する。
    assert ARTICLE_ACTIVE_PAGE_KEY not in get_article_persist_keys()


def test_article_active_page_defaults_to_basic_page():
    _reset_session_state()
    render_article_ui(**_common_kwargs())

    assert st.session_state[ARTICLE_ACTIVE_PAGE_KEY] == ARTICLE_PAGE_BASIC
    assert ARTICLE_PAGE_BASIC == 1


def test_article_mode_is_six_pages_and_precheck_is_the_last_page():
    # 7/7（編集後確認・保存）を削除し、記事モードを6ページ構成に戻したことを
    # 確認する。6/6（下書きの確認）が最終ページになる。
    assert article_ui.ARTICLE_PAGE_COUNT == 6
    assert ARTICLE_PAGE_PRECHECK == article_ui.ARTICLE_PAGE_COUNT


def test_render_article_ui_dispatches_only_the_active_page(monkeypatch):
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_OFFICIAL

    calls = []
    monkeypatch.setattr(article_ui, "_render_page_1_basic", lambda: calls.append(1))
    monkeypatch.setattr(article_ui, "_render_page_2_keyword_and_detail_entry", lambda: calls.append(2))
    monkeypatch.setattr(article_ui, "_render_page_3_official_info", lambda: calls.append(3))
    monkeypatch.setattr(article_ui, "_render_page_4_writing_style", lambda: calls.append(4))
    monkeypatch.setattr(article_ui, "_render_page_5_draft", lambda **kw: calls.append(5))
    monkeypatch.setattr(article_ui, "_render_page_6_precheck", lambda: calls.append(6))

    render_article_ui(**_common_kwargs())

    assert calls == [3]


def test_go_to_page_switches_active_page():
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC

    article_ui._go_to_page(ARTICLE_PAGE_DRAFT)
    assert st.session_state[ARTICLE_ACTIVE_PAGE_KEY] == ARTICLE_PAGE_DRAFT


def test_page_nav_buttons_show_only_next_on_first_page(monkeypatch):
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC

    captured = []
    monkeypatch.setattr(st, "button", lambda label, **kwargs: captured.append(label))
    article_ui._render_page_nav_buttons(position="test")

    assert captured == ["次へ →"]


def test_page_nav_buttons_show_only_back_on_last_page(monkeypatch):
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_PRECHECK

    captured = []
    monkeypatch.setattr(st, "button", lambda label, **kwargs: captured.append(label))
    article_ui._render_page_nav_buttons(position="test")

    assert captured == ["← 戻る"]


def test_page_nav_buttons_show_both_on_middle_page(monkeypatch):
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_OFFICIAL

    captured = []
    monkeypatch.setattr(st, "button", lambda label, **kwargs: captured.append(label))
    article_ui._render_page_nav_buttons(position="test")

    assert captured == ["← 戻る", "次へ →"]


def test_input_values_survive_switching_between_pages():
    # ページを移動しても、既存のsession_state(KEYS)に入れた入力内容が
    # 消えないことを確認する（新しい自動保存・復帰の仕組みは追加していない）。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    st.session_state[KEYS["consult_situation"]] = "テスト用の状況"
    st.session_state[KEYS["consult_question"]] = "テスト用の質問"

    render_article_ui(**_common_kwargs())
    assert st.session_state[KEYS["consult_situation"]] == "テスト用の状況"
    assert st.session_state[KEYS["consult_question"]] == "テスト用の質問"

    article_ui._go_to_page(ARTICLE_PAGE_DRAFT)
    render_article_ui(**_common_kwargs())

    assert st.session_state[KEYS["consult_situation"]] == "テスト用の状況"
    assert st.session_state[KEYS["consult_question"]] == "テスト用の質問"
    assert st.session_state[ARTICLE_ACTIVE_PAGE_KEY] == ARTICLE_PAGE_DRAFT


def test_shadow_state_restores_blank_field_only_on_page_change():
    # ページを移動した直後は、空欄になっている項目がシャドウStateから
    # 復元されること（意図した挙動が壊れていないことの回帰確認）。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    st.session_state[KEYS["suggest"]] = "keyword A"

    render_article_ui(**_common_kwargs())
    assert st.session_state["article_shadow__search_keyword"] == "keyword A"

    # 何らかの理由で欄が空になった状態で、実際にページ移動が起きたとする。
    st.session_state[KEYS["suggest"]] = ""
    article_ui._go_to_page(ARTICLE_PAGE_DRAFT)
    render_article_ui(**_common_kwargs())

    assert st.session_state[KEYS["suggest"]] == "keyword A"


def test_cleared_value_does_not_revive_on_same_page_rerender():
    # 「消したのに戻る」問題の回帰確認。
    # 同じページ内の再描画（ページ移動なし）では、利用者が今まさに空にした
    # 欄へ、古いシャドウStateの値を書き戻してはいけない。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    st.session_state[KEYS["suggest"]] = "keyword A"

    render_article_ui(**_common_kwargs())
    assert st.session_state["article_shadow__search_keyword"] == "keyword A"

    # ページは移動せず、欄だけ意図的に空にする。
    st.session_state[KEYS["suggest"]] = ""
    render_article_ui(**_common_kwargs())

    assert st.session_state[KEYS["suggest"]] == ""


def test_clear_form_only_clears_shadow_state_and_input_backup():
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    st.session_state[KEYS["consult_situation"]] = "テスト用の状況"
    st.session_state[KEYS["suggest"]] = "keyword A"

    render_article_ui(**_common_kwargs())
    assert st.session_state["article_shadow__consult_situation"] == "テスト用の状況"
    assert st.session_state["article__input_backup"][KEYS["consult_situation"]] == "テスト用の状況"

    article_ui._clear_form_only()

    for shadow_key in article_ui.SHADOW_KEYS.values():
        assert st.session_state[shadow_key] == ""
    assert st.session_state["article__input_backup"] == {}


def test_sidebar_equivalent_navigation_backs_up_shadow_state_like_go_to_page():
    # app.py側のサイドバー画面移動サポートボタンは _go_to_page を
    # _go_to_article_page としてimportして呼ぶ（app.py:24, 847）。
    # ここでは、その同じ関数をサイドバーの代わりに直接呼んだ場合でも、
    # ページ下部の「次へ」「戻る」と同じ退避処理が走ることを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    st.session_state[KEYS["consult_situation"]] = "サイドバー経由の状況"
    st.session_state[KEYS["consult_question"]] = "サイドバー経由の質問"
    st.session_state[KEYS["suggest"]] = "サイドバーキーワード"
    st.session_state[KEYS["tone_reg"]] = "サイドバートンマナ"

    assert app._go_to_article_page is article_ui._go_to_page

    app._go_to_article_page(ARTICLE_PAGE_DRAFT)

    assert st.session_state[ARTICLE_ACTIVE_PAGE_KEY] == ARTICLE_PAGE_DRAFT
    assert st.session_state["article_shadow__consult_situation"] == "サイドバー経由の状況"
    assert st.session_state["article_shadow__consult_question"] == "サイドバー経由の質問"
    assert st.session_state["article_shadow__search_keyword"] == "サイドバーキーワード"
    assert st.session_state["article_shadow__tone_reg"] == "サイドバートンマナ"


def test_sidebar_equivalent_navigation_preserves_inputs_across_render():
    # サイドバー相当のページ移動を経ても、consult_situation / consult_question /
    # suggest_text / tone_regulation が失われないことを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    st.session_state[KEYS["consult_situation"]] = "サイドバー経由の状況"
    st.session_state[KEYS["consult_question"]] = "サイドバー経由の質問"
    st.session_state[KEYS["suggest"]] = "サイドバーキーワード"
    st.session_state[KEYS["tone_reg"]] = "サイドバートンマナ"

    render_article_ui(**_common_kwargs())

    # サイドバーの画面移動サポートボタンが押された時と同じ呼び出し。
    app._go_to_article_page(ARTICLE_PAGE_OFFICIAL)
    render_article_ui(**_common_kwargs())

    assert st.session_state[KEYS["consult_situation"]] == "サイドバー経由の状況"
    assert st.session_state[KEYS["consult_question"]] == "サイドバー経由の質問"
    assert st.session_state[KEYS["suggest"]] == "サイドバーキーワード"
    assert st.session_state[KEYS["tone_reg"]] == "サイドバートンマナ"
    assert st.session_state[ARTICLE_ACTIVE_PAGE_KEY] == ARTICLE_PAGE_OFFICIAL


def test_render_page_5_draft_does_not_call_scroll_tracker_or_restore():
    # ページ5(下書き作成)の中身にも、自動スクロール保存・自動復帰の呼び出しが
    # 紛れ込んでいないことを回帰確認する。
    active_source = _active_code_lines(inspect.getsource(article_ui._render_page_5_draft))

    assert "_render_article_scroll_tracker()" not in active_source
    assert "_render_article_scroll_restore(" not in active_source


# =========================
# 非表示ページのwidget keyがStreamlitの仕様で消えた場合の安定化
# =========================

def test_memo_is_included_in_shadow_keys():
    # 読者や書き方のメモ(article__memo)は、他の入力欄よりシャドウStateの
    # 保護を受けておらず消えやすい状態だったため、追加されたことを確認する。
    assert KEYS["memo"] in article_ui.SHADOW_KEYS
    assert article_ui.SHADOW_KEYS[KEYS["memo"]] == "article_shadow__memo"


def test_clear_shadow_state_clears_memo_shadow_too():
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    st.session_state["article_shadow__memo"] = "前のメモ"

    article_ui._clear_shadow_state()

    assert st.session_state["article_shadow__memo"] == ""


def test_backup_article_inputs_does_not_overwrite_with_blank():
    # _backup_shadow_state()と同じ考え方で、現在値が空文字のときは
    # 既存のarticle__input_backupを空で潰さないことを確認する。
    _reset_session_state()
    st.session_state[KEYS["consult_situation"]] = "テスト用の状況"

    article_ui._backup_article_inputs()
    assert st.session_state["article__input_backup"][KEYS["consult_situation"]] == "テスト用の状況"

    # 何らかの理由（非表示ページのwidget keyが消えた等）で現在値が空になった。
    st.session_state[KEYS["consult_situation"]] = ""
    article_ui._backup_article_inputs()

    # 既存のバックアップ値は空で潰されず、そのまま残る。
    assert st.session_state["article__input_backup"][KEYS["consult_situation"]] == "テスト用の状況"


def test_clear_form_only_still_empties_input_backup_after_guard_added():
    # 空文字上書き防止ガードを追加しても、明示クリア操作では
    # article__input_backupが確実に空になることの回帰確認
    # （test_clear_form_only_clears_shadow_state_and_input_backupと重複する
    # 観点だが、_backup_article_inputs()側の変更を直接対象にするため個別に置く）。
    _reset_session_state()
    st.session_state[KEYS["consult_situation"]] = "テスト用の状況"
    article_ui._backup_article_inputs()
    assert st.session_state["article__input_backup"] != {}

    article_ui._clear_form_only()

    assert st.session_state["article__input_backup"] == {}


def test_get_current_consult_values_is_read_only_and_uses_backup_fallback():
    # Streamlitの仕様で、非表示ページのwidget keyがsession_stateから
    # 削除された状態を人工的に再現する（del）。
    _reset_session_state()
    st.session_state[KEYS["consult_situation"]] = "テスト用の状況"
    st.session_state[KEYS["consult_question"]] = "テスト用の質問"
    article_ui._backup_article_inputs()

    del st.session_state[KEYS["consult_situation"]]
    del st.session_state[KEYS["consult_question"]]

    situation, question = article_ui._get_current_consult_values()
    assert situation == "テスト用の状況"
    assert question == "テスト用の質問"

    # 読む専用ヘルパーのため、呼んだだけではsession_stateへ書き戻さない。
    assert KEYS["consult_situation"] not in st.session_state
    assert KEYS["consult_question"] not in st.session_state


def test_get_current_consult_values_uses_shadow_when_backup_is_empty():
    _reset_session_state()
    st.session_state[KEYS["consult_situation"]] = ""
    st.session_state[KEYS["consult_question"]] = ""
    st.session_state["article_shadow__consult_situation"] = "シャドウの状況"
    st.session_state["article_shadow__consult_question"] = "シャドウの質問"

    situation, question = article_ui._get_current_consult_values()
    assert situation == "シャドウの状況"
    assert question == "シャドウの質問"


def test_get_current_consult_values_returns_blank_after_explicit_clear():
    # 「入力欄を空にする」で明示的に空にした直後は、backup/shadowも
    # 一緒に消えているため、読む専用ヘルパーでも古い値が復活しないこと。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    st.session_state[KEYS["consult_situation"]] = "テスト用の状況"
    st.session_state[KEYS["consult_question"]] = "テスト用の質問"
    render_article_ui(**_common_kwargs())

    article_ui._clear_form_only()

    situation, question = article_ui._get_current_consult_values()
    assert situation == ""
    assert question == ""


def test_restore_blank_generation_inputs_from_backup_or_shadow_restores_widget_keys():
    # 下書き作成直前の書き戻しは、consult_situation/consult_question以外に
    # suggest/tone_regも対象にすることを確認する。
    # evidence_url/evidence_title/evidence_facts/evidence_pointsは
    # backup/shadowの復元競合を避けるため対象外にしたので、この経路では
    # 検証しない（form_data経由の復元はtest_restore_blank_generation_inputs_
    # fills_all_evidence_fields_from_form_dataで別途検証する）。
    _reset_session_state()
    st.session_state[KEYS["consult_situation"]] = "テスト用の状況"
    st.session_state[KEYS["consult_question"]] = "テスト用の質問"
    st.session_state[KEYS["suggest"]] = "keyword A"
    st.session_state[KEYS["tone_reg"]] = "です・ます調"
    article_ui._backup_article_inputs()
    article_ui._backup_shadow_state()

    for key in (
        KEYS["consult_situation"],
        KEYS["consult_question"],
        KEYS["suggest"],
        KEYS["tone_reg"],
    ):
        del st.session_state[key]

    article_ui._restore_blank_generation_inputs_from_backup_or_shadow()

    assert st.session_state[KEYS["consult_situation"]] == "テスト用の状況"
    assert st.session_state[KEYS["consult_question"]] == "テスト用の質問"
    assert st.session_state[KEYS["suggest"]] == "keyword A"
    assert st.session_state[KEYS["tone_reg"]] == "です・ます調"


def test_restore_blank_generation_inputs_does_not_revive_after_explicit_clear():
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    st.session_state[KEYS["consult_situation"]] = "テスト用の状況"
    st.session_state[KEYS["consult_question"]] = "テスト用の質問"
    render_article_ui(**_common_kwargs())

    article_ui._clear_form_only()
    article_ui._restore_blank_generation_inputs_from_backup_or_shadow()

    assert st.session_state[KEYS["consult_situation"]] == ""
    assert st.session_state[KEYS["consult_question"]] == ""


def test_restore_blank_generation_inputs_does_not_overwrite_existing_non_blank_value():
    # 現在値が既に非空なら、backup/shadowの値で上書きしないこと。
    _reset_session_state()
    st.session_state[KEYS["consult_situation"]] = "古い状況"
    article_ui._backup_article_inputs()

    st.session_state[KEYS["consult_situation"]] = "新しい状況"
    article_ui._restore_blank_generation_inputs_from_backup_or_shadow()

    assert st.session_state[KEYS["consult_situation"]] == "新しい状況"


def test_generate_draft_uses_backup_when_widget_keys_were_pruned(monkeypatch):
    # 5/7ページの「入力あり」表示と、「下書きを作る」ボタンの判定が
    # 同じヘルパーを使うことで、非表示ページのwidget keyがStreamlitの仕様で
    # 消えていても、backupに値があれば「空にしてください」警告が出ず、
    # 実際に下書きが生成されることを確認する（回帰の中心シナリオ）。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_DRAFT
    st.session_state[KEYS["consult_situation"]] = "テスト用の状況"
    st.session_state[KEYS["consult_question"]] = "テスト用の質問"

    # ページ1のwidgetが退避しておいた状態を再現する。
    article_ui._backup_article_inputs()
    article_ui._backup_shadow_state()

    # Streamlitの仕様で、ページ1のwidget keyが削除された状態を人工的に再現する。
    del st.session_state[KEYS["consult_situation"]]
    del st.session_state[KEYS["consult_question"]]

    warnings = []
    monkeypatch.setattr(st, "warning", lambda text: warnings.append(text))
    monkeypatch.setattr(st, "button", lambda label, **kwargs: label == "✨ 下書きを作る")

    render_article_ui(**_common_kwargs())

    assert "『今の状況』と『知りたいこと』を入れてください。" not in warnings
    assert str(st.session_state.get(KEYS["last_text"], "")).strip() != ""


# =========================
# article__form_data 単一ソース化（第1段階）
# =========================

def test_form_data_bootstraps_from_existing_widget_values_on_first_render():
    # 旧方式（widget keyのみ）からの移行時、初回描画だけform_dataへ取り込む。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    st.session_state[KEYS["consult_situation"]] = "テスト用の状況"
    st.session_state[KEYS["consult_question"]] = "テスト用の質問"

    render_article_ui(**_common_kwargs())

    assert article_ui._get_form_data_value("consult_situation") == "テスト用の状況"
    assert article_ui._get_form_data_value("consult_question") == "テスト用の質問"


def test_page1_inputs_are_readable_from_form_data_after_widget_key_pruned():
    # 1/7でconsult_situation/consult_questionを入力→5/7へ進む→widget keyを
    # delしても、form_dataから表示・判定できることを確認する（回帰の中心）。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    st.session_state[KEYS["consult_situation"]] = "テスト用の状況"
    st.session_state[KEYS["consult_question"]] = "テスト用の質問"
    render_article_ui(**_common_kwargs())

    article_ui._go_to_page(ARTICLE_PAGE_DRAFT)

    # Streamlitの仕様で、ページ1のwidget keyが削除された状態を人工的に再現する。
    del st.session_state[KEYS["consult_situation"]]
    del st.session_state[KEYS["consult_question"]]

    situation, question = article_ui._get_current_consult_values()
    assert situation == "テスト用の状況"
    assert question == "テスト用の質問"


def test_generate_draft_reads_form_data_directly_without_backup_or_shadow(monkeypatch):
    # backup/shadowを一切経由せず、article__form_dataだけから
    # 「今の状況」「知りたいこと」を読めることを確認する（単一ソース化の核心）。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_DRAFT
    article_ui._set_form_data_value("consult_situation", "フォームデータの状況")
    article_ui._set_form_data_value("consult_question", "フォームデータの質問")

    warnings = []
    monkeypatch.setattr(st, "warning", lambda text: warnings.append(text))
    monkeypatch.setattr(st, "button", lambda label, **kwargs: label == "✨ 下書きを作る")

    render_article_ui(**_common_kwargs())

    assert "『今の状況』と『知りたいこと』を入れてください。" not in warnings
    assert str(st.session_state.get(KEYS["last_text"], "")).strip() != ""


def test_page6_does_not_render_manual_edit_text_area(monkeypatch):
    # 記事モードの役割を「AI下書きを作る場所」に戻すため、6/6（最終ページ）には
    # 手動編集用の大きなst.text_areaを置かないことを確認する（回帰防止）。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_PRECHECK
    st.session_state[KEYS["last_text"]] = "AIが作った初稿です。"
    article_ui._set_form_data_value("last_text", "AIが作った初稿です。")

    text_area_calls = []
    monkeypatch.setattr(st, "text_area", lambda *a, **k: text_area_calls.append((a, k)))

    render_article_ui(**_common_kwargs())

    assert text_area_calls == []


def test_page6_shows_last_text_readonly(monkeypatch):
    # 6/6はlast_textを読み取り専用で表示することを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_PRECHECK
    st.session_state[KEYS["last_text"]] = "AIが作った初稿です。"
    article_ui._set_form_data_value("last_text", "AIが作った初稿です。")

    captured_code = []
    monkeypatch.setattr(st, "code", lambda text, **kwargs: captured_code.append(text))

    render_article_ui(**_common_kwargs())

    assert "AIが作った初稿です。" in captured_code


def test_page6_shows_check_mode_handoff_not_save_body(monkeypatch):
    # 6/6（最終ページ）は「保存する本文」ではなく、文章チェックへ進む導線に
    # なっていることを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_PRECHECK
    st.session_state[KEYS["last_text"]] = "AIが作った初稿です。"
    article_ui._set_form_data_value("last_text", "AIが作った初稿です。")

    markdown_calls = []
    monkeypatch.setattr(st, "markdown", lambda text, **kwargs: markdown_calls.append(text))
    monkeypatch.setattr(st, "button", lambda label, **kwargs: False)

    render_article_ui(**_common_kwargs())

    assert not any("保存する本文" in text for text in markdown_calls)
    assert any("文章チェック" in text for text in markdown_calls)


def test_send_last_text_to_check_mode_fills_quality_inputs_and_requests_menu():
    # last_textが文章チェックモード用の入力欄に渡せることを確認する。
    _reset_session_state()
    st.session_state[KEYS["last_text"]] = "AIが作った初稿です。"

    article_ui._send_last_text_to_check_mode()

    from modules.quality_ui import KEYS as quality_keys, QUALITY_MENU_LABEL

    assert st.session_state[quality_keys["check_text_saved"]] == "AIが作った初稿です。"
    assert st.session_state[quality_keys["check_text_widget"]] == "AIが作った初稿です。"
    assert st.session_state["menu_request"] == QUALITY_MENU_LABEL


def test_last_text_does_not_overwrite_edited_copy_text_on_regenerate(monkeypatch):
    # 編集済みcopy_textは、下書き再生成（last_text更新）で勝手に上書きされない。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_DRAFT
    st.session_state[KEYS["consult_situation"]] = "テスト用の状況"
    st.session_state[KEYS["consult_question"]] = "テスト用の質問"
    article_ui._set_form_data_value("copy_text", "利用者が手直しした本文です。")
    article_ui._set_form_data_value("copy_last_sig", "old-sig")

    monkeypatch.setattr(st, "button", lambda label, **kwargs: label == "✨ 下書きを作る")

    render_article_ui(**_common_kwargs())

    assert str(st.session_state.get(KEYS["last_text"], "")).strip() != ""
    assert article_ui._get_form_data_value("copy_text") == "利用者が手直しした本文です。"


def test_clear_form_only_empties_form_data_basic_inputs():
    # 「入力欄を空にする」でform_dataのconsult_situation/consult_questionも
    # 空になり、古い値が復活しないことを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    st.session_state[KEYS["consult_situation"]] = "テスト用の状況"
    st.session_state[KEYS["consult_question"]] = "テスト用の質問"
    render_article_ui(**_common_kwargs())

    article_ui._clear_form_only()

    assert article_ui._get_form_data_value("consult_situation") == ""
    assert article_ui._get_form_data_value("consult_question") == ""


def test_clear_generated_only_empties_form_data_generated_fields():
    # 「下書きを消す」でform_dataのlast_text/plan_result/copy_text/
    # copy_last_sigも空になることを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_DRAFT
    article_ui._set_form_data_value("last_text", "AIが作った初稿です。")
    article_ui._set_form_data_value("plan_result", "設計図です。")
    article_ui._set_form_data_value("copy_text", "利用者が手直しした本文です。")
    article_ui._set_form_data_value("copy_last_sig", "sig-value")

    article_ui._clear_generated_only()

    assert article_ui._get_form_data_value("last_text") == ""
    assert article_ui._get_form_data_value("plan_result") == ""
    assert article_ui._get_form_data_value("copy_text") == ""
    assert article_ui._get_form_data_value("copy_last_sig") == ""


# =========================
# article__form_data 第2段階：未対応入力欄の追加
# （メニュー往復で記事モードの入力欄が空になる問題の回帰確認）
# =========================

_EXPANDED_FORM_DATA_FIELDS = (
    "main_kw",
    "sub_kw",
    "theme",
    "memo",
    "evidence_url",
    "evidence_title",
    "evidence_facts",
    "evidence_points",
    "evidence",
    "suggest",
    "tone_reg",
)


def test_form_data_stage1_fields_cover_previously_unprotected_inputs():
    # 未対応だった基本入力・確認先・書き方の希望の各欄が、
    # 第1段階のフィールド群に追加されたことを確認する。
    for field in _EXPANDED_FORM_DATA_FIELDS:
        assert field in article_ui.FORM_DATA_STAGE1_FIELDS
        assert field in article_ui.FORM_DATA_WIDGET_SYNC_FIELDS

    # 既存フィールドが温存されていることも回帰確認する。
    for legacy_field in (
        "consult_situation", "consult_question",
        "last_text", "plan_result", "copy_text", "copy_last_sig",
    ):
        assert legacy_field in article_ui.FORM_DATA_STAGE1_FIELDS


def test_form_data_field_by_widget_key_matches_sync_fields():
    # _get_effective_value()が使う逆引き辞書が、FORM_DATA_WIDGET_SYNC_FIELDS
    # と常に一致していることを確認する（ハードコードの取りこぼしを防ぐ）。
    for field in article_ui.FORM_DATA_WIDGET_SYNC_FIELDS:
        widget_key = KEYS[field]
        assert article_ui._FORM_DATA_FIELD_BY_WIDGET_KEY[widget_key] == field


def test_article_form_data_never_stores_api_key():
    # ベル憲法：APIキーはarticle__form_dataへ絶対に入れない。
    assert "openai_api_key" not in KEYS.values()
    assert "openai_api_key" not in article_ui.FORM_DATA_STAGE1_FIELDS


def test_expanded_fields_are_reseeded_from_form_data_when_widget_key_missing():
    # widget key削除（Streamlitの仕様で非表示ページ・非表示モードの値が
    # 消える挙動）を模擬しても、article__form_dataから正しく再シード
    # されることを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_STYLE
    st.session_state[article_ui.ARTICLE_FORM_DATA_KEY] = {
        "main_kw": "相続税",
        "sub_kw": "基礎控除",
        "theme": "相続税の基本",
        "memo": "わかりやすく",
        "evidence_url": "https://example.jp/tax",
        "evidence_title": "国税庁資料",
        "evidence_facts": "3000万円",
        "evidence_points": "基礎控除の計算方法",
        "suggest": "相続税, 基礎控除",
        "tone_reg": "だ・である調",
    }
    # widget keyは一切存在しない状態（初回描画やメニュー往復直後を再現）。

    render_article_ui(**_common_kwargs())

    assert st.session_state[KEYS["main_kw"]] == "相続税"
    assert st.session_state[KEYS["sub_kw"]] == "基礎控除"
    assert st.session_state[KEYS["theme"]] == "相続税の基本"
    assert st.session_state[KEYS["memo"]] == "わかりやすく"
    assert st.session_state[KEYS["evidence_url"]] == "https://example.jp/tax"
    assert st.session_state[KEYS["evidence_title"]] == "国税庁資料"
    assert st.session_state[KEYS["evidence_facts"]] == "3000万円"
    assert st.session_state[KEYS["evidence_points"]] == "基礎控除の計算方法"
    assert st.session_state[KEYS["suggest"]] == "相続税, 基礎控除"
    assert st.session_state[KEYS["tone_reg"]] == "だ・である調"


def test_menu_round_trip_does_not_blank_article_inputs():
    # 本番で報告された不具合の回帰テスト：
    # 記事モード→他モード→記事モードという往復（ページ番号は変わらない）で、
    # Streamlitの仕様によりwidget keyがsession_stateから削除された状態を
    # 再現しても、入力欄が空に見えないことを確認する。
    # （_restore_stale_inputs_on_page_change()はページ番号が変わった時にしか
    #   復元しないため、form_data化前はこのケースで空欄化していた）
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_KEYWORD

    st.session_state[KEYS["main_kw"]] = "在職老齢年金"
    st.session_state[KEYS["sub_kw"]] = "支給停止"
    st.session_state[KEYS["theme"]] = "年金の仕組み"
    st.session_state[KEYS["memo"]] = "わかりやすく"
    st.session_state[KEYS["evidence_url"]] = "https://example.jp/pension"
    st.session_state[KEYS["evidence_title"]] = "厚生労働省資料"
    st.session_state[KEYS["evidence_facts"]] = "65歳"
    st.session_state[KEYS["evidence_points"]] = "支給停止の条件"
    st.session_state[KEYS["suggest"]] = "在職老齢年金, 支給停止"
    st.session_state[KEYS["tone_reg"]] = "ですます調"

    render_article_ui(**_common_kwargs())

    # メニュー移動で記事モードが描画されない1回のrerunを経て、
    # Streamlitがwidget keyをsession_stateから削除する挙動を再現する。
    # ARTICLE_ACTIVE_PAGE_KEYはwidget keyではないため、この間も
    # ARTICLE_PAGE_KEYWORDのまま維持される（＝ページ番号は変わらない）。
    for field in (
        "main_kw", "sub_kw", "theme", "memo",
        "evidence_url", "evidence_title", "evidence_facts", "evidence_points",
        "suggest", "tone_reg",
    ):
        del st.session_state[KEYS[field]]

    render_article_ui(**_common_kwargs())

    assert st.session_state[KEYS["main_kw"]] == "在職老齢年金"
    assert st.session_state[KEYS["sub_kw"]] == "支給停止"
    assert st.session_state[KEYS["theme"]] == "年金の仕組み"
    assert st.session_state[KEYS["memo"]] == "わかりやすく"
    assert st.session_state[KEYS["evidence_url"]] == "https://example.jp/pension"
    assert st.session_state[KEYS["evidence_title"]] == "厚生労働省資料"
    assert st.session_state[KEYS["evidence_facts"]] == "65歳"
    assert st.session_state[KEYS["evidence_points"]] == "支給停止の条件"
    assert st.session_state[KEYS["suggest"]] == "在職老齢年金, 支給停止"
    assert st.session_state[KEYS["tone_reg"]] == "ですます調"


def test_clear_form_only_empties_form_data_for_expanded_fields():
    # 「入力欄を空にする」で、拡張したform_dataフィールドも空になり、
    # メニュー往復後に古い値で復活しないことを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    st.session_state[KEYS["main_kw"]] = "テストキーワード"
    st.session_state[KEYS["evidence_url"]] = "https://example.jp"
    render_article_ui(**_common_kwargs())

    article_ui._clear_form_only()

    for field in _EXPANDED_FORM_DATA_FIELDS:
        assert article_ui._get_form_data_value(field) == ""


def test_clear_generated_only_preserves_form_data_input_fields():
    # 「下書きを消す」は生成結果だけを消す仕様に変更した。
    # 拡張したform_dataフィールド（入力材料）は消さずに残すことを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    st.session_state[KEYS["main_kw"]] = "テストキーワード"
    st.session_state[KEYS["evidence_url"]] = "https://example.jp"
    render_article_ui(**_common_kwargs())

    article_ui._clear_generated_only()

    assert article_ui._get_form_data_value("main_kw") == "テストキーワード"
    assert article_ui._get_form_data_value("evidence_url") == "https://example.jp"


def test_restore_snapshot_fill_blanks_syncs_restored_values_into_form_data():
    # 空欄だけ前の状態を戻す操作の後、form_data側にも復元後の値が
    # 反映されていることを確認する（反映しないと、後でwidget keyが
    # Streamlitの仕様で消えたときに、form_dataの古い空値で再び
    # 空欄化してしまう）。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    st.session_state[KEYS["main_kw"]] = "元のキーワード"
    render_article_ui(**_common_kwargs())

    article_ui._save_snapshot()

    st.session_state[KEYS["main_kw"]] = ""
    article_ui._sync_form_data_field_from_widget("main_kw")

    article_ui._restore_snapshot_fill_blanks()

    assert st.session_state[KEYS["main_kw"]] == "元のキーワード"
    assert article_ui._get_form_data_value("main_kw") == "元のキーワード"


# =========================
# st.form4項目（公式情報・確認先ページ）の空文字復元
# （3/6ページの入力欄が消える不具合の回帰確認）
# =========================
#
# st.form内のwidget（evidence_url/evidence_title/evidence_facts/
# evidence_points）は、そのフォームが描画されないrunがあると、widget key
# そのものは残るが値だけStreamlitの実行完了時処理で空文字に戻ることが
# ある（missingにはならない）。_seed_widget_from_form_data_if_missing()は
# 「widget keyが無い場合だけ」しか復元しないため、この「キーはあるが
# 空文字」のケースを救えない。ここでは、この状態を直接再現して検証する。
#
# なお、この「キーは残るが値だけ空文字に戻る」現象はst.form内の項目に
# 限らないことが判明したため、実際の復元処理（_reseed_blank_widget_from_form_data）
# はFORM_DATA_WIDGET_SYNC_FIELDS全体に適用されている。他フィールド
# （suggest/memo/tone_reg/main_kw/sub_kw/theme）向けの同様のテストは、
# このすぐ後のセクションにまとめている。

_FORM_SCOPED_FIELDS = ("evidence_url", "evidence_title", "evidence_facts", "evidence_points")


def test_form_scoped_fields_restore_from_form_data_when_widget_key_is_blank_but_present():
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_STYLE
    st.session_state[article_ui.ARTICLE_FORM_DATA_KEY] = {
        "evidence_url": "https://example.jp/pension",
        "evidence_title": "厚生労働省資料",
        "evidence_facts": "65歳",
        "evidence_points": "支給停止の条件",
    }
    # widget keyは「存在するが空文字」の状態（st.form未描画runでの
    # Streamlitの強制リセットを再現）。
    for field in _FORM_SCOPED_FIELDS:
        st.session_state[KEYS[field]] = ""

    render_article_ui(**_common_kwargs())

    assert st.session_state[KEYS["evidence_url"]] == "https://example.jp/pension"
    assert st.session_state[KEYS["evidence_title"]] == "厚生労働省資料"
    assert st.session_state[KEYS["evidence_facts"]] == "65歳"
    assert st.session_state[KEYS["evidence_points"]] == "支給停止の条件"


def test_form_scoped_fields_do_not_revive_when_form_data_is_also_blank():
    # 利用者がフォームで実際に空欄のまま送信した場合（form_data側も
    # 空文字で揃っている）は、widget値が空文字のままで正しい。
    # 古い値の復活が起きないことを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_STYLE
    st.session_state[article_ui.ARTICLE_FORM_DATA_KEY] = {
        "evidence_url": "",
        "evidence_title": "",
        "evidence_facts": "",
        "evidence_points": "",
    }
    for field in _FORM_SCOPED_FIELDS:
        st.session_state[KEYS[field]] = ""

    render_article_ui(**_common_kwargs())

    for field in _FORM_SCOPED_FIELDS:
        assert st.session_state[KEYS[field]] == ""


def test_form_scoped_fields_do_not_overwrite_widget_value_that_is_already_non_blank():
    # 表示widgetにすでに非空値が入っている場合（今まさに編集中）は、
    # form_dataの別の値で上書きしないことを確認する。
    # （表示widget keyがst.text_area/st.text_inputの実際のkey=になった
    #   ため、「編集中」はKEYS[field]ではなく表示widget keyで再現する）
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_OFFICIAL
    st.session_state[article_ui.ARTICLE_FORM_DATA_KEY] = {
        "evidence_url": "https://example.jp/old",
    }
    display_key = article_ui._get_display_widget_key("evidence_url")
    st.session_state[display_key] = "https://example.jp/new-being-typed"

    render_article_ui(**_common_kwargs())

    assert st.session_state[display_key] == "https://example.jp/new-being-typed"


def test_form_scoped_fields_still_restore_when_widget_key_is_fully_missing():
    # 既存の「widget keyが無い場合」の復元（_seed_widget_from_form_data_if_missing）
    # が、今回の変更で壊れていないことを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_STYLE
    st.session_state[article_ui.ARTICLE_FORM_DATA_KEY] = {
        "evidence_url": "https://example.jp/pension",
        "evidence_title": "厚生労働省資料",
        "evidence_facts": "65歳",
        "evidence_points": "支給停止の条件",
    }
    # widget keyは一切存在しない状態。

    render_article_ui(**_common_kwargs())

    assert st.session_state[KEYS["evidence_url"]] == "https://example.jp/pension"
    assert st.session_state[KEYS["evidence_title"]] == "厚生労働省資料"
    assert st.session_state[KEYS["evidence_facts"]] == "65歳"
    assert st.session_state[KEYS["evidence_points"]] == "支給停止の条件"


# =========================
# 3/6ページ（公式情報・確認先）のst.form撤去
# （st.form内のwidgetは反映ボタンを押すまでsession_stateへ反映されない
#   仕様のため、反映ボタンを押さずにページ移動すると入力が消えて見える
#   不具合があった。evidence_url/title/facts/pointsを通常widget化し、
#   on_changeで即時article__form_dataへ同期する方式に変更した）
# =========================

def test_official_info_page_does_not_use_st_form():
    source = inspect.getsource(article_ui._render_page_3_official_info)
    assert "st.form(" not in source
    assert "st.form_submit_button(" not in source


def test_official_info_page_evidence_fields_have_on_change_sync():
    source = inspect.getsource(article_ui._render_page_3_official_info)
    for field in ("evidence_url", "evidence_title", "evidence_facts", "evidence_points"):
        assert f'args=("{field}",)' in source
    # article__inputs_saved化した12項目のため、on_change先は表示widget
    # 対応の同期関数（_sync_display_widget_to_inputs_saved）。内部で
    # article__form_data・旧KEYS[field]（互換ミラー）にも書くため、
    # form_dataへの反映自体は引き続き行われる。
    assert source.count("on_change=_sync_display_widget_to_inputs_saved") == 4


def test_evidence_fields_persist_to_form_data_without_pressing_apply_button():
    # on_change相当（_sync_form_data_field_from_widget）を模擬した後、
    # 「この確認先を下書きに反映する」を押さずにページを移動しても、
    # article__form_dataに値が残ることを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_OFFICIAL
    render_article_ui(**_common_kwargs())

    st.session_state[KEYS["evidence_url"]] = "https://example.jp/new"
    st.session_state[KEYS["evidence_title"]] = "新しい資料名"
    st.session_state[KEYS["evidence_facts"]] = "新しい数字"
    st.session_state[KEYS["evidence_points"]] = "新しい要点"
    for field in ("evidence_url", "evidence_title", "evidence_facts", "evidence_points"):
        article_ui._sync_form_data_field_from_widget(field)
    # 反映ボタンは押さない。

    article_ui._go_to_page(ARTICLE_PAGE_STYLE)
    render_article_ui(**_common_kwargs())

    assert article_ui._get_form_data_value("evidence_url") == "https://example.jp/new"
    assert article_ui._get_form_data_value("evidence_title") == "新しい資料名"
    assert article_ui._get_form_data_value("evidence_facts") == "新しい数字"
    assert article_ui._get_form_data_value("evidence_points") == "新しい要点"


def test_apply_button_still_builds_combined_evidence_text():
    # 反映ボタンの役割は「入力保存」ではなく、4項目からevidence合成文を
    # 作ること。_sync_evidence_text_from_parts()の挙動自体は変更していない
    # ことを確認する。
    _reset_session_state()
    st.session_state[KEYS["evidence_url"]] = "https://example.jp"
    st.session_state[KEYS["evidence_title"]] = "資料名"
    st.session_state[KEYS["evidence_facts"]] = "大事な数字"
    st.session_state[KEYS["evidence_points"]] = "要点"

    article_ui._sync_evidence_text_from_parts()

    combined = st.session_state[KEYS["evidence"]]
    assert "https://example.jp" in combined
    assert "資料名" in combined
    assert "大事な数字" in combined
    assert "要点" in combined


def test_effective_evidence_text_works_without_pressing_apply_button():
    # 下書き生成が実際に使う_get_effective_input_evidence_text()は、
    # 反映ボタンを押していなくても4項目の現在値からその場で確認先文を
    # 作れることを確認する（反映ボタンは要約文の作成用途のみで、
    # 生成結果そのものには影響しない設計であることの回帰確認）。
    _reset_session_state()
    st.session_state[KEYS["evidence_url"]] = "https://example.jp/pending"
    st.session_state[KEYS["evidence_title"]] = "未反映の資料名"
    st.session_state[KEYS["evidence_facts"]] = "未反映の数字"
    st.session_state[KEYS["evidence_points"]] = "未反映の要点"

    text = article_ui._get_effective_input_evidence_text()

    assert "https://example.jp/pending" in text
    assert "未反映の資料名" in text
    assert "未反映の数字" in text
    assert "未反映の要点" in text


# =========================
# 3/6の4項目をshadow/input_backupの復元競合から除外
# （backup→shadow→form_dataという復元順序では、backup/shadowが
#   form_dataより古い値を持っている場合にその古い値が先に空欄を埋めて
#   しまい、正本のform_dataが負けてしまう競合があった。evidence_url/
#   evidence_title/evidence_facts/evidence_pointsはこの4系統をやめ、
#   article__form_data一本にする）
# =========================

_EVIDENCE_SPLIT_FIELDS = ("evidence_url", "evidence_title", "evidence_facts", "evidence_points")


def test_evidence_fields_are_excluded_from_shadow_keys():
    for field in _EVIDENCE_SPLIT_FIELDS:
        assert KEYS[field] not in article_ui.SHADOW_KEYS


def test_evidence_fields_are_excluded_from_input_backup_keys():
    for field in _EVIDENCE_SPLIT_FIELDS:
        assert KEYS[field] not in article_ui._ARTICLE_INPUT_BACKUP_KEYS


def test_form_data_wins_over_stale_shadow_and_backup_for_evidence_fields():
    # 今回発見した競合の回帰確認。backup/shadowに古い値が残っていても
    # （除外前のセッションの残骸を想定）、evidence 4項目はもう
    # backup/shadow経由では復元されず、article__form_dataの新しい値だけが
    # 使われることを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_OFFICIAL
    st.session_state[article_ui.ARTICLE_FORM_DATA_KEY] = {
        "evidence_url": "https://example.jp/new",
        "evidence_title": "新資料名",
        "evidence_facts": "新数字",
        "evidence_points": "新要点",
    }
    st.session_state["article__input_backup"] = {
        KEYS["evidence_url"]: "https://example.jp/old",
        KEYS["evidence_title"]: "旧資料名",
        KEYS["evidence_facts"]: "旧数字",
        KEYS["evidence_points"]: "旧要点",
    }
    st.session_state["article_shadow__evidence_url"] = "https://example.jp/old"
    st.session_state["article_shadow__evidence_title"] = "旧資料名"
    st.session_state["article_shadow__evidence_facts"] = "旧数字"
    st.session_state["article_shadow__evidence_points"] = "旧要点"
    # widget keyはStreamlitの仕様で消えた状態を再現。
    for field in _EVIDENCE_SPLIT_FIELDS:
        if KEYS[field] in st.session_state:
            del st.session_state[KEYS[field]]

    render_article_ui(**_common_kwargs())

    assert st.session_state[KEYS["evidence_url"]] == "https://example.jp/new"
    assert st.session_state[KEYS["evidence_title"]] == "新資料名"
    assert st.session_state[KEYS["evidence_facts"]] == "新数字"
    assert st.session_state[KEYS["evidence_points"]] == "新要点"


def test_evidence_fields_survive_multi_hop_page_jump_like_sidebar():
    # 3/6 -> 1/6 -> 3/6（サイドバー画面移動サポート相当の複数ページ移動）
    # を経ても4項目が残ることを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_OFFICIAL
    render_article_ui(**_common_kwargs())

    st.session_state[KEYS["evidence_url"]] = "https://example.jp/hop"
    st.session_state[KEYS["evidence_title"]] = "資料hop"
    st.session_state[KEYS["evidence_facts"]] = "数字hop"
    st.session_state[KEYS["evidence_points"]] = "要点hop"
    for field in _EVIDENCE_SPLIT_FIELDS:
        article_ui._sync_form_data_field_from_widget(field)

    # サイドバーの「1. 基本入力へ」相当（app._go_to_article_page）。
    app._go_to_article_page(ARTICLE_PAGE_BASIC)
    for field in _EVIDENCE_SPLIT_FIELDS:
        if KEYS[field] in st.session_state:
            del st.session_state[KEYS[field]]
    render_article_ui(**_common_kwargs())

    # サイドバーの「3. 公式情報へ」相当で戻る。
    app._go_to_article_page(ARTICLE_PAGE_OFFICIAL)
    render_article_ui(**_common_kwargs())

    assert st.session_state[KEYS["evidence_url"]] == "https://example.jp/hop"
    assert st.session_state[KEYS["evidence_title"]] == "資料hop"
    assert st.session_state[KEYS["evidence_facts"]] == "数字hop"
    assert st.session_state[KEYS["evidence_points"]] == "要点hop"


def test_evidence_fields_survive_draft_and_precheck_round_trip():
    # 3/6 -> 5/6(下書き作成) -> 6/6 -> 3/6という移動を経ても4項目が
    # 残ることを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_OFFICIAL
    render_article_ui(**_common_kwargs())

    st.session_state[KEYS["evidence_url"]] = "https://example.jp/draft"
    st.session_state[KEYS["evidence_title"]] = "資料draft"
    st.session_state[KEYS["evidence_facts"]] = "数字draft"
    st.session_state[KEYS["evidence_points"]] = "要点draft"
    for field in _EVIDENCE_SPLIT_FIELDS:
        article_ui._sync_form_data_field_from_widget(field)

    article_ui._go_to_page(ARTICLE_PAGE_DRAFT)
    for field in _EVIDENCE_SPLIT_FIELDS:
        if KEYS[field] in st.session_state:
            del st.session_state[KEYS[field]]
    render_article_ui(**_common_kwargs())

    article_ui._go_to_page(ARTICLE_PAGE_PRECHECK)
    render_article_ui(**_common_kwargs())

    article_ui._go_to_page(ARTICLE_PAGE_OFFICIAL)
    render_article_ui(**_common_kwargs())

    assert st.session_state[KEYS["evidence_url"]] == "https://example.jp/draft"
    assert st.session_state[KEYS["evidence_title"]] == "資料draft"
    assert st.session_state[KEYS["evidence_facts"]] == "数字draft"
    assert st.session_state[KEYS["evidence_points"]] == "要点draft"


def test_generation_restore_keys_include_all_four_evidence_fields():
    # evidence_url/evidence_titleだけでなくevidence_facts/evidence_pointsも
    # 生成直前の書き戻し対象に揃えたことを確認する。
    for field in _EVIDENCE_SPLIT_FIELDS:
        assert KEYS[field] in article_ui._GENERATION_RESTORE_KEYS


def test_restore_blank_generation_inputs_fills_all_evidence_fields_from_form_data():
    _reset_session_state()
    st.session_state[article_ui.ARTICLE_FORM_DATA_KEY] = {
        "evidence_url": "https://example.jp/gen",
        "evidence_title": "資料gen",
        "evidence_facts": "数字gen",
        "evidence_points": "要点gen",
    }
    for field in _EVIDENCE_SPLIT_FIELDS:
        st.session_state[KEYS[field]] = ""

    article_ui._restore_blank_generation_inputs_from_backup_or_shadow()

    assert st.session_state[KEYS["evidence_url"]] == "https://example.jp/gen"
    assert st.session_state[KEYS["evidence_title"]] == "資料gen"
    assert st.session_state[KEYS["evidence_facts"]] == "数字gen"
    assert st.session_state[KEYS["evidence_points"]] == "要点gen"


# =========================
# 2/6・4/6へのon_change同期追加
# （記事モードのサイドバー青ボタン撤去にあわせ、下部「次へ」「戻る」で
#   進む際の安全性を上げるため、1/6・3/6と同じon_change即時同期を
#   2/6のsuggest、4/6のmemo/tone_reg/main_kw/sub_kw/themeにも揃えた）
# =========================

_PAGE2_ON_CHANGE_FIELDS = ("suggest",)
_PAGE4_ON_CHANGE_FIELDS = ("memo", "tone_reg", "main_kw", "sub_kw", "theme")


def test_page2_suggest_field_has_on_change_sync():
    source = inspect.getsource(article_ui._render_page_2_keyword_and_detail_entry)
    for field in _PAGE2_ON_CHANGE_FIELDS:
        assert f'args=("{field}",)' in source
    # article__inputs_saved化した12項目のため、on_change先は表示widget
    # 対応の同期関数（_sync_display_widget_to_inputs_saved）に変わった。
    assert source.count("on_change=_sync_display_widget_to_inputs_saved") == len(_PAGE2_ON_CHANGE_FIELDS)


def test_page4_fields_have_on_change_sync():
    source = inspect.getsource(article_ui._render_page_4_writing_style)
    for field in _PAGE4_ON_CHANGE_FIELDS:
        assert f'args=("{field}",)' in source
    # article__inputs_saved化した12項目のため、on_change先は表示widget
    # 対応の同期関数（_sync_display_widget_to_inputs_saved）に変わった。
    assert source.count("on_change=_sync_display_widget_to_inputs_saved") == len(_PAGE4_ON_CHANGE_FIELDS)


def test_page2_and_page4_fields_persist_to_form_data_without_page_transition():
    # on_change相当（_sync_form_data_field_from_widget）を模擬した直後、
    # ページ移動を挟まなくてもarticle__form_dataに値が反映されることを
    # 確認する（1/6・3/6と同じ即時同期方式になったことの回帰確認）。
    _reset_session_state()
    for field in _PAGE2_ON_CHANGE_FIELDS + _PAGE4_ON_CHANGE_FIELDS:
        st.session_state[KEYS[field]] = f"value-{field}"
        article_ui._sync_form_data_field_from_widget(field)

    for field in _PAGE2_ON_CHANGE_FIELDS + _PAGE4_ON_CHANGE_FIELDS:
        assert article_ui._get_form_data_value(field) == f"value-{field}"


# =========================
# 第2段階：_sync_form_data_stage1_from_widgetsの空文字ガード（案B-lite）
# （本番調査で、非表示ページのwidget keyが空文字のまま残っている場合に、
#   _go_to_page経由でarticle__form_dataの正しい値が空文字で踏み潰される
#   ことを確認した。article__inputs_saved化した12項目については、
#   widget keyが空文字ならform_dataを上書きしない）
# =========================

def test_sync_form_data_stage1_does_not_blank_out_stage1_fields():
    _reset_session_state()
    for field in article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS:
        article_ui._set_form_data_value(field, f"正しい値-{field}")
        # 非表示ページのwidget keyが空文字のまま残っている状況を再現する。
        st.session_state[KEYS[field]] = ""

    article_ui._sync_form_data_stage1_from_widgets()

    for field in article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS:
        assert article_ui._get_form_data_value(field) == f"正しい値-{field}"


def test_sync_form_data_stage1_still_syncs_non_blank_stage1_fields():
    # 空文字ガードを追加しても、widgetに実際に入力された非空値は
    # 従来通りform_dataへ反映されることを確認する（回帰確認）。
    _reset_session_state()
    for field in article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS:
        st.session_state[KEYS[field]] = f"新しい値-{field}"

    article_ui._sync_form_data_stage1_from_widgets()

    for field in article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS:
        assert article_ui._get_form_data_value(field) == f"新しい値-{field}"


def test_sync_form_data_stage1_still_blanks_out_non_stage1_fields():
    # 12項目以外（copy_text/evidence）は、案B-lite導入前と同じ挙動
    # （空文字も同期する）を維持することを確認する。
    _reset_session_state()
    article_ui._set_form_data_value("copy_text", "古いコピー本文")
    article_ui._set_form_data_value("evidence", "古い根拠")
    st.session_state[KEYS["copy_text"]] = ""
    st.session_state[KEYS["evidence"]] = ""

    article_ui._sync_form_data_stage1_from_widgets()

    assert article_ui._get_form_data_value("copy_text") == ""
    assert article_ui._get_form_data_value("evidence") == ""


# =========================
# blank時reseedの全FORM_DATA_WIDGET_SYNC_FIELDSへの拡張
# （suggest/memo/tone_reg/main_kw/sub_kw/theme も、widget keyは残るが
#   値だけ空文字に戻る現象が起きることが本番調査で判明したための回帰確認）
# =========================

_NON_FORM_BLANK_RESEED_FIELDS = ("suggest", "memo", "tone_reg", "main_kw", "sub_kw", "theme")


def test_non_form_fields_restore_from_form_data_when_widget_key_is_blank_but_present():
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_DRAFT
    st.session_state[article_ui.ARTICLE_FORM_DATA_KEY] = {
        "suggest": "在職老齢年金, 支給停止",
        "memo": "わかりやすく",
        "tone_reg": "ですます調",
        "main_kw": "在職老齢年金",
        "sub_kw": "支給停止",
        "theme": "年金の仕組み",
    }
    # widget keyは「存在するが空文字」の状態（描画されないrunでの
    # Streamlitの強制リセットを再現）。
    for field in _NON_FORM_BLANK_RESEED_FIELDS:
        st.session_state[KEYS[field]] = ""

    render_article_ui(**_common_kwargs())

    assert st.session_state[KEYS["suggest"]] == "在職老齢年金, 支給停止"
    assert st.session_state[KEYS["memo"]] == "わかりやすく"
    assert st.session_state[KEYS["tone_reg"]] == "ですます調"
    assert st.session_state[KEYS["main_kw"]] == "在職老齢年金"
    assert st.session_state[KEYS["sub_kw"]] == "支給停止"
    assert st.session_state[KEYS["theme"]] == "年金の仕組み"


def test_non_form_fields_do_not_revive_when_form_data_is_also_blank():
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_DRAFT
    st.session_state[article_ui.ARTICLE_FORM_DATA_KEY] = {
        field: "" for field in _NON_FORM_BLANK_RESEED_FIELDS
    }
    for field in _NON_FORM_BLANK_RESEED_FIELDS:
        st.session_state[KEYS[field]] = ""

    render_article_ui(**_common_kwargs())

    for field in _NON_FORM_BLANK_RESEED_FIELDS:
        assert st.session_state[KEYS[field]] == ""


def test_non_form_fields_do_not_overwrite_widget_value_that_is_already_non_blank():
    # 表示widgetにすでに非空値が入っている場合（今まさに編集中）は、
    # form_dataの別の値で上書きしないことを確認する。
    # （表示widget keyがst.text_area/st.text_inputの実際のkey=になった
    #   ため、「編集中」はKEYS[field]ではなく表示widget keyで再現する）
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_STYLE
    st.session_state[article_ui.ARTICLE_FORM_DATA_KEY] = {
        "memo": "古いメモ",
    }
    display_key = article_ui._get_display_widget_key("memo")
    st.session_state[display_key] = "いま編集中のメモ"

    render_article_ui(**_common_kwargs())

    assert st.session_state[display_key] == "いま編集中のメモ"


def test_non_form_fields_still_restore_when_widget_key_is_fully_missing():
    # 既存の「widget keyが無い場合」の復元が、今回の拡張後も壊れていないことを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_DRAFT
    st.session_state[article_ui.ARTICLE_FORM_DATA_KEY] = {
        "suggest": "在職老齢年金, 支給停止",
        "memo": "わかりやすく",
        "tone_reg": "ですます調",
        "main_kw": "在職老齢年金",
        "sub_kw": "支給停止",
        "theme": "年金の仕組み",
    }
    # widget keyは一切存在しない状態。

    render_article_ui(**_common_kwargs())

    assert st.session_state[KEYS["suggest"]] == "在職老齢年金, 支給停止"
    assert st.session_state[KEYS["memo"]] == "わかりやすく"
    assert st.session_state[KEYS["tone_reg"]] == "ですます調"
    assert st.session_state[KEYS["main_kw"]] == "在職老齢年金"
    assert st.session_state[KEYS["sub_kw"]] == "支給停止"
    assert st.session_state[KEYS["theme"]] == "年金の仕組み"


def test_blank_reseed_never_targets_api_key():
    # ベル憲法：APIキーはblank時reseedの対象に絶対に含めない。
    assert "openai_api_key" not in article_ui.FORM_DATA_WIDGET_SYNC_FIELDS


# =========================
# _clear_generated_only：生成結果だけを消し、入力材料は消さない
# =========================

def test_clear_generated_only_does_not_clear_any_input_material():
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    st.session_state[KEYS["consult_situation"]] = "相談内容"
    st.session_state[KEYS["consult_question"]] = "知りたいこと"
    st.session_state[KEYS["main_kw"]] = "メインキーワード"
    st.session_state[KEYS["sub_kw"]] = "サブキーワード"
    st.session_state[KEYS["theme"]] = "テーマ"
    st.session_state[KEYS["memo"]] = "書き方メモ"
    st.session_state[KEYS["evidence_url"]] = "https://example.jp"
    st.session_state[KEYS["evidence_title"]] = "資料名"
    st.session_state[KEYS["evidence_facts"]] = "大事な数字"
    st.session_state[KEYS["evidence_points"]] = "要点"
    st.session_state[KEYS["evidence"]] = "根拠まとめ"
    st.session_state[KEYS["suggest"]] = "検索キーワード"
    st.session_state[KEYS["tone_reg"]] = "ですます調"
    render_article_ui(**_common_kwargs())

    article_ui._clear_generated_only()

    assert st.session_state[KEYS["consult_situation"]] == "相談内容"
    assert st.session_state[KEYS["consult_question"]] == "知りたいこと"
    assert st.session_state[KEYS["main_kw"]] == "メインキーワード"
    assert st.session_state[KEYS["sub_kw"]] == "サブキーワード"
    assert st.session_state[KEYS["theme"]] == "テーマ"
    assert st.session_state[KEYS["memo"]] == "書き方メモ"
    assert st.session_state[KEYS["evidence_url"]] == "https://example.jp"
    assert st.session_state[KEYS["evidence_title"]] == "資料名"
    assert st.session_state[KEYS["evidence_facts"]] == "大事な数字"
    assert st.session_state[KEYS["evidence_points"]] == "要点"
    assert st.session_state[KEYS["evidence"]] == "根拠まとめ"
    assert st.session_state[KEYS["suggest"]] == "検索キーワード"
    assert st.session_state[KEYS["tone_reg"]] == "ですます調"

    for field in (
        "consult_situation", "consult_question", "main_kw", "sub_kw", "theme", "memo",
        "evidence_url", "evidence_title", "evidence_facts", "evidence_points",
        "evidence", "suggest", "tone_reg",
    ):
        assert article_ui._get_form_data_value(field) != ""


def test_clear_generated_only_clears_generated_results():
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_PRECHECK
    st.session_state[KEYS["last_text"]] = "AIが作った下書き"
    st.session_state[KEYS["plan_result"]] = "設計図"
    st.session_state[KEYS["proof_evidence"]] = "証拠として固定した根拠"
    st.session_state[KEYS["proof_evidence_compact"]] = "証拠として固定した要点"
    st.session_state[KEYS["proof_suggest"]] = "証拠として固定した検索語"
    st.session_state[KEYS["proof_memo"]] = "証拠として固定したメモ"
    render_article_ui(**_common_kwargs())
    article_ui._set_copy_state_from_text("編集欄の本文")

    article_ui._clear_generated_only()

    assert st.session_state[KEYS["last_text"]] == ""
    assert st.session_state[KEYS["plan_result"]] == ""
    assert st.session_state[KEYS["proof_evidence"]] == ""
    assert st.session_state[KEYS["proof_evidence_compact"]] == ""
    assert st.session_state[KEYS["proof_suggest"]] == ""
    assert st.session_state[KEYS["proof_memo"]] == ""
    assert st.session_state[KEYS["copy_text"]] == ""
    assert st.session_state[KEYS["copy_last_sig"]] == ""
    assert article_ui._get_form_data_value("last_text") == ""
    assert article_ui._get_form_data_value("plan_result") == ""
    assert article_ui._get_form_data_value("copy_text") == ""


# =========================
# 記事モード上部ナビゲーションボタンの撤去
# =========================

def test_render_article_ui_does_not_render_top_nav_buttons(monkeypatch):
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_OFFICIAL

    captured_keys = []

    def fake_button(label, **kwargs):
        captured_keys.append(kwargs.get("key"))
        return False

    monkeypatch.setattr(st, "button", fake_button)

    render_article_ui(**_common_kwargs())

    assert "btn_article_page_next_top" not in captured_keys
    assert "btn_article_page_back_top" not in captured_keys


def test_render_article_ui_still_renders_bottom_nav_buttons(monkeypatch):
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_OFFICIAL

    captured_keys = []

    def fake_button(label, **kwargs):
        captured_keys.append(kwargs.get("key"))
        return False

    monkeypatch.setattr(st, "button", fake_button)

    render_article_ui(**_common_kwargs())

    assert "btn_article_page_next_bottom" in captured_keys
    assert "btn_article_page_back_bottom" in captured_keys


# =========================
# 5/6：下書き生成のバリデーション失敗時も詰まらないことの回帰確認
# （st.stop()がrender_article_ui末尾の下部ナビゲーションの描画まで
#   止めてしまい、利用者がページ移動できなくなっていた不具合の修正確認）
# =========================

def test_page5_validation_failure_still_shows_bottom_back_button(monkeypatch):
    # consult_situation/consult_questionが空のまま「下書きを作る」を押すと
    # バリデーションに失敗するが、その場合でも下部の「戻る」ボタンが
    # 必ず描画されることを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_DRAFT

    captured_keys = []

    def fake_button(label, **kwargs):
        captured_keys.append(kwargs.get("key"))
        return label == "✨ 下書きを作る"

    monkeypatch.setattr(st, "button", fake_button)

    render_article_ui(**_common_kwargs())

    assert "btn_article_page_back_bottom" in captured_keys


def test_page5_validation_failure_does_not_generate_draft(monkeypatch):
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_DRAFT

    monkeypatch.setattr(st, "button", lambda label, **kwargs: label == "✨ 下書きを作る")

    render_article_ui(**_common_kwargs())

    assert st.session_state.get(KEYS["last_text"], "") == ""


# =========================
# article__inputs_saved（第1段階：文章チェックモード型の正本を12項目だけ導入）
# 1/6〜4/6の入力材料12項目（consult_situation/consult_question/suggest/
# evidence_url/evidence_title/evidence_facts/evidence_points/memo/
# tone_reg/main_kw/sub_kw/theme）だけを対象に、article__form_dataと並行して
# 存在する新しい正本article__inputs_savedを導入する。
# copy_text/evidence/last_text/plan_result/copy_last_signはこの段階では対象外。
# =========================

def test_inputs_saved_stage1_fields_has_exactly_12_items():
    assert len(article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS) == 12
    assert set(article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS) == {
        "consult_situation", "consult_question", "suggest",
        "evidence_url", "evidence_title", "evidence_facts", "evidence_points",
        "memo", "tone_reg", "main_kw", "sub_kw", "theme",
    }


def test_inputs_saved_stage1_fields_excludes_out_of_scope_fields():
    # copy_text/evidence/last_text/plan_result/copy_last_sigは第1段階の対象外。
    for field in ("copy_text", "evidence", "last_text", "plan_result", "copy_last_sig"):
        assert field not in article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS


def test_inputs_saved_fields_by_page_covers_exactly_stage1_fields():
    # ページごとの対象フィールド表を全部足し合わせると、12項目のフラット
    # 一覧とちょうど一致する（漏れ・重複が無い）ことを確認する。
    flattened = [
        field
        for fields in article_ui.ARTICLE_INPUTS_SAVED_FIELDS_BY_PAGE.values()
        for field in fields
    ]
    assert sorted(flattened) == sorted(article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS)
    assert len(flattened) == len(set(flattened))


def test_all_12_fields_are_saved_into_inputs_saved_when_synced():
    # 12項目それぞれについて、on_change相当（_sync_widget_to_inputs_saved）を
    # 各ページで模擬すると、article__inputs_savedに反映されることを確認する。
    _reset_session_state()
    field_values = {field: f"value-{field}" for field in article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS}

    for page, fields in article_ui.ARTICLE_INPUTS_SAVED_FIELDS_BY_PAGE.items():
        st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = page
        for field in fields:
            st.session_state[KEYS[field]] = field_values[field]
            article_ui._sync_widget_to_inputs_saved(field)

    for field, value in field_values.items():
        assert article_ui._get_inputs_saved_value(field) == value


def test_go_to_page_only_syncs_current_page_fields_into_inputs_saved():
    # 現在ページ以外の項目のwidget keyが空文字で残っていても、article__inputs_saved
    # の値を踏み潰さないことを確認する（12項目一括同期をやめ、現在ページの
    # 項目だけに限定した第1段階修正の核心となる回帰テスト）。
    _reset_session_state()
    article_ui._set_inputs_saved_value("consult_situation", "非表示ページの正しい値")
    # 1/6ページ（consult_situationが属するページ）のwidget keyが、
    # 何らかの理由で空文字のまま残っている状況を再現する。
    st.session_state[KEYS["consult_situation"]] = ""
    # 現在ページは4/6（consult_situationとは無関係のページ）。
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_STYLE
    st.session_state[KEYS["memo"]] = "スタイルページの新しい値"

    article_ui._go_to_page(ARTICLE_PAGE_DRAFT)

    # 現在ページ（4/6）のmemoは同期される。
    assert article_ui._get_inputs_saved_value("memo") == "スタイルページの新しい値"
    # 現在ページに属さないconsult_situationは、widget keyが空文字でも
    # 上書きされず、元の非空値のままである。
    assert article_ui._get_inputs_saved_value("consult_situation") == "非表示ページの正しい値"


def test_widget_key_missing_restores_from_inputs_saved():
    # widget keyがsession_stateに無い（非表示ページでStreamlitの仕様により
    # 消えた想定）場合、article__inputs_savedから復元されることを確認する。
    _reset_session_state()
    article_ui._set_inputs_saved_value("main_kw", "保存済みのキーワード")
    if KEYS["main_kw"] in st.session_state:
        del st.session_state[KEYS["main_kw"]]

    article_ui._seed_widget_from_inputs_saved_if_missing("main_kw")

    assert st.session_state[KEYS["main_kw"]] == "保存済みのキーワード"


def test_widget_key_blank_restores_from_inputs_saved_via_reseed():
    # widget keyは残るが値だけ空文字に戻るケースでも、article__inputs_saved
    # から復元されることを確認する。
    _reset_session_state()
    article_ui._set_inputs_saved_value("theme", "保存済みのテーマ")
    st.session_state[KEYS["theme"]] = ""

    article_ui._reseed_blank_widget_from_inputs_saved("theme")

    assert st.session_state[KEYS["theme"]] == "保存済みのテーマ"


def test_page_change_restores_blank_widget_from_inputs_saved():
    # 実際のページ切り替え経路（_restore_stale_inputs_on_page_change）を
    # 通しても、空文字widgetがarticle__inputs_savedから復元されることを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    article_ui._set_inputs_saved_value("consult_question", "保存済みの質問")
    st.session_state[KEYS["consult_question"]] = ""
    # ページが実際に切り替わった直後であることにする
    # （このガードが無いと同じページ内の再描画のたびに毎回復元してしまう）。
    st.session_state[article_ui.ARTICLE_SHADOW_RESTORED_PAGE_KEY] = ARTICLE_PAGE_KEYWORD

    article_ui._restore_stale_inputs_on_page_change()

    assert st.session_state[KEYS["consult_question"]] == "保存済みの質問"


def test_get_effective_value_prefers_inputs_saved_over_form_data():
    # 表示・判定用の読み取りヘルパーで、article__form_dataより
    # article__inputs_savedが優先されることを確認する。
    _reset_session_state()
    article_ui._set_form_data_value("suggest", "古いform_dataの値")
    article_ui._set_inputs_saved_value("suggest", "新しいinputs_savedの値")
    if KEYS["suggest"] in st.session_state:
        del st.session_state[KEYS["suggest"]]

    assert article_ui._get_effective_value(KEYS["suggest"]) == "新しいinputs_savedの値"


def test_seed_widget_prefers_inputs_saved_over_form_data():
    # widget key不在時のseedでも、article__form_dataより
    # article__inputs_savedが先に埋まって優先されることを確認する
    # （render_article_ui冒頭のbulk seedループの呼び出し順序の回帰確認）。
    _reset_session_state()
    article_ui._set_form_data_value("evidence_title", "古いform_dataの値")
    article_ui._set_inputs_saved_value("evidence_title", "新しいinputs_savedの値")
    if KEYS["evidence_title"] in st.session_state:
        del st.session_state[KEYS["evidence_title"]]

    article_ui._seed_widget_from_inputs_saved_if_missing("evidence_title")
    article_ui._seed_widget_from_form_data_if_missing("evidence_title")

    assert st.session_state[KEYS["evidence_title"]] == "新しいinputs_savedの値"


def test_reseed_widget_prefers_inputs_saved_over_form_data():
    # widget値が空文字のときのreseedでも、article__form_dataより
    # article__inputs_savedが先に埋まって優先されることを確認する
    # （_restore_stale_inputs_on_page_change内の呼び出し順序の回帰確認）。
    _reset_session_state()
    article_ui._set_form_data_value("sub_kw", "古いform_dataの値")
    article_ui._set_inputs_saved_value("sub_kw", "新しいinputs_savedの値")
    st.session_state[KEYS["sub_kw"]] = ""

    article_ui._reseed_blank_widget_from_inputs_saved("sub_kw")
    article_ui._reseed_blank_widget_from_form_data("sub_kw")

    assert st.session_state[KEYS["sub_kw"]] == "新しいinputs_savedの値"


def test_clear_generated_only_preserves_inputs_saved():
    # 「下書きを消す」操作では、article__inputs_savedの12項目を消さないことを確認する。
    _reset_session_state()
    for field in article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS:
        article_ui._set_inputs_saved_value(field, f"value-{field}")
    st.session_state[KEYS["last_text"]] = "AIが作った下書き"

    article_ui._clear_generated_only()

    for field in article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS:
        assert article_ui._get_inputs_saved_value(field) == f"value-{field}"


def test_clear_form_only_clears_inputs_saved_stage1_fields():
    # 「入力欄を空にする」操作のときだけ、article__inputs_savedの12項目が空になることを確認する。
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    render_article_ui(**_common_kwargs())
    for field in article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS:
        article_ui._set_inputs_saved_value(field, f"value-{field}")

    article_ui._clear_form_only()

    for field in article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS:
        assert article_ui._get_inputs_saved_value(field) == ""


# =========================
# 開発用：入力保持デバッグ（原因特定用の一時機能）
# 1/6〜4/6の入力材料12項目について、widget key/inputs_saved/form_data/
# backup/shadowの状態を本番画面で確認するための一時デバッグ表示。
# APIキー・secrets・環境変数・本文全文は表示しない設計になっていることを確認する。
# =========================

def test_debug_preview_text_truncates_to_20_chars():
    long_text = "あ" * 40
    preview = article_ui._debug_preview_text(long_text)
    assert preview != long_text
    assert preview.startswith("あ" * 20)
    assert len(preview) <= 21  # 20文字 + 省略記号1文字


def test_debug_preview_text_does_not_truncate_short_text():
    short_text = "短い値"
    assert article_ui._debug_preview_text(short_text) == short_text


def test_debug_field_status_covers_only_stage1_fields():
    _reset_session_state()
    rows = [article_ui._debug_field_status(field) for field in article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS]

    assert len(rows) == 12
    assert {row["項目"] for row in rows} == set(article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS)

    excluded_fields = {"copy_text", "evidence", "last_text", "plan_result", "copy_last_sig"}
    assert excluded_fields.isdisjoint({row["項目"] for row in rows})


def test_debug_field_status_widget_key_names_exclude_generated_text_fields():
    excluded_widget_keys = {
        KEYS["copy_text"], KEYS["evidence"], KEYS["last_text"],
        KEYS["plan_result"], KEYS["copy_last_sig"],
    }
    for field in article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS:
        row = article_ui._debug_field_status(field)
        assert row["表示widget key"] not in excluded_widget_keys


def test_debug_field_status_never_exposes_api_key():
    _reset_session_state()
    st.session_state["openai_api_key"] = "sk-should-not-leak"
    st.session_state[KEYS["main_kw"]] = "テストキーワード"

    row = article_ui._debug_field_status("main_kw")

    for value in row.values():
        assert "sk-should-not-leak" not in str(value)


def test_debug_field_status_only_shows_preview_not_full_text():
    _reset_session_state()
    long_value = "個人情報を含む長い相談内容です。" * 5
    display_key = article_ui._get_display_widget_key("consult_situation")
    st.session_state[display_key] = long_value

    row = article_ui._debug_field_status("consult_situation")

    assert row["表示widget先頭20文字"] != long_value
    assert len(row["表示widget先頭20文字"]) <= 21
    assert row["表示widget文字数"] == len(long_value)


def test_debug_panel_hidden_when_checkbox_unchecked(monkeypatch):
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC

    dataframe_calls = []
    monkeypatch.setattr(st, "checkbox", lambda label, **kwargs: False)
    monkeypatch.setattr(st, "dataframe", lambda *a, **k: dataframe_calls.append((a, k)))

    article_ui._render_debug_inputs_saved_panel()

    assert dataframe_calls == []


def test_debug_panel_shows_exactly_12_rows_when_checkbox_checked(monkeypatch):
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC
    for field in article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS:
        article_ui._set_inputs_saved_value(field, f"value-{field}")

    dataframe_calls = []
    monkeypatch.setattr(st, "checkbox", lambda label, **kwargs: True)
    monkeypatch.setattr(st, "dataframe", lambda *a, **k: dataframe_calls.append((a, k)))

    article_ui._render_debug_inputs_saved_panel()

    assert len(dataframe_calls) == 1
    rows = dataframe_calls[0][0][0]
    assert len(rows) == 12
    assert {row["項目"] for row in rows} == set(article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS)


# =========================
# 世代番号付き表示widget key（本番調査：widget/inputs_savedの両方に値が
# 残っているのに画面の入力欄が空に見える現象がst.rerun()方式でも直らず、
# 同一固定keyのままではブラウザ側の表示が追従しないと判断したための対応）
# =========================

def test_get_display_widget_key_returns_generation_numbered_key():
    _reset_session_state()
    assert article_ui._get_display_widget_key("consult_situation") == "article__display__consult_situation__v1"
    assert article_ui._get_display_key_generation("consult_situation") == 1


def test_prepare_current_page_display_widgets_bumps_generation_only_when_restoring():
    _reset_session_state()
    article_ui._set_inputs_saved_value("consult_situation", "続きの相談内容")

    assert article_ui._get_display_key_generation("consult_situation") == 1
    article_ui._prepare_current_page_display_widgets_before_render(ARTICLE_PAGE_BASIC)
    assert article_ui._get_display_key_generation("consult_situation") == 2


def test_prepare_current_page_display_widgets_does_not_bump_generation_when_display_key_non_blank():
    # typing中（表示widget keyが非空）は、世代を上げない＝副作用を起こさない。
    _reset_session_state()
    display_key = article_ui._get_display_widget_key("consult_situation")
    st.session_state[display_key] = "入力中の値"
    article_ui._set_inputs_saved_value("consult_situation", "別の保存値")

    article_ui._prepare_current_page_display_widgets_before_render(ARTICLE_PAGE_BASIC)

    assert article_ui._get_display_key_generation("consult_situation") == 1
    assert st.session_state[display_key] == "入力中の値"


def test_prepare_current_page_display_widgets_deletes_old_generation_key():
    _reset_session_state()
    old_key = article_ui._get_display_widget_key("consult_situation")
    st.session_state[old_key] = ""
    article_ui._set_inputs_saved_value("consult_situation", "続きの相談内容")

    article_ui._prepare_current_page_display_widgets_before_render(ARTICLE_PAGE_BASIC)

    new_key = article_ui._get_display_widget_key("consult_situation")
    assert new_key != old_key
    assert old_key not in st.session_state
    assert st.session_state[new_key] == "続きの相談内容"


def test_prepare_current_page_display_widgets_seeds_new_generation_from_inputs_saved():
    _reset_session_state()
    article_ui._set_inputs_saved_value("consult_question", "知りたいことの続き")

    article_ui._prepare_current_page_display_widgets_before_render(ARTICLE_PAGE_BASIC)

    new_key = article_ui._get_display_widget_key("consult_question")
    assert st.session_state[new_key] == "知りたいことの続き"
    # 互換ミラーの旧KEYS[field]にも同じ値が反映される。
    assert st.session_state[KEYS["consult_question"]] == "知りたいことの続き"


def test_prepare_current_page_display_widgets_falls_back_to_form_data():
    _reset_session_state()
    article_ui._set_form_data_value("consult_question", "form_dataだけにある値")

    article_ui._prepare_current_page_display_widgets_before_render(ARTICLE_PAGE_BASIC)

    new_key = article_ui._get_display_widget_key("consult_question")
    assert st.session_state[new_key] == "form_dataだけにある値"


def test_prepare_current_page_display_widgets_only_touches_current_page_fields():
    _reset_session_state()
    # suggestは2/6の項目。1/6分の準備を呼んでも触らないことを確認する。
    article_ui._set_inputs_saved_value("suggest", "サジェストの値")

    article_ui._prepare_current_page_display_widgets_before_render(ARTICLE_PAGE_BASIC)

    assert "article__display__suggest__v1" not in st.session_state
    assert article_ui._get_display_key_generation("suggest") == 1


def test_prepare_current_page_display_widgets_never_touches_out_of_scope_fields():
    # copy_text/evidence/last_text/plan_result/copy_last_sigは
    # ARTICLE_INPUTS_SAVED_FIELDS_BY_PAGEに含まれないため対象外。
    _reset_session_state()
    for page in (ARTICLE_PAGE_BASIC, ARTICLE_PAGE_KEYWORD, ARTICLE_PAGE_OFFICIAL, ARTICLE_PAGE_STYLE):
        article_ui._prepare_current_page_display_widgets_before_render(page)
    for field in ("copy_text", "evidence", "last_text", "plan_result", "copy_last_sig"):
        assert f"article__display__{field}__v1" not in st.session_state


def test_sync_display_widget_to_inputs_saved_updates_inputs_saved_form_data_and_mirror():
    _reset_session_state()
    display_key = article_ui._get_display_widget_key("theme")
    st.session_state[display_key] = "新しいテーマ"

    article_ui._sync_display_widget_to_inputs_saved("theme")

    assert article_ui._get_inputs_saved_value("theme") == "新しいテーマ"
    assert article_ui._get_form_data_value("theme") == "新しいテーマ"
    assert st.session_state[KEYS["theme"]] == "新しいテーマ"


def test_page_1_renders_consult_fields_with_display_widget_key(monkeypatch):
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC

    observed_keys = []

    def fake_text_area(label, *args, **kwargs):
        observed_keys.append(kwargs.get("key"))
        return ""

    monkeypatch.setattr(st, "text_area", fake_text_area)

    article_ui._render_page_1_basic()

    assert article_ui._get_display_widget_key("consult_situation") in observed_keys
    assert article_ui._get_display_widget_key("consult_question") in observed_keys
    assert KEYS["consult_situation"] not in observed_keys
    assert KEYS["consult_question"] not in observed_keys


def test_page_2_renders_suggest_with_display_widget_key(monkeypatch):
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_KEYWORD

    observed_keys = []

    def fake_text_input(label, *args, **kwargs):
        observed_keys.append(kwargs.get("key"))
        return ""

    monkeypatch.setattr(st, "text_input", fake_text_input)
    monkeypatch.setattr(st, "button", lambda label, **kwargs: False)

    article_ui._render_page_2_keyword_and_detail_entry()

    assert article_ui._get_display_widget_key("suggest") in observed_keys
    assert KEYS["suggest"] not in observed_keys


def test_debug_field_status_reflects_current_generation_display_key():
    _reset_session_state()
    article_ui._set_inputs_saved_value("consult_situation", "続きの相談内容")
    article_ui._prepare_current_page_display_widgets_before_render(ARTICLE_PAGE_BASIC)

    row = article_ui._debug_field_status("consult_situation")

    assert row["世代番号"] == 2
    assert row["表示widget key"] == article_ui._get_display_widget_key("consult_situation")
    assert row["表示widget値"] == "非空"
    assert row["表示widget先頭20文字"] == "続きの相談内容"


def test_prepare_current_page_display_widgets_no_side_effect_while_typing():
    # 復元不要時（表示widget keyが非空）は、何度呼んでも世代・値が
    # 変わらないことを確認する（typing中の副作用防止）。
    _reset_session_state()
    display_key = article_ui._get_display_widget_key("consult_situation")
    st.session_state[display_key] = "た"
    article_ui._set_inputs_saved_value("consult_situation", "た")

    for _ in range(3):
        article_ui._prepare_current_page_display_widgets_before_render(ARTICLE_PAGE_BASIC)
        assert article_ui._get_display_key_generation("consult_situation") == 1
        assert st.session_state[display_key] == "た"


def test_clear_form_only_also_clears_current_generation_display_keys():
    _reset_session_state()
    for field in article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS:
        st.session_state[article_ui._get_display_widget_key(field)] = f"value-{field}"

    article_ui._clear_form_only()

    for field in article_ui.ARTICLE_INPUTS_SAVED_STAGE1_FIELDS:
        assert st.session_state[article_ui._get_display_widget_key(field)] == ""


def test_generation_evidence_text_keeps_non_priority_term_facts_with_url_and_title():
    # 本番調査で見つかった不具合の再現：URL・資料名を入力し、「大事な数字・
    # 期限」に老齢厚生年金など_extract_key_fact_lines()のpriority_terms（
    # ドメイン固有語）に一致しない文章を入れると、URL/資料名だけで
    # important_rowsが非空になり、フォールバック（全行採用）が発動せず
    # factsが丸ごと消えていた。分割入力がある場合はbuild_evidence_text()の
    # 出力をそのまま使い、圧縮しないことを確認する。
    _reset_session_state()
    st.session_state[KEYS["evidence_url"]] = "https://www.saisoncard.co.jp/customer-support/"
    st.session_state[KEYS["evidence_title"]] = "カスタマーサポート"
    st.session_state[KEYS["evidence_facts"]] = (
        "継続手数料2200円・1年間使用が無い場合に継続手数料が掛かる。"
    )
    st.session_state[KEYS["evidence_points"]] = ""

    result = article_ui._get_generation_evidence_text()

    assert "継続手数料2200円・1年間使用が無い場合に継続手数料が掛かる。" in result


def test_generation_evidence_text_keeps_facts_when_points_is_blank():
    _reset_session_state()
    st.session_state[KEYS["evidence_url"]] = ""
    st.session_state[KEYS["evidence_title"]] = ""
    st.session_state[KEYS["evidence_facts"]] = "重要な事実の本文"
    st.session_state[KEYS["evidence_points"]] = ""

    result = article_ui._get_generation_evidence_text()

    assert "重要な事実の本文" in result


def test_generation_evidence_text_uses_build_evidence_text_output_as_is_when_split_mode():
    _reset_session_state()
    st.session_state[KEYS["evidence_url"]] = "https://example.com/info"
    st.session_state[KEYS["evidence_title"]] = "資料タイトル"
    st.session_state[KEYS["evidence_facts"]] = "本文A\n本文B"
    st.session_state[KEYS["evidence_points"]] = "一番大事なこと"

    expected = article_ui.build_evidence_text(
        url="https://example.com/info",
        title="資料タイトル",
        facts="本文A\n本文B",
        points="一番大事なこと",
    ).strip()

    result = article_ui._get_generation_evidence_text()

    assert result == expected


def test_generation_evidence_text_still_compacts_legacy_evidence_when_split_fields_blank():
    # 分割欄がすべて空で旧統合フィールドevidenceだけが使われる場合は、
    # 従来通り_extract_key_fact_lines()による圧縮を適用する（回帰確認）。
    _reset_session_state()
    st.session_state[KEYS["evidence_url"]] = ""
    st.session_state[KEYS["evidence_title"]] = ""
    st.session_state[KEYS["evidence_facts"]] = ""
    st.session_state[KEYS["evidence_points"]] = ""
    st.session_state[KEYS["evidence"]] = (
        "老齢厚生年金の受給要件は、基礎控除の対象となる期限を含む。\n"
        "ホーム > ページの先頭\n"
        "無関係なノイズ行"
    )

    result = article_ui._get_generation_evidence_text()

    assert "老齢厚生年金の受給要件は、基礎控除の対象となる期限を含む。" in result
    assert "ホーム > ページの先頭" not in result


def test_is_money_contract_topic_detects_fee_and_card_keywords():
    for keyword in ("継続手数料", "解約", "カード", "年会費", "返金", "請求"):
        _reset_session_state()
        st.session_state[KEYS["consult_question"]] = f"{keyword}について知りたいです。"
        assert article_ui._is_money_contract_topic() is True, keyword


def test_is_money_contract_topic_is_false_for_low_risk_generic_topic():
    _reset_session_state()
    st.session_state[KEYS["consult_situation"]] = "掃除機の吸引力が落ちてきました。"
    st.session_state[KEYS["consult_question"]] = "掃除機のお手入れ方法を知りたいです。"

    assert article_ui._is_money_contract_topic() is False


def test_build_writing_prompt_includes_money_contract_caution_rules_for_saison_card_example():
    _reset_session_state()
    st.session_state[KEYS["consult_situation"]] = "セゾンカードを持っていますが、ほとんど使っていません。"
    st.session_state[KEYS["consult_question"]] = "継続手数料2200円はどんな時に請求されますか。異議申し立てはできますか。"
    st.session_state[KEYS["main_kw"]] = "セゾンカード 継続手数料"
    st.session_state[KEYS["evidence_url"]] = ""
    st.session_state[KEYS["evidence_title"]] = ""
    st.session_state[KEYS["evidence_facts"]] = ""
    st.session_state[KEYS["evidence_points"]] = ""
    st.session_state[KEYS["evidence"]] = "継続手数料は年1回、税込2200円。"

    prompt = article_ui._build_writing_prompt("")

    assert "【お金・契約テーマの追加ルール】" in prompt
    assert "断定しすぎないでください" in prompt
    assert "問い合わせて確認するのが安全です" in prompt
    assert "根拠に明記されていない限り断定しないでください" in prompt
    assert "根拠に明記されていない専門用語・制度用語・原因説明を勝手に作らないでください" in prompt
    assert "休眠状態" in prompt
    assert "顧客の責任" in prompt


def test_build_writing_prompt_does_not_include_money_contract_rules_for_low_risk_topic():
    _reset_session_state()
    st.session_state[KEYS["consult_situation"]] = "掃除機の吸引力が落ちてきました。"
    st.session_state[KEYS["consult_question"]] = "掃除機のお手入れ方法を知りたいです。"
    st.session_state[KEYS["main_kw"]] = "掃除機 お手入れ"
    st.session_state[KEYS["evidence_url"]] = ""
    st.session_state[KEYS["evidence_title"]] = ""
    st.session_state[KEYS["evidence_facts"]] = ""
    st.session_state[KEYS["evidence_points"]] = ""
    st.session_state[KEYS["evidence"]] = ""

    prompt = article_ui._build_writing_prompt("")

    assert "【お金・契約テーマの追加ルール】" not in prompt


def test_build_writing_prompt_still_includes_pension_rules_and_excludes_money_rules():
    # 既存の年金テーマ追加ルールが、今回のお金・契約テーマ追加ルールの影響を受けずに
    # そのまま動くことを確認する回帰テスト。
    _reset_session_state()
    st.session_state[KEYS["consult_situation"]] = "働きながら年金を受け取っています。"
    st.session_state[KEYS["consult_question"]] = "在職老齢年金の基準額を教えてください。"
    st.session_state[KEYS["main_kw"]] = "在職老齢年金 基準額"
    st.session_state[KEYS["evidence_url"]] = ""
    st.session_state[KEYS["evidence_title"]] = ""
    st.session_state[KEYS["evidence_facts"]] = ""
    st.session_state[KEYS["evidence_points"]] = ""
    st.session_state[KEYS["evidence"]] = "在職老齢年金の基準額は月51万円。"

    prompt = article_ui._build_writing_prompt("")

    assert "【年金テーマの追加ルール】" in prompt
    assert "【お金・契約テーマの追加ルール】" not in prompt


def test_build_writing_prompt_still_includes_forecast_rules_and_excludes_money_rules():
    # 既存の見通しテーマ追加ルールも同様に、影響を受けないことを確認する回帰テスト。
    _reset_session_state()
    st.session_state[KEYS["consult_situation"]] = "業界の先行きに関心がある。"
    st.session_state[KEYS["consult_question"]] = "市場は将来どうなる見通しですか。"
    st.session_state[KEYS["main_kw"]] = "市場 将来 見通し"
    st.session_state[KEYS["evidence_url"]] = ""
    st.session_state[KEYS["evidence_title"]] = ""
    st.session_state[KEYS["evidence_facts"]] = ""
    st.session_state[KEYS["evidence_points"]] = ""
    st.session_state[KEYS["evidence"]] = "業界団体の発表によると、来期は横ばいの見通し。"

    prompt = article_ui._build_writing_prompt("")

    assert "【今後の見通しテーマの追加ルール】" in prompt
    assert "【お金・契約テーマの追加ルール】" not in prompt


# =========================
# お金・契約テーマ：根拠外の制度用語の保存前ブロック
# =========================

def test_money_contract_terms_not_in_evidence_detects_term_missing_from_evidence():
    result = article_ui._money_contract_terms_not_in_evidence(
        generated_text="一般的には、カード会社に異議申し立てを行うことで、対象となる場合があります。",
        evidence_text="継続手数料は年1回、税込2200円。",
    )
    assert result == ["異議申し立て"]


def test_money_contract_terms_not_in_evidence_excludes_term_present_in_both():
    result = article_ui._money_contract_terms_not_in_evidence(
        generated_text="一般的には、カード会社に異議申し立てを行うことで、対象となる場合があります。",
        evidence_text="異議申し立てができる場合があると規約に明記されている。",
    )
    assert result == []


def test_money_contract_terms_not_in_evidence_returns_empty_when_term_not_in_body():
    result = article_ui._money_contract_terms_not_in_evidence(
        generated_text="継続手数料は年1回、税込2200円が請求される場合があります。",
        evidence_text="継続手数料は年1回、税込2200円。",
    )
    assert result == []


def test_money_contract_terms_not_in_evidence_detects_multiple_terms_at_once():
    result = article_ui._money_contract_terms_not_in_evidence(
        generated_text=(
            "休眠状態のカードは顧客の責任で管理する必要があるとされ、"
            "異議申し立ても行えるとされています。"
        ),
        evidence_text="継続手数料は年1回、税込2200円。",
    )
    assert result == ["異議申し立て", "休眠状態", "顧客の責任"]


def _fake_generate_markdown_two_calls(plan_text: str, body_text: str):
    calls = {"n": 0}

    def fake(**kwargs):
        calls["n"] += 1
        return plan_text if calls["n"] == 1 else body_text

    return fake


_SAISON_UNGROUNDED_BODY = (
    "一般的には、カード会社に異議申し立てを行うことで、対象となる場合があります。"
)


def _set_saison_money_contract_inputs():
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_DRAFT
    st.session_state[KEYS["consult_situation"]] = "セゾンカードをほとんど使っていません。"
    st.session_state[KEYS["consult_question"]] = "継続手数料はどんな時に請求されますか。"
    st.session_state[KEYS["main_kw"]] = "セゾンカード 継続手数料"
    st.session_state[KEYS["evidence_facts"]] = "継続手数料は年1回、税込2200円。"


def test_generate_draft_blocks_save_when_money_contract_term_is_ungrounded(monkeypatch):
    _reset_session_state()
    _set_saison_money_contract_inputs()

    warnings = []
    monkeypatch.setattr(st, "warning", lambda text: warnings.append(text))
    monkeypatch.setattr(st, "button", lambda label, **kwargs: label == "✨ 下書きを作る")
    monkeypatch.setattr(
        article_ui,
        "generate_markdown",
        _fake_generate_markdown_two_calls("## 見出し1\n## 見出し2", _SAISON_UNGROUNDED_BODY),
    )

    render_article_ui(**_common_kwargs())

    assert st.session_state[KEYS["last_text"]] == ""
    assert st.session_state[KEYS["copy_text"]] == ""
    assert article_ui._get_form_data_value("last_text") == ""
    assert article_ui._get_form_data_value("copy_text") == ""
    assert st.session_state[KEYS["plan_result"]] == ""
    assert st.session_state[KEYS["proof_evidence"]] == ""
    assert st.session_state[KEYS["proof_evidence_compact"]] == ""
    assert st.session_state[KEYS["money_contract_block_terms"]] == "異議申し立て"


def test_generate_draft_block_warning_shows_detected_term_and_old_draft_notice(monkeypatch):
    _reset_session_state()
    _set_saison_money_contract_inputs()

    warnings = []
    monkeypatch.setattr(st, "warning", lambda text: warnings.append(text))
    monkeypatch.setattr(st, "button", lambda label, **kwargs: label == "✨ 下書きを作る")
    monkeypatch.setattr(
        article_ui,
        "generate_markdown",
        _fake_generate_markdown_two_calls("## 見出し1\n## 見出し2", _SAISON_UNGROUNDED_BODY),
    )

    render_article_ui(**_common_kwargs())

    assert any("異議申し立て" in w for w in warnings)
    assert any("それ以前に保存された下書き" in w for w in warnings)
    # 内部用語は画面に出さない
    assert not any("ブロック" in w for w in warnings)
    assert not any("session_state" in w for w in warnings)


def test_generate_draft_saves_normally_when_money_contract_term_is_grounded(monkeypatch):
    _reset_session_state()
    _set_saison_money_contract_inputs()
    st.session_state[KEYS["evidence_points"]] = "異議申し立てができる場合があると規約に明記されている。"

    monkeypatch.setattr(st, "warning", lambda text: None)
    monkeypatch.setattr(st, "button", lambda label, **kwargs: label == "✨ 下書きを作る")
    monkeypatch.setattr(
        article_ui,
        "generate_markdown",
        _fake_generate_markdown_two_calls("## 見出し1\n## 見出し2", _SAISON_UNGROUNDED_BODY),
    )

    render_article_ui(**_common_kwargs())

    assert st.session_state[KEYS["last_text"]] == _SAISON_UNGROUNDED_BODY
    assert article_ui._get_form_data_value("last_text") == _SAISON_UNGROUNDED_BODY
    assert st.session_state[KEYS["money_contract_block_terms"]] == ""


def test_generate_draft_does_not_block_for_non_money_contract_topic(monkeypatch):
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_DRAFT
    st.session_state[KEYS["consult_situation"]] = "掃除機の吸引力が落ちてきました。"
    st.session_state[KEYS["consult_question"]] = "掃除機のお手入れのコツを知りたいです。"
    st.session_state[KEYS["main_kw"]] = "掃除機 お手入れ"

    monkeypatch.setattr(st, "warning", lambda text: None)
    monkeypatch.setattr(st, "button", lambda label, **kwargs: label == "✨ 下書きを作る")
    monkeypatch.setattr(
        article_ui,
        "generate_markdown",
        _fake_generate_markdown_two_calls(
            "## 見出し1\n## 見出し2",
            "フィルターの異議申し立てという言葉が偶然入った本文です。",
        ),
    )

    render_article_ui(**_common_kwargs())

    assert st.session_state[KEYS["last_text"]] != ""
    assert st.session_state[KEYS["money_contract_block_terms"]] == ""


def test_generate_draft_keeps_old_last_text_when_new_attempt_is_blocked(monkeypatch):
    _reset_session_state()
    _set_saison_money_contract_inputs()
    st.session_state[KEYS["last_text"]] = "以前保存された安全な下書き"
    article_ui._set_form_data_value("last_text", "以前保存された安全な下書き")

    monkeypatch.setattr(st, "warning", lambda text: None)
    monkeypatch.setattr(st, "button", lambda label, **kwargs: label == "✨ 下書きを作る")
    monkeypatch.setattr(
        article_ui,
        "generate_markdown",
        _fake_generate_markdown_two_calls("## 見出し1\n## 見出し2", _SAISON_UNGROUNDED_BODY),
    )

    render_article_ui(**_common_kwargs())

    assert st.session_state[KEYS["last_text"]] == "以前保存された安全な下書き"
    assert article_ui._get_form_data_value("last_text") == "以前保存された安全な下書き"


def test_clear_generated_only_clears_money_contract_block_terms():
    _reset_session_state()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_PRECHECK
    st.session_state[KEYS["money_contract_block_terms"]] = "異議申し立て"
    render_article_ui(**_common_kwargs())

    article_ui._clear_generated_only()

    assert st.session_state[KEYS["money_contract_block_terms"]] == ""
