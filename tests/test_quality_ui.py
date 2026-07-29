import contextlib
import inspect
import json

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
    _quality_text_fingerprint,
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


def test_quality_page_3_renders_manual_edit_text_area(monkeypatch):
    # 修正導線は3/3に一本化されているため、3/3では編集用text_areaが描画される。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_FIX_SAVE
    st.session_state[KEYS["check_text_saved"]] = "確認したい本文です。"

    text_area_calls = []
    monkeypatch.setattr(st, "text_area", lambda *a, **k: text_area_calls.append(k.get("key")))

    render_quality_ui()

    assert KEYS["manual_rewrite_text_widget"] in text_area_calls


def test_quality_page_3_first_visit_prefills_manual_rewrite_from_check_text():
    # テストA：3/3へ初めて入ると、check_text_saved の本文が編集欄へ入る。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_FIX_SAVE
    st.session_state[KEYS["check_text_saved"]] = "確認したい本文です。"

    render_quality_ui()

    assert st.session_state[KEYS["manual_rewrite_text_widget"]] == "確認したい本文です。"


def test_quality_page_3_does_not_overwrite_existing_manual_rewrite():
    # テストB：manual_rewrite_text_saved に編集済み文章がある場合、
    # 元の本文（check_text_saved）で上書きされない。
    # source_hash は「この本文に対してすでに初期化済み」を表すため、
    # 現実の利用（初回表示 → 編集）を再現する形であらかじめそろえておく。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_FIX_SAVE
    st.session_state[KEYS["check_text_saved"]] = "確認したい本文です。"
    st.session_state[KEYS["manual_rewrite_text_saved"]] = "すでに書き直した文章です。"
    st.session_state[KEYS["manual_rewrite_source_hash"]] = _quality_text_fingerprint(
        "確認したい本文です。"
    )

    render_quality_ui()

    assert st.session_state[KEYS["manual_rewrite_text_widget"]] == "すでに書き直した文章です。"


def test_quality_page_3_edit_survives_round_trip_through_page_2():
    # テストC：3/3 → 2/3 → 3/3 と移動しても編集内容が残る。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_FIX_SAVE
    st.session_state[KEYS["check_text_saved"]] = "確認したい本文です。"

    # 初回表示で本文が編集欄に入る（同時にsource_hashも記録される）。
    render_quality_ui()
    assert st.session_state[KEYS["manual_rewrite_text_widget"]] == "確認したい本文です。"

    # 利用者が編集する。
    st.session_state[KEYS["manual_rewrite_text_widget"]] = "編集途中の文章です。"

    # 2/3へ戻る（ページ移動前の同期で widget -> saved に反映される）。
    quality_ui._go_to_quality_page(QUALITY_PAGE_RESULT)
    assert st.session_state[KEYS["manual_rewrite_text_saved"]] == "編集途中の文章です。"

    # 3/3へ再び進むと、widgetキーはStreamlitの仕様上削除されているはずなので、
    # 未描画状態を再現してから3/3を描画する。
    del st.session_state[KEYS["manual_rewrite_text_widget"]]
    quality_ui._go_to_quality_page(QUALITY_PAGE_FIX_SAVE)
    render_quality_ui()

    assert st.session_state[KEYS["manual_rewrite_text_widget"]] == "編集途中の文章です。"


def test_quality_page_3_shows_fix_area_for_guardrail_originated_caution(monkeypatch):
    # テストD：CAUTIONの原因がguardrails由来（codeキーを持たない診断）でも、
    # 3/3には修正欄が表示される。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_FIX_SAVE
    st.session_state[KEYS["check_text_saved"]] = "確認したい本文です。"
    st.session_state[KEYS["diag_level"]] = "CAUTION"
    st.session_state[KEYS["diag_payload_json"]] = json.dumps(
        [{
            "rank": "CAUTION",
            "headline": "公開前に確認したい点があります。",
            "lead": "",
            "issue_label": "",
            "issue_text": "",
            "reason_text": "理由テキスト",
            "fix_text": "直し方テキスト",
            "rewrite_example": "",
            "matched_texts": [],
        }],
        ensure_ascii=False,
    )

    text_area_calls = []
    monkeypatch.setattr(st, "text_area", lambda *a, **k: text_area_calls.append(k.get("key")))

    render_quality_ui()

    assert KEYS["manual_rewrite_text_widget"] in text_area_calls


def test_quality_page_3_shows_fix_area_for_non_convenient_phrase_finding(monkeypatch):
    # テストE：便利表現チェック以外の指摘でも、3/3に修正欄が表示される。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_FIX_SAVE
    st.session_state[KEYS["check_text_saved"]] = "確認したい本文です。"
    st.session_state[KEYS["style_level"]] = "CAUTION"
    st.session_state[KEYS["style_payload_json"]] = json.dumps(
        [{
            "rank": "CAUTION",
            "headline": "表記をそろえたい箇所があります。",
            "lead": "",
            "issue_label": "表記",
            "issue_text": "",
            "reason_text": "理由テキスト",
            "fix_text": "直し方テキスト",
            "rewrite_example": "",
            "matched_texts": ["例"],
            "code": "表記ゆれ候補",
        }],
        ensure_ascii=False,
    )

    text_area_calls = []
    monkeypatch.setattr(st, "text_area", lambda *a, **k: text_area_calls.append(k.get("key")))

    render_quality_ui()

    assert KEYS["manual_rewrite_text_widget"] in text_area_calls


def test_quality_page_2_does_not_render_manual_rewrite_text_area(monkeypatch):
    # テストF：2/3には修正用text_areaが重複表示されない
    # （便利表現チェックの指摘があっても、修正欄は3/3に一本化されている）。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_RESULT
    st.session_state[KEYS["check_text_saved"]] = "これにより効果があります。"
    st.session_state[KEYS["style_level"]] = "CAUTION"
    st.session_state[KEYS["style_payload_json"]] = json.dumps(
        [{
            "rank": "CAUTION",
            "headline": "少し直した方がよい言い方があります。",
            "lead": "",
            "issue_label": "",
            "issue_text": "",
            "reason_text": "理由テキスト",
            "fix_text": "直し方テキスト",
            "rewrite_example": "",
            "matched_texts": ["これにより"],
            "code": "便利表現チェック",
        }],
        ensure_ascii=False,
    )

    text_area_calls = []
    monkeypatch.setattr(st, "text_area", lambda *a, **k: text_area_calls.append(k.get("key")))
    monkeypatch.setattr(st, "button", lambda label, **kwargs: False)

    render_quality_ui()

    assert KEYS["manual_rewrite_text_widget"] not in text_area_calls


def test_quality_page_3_copy_button_targets_edited_manual_rewrite_text(monkeypatch):
    # テストG：「修正文をコピー」が編集後の文章（manual_rewrite_text_saved）を対象にする。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_FIX_SAVE
    st.session_state[KEYS["check_text_saved"]] = "元の本文です。"
    st.session_state[KEYS["manual_rewrite_text_saved"]] = "編集済みの文章です。"
    st.session_state[KEYS["manual_rewrite_source_hash"]] = _quality_text_fingerprint(
        "元の本文です。"
    )

    copy_calls = []
    monkeypatch.setattr(
        quality_ui,
        "_render_copy_button",
        lambda text, label: copy_calls.append((text, label)),
    )

    render_quality_ui()

    assert ("編集済みの文章です。", "修正文をコピー") in copy_calls


def test_clear_check_text_resets_manual_rewrite_state():
    # テストH：入力リセット時（「入力を空にする」）に古い修正文が残らない。
    _reset_session_state()
    st.session_state[KEYS["check_text_saved"]] = "元の本文です。"
    st.session_state[KEYS["check_text_widget"]] = "元の本文です。"
    st.session_state[KEYS["manual_rewrite_text_saved"]] = "編集済みの文章です。"
    st.session_state[KEYS["manual_rewrite_text_widget"]] = "編集済みの文章です。"
    st.session_state[KEYS["manual_rewrite_source_hash"]] = _quality_text_fingerprint(
        "元の本文です。"
    )

    quality_ui._clear_check_text()

    assert st.session_state[KEYS["manual_rewrite_text_saved"]] == ""
    assert st.session_state[KEYS["manual_rewrite_text_widget"]] == ""
    assert st.session_state[KEYS["manual_rewrite_source_hash"]] == ""


def test_quality_page_3_first_visit_copy_targets_original_body(monkeypatch):
    # テストI：3/3初回表示直後、何も編集せず「修正文をコピー」すると
    # 元本文がコピー対象になる（初回表示時からwidget/saved/コピー対象がそろっている）。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_FIX_SAVE
    st.session_state[KEYS["check_text_saved"]] = "確認したい本文です。"

    copy_calls = []
    monkeypatch.setattr(
        quality_ui,
        "_render_copy_button",
        lambda text, label: copy_calls.append((text, label)),
    )

    render_quality_ui()

    assert st.session_state[KEYS["manual_rewrite_text_widget"]] == "確認したい本文です。"
    assert st.session_state[KEYS["manual_rewrite_text_saved"]] == "確認したい本文です。"
    assert ("確認したい本文です。", "修正文をコピー") in copy_calls


def test_quality_page_3_emptied_manual_rewrite_stays_empty_after_round_trip():
    # テストJ：修正文を全文削除して空にし、2/3→3/3と往復しても元本文が復活しない
    # （3/3をまだ一度も初期化していない空 と 利用者が編集した結果としての空 を区別する）。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_FIX_SAVE
    st.session_state[KEYS["check_text_saved"]] = "確認したい本文です。"

    # 初回表示で本文が初期値として入る。
    render_quality_ui()
    assert st.session_state[KEYS["manual_rewrite_text_widget"]] == "確認したい本文です。"

    # 利用者が全文削除する（on_changeによる同期を再現）。
    st.session_state[KEYS["manual_rewrite_text_widget"]] = ""
    quality_ui._sync_widget_to_saved(
        KEYS["manual_rewrite_text_widget"], KEYS["manual_rewrite_text_saved"]
    )
    assert st.session_state[KEYS["manual_rewrite_text_saved"]] == ""

    # 2/3へ移動 → 3/3へ戻る。
    quality_ui._go_to_quality_page(QUALITY_PAGE_RESULT)
    del st.session_state[KEYS["manual_rewrite_text_widget"]]
    quality_ui._go_to_quality_page(QUALITY_PAGE_FIX_SAVE)
    render_quality_ui()

    assert st.session_state[KEYS["manual_rewrite_text_widget"]] == ""
    assert st.session_state[KEYS["manual_rewrite_text_saved"]] == ""


def test_quality_page_3_reinitializes_when_body_changes_to_different_text():
    # テストK：1/3で文章Aから文章Bへ直接変更した場合、文章Aの修正文が残らず、
    # 文章Bで初期化される。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_FIX_SAVE
    st.session_state[KEYS["check_text_saved"]] = "文章Aです。"

    render_quality_ui()  # 文章Aで初期化される。
    st.session_state[KEYS["manual_rewrite_text_widget"]] = "文章Aを直した文章です。"

    # 1/3へ戻る（ページ移動前の同期で widget -> saved に反映される）。
    quality_ui._go_to_quality_page(QUALITY_PAGE_INPUT)
    assert st.session_state[KEYS["manual_rewrite_text_saved"]] == "文章Aを直した文章です。"

    # 「入力を空にする」も「最新の下書きを貼り付ける」も使わず、
    # 1/3のtext_areaへ文章Bを直接入力したことを再現する（on_changeでの同期）。
    st.session_state[KEYS["check_text_widget"]] = "文章Bです。"
    quality_ui._sync_widget_to_saved(KEYS["check_text_widget"], KEYS["check_text_saved"])
    assert st.session_state[KEYS["check_text_saved"]] == "文章Bです。"

    # 3/3へ進む（widgetキーはページ移動でいったん落ちている状態を再現する）。
    del st.session_state[KEYS["manual_rewrite_text_widget"]]
    quality_ui._go_to_quality_page(QUALITY_PAGE_FIX_SAVE)
    render_quality_ui()

    assert st.session_state[KEYS["manual_rewrite_text_widget"]] == "文章Bです。"
    assert st.session_state[KEYS["manual_rewrite_text_saved"]] == "文章Bです。"


def test_quality_page_3_to_2_to_3_round_trip_keeps_edit_with_full_render(monkeypatch):
    # テストL：同じ本文のまま2/3⇄3/3をフル描画で往復しても、編集済み文章をリセットしない。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_FIX_SAVE
    st.session_state[KEYS["check_text_saved"]] = "確認したい本文です。"
    monkeypatch.setattr(st, "button", lambda label, **kwargs: False)

    render_quality_ui()  # 初回表示（本文で初期化される）。
    st.session_state[KEYS["manual_rewrite_text_widget"]] = "編集した文章です。"

    # 2/3へ移動して2/3をフル描画する（このページはmanual_rewrite widgetを描画しない）。
    quality_ui._go_to_quality_page(QUALITY_PAGE_RESULT)
    del st.session_state[KEYS["manual_rewrite_text_widget"]]
    render_quality_ui()

    # 3/3へ戻ってフル描画する。
    quality_ui._go_to_quality_page(QUALITY_PAGE_FIX_SAVE)
    render_quality_ui()

    assert st.session_state[KEYS["manual_rewrite_text_widget"]] == "編集した文章です。"


def test_paste_latest_generated_resets_manual_rewrite_state(monkeypatch):
    # 「新しい文章を1/3へ入力した場合」の経路（最新の下書きを貼り付け）でも、
    # 古い案文に対する修正文を持ち越さない。
    _reset_session_state()
    st.session_state[KEYS["manual_rewrite_text_saved"]] = "古い修正文です。"
    st.session_state[KEYS["manual_rewrite_text_widget"]] = "古い修正文です。"
    st.session_state[KEYS["manual_rewrite_source_hash"]] = _quality_text_fingerprint(
        "古い本文です。"
    )
    monkeypatch.setattr(quality_ui, "_resolve_article_body", lambda: "新しい下書きです。")

    quality_ui._paste_latest_generated()

    assert st.session_state[KEYS["manual_rewrite_text_saved"]] == ""
    assert st.session_state[KEYS["manual_rewrite_text_widget"]] == ""
    assert st.session_state[KEYS["manual_rewrite_source_hash"]] == ""


def test_fingerprint_returns_same_hash_for_same_text():
    # テストM：fingerprint関数が同じ本文に同じ64文字のハッシュを返す。
    a = _quality_text_fingerprint("確認したい本文です。")
    b = _quality_text_fingerprint("確認したい本文です。")

    assert a == b
    assert len(a) == 64


def test_fingerprint_returns_different_hash_for_different_text():
    # テストN：異なる本文では異なるハッシュになる。
    a = _quality_text_fingerprint("文章Aです。")
    b = _quality_text_fingerprint("文章Bです。")

    assert a != b


def test_quality_page_3_first_visit_records_source_hash_of_original_body():
    # テストO：3/3初回表示後、source_hashが元本文のハッシュと一致する。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_FIX_SAVE
    st.session_state[KEYS["check_text_saved"]] = "確認したい本文です。"

    render_quality_ui()

    assert st.session_state[KEYS["manual_rewrite_source_hash"]] == _quality_text_fingerprint(
        "確認したい本文です。"
    )


def test_quality_page_3_source_hash_stays_matched_after_emptying_and_round_trip():
    # テストP：利用者が全文削除して往復しても、source_hashが一致しているため
    # 元本文が復活しない。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_FIX_SAVE
    st.session_state[KEYS["check_text_saved"]] = "確認したい本文です。"

    render_quality_ui()
    original_hash = _quality_text_fingerprint("確認したい本文です。")
    assert st.session_state[KEYS["manual_rewrite_source_hash"]] == original_hash

    st.session_state[KEYS["manual_rewrite_text_widget"]] = ""
    quality_ui._sync_widget_to_saved(
        KEYS["manual_rewrite_text_widget"], KEYS["manual_rewrite_text_saved"]
    )

    quality_ui._go_to_quality_page(QUALITY_PAGE_RESULT)
    del st.session_state[KEYS["manual_rewrite_text_widget"]]
    quality_ui._go_to_quality_page(QUALITY_PAGE_FIX_SAVE)
    render_quality_ui()

    assert st.session_state[KEYS["manual_rewrite_source_hash"]] == original_hash
    assert st.session_state[KEYS["manual_rewrite_text_widget"]] == ""


def test_quality_page_3_source_hash_updates_when_body_changes():
    # テストQ：本文Aから本文Bへ変わると、source_hashも本文Bのハッシュへ更新される。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_FIX_SAVE
    st.session_state[KEYS["check_text_saved"]] = "文章Aです。"

    render_quality_ui()
    assert st.session_state[KEYS["manual_rewrite_source_hash"]] == _quality_text_fingerprint(
        "文章Aです。"
    )

    st.session_state[KEYS["check_text_saved"]] = "文章Bです。"
    del st.session_state[KEYS["manual_rewrite_text_widget"]]
    render_quality_ui()

    assert st.session_state[KEYS["manual_rewrite_source_hash"]] == _quality_text_fingerprint(
        "文章Bです。"
    )
    assert st.session_state[KEYS["manual_rewrite_text_widget"]] == "文章Bです。"


def test_manual_rewrite_source_hash_key_uses_tmp_prefix():
    # テストR：新キーがtmp__で始まること（app.py/state_io.pyの除外接頭辞に一致させ、
    # 自動保存・手動バックアップの対象外にするため）。
    assert KEYS["manual_rewrite_source_hash"].startswith("tmp__")


def test_old_source_text_key_name_is_not_present():
    # テストS：旧source_textキー名がKEYSや処理に残っていないこと。
    assert "manual_rewrite_source_text" not in KEYS
    assert "quality__manual_rewrite_source_text" not in KEYS.values()

    source = inspect.getsource(quality_ui)
    assert "manual_rewrite_source_text" not in source
    assert "quality__manual_rewrite_source_text" not in source


def test_quality_module_has_no_url_hash_anchor_markup():
    # 記事モードのhrefアンカー方式が本番で不安定要因になった教訓を踏まえ、
    # 文章チェックモードは最初からURL hash用のアンカー要素(id="quality-...")を
    # 持たない設計にする。URL hashのクリア自体はapp.py側の共通処理が担うため、
    # quality_ui.py自身がhash操作を持たないことも回帰確認する。
    source = inspect.getsource(quality_ui)

    assert 'id="quality-top"' not in source
    assert 'id="quality-text"' not in source
    assert 'id="quality-guide"' not in source
    assert 'id="quality-evidence"' not in source
    assert 'id="quality-wording"' not in source
    assert 'id="quality-fix-place"' not in source
    assert "scrollIntoView" not in source
    assert "sessionStorage" not in source
    assert "replaceState" not in source


# =========================
# ページ移動前の明示同期
# （on_change/blur任せにしない、Task 3の回帰確認）
# =========================

def test_go_to_quality_page_syncs_widget_to_saved_before_switching():
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_INPUT
    st.session_state[KEYS["check_text_widget"]] = "書きかけの本文"
    st.session_state[KEYS["check_text_saved"]] = ""

    quality_ui._go_to_quality_page(QUALITY_PAGE_RESULT)

    assert st.session_state[KEYS["check_text_saved"]] == "書きかけの本文"
    assert st.session_state[QUALITY_ACTIVE_PAGE_KEY] == QUALITY_PAGE_RESULT


def test_go_to_quality_page_syncs_manual_rewrite_widget_to_saved():
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_RESULT
    st.session_state[KEYS["manual_rewrite_text_widget"]] = "書きかけの修正文"
    st.session_state[KEYS["manual_rewrite_text_saved"]] = ""

    quality_ui._go_to_quality_page(QUALITY_PAGE_FIX_SAVE)

    assert st.session_state[KEYS["manual_rewrite_text_saved"]] == "書きかけの修正文"


def test_go_to_quality_page_does_not_blank_saved_when_widget_never_rendered():
    # widget keyがまだ一度も描画されていない（session_stateに存在しない）
    # 場合は、空文字で正本(saved側)を上書きしないことを確認する。
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_INPUT
    st.session_state[KEYS["check_text_saved"]] = "既存の本文"
    # KEYS["check_text_widget"]は未設定のまま。

    quality_ui._go_to_quality_page(QUALITY_PAGE_RESULT)

    assert st.session_state[KEYS["check_text_saved"]] == "既存の本文"


# =========================
# 2/3 カード＋表形式レイアウト
# （重複する共通案内文の整理、1件＝1カード表示の回帰確認）
# =========================

def _finding(**overrides):
    base = {
        "rank": "CAUTION",
        "headline": "公開前に確認したい点があります。",
        "lead": "",
        "issue_label": "確認したいラベル",
        "issue_text": "確認したい内容の説明です。",
        "reason_text": "理由の説明です。",
        "fix_text": "直し方の説明です。",
        "rewrite_example": "",
        "matched_texts": ["対象語句A"],
        "code": "表記ゆれ候補",
    }
    base.update(overrides)
    return base


def _prepare_page2_result(
    monkeypatch,
    *,
    diag_level: str = "",
    diag_items=None,
    style_level: str = "",
    style_items=None,
    body: str = "確認したい本文です。",
):
    _reset_session_state()
    st.session_state[QUALITY_ACTIVE_PAGE_KEY] = QUALITY_PAGE_RESULT
    st.session_state[KEYS["check_text_saved"]] = body
    st.session_state[KEYS["diag_level"]] = diag_level
    st.session_state[KEYS["diag_payload_json"]] = json.dumps(diag_items or [], ensure_ascii=False)
    st.session_state[KEYS["style_level"]] = style_level
    st.session_state[KEYS["style_payload_json"]] = json.dumps(style_items or [], ensure_ascii=False)
    monkeypatch.setattr(st, "button", lambda label, **kwargs: False)


def _capture_render_calls(monkeypatch):
    # st.markdown / st.write / st.warning / st.error / st.success の呼び出しを
    # (種類, テキスト) のタプルとして時系列で記録する。
    calls = []

    def _record(kind):
        def _fn(text, *args, **kwargs):
            calls.append((kind, str(text)))
        return _fn

    monkeypatch.setattr(st, "markdown", _record("markdown"))
    monkeypatch.setattr(st, "write", _record("write"))
    monkeypatch.setattr(st, "warning", _record("warning"))
    monkeypatch.setattr(st, "error", _record("error"))
    monkeypatch.setattr(st, "success", _record("success"))
    monkeypatch.setattr(st, "info", _record("info"))
    return calls


def _capture_container_borders(monkeypatch):
    # st.container(border=...) の呼び出し回数・引数を記録する。
    borders = []

    @contextlib.contextmanager
    def _fake_container(*args, **kwargs):
        borders.append(kwargs.get("border"))
        yield None

    monkeypatch.setattr(st, "container", _fake_container)
    return borders


def test_page2_common_caution_notice_shown_exactly_once(monkeypatch):
    # テストA：安全チェック・表記チェックの両方がCAUTIONでも、
    # 共通案内文は画面全体で1回だけ表示される。
    diag_items = [_finding(matched_texts=["対象語句A"]), _finding(matched_texts=["対象語句B"])]
    style_items = [_finding(code="表記ゆれ候補", matched_texts=["表記A"])]
    _prepare_page2_result(
        monkeypatch,
        diag_level="CAUTION",
        diag_items=diag_items,
        style_level="CAUTION",
        style_items=style_items,
    )
    calls = _capture_render_calls(monkeypatch)
    _capture_container_borders(monkeypatch)

    render_quality_ui()

    notice = quality_ui._QUALITY_COMMON_CAUTION_NOTICE
    notice_calls = [c for c in calls if c == ("warning", notice)]
    assert len(notice_calls) == 1


def test_page2_finding_count_matches_bordered_container_count(monkeypatch):
    # テストB：findingが2件なら、border付きcontainerが2件分使われる。
    diag_items = [_finding(matched_texts=["対象語句A"]), _finding(matched_texts=["対象語句B"])]
    _prepare_page2_result(monkeypatch, diag_level="CAUTION", diag_items=diag_items)
    _capture_render_calls(monkeypatch)
    borders = _capture_container_borders(monkeypatch)

    render_quality_ui()

    assert borders.count(True) == 2


def test_page2_card_shows_fields_in_fixed_order(monkeypatch):
    # テストC：各カードは 状態 → 確認内容 → 対象語句・確認箇所 → 理由 → 直し方 の順で表示される。
    diag_items = [_finding()]
    _prepare_page2_result(monkeypatch, diag_level="CAUTION", diag_items=diag_items)
    calls = _capture_render_calls(monkeypatch)
    _capture_container_borders(monkeypatch)

    render_quality_ui()

    texts = [text for _, text in calls]

    def first_index(marker):
        for i, text in enumerate(texts):
            if marker in text:
                return i
        raise AssertionError(f"marker not found: {marker}")

    idx_status = first_index("状態")
    idx_confirm = first_index("確認内容")
    idx_target = first_index("対象語句・確認箇所")
    idx_reason = first_index("理由")
    idx_fix = first_index("直し方")

    assert idx_status < idx_confirm < idx_target < idx_reason < idx_fix


def test_page2_matched_texts_render_as_bracketed_terms(monkeypatch):
    # テストD：matched_textsがある場合、対象語句・確認箇所が「」区切りで表示される。
    diag_items = [_finding(matched_texts=["必要です", "求められます"])]
    _prepare_page2_result(monkeypatch, diag_level="CAUTION", diag_items=diag_items)
    calls = _capture_render_calls(monkeypatch)
    _capture_container_borders(monkeypatch)

    render_quality_ui()

    assert ("write", "「必要です」「求められます」") in calls


def test_page2_empty_matched_texts_skip_target_heading(monkeypatch):
    # テストE：matched_textsが空の場合、対象語句・確認箇所欄自体を表示しない。
    diag_items = [_finding(matched_texts=[])]
    _prepare_page2_result(monkeypatch, diag_level="CAUTION", diag_items=diag_items)
    calls = _capture_render_calls(monkeypatch)
    _capture_container_borders(monkeypatch)

    render_quality_ui()

    assert ("markdown", "**対象語句・確認箇所**") not in calls


def test_page2_generic_caution_headline_not_repeated_in_cards(monkeypatch):
    # テストF：findingごとの共通headline「公開前に確認したい点があります。」は、
    # 複数件あってもカード内で繰り返し表示されない（データは残るが表示だけ省略）。
    duplicate_headline = "公開前に確認したい点があります。"
    diag_items = [
        _finding(headline=duplicate_headline, matched_texts=["対象語句A"]),
        _finding(headline=duplicate_headline, matched_texts=["対象語句B"]),
    ]
    _prepare_page2_result(monkeypatch, diag_level="CAUTION", diag_items=diag_items)
    calls = _capture_render_calls(monkeypatch)
    _capture_container_borders(monkeypatch)

    render_quality_ui()

    assert all(text != duplicate_headline for _, text in calls)
    assert all(text != f"**{duplicate_headline}**" for _, text in calls)
    # データ自体は削除していないことも確認する。
    assert all(item["headline"] == duplicate_headline for item in diag_items)


def test_page2_specific_headline_is_shown_in_card(monkeypatch):
    # テストB：finding固有のheadline「少し直した方がよい言い方があります。」は
    # 共通文言と一致しないため、カード内に表示される。
    specific_headline = "少し直した方がよい言い方があります。"
    style_items = [_finding(
        code="便利表現チェック",
        headline=specific_headline,
        issue_label="",
        issue_text="",
        matched_texts=["これにより"],
    )]
    _prepare_page2_result(monkeypatch, style_level="CAUTION", style_items=style_items)
    calls = _capture_render_calls(monkeypatch)
    _capture_container_borders(monkeypatch)

    render_quality_ui()

    assert ("write", specific_headline) in calls


def test_page2_specific_headline_appears_after_status_and_before_confirm_content(monkeypatch):
    # テストC：固有headlineの表示位置は「状態」の直後・「確認内容」の前であること。
    specific_headline = "少し直した方がよい言い方があります。"
    diag_items = [_finding(headline=specific_headline)]
    _prepare_page2_result(monkeypatch, diag_level="CAUTION", diag_items=diag_items)
    calls = _capture_render_calls(monkeypatch)
    _capture_container_borders(monkeypatch)

    render_quality_ui()

    texts = [text for _, text in calls]

    def first_index(marker):
        for i, text in enumerate(texts):
            if marker in text:
                return i
        raise AssertionError(f"marker not found: {marker}")

    idx_status = first_index("状態")
    idx_headline = first_index(specific_headline)
    idx_confirm = first_index("確認内容")

    assert idx_status < idx_headline < idx_confirm


def test_page2_multiple_findings_hide_common_headline_and_show_specific_headlines(monkeypatch):
    # テストD：複数findingが混在する場合、共通headlineは非表示のまま、
    # finding固有のheadlineはそれぞれ個別に表示される。
    common_headline = "公開前に確認したい点があります。"
    specific_headline_1 = "少し直した方がよい言い方があります。"
    specific_headline_2 = "表記をそろえたい箇所があります。"

    diag_items = [_finding(headline=common_headline, matched_texts=["対象語句A"])]
    style_items = [
        _finding(code="便利表現チェック", headline=specific_headline_1, matched_texts=["これにより"]),
        _finding(code="表記ゆれ候補", headline=specific_headline_2, matched_texts=["表記A"]),
    ]
    _prepare_page2_result(
        monkeypatch,
        diag_level="CAUTION",
        diag_items=diag_items,
        style_level="CAUTION",
        style_items=style_items,
    )
    calls = _capture_render_calls(monkeypatch)
    _capture_container_borders(monkeypatch)

    render_quality_ui()

    assert all(text != common_headline for _, text in calls)
    assert ("write", specific_headline_1) in calls
    assert ("write", specific_headline_2) in calls


def test_page2_news_timeliness_finding_uses_same_card_format(monkeypatch):
    # テストG：最新情報・時事性警告（guardrails由来）でも同じカード形式になる。
    diag_items = [_finding(
        code="最新情報は最終確認前提",
        issue_label="参照日・発表元・確認先",
        issue_text="本文で最新の出来事や時事性のある内容を扱っています。",
        reason_text="最新情報は、追加の発表や訂正で内容が変わることがあります。",
        fix_text="参照日と発表元を確認し、複数の確認先で照合してください。",
        matched_texts=[],
    )]
    _prepare_page2_result(monkeypatch, diag_level="CAUTION", diag_items=diag_items)
    calls = _capture_render_calls(monkeypatch)
    borders = _capture_container_borders(monkeypatch)

    render_quality_ui()

    assert borders.count(True) == 1
    assert ("markdown", "**状態：** CAUTION") in calls
    assert ("markdown", "**理由**") in calls
    assert ("markdown", "**直し方**") in calls


def test_page2_style_finding_uses_same_card_format(monkeypatch):
    # テストH：表記・言い回し警告でも同じカード形式になる。
    style_items = [_finding(code="表記ゆれ候補", matched_texts=["表記A"])]
    _prepare_page2_result(monkeypatch, style_level="CAUTION", style_items=style_items)
    calls = _capture_render_calls(monkeypatch)
    borders = _capture_container_borders(monkeypatch)

    render_quality_ui()

    assert borders.count(True) == 1
    assert ("markdown", "**状態：** CAUTION") in calls
    assert ("markdown", "**対象語句・確認箇所**") in calls


def test_page2_rewrite_example_still_rendered(monkeypatch):
    # テストI-1：rewrite_exampleが維持され、カード内に表示される。
    style_items = [_finding(code="語尾3連続", rewrite_example="例：言い換え例です。")]
    _prepare_page2_result(monkeypatch, style_level="CAUTION", style_items=style_items)
    calls = _capture_render_calls(monkeypatch)
    _capture_container_borders(monkeypatch)

    render_quality_ui()

    assert ("markdown", "**言い換え例**") in calls
    assert ("write", "例：言い換え例です。") in calls


def test_page2_convenient_phrase_finding_keeps_highlight_and_copy_button(monkeypatch):
    # テストI-2：便利表現チェックの本文ハイライト表示・
    # 「指摘付き本文をコピー」の既存コピー機能が維持される。
    body = "これにより効果があります。"
    style_items = [_finding(
        code="便利表現チェック",
        headline="少し直した方がよい言い方があります。",
        issue_label="",
        issue_text="",
        matched_texts=["これにより"],
    )]
    _prepare_page2_result(monkeypatch, style_level="CAUTION", style_items=style_items, body=body)
    _capture_render_calls(monkeypatch)
    _capture_container_borders(monkeypatch)

    copy_calls = []
    monkeypatch.setattr(
        quality_ui,
        "_render_copy_button",
        lambda text, label: copy_calls.append((text, label)),
    )

    render_quality_ui()

    assert (body, "指摘付き本文をコピー") in copy_calls
