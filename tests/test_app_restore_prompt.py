import streamlit as st

import app


def _reset_session_state():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def _set_full_article_state(**overrides):
    values = {key: "" for key in app.WORK_SIG_KEYS}
    values.update(overrides)
    for key, value in values.items():
        st.session_state[key] = value


def _write_autosave_file(tmp_path, content: str = '{"article__main_kw": "遺族年金"}') -> None:
    fp = tmp_path / app.AUTOSAVE_FILENAME
    fp.write_text(content, encoding="utf-8")


def test_offers_restore_when_autosave_exists_and_inputs_blank(tmp_path):
    _reset_session_state()
    _set_full_article_state()
    _write_autosave_file(tmp_path)

    assert app._should_offer_autosave_restore(tmp_path) is True


def test_does_not_offer_when_autosave_file_missing(tmp_path):
    _reset_session_state()
    _set_full_article_state()

    assert app._should_offer_autosave_restore(tmp_path) is False


def test_does_not_offer_when_inputs_already_have_content(tmp_path):
    _reset_session_state()
    _set_full_article_state(article__main_kw="入力中の内容")
    _write_autosave_file(tmp_path)

    assert app._should_offer_autosave_restore(tmp_path) is False


def test_does_not_offer_when_dismissed_this_session(tmp_path):
    _reset_session_state()
    _set_full_article_state()
    _write_autosave_file(tmp_path)
    st.session_state["tmp__restore_prompt_dismissed"] = True

    assert app._should_offer_autosave_restore(tmp_path) is False


def test_does_not_offer_when_autosave_file_is_empty(tmp_path):
    _reset_session_state()
    _set_full_article_state()
    _write_autosave_file(tmp_path, content="")

    assert app._should_offer_autosave_restore(tmp_path) is False


def test_restore_button_state_feeds_existing_restore_flow(tmp_path):
    _reset_session_state()
    _set_full_article_state()

    # 「前回の入力を復元する」ボタン押下時と同じsession_state操作を再現する
    st.session_state["backup__restore_request"] = True
    st.session_state["backup__restore_target"] = app.AUTOSAVE_FILENAME
    st.session_state["tmp__restore_prompt_dismissed"] = True

    assert app._has_restore_request() is True
    assert app._extract_restore_target() == app.AUTOSAVE_FILENAME


def test_dismiss_without_restore_does_not_delete_autosave_file(tmp_path):
    _reset_session_state()
    _set_full_article_state()
    _write_autosave_file(tmp_path)

    # 「今回は使わない」ボタン押下時と同じsession_state操作を再現する
    st.session_state["tmp__restore_prompt_dismissed"] = True

    fp = tmp_path / app.AUTOSAVE_FILENAME
    assert fp.exists()
    assert app._should_offer_autosave_restore(tmp_path) is False


def test_dismiss_flag_excluded_from_saved_payload():
    _reset_session_state()
    _set_full_article_state(article__main_kw="遺族年金")
    st.session_state["tmp__restore_prompt_dismissed"] = True

    payload = app._safe_dump_state()

    assert "tmp__restore_prompt_dismissed" not in payload
