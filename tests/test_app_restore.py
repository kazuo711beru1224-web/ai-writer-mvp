import streamlit as st

import app
import modules.article_ui as article_ui


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


# =========================
# article__inputs_saved（第2段階：自動保存・復元経路への追加）
# 再読み込み・スリープ復帰・「前回の入力を復元する」でも1/6〜4/6の入力材料
# 12項目が消えないよう、article__inputs_savedを保存payloadから復元する。
# =========================

def test_apply_restore_payload_restores_inputs_saved():
    _reset_session_state()
    payload = {
        article_ui.ARTICLE_INPUTS_SAVED_KEY: {
            "consult_situation": "夫が急に他界した",
            "consult_question": "遺族年金はもらえるか",
            "suggest": "遺族年金, 支給要件",
            "evidence_url": "https://example.jp/pension",
            "evidence_title": "遺族年金の制度案内",
            "evidence_facts": "支給要件は保険料納付済期間が3分の2以上",
            "evidence_points": "配偶者は年齢要件あり",
            "memo": "わかりやすく",
            "tone_reg": "ですます調",
            "main_kw": "遺族年金",
            "sub_kw": "支給要件",
            "theme": "遺族年金の仕組み",
        },
    }

    app._apply_restore_payload(payload)

    restored = st.session_state[article_ui.ARTICLE_INPUTS_SAVED_KEY]
    for field, expected in payload[article_ui.ARTICLE_INPUTS_SAVED_KEY].items():
        assert restored[field] == expected


def test_apply_restore_payload_never_lets_api_key_into_inputs_saved():
    _reset_session_state()
    payload = {
        article_ui.ARTICLE_INPUTS_SAVED_KEY: {
            "main_kw": "遺族年金",
            "openai_api_key": "sk-should-not-leak",
        },
    }

    app._apply_restore_payload(payload)

    restored = st.session_state[article_ui.ARTICLE_INPUTS_SAVED_KEY]
    assert "openai_api_key" not in restored
    assert restored["main_kw"] == "遺族年金"


def test_apply_restore_payload_skips_blank_values_in_inputs_saved():
    _reset_session_state()
    st.session_state[article_ui.ARTICLE_INPUTS_SAVED_KEY] = {"main_kw": "既存の値"}
    payload = {
        article_ui.ARTICLE_INPUTS_SAVED_KEY: {
            "main_kw": "",
            "sub_kw": "",
        },
    }

    app._apply_restore_payload(payload)

    restored = st.session_state[article_ui.ARTICLE_INPUTS_SAVED_KEY]
    # 空文字はinputs_savedへ書き込まれず、既存の非空値も上書きされない。
    assert restored["main_kw"] == "既存の値"
    assert restored.get("sub_kw", "") == ""


def test_apply_restore_payload_migrates_inputs_saved_from_old_form_data():
    # 旧形式（article__inputs_savedキーが存在しない保存データ）からの
    # 互換移行。article__form_dataの12項目のうち非空のものだけを取り込む。
    _reset_session_state()
    payload = {
        article_ui.ARTICLE_FORM_DATA_KEY: {
            "consult_situation": "旧形式の状況",
            "consult_question": "旧形式の質問",
            "main_kw": "旧形式のキーワード",
            "sub_kw": "",  # 空文字は移行されないことの確認対象
        },
    }

    app._apply_restore_payload(payload)

    restored = st.session_state[article_ui.ARTICLE_INPUTS_SAVED_KEY]
    assert restored["consult_situation"] == "旧形式の状況"
    assert restored["consult_question"] == "旧形式の質問"
    assert restored["main_kw"] == "旧形式のキーワード"
    assert "sub_kw" not in restored


def test_apply_restore_payload_does_not_migrate_when_inputs_saved_already_present():
    # 新形式（両方ある）では移行処理が発動せず、payloadのinputs_savedが
    # そのまま復元されることを確認する（inputs_saved優先の回帰確認）。
    _reset_session_state()
    payload = {
        article_ui.ARTICLE_FORM_DATA_KEY: {
            "main_kw": "form_dataの古い値",
        },
        article_ui.ARTICLE_INPUTS_SAVED_KEY: {
            "main_kw": "inputs_savedの新しい値",
        },
    }

    app._apply_restore_payload(payload)

    assert st.session_state[article_ui.ARTICLE_INPUTS_SAVED_KEY]["main_kw"] == "inputs_savedの新しい値"


def test_restore_survives_form_data_contaminated_with_blank():
    # 本番調査で確認した破壊シーケンスの回帰テスト：
    # article__form_dataが（非表示ページの空文字混入で）汚染されていても、
    # article__inputs_savedの非空値が保存・復元を経て正しく生き残り、
    # article_ui._get_effective_value()経由でユーザーに見える値が守られることを確認する。
    _reset_session_state()
    payload = {
        article_ui.ARTICLE_FORM_DATA_KEY: {
            "main_kw": "",  # 汚染された状態を再現
        },
        article_ui.ARTICLE_INPUTS_SAVED_KEY: {
            "main_kw": "正しい値",
        },
    }

    app._apply_restore_payload(payload)

    if article_ui.KEYS["main_kw"] in st.session_state:
        del st.session_state[article_ui.KEYS["main_kw"]]

    assert article_ui._get_effective_value(article_ui.KEYS["main_kw"]) == "正しい値"
