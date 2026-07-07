import streamlit as st

import app


NEW_KEYS = [
    "article__consult_situation",
    "article__consult_question",
    "article__evidence_url",
    "article__evidence_title",
    "article__evidence_facts",
    "article__evidence_points",
    "article__tone_regulation",
]


def _reset_session_state():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def test_restore_apply_keys_include_article_detail_fields():
    for key in NEW_KEYS:
        assert key in app.RESTORE_APPLY_KEYS


def test_apply_restore_payload_restores_new_keys():
    _reset_session_state()
    payload = {
        "article__consult_situation": "夫が急に他界した",
        "article__consult_question": "遺族年金はもらえるか",
        "article__evidence_url": "https://example.jp/pension",
        "article__evidence_title": "遺族年金の制度案内",
        "article__evidence_facts": "支給要件は保険料納付済期間が3分の2以上",
        "article__evidence_points": "配偶者は年齢要件あり",
        "article__tone_regulation": "断定は避け、確認先を明記する",
    }

    app._apply_restore_payload(payload)

    for key, expected in payload.items():
        assert st.session_state[key] == expected


def test_apply_restore_payload_ignores_missing_new_keys_without_error():
    _reset_session_state()
    st.session_state["article__consult_situation"] = "既存の入力"

    old_payload = {
        "article__main_kw": "遺族年金",
        "article__last_text": "本文サンプル",
    }

    app._apply_restore_payload(old_payload)

    assert st.session_state["article__main_kw"] == "遺族年金"
    assert st.session_state["article__last_text"] == "本文サンプル"
    # 旧形式のバックアップに新キーが無くても、既存値は上書きされずエラーにもならない
    assert st.session_state["article__consult_situation"] == "既存の入力"
