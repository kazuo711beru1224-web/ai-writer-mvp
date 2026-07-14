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
    ARTICLE_PAGE_OFFICIAL,
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
    # suggest/evidence_url/evidence_title/tone_regも対象にすることを確認する。
    _reset_session_state()
    st.session_state[KEYS["consult_situation"]] = "テスト用の状況"
    st.session_state[KEYS["consult_question"]] = "テスト用の質問"
    st.session_state[KEYS["suggest"]] = "keyword A"
    st.session_state[KEYS["evidence_url"]] = "https://example.com"
    st.session_state[KEYS["evidence_title"]] = "資料名"
    st.session_state[KEYS["tone_reg"]] = "です・ます調"
    article_ui._backup_article_inputs()
    article_ui._backup_shadow_state()

    for key in (
        KEYS["consult_situation"],
        KEYS["consult_question"],
        KEYS["suggest"],
        KEYS["evidence_url"],
        KEYS["evidence_title"],
        KEYS["tone_reg"],
    ):
        del st.session_state[key]

    article_ui._restore_blank_generation_inputs_from_backup_or_shadow()

    assert st.session_state[KEYS["consult_situation"]] == "テスト用の状況"
    assert st.session_state[KEYS["consult_question"]] == "テスト用の質問"
    assert st.session_state[KEYS["suggest"]] == "keyword A"
    assert st.session_state[KEYS["evidence_url"]] == "https://example.com"
    assert st.session_state[KEYS["evidence_title"]] == "資料名"
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
