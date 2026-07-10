import streamlit as st

from modules.article_ui import (
    _build_article_scroll_restore_script_html,
    _build_article_scroll_tracker_script_html,
    _classify_question_type,
    _render_large_text_preview,
    _render_reference_hint_section,
    get_article_persist_keys,
    ARTICLE_SCROLL_STORAGE_KEY,
    ARTICLE_TOP_ANCHOR_ID,
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
