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
