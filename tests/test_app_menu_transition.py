import streamlit as st

import app


def _reset_session_state():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def test_consume_menu_transition_true_on_first_entry():
    _reset_session_state()
    assert app._consume_menu_transition(app.MENU_ARTICLE) is True


def test_consume_menu_transition_false_while_staying_on_same_menu():
    _reset_session_state()
    assert app._consume_menu_transition(app.MENU_ARTICLE) is True
    # 同じメニューのままの再実行（入力中など）ではFalseになる
    assert app._consume_menu_transition(app.MENU_ARTICLE) is False
    assert app._consume_menu_transition(app.MENU_ARTICLE) is False


def test_consume_menu_transition_true_again_after_returning():
    _reset_session_state()
    assert app._consume_menu_transition(app.MENU_ARTICLE) is True
    assert app._consume_menu_transition(app.MENU_HOME) is True
    # ホームを経由して記事モードへ戻ってきたときも、また1回だけTrueになる
    assert app._consume_menu_transition(app.MENU_ARTICLE) is True
    assert app._consume_menu_transition(app.MENU_ARTICLE) is False


def test_menu_transition_tracking_key_excluded_from_saved_payload():
    # スクロール復帰専用の内部キーが、自動保存/手動保存のペイロードに
    # 混ざらないことを確認する（tmp__ prefixによる既存の除外の回帰確認）。
    _reset_session_state()
    app._consume_menu_transition(app.MENU_ARTICLE)

    payload = app._safe_dump_state()

    assert "tmp__last_rendered_menu" not in payload
