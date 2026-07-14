import inspect

import streamlit as st

import modules.quality_ui as quality_ui
from modules.quality_ui import (
    KEYS,
    QUALITY_ACTIVE_PAGE_KEY,
    QUALITY_PAGE_INPUT,
    QUALITY_PAGE_RESULT,
    QUALITY_PAGE_FIX_SAVE,
    QUALITY_PAGE_COUNT,
    _build_common_kanji_misuse_items,
    render_quality_ui,
)


def _reset_session_state():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def test_common_kanji_misuse_detection():
    text = (
        "お客様を向かえる体制です。\n"
        "お客様を向かい入れる準備をしています。\n"
        "対象商品を進めます。\n"
        "本人の意志を確認します。\n"
        "計画を進めます。\n"
        "強い意志を持って取り組みます。\n"
    )

    items = _build_common_kanji_misuse_items(text)
    assert len(items) == 1

    matched_texts = set(items[0]["matched_texts"])
    assert matched_texts == {
        "向かえる → 迎える",
        "向かい入れる → 迎え入れる",
        "進める → 勧める",
        "意志 → 意思",
    }


# =========================
# 文章チェックモードのページ区切り型UI（3ページ）
# =========================

def test_quality_page_count_is_three():
    assert QUALITY_PAGE_COUNT == 3


def test_quality_active_page_defaults_to_input_page():
    _reset_session_state()
    render_quality_ui()

    assert st.session_state[QUALITY_ACTIVE_PAGE_KEY] == QUALITY_PAGE_INPUT
    assert QUALITY_PAGE_INPUT == 1


def test_render_quality_ui_dispatches_only_the_active_page(monkeypatch):
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_RESULT

    calls = []
    monkeypatch.setattr(quality_ui, "_render_quality_page_1_input", lambda: calls.append(1))
    monkeypatch.setattr(quality_ui, "_render_quality_page_2_result", lambda: calls.append(2))
    monkeypatch.setattr(quality_ui, "_render_quality_page_3_fix_save", lambda: calls.append(3))

    render_quality_ui()

    assert calls == [2]


def test_quality_page_1_renders_main_text_area(monkeypatch):
    # 1/3は「確認したい文章」の入力欄(st.text_area)を描画することを確認する。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_INPUT

    text_area_calls = []
    monkeypatch.setattr(st, "text_area", lambda *a, **k: text_area_calls.append(k.get("key")))

    render_quality_ui()

    assert KEYS["check_text_widget"] in text_area_calls


def test_quality_page_2_does_not_render_main_input_text_area(monkeypatch):
    # 2/3では「確認したい文章」の入力欄は描画しない（1/3専用）ことを確認する。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_RESULT
    st.session_state[KEYS["check_text_saved"]] = "確認したい本文です。"

    text_area_calls = []
    monkeypatch.setattr(st, "text_area", lambda *a, **k: text_area_calls.append(k.get("key")))
    monkeypatch.setattr(st, "button", lambda label, **kwargs: False)

    render_quality_ui()

    assert KEYS["check_text_widget"] not in text_area_calls


def test_quality_page_3_shows_readonly_body_and_save_placeholder(monkeypatch):
    # 3/3は保存する本文を読み取り専用で表示し、保存機能は準備中の案内にとどめる
    # ことを確認する（本格的な保存機能はまだ実装しない）。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_FIX_SAVE
    st.session_state[KEYS["check_text_saved"]] = "確認したい本文です。"

    captured_code = []
    monkeypatch.setattr(st, "code", lambda text, **kwargs: captured_code.append(text))

    render_quality_ui()

    assert "確認したい本文です。" in captured_code


def test_quality_page_3_does_not_render_manual_edit_text_area(monkeypatch):
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_FIX_SAVE
    st.session_state[KEYS["check_text_saved"]] = "確認したい本文です。"

    text_area_calls = []
    monkeypatch.setattr(st, "text_area", lambda *a, **k: text_area_calls.append((a, k)))

    render_quality_ui()

    assert text_area_calls == []


def test_quality_module_has_no_url_hash_anchor_markup():
    # 記事モードのhrefアンカー方式が本番で不安定要因になった教訓を踏まえ、
    # 文章チェックモードは最初からURL hash用のアンカー要素(id="quality-...")を
    # 持たない設計にする。
    source = inspect.getsource(quality_ui)

    assert 'id="quality-top"' not in source
    assert 'id="quality-text"' not in source
    assert 'id="quality-guide"' not in source
    assert 'id="quality-evidence"' not in source
    assert 'id="quality-wording"' not in source
    assert 'id="quality-fix-place"' not in source
    assert "scrollIntoView" not in source
