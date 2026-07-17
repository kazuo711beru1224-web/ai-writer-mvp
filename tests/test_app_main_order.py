import inspect

import app


def test_handle_pending_restore_runs_before_render_current_page():
    # 記事モードなどの入力ウィジェットが生成される前に復元処理を終える必要がある。
    # ここが逆転すると「ウィジェット生成後にsession_stateを書き換えた」エラーが再発する。
    source = inspect.getsource(app.main)

    restore_pos = source.index("_handle_pending_restore(LOGS_DIR)")
    render_pos = source.index("_render_current_page(menu)")

    assert restore_pos < render_pos


def test_backup_save_and_autosave_still_run_after_render_current_page():
    # 手動保存・自動保存はウィジェットの値を書き換えないため、
    # 本文描画後のままでよいという設計判断を回帰させないための確認。
    source = inspect.getsource(app.main)

    render_pos = source.index("_render_current_page(menu)")
    backup_save_pos = source.index("_handle_pending_backup_save(LOGS_DIR)")
    autosave_pos = source.index("_autosave_state(LOGS_DIR)")

    assert render_pos < backup_save_pos
    assert render_pos < autosave_pos


def test_sidebar_autosaves_before_menu_switch_rerun():
    # メニュー切替はst.rerun()でその場に打ち切られ、main()末尾の自動保存まで
    # 到達しない。切替直前の入力を取りこぼさないよう、rerun()の前に
    # 自動保存を挟んでいることの回帰確認。
    source = inspect.getsource(app._render_sidebar)

    autosave_pos = source.index("_autosave_state(LOGS_DIR)")
    rerun_pos = source.index("st.rerun()")

    assert autosave_pos < rerun_pos


def test_article_mode_sidebar_navigation_has_no_url_hash_links():
    # 記事モードの画面移動サポートは、本番Streamlit CloudでURL hashが
    # 残ってしまう問題を避けるため、href="#..."によるアンカー移動を完全に
    # やめ、st.button + session_state方式へ切り替えた。href="#article-"や
    # data-ai-scroll-target属性が復活していないことを回帰確認する。
    source = inspect.getsource(app._render_sidebar)

    assert 'href="#article' not in source
    assert "data-ai-scroll-target" not in source


def test_article_mode_sidebar_has_no_page_jump_buttons():
    # 記事モードは入力欄が多く状態管理も複雑なため、サイドバーからの
    # 複数ページジャンプは入力欄が消えるリスクがあった（本番で複数回報告）。
    # ページジャンプ用ボタンは撤去し、本文下部の「次へ」「戻る」（1段階移動
    # のみ）に一本化したことを確認する。ARTICLE_ACTIVE_PAGE_KEYを直接
    # 書き換える古い方式や、scrollIntoView系の仕組みが復活していないことも
    # 合わせて回帰確認する。
    source = inspect.getsource(app._render_sidebar)

    # "if current_menu == MENU_ARTICLE:"／"MENU_CHECK:"は_render_sidebar内に
    # それぞれ2箇所ある（メニュー切替直後の同期処理のif/elifと、選択中の
    # 画面移動サポート表示のif）。インデント幅（8スペース）で後者だけを
    # 一意に取り出す。
    article_block_start = source.index("\n        if current_menu == MENU_ARTICLE:")
    article_block_end = source.index("\n        if current_menu == MENU_CHECK:")
    article_block = source[article_block_start:article_block_end]

    assert "st.button(" not in article_block
    assert "_go_to_article_page(" not in article_block
    assert "ARTICLE_ACTIVE_PAGE_KEY] = target_page" not in article_block
    assert "ARTICLE_SCROLL_REQUEST_KEY" not in article_block

    for target_page in (
        "ARTICLE_PAGE_BASIC",
        "ARTICLE_PAGE_KEYWORD",
        "ARTICLE_PAGE_OFFICIAL",
        "ARTICLE_PAGE_STYLE",
        "ARTICLE_PAGE_DRAFT",
        "ARTICLE_PAGE_PRECHECK",
    ):
        assert target_page not in article_block


def test_article_mode_sidebar_shows_input_protection_guidance():
    # ページジャンプボタンの代わりに、入力保護のための案内文が
    # 表示されることを確認する。
    source = inspect.getsource(app._render_sidebar)

    # "if current_menu == MENU_ARTICLE:"／"MENU_CHECK:"は_render_sidebar内に
    # それぞれ2箇所ある（メニュー切替直後の同期処理のif/elifと、選択中の
    # 画面移動サポート表示のif）。インデント幅（8スペース）で後者だけを
    # 一意に取り出す。
    article_block_start = source.index("\n        if current_menu == MENU_ARTICLE:")
    article_block_end = source.index("\n        if current_menu == MENU_CHECK:")
    article_block = source[article_block_start:article_block_end]

    assert "次へ" in article_block
    assert "戻る" in article_block
    assert "st.caption(" in article_block


def test_main_menu_options_are_unchanged():
    # 記事モードのページジャンプボタン撤去は、メインメニュー（モード切替）
    # には影響しないことの回帰確認。
    assert app.MENU_OPTIONS == [
        app.MENU_HOME,
        app.MENU_ARTICLE,
        app.MENU_CHECK,
        app.MENU_OFFICIAL,
        app.MENU_HISTORY,
        app.MENU_TERMS,
    ]


def test_quality_mode_sidebar_navigation_has_no_url_hash_links():
    # 文章チェックモードの画面移動サポートも、記事モードと同じ理由で
    # href="#quality-..."によるアンカー移動を使わない設計にする。
    source = inspect.getsource(app._render_sidebar)

    assert 'href="#quality' not in source


def test_quality_mode_sidebar_navigation_uses_buttons_with_active_page():
    # st.button押下で_go_to_quality_page()を呼ぶ構造になっていることを
    # 確認する（scrollIntoViewや直接のactive_page書き換えは使わない）。
    source = inspect.getsource(app._render_sidebar)

    assert "st.button(" in source
    assert "_go_to_quality_page(" in source
    assert "QUALITY_ACTIVE_PAGE_KEY] = target_page" not in source

    for target_page in (
        "QUALITY_PAGE_INPUT",
        "QUALITY_PAGE_RESULT",
        "QUALITY_PAGE_FIX_SAVE",
    ):
        assert target_page in source


# =========================
# URL hashの安全なクリア（共通・全モード）
# =========================

def test_hash_clear_script_has_no_scroll_into_view_or_session_storage():
    # #quality-fix-place等の残骸を消す専用処理は、scrollIntoViewや
    # sessionStorageへの保存・復元を絶対に含めない設計であることを確認する。
    html_out = app._build_hash_clear_script_html()

    assert "scrollIntoView" not in html_out
    assert "sessionStorage" not in html_out


def test_hash_clear_script_uses_history_replace_state_only():
    # hashクリアはhistory.replaceStateだけで行う設計であることを確認する。
    html_out = app._build_hash_clear_script_html()

    assert "history.replaceState" in html_out
    assert "<script>" in html_out
    # 画面移動・自動スクロールにつながる要素を持ち込んでいないことも確認する。
    assert "scrollTop" not in html_out
    assert "scrollIntoView" not in html_out


def test_render_hash_clear_is_called_before_render_current_page():
    # モードに関わらず、本文が描画される前にhashクリアが走ることを確認する。
    source = inspect.getsource(app.main)

    hash_clear_pos = source.index("_render_hash_clear()")
    render_pos = source.index("_render_current_page(menu)")

    assert hash_clear_pos < render_pos


# =========================
# メニュー切替時の同期漏れ対策
# （st.rerun()でrender_article_ui/render_quality_ui末尾の同期に
#   到達できない問題の回帰確認）
# =========================

def test_sidebar_syncs_article_form_data_before_menu_switch_rerun():
    source = inspect.getsource(app._render_sidebar)

    sync_pos = source.index("_sync_article_form_data_from_widgets()")
    rerun_pos = source.index("st.rerun()")

    assert sync_pos < rerun_pos


def test_sidebar_syncs_quality_widgets_before_menu_switch_rerun():
    source = inspect.getsource(app._render_sidebar)

    sync_pos = source.index("_sync_quality_widgets_to_saved()")
    rerun_pos = source.index("st.rerun()")

    assert sync_pos < rerun_pos
