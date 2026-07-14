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


def test_article_mode_sidebar_navigation_uses_buttons_with_active_page():
    # st.button押下で、ページ下部の「次へ」「戻る」と同じ_go_to_page()
    # （app.py側では_go_to_article_pageとしてimport）を呼ぶ構造になっている
    # ことを確認する（scrollIntoView・ARTICLE_SCROLL_REQUEST_KEYはどちらも
    # 使わない）。ARTICLE_ACTIVE_PAGE_KEYを直接書き換える古い方式に戻って
    # いないことの回帰確認でもある。
    source = inspect.getsource(app._render_sidebar)

    assert "st.button(" in source
    assert "_go_to_article_page(" in source
    assert "ARTICLE_ACTIVE_PAGE_KEY] = target_page" not in source
    assert "ARTICLE_SCROLL_REQUEST_KEY" not in source

    for target_page in (
        "ARTICLE_PAGE_BASIC",
        "ARTICLE_PAGE_KEYWORD",
        "ARTICLE_PAGE_OFFICIAL",
        "ARTICLE_PAGE_STYLE",
        "ARTICLE_PAGE_DRAFT",
        "ARTICLE_PAGE_PRECHECK",
    ):
        assert target_page in source


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
