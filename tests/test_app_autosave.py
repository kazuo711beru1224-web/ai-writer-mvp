import json
from pathlib import Path

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


def test_autosave_creates_fixed_filename(tmp_path):
    _reset_session_state()
    _set_full_article_state(article__main_kw="遺族年金")

    app._autosave_state(tmp_path)

    fp = tmp_path / app.AUTOSAVE_FILENAME
    assert fp.exists()
    assert fp.name == "autosave_state.json"


def test_autosave_filename_does_not_match_manual_backup_pattern():
    # 手動保存が一覧化する state_*.json パターンに混ざらないことの回帰確認
    assert not app.AUTOSAVE_FILENAME.startswith(app.BACKUP_PREFIX)


def test_autosave_skips_rewrite_when_content_unchanged(tmp_path, monkeypatch):
    _reset_session_state()
    _set_full_article_state(article__main_kw="遺族年金")

    write_calls = []
    original_write_text = Path.write_text

    def spy_write_text(self, *args, **kwargs):
        write_calls.append(self)
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", spy_write_text)

    app._autosave_state(tmp_path)
    assert len(write_calls) == 1

    # 内容を変えずにもう一度呼んでも、再書き込みは発生しない
    app._autosave_state(tmp_path)
    assert len(write_calls) == 1


def test_autosave_updates_same_file_when_content_changes(tmp_path):
    _reset_session_state()
    _set_full_article_state(article__main_kw="遺族年金")
    app._autosave_state(tmp_path)

    fp = tmp_path / app.AUTOSAVE_FILENAME
    first_content = json.loads(fp.read_text(encoding="utf-8"))
    assert first_content["article__main_kw"] == "遺族年金"

    st.session_state["article__main_kw"] = "遺族基礎年金"
    app._autosave_state(tmp_path)

    # タイムスタンプ付きの新規ファイルは増えず、同じファイル名のまま中身だけ更新される
    autosave_files = [p for p in tmp_path.iterdir() if p.name == app.AUTOSAVE_FILENAME]
    assert len(autosave_files) == 1

    # 手動保存が使う state_*.json 形式のファイルは作られない
    assert list(tmp_path.glob("state_*.json")) == []

    second_content = json.loads(fp.read_text(encoding="utf-8"))
    assert second_content["article__main_kw"] == "遺族基礎年金"


def test_autosave_file_excluded_from_manual_backup_listing(tmp_path):
    _reset_session_state()
    _set_full_article_state(article__main_kw="遺族年金")
    app._autosave_state(tmp_path)

    manual_fp = tmp_path / "state_20260101_000000.json"
    manual_fp.write_text("{}", encoding="utf-8")

    listed_names = {p.name for p in app._iter_backup_files(tmp_path)}

    assert manual_fp.name in listed_names
    assert app.AUTOSAVE_FILENAME not in listed_names


def test_autosave_file_does_not_contain_api_key(tmp_path):
    _reset_session_state()
    _set_full_article_state(article__main_kw="遺族年金")
    st.session_state["openai_api_key"] = "sk-super-secret-value"

    app._autosave_state(tmp_path)

    fp = tmp_path / app.AUTOSAVE_FILENAME
    raw = fp.read_text(encoding="utf-8")
    assert "sk-super-secret-value" not in raw

    data = json.loads(raw)
    assert "openai_api_key" not in data


def test_autosave_before_menu_switch_keeps_consult_inputs(tmp_path):
    # メニュー切替でst.rerun()する直前にも自動保存するようになったため、
    # 記事モード入力直後にホームへ移動しても内容が残ることの回帰確認。
    _reset_session_state()
    _set_full_article_state(
        article__consult_situation="63歳会社員。給与28万円と賞与があり、年金がどう変わるか知りたい。",
        article__consult_question="給与と賞与はどう合算されるか。",
        article__main_kw="在職老齢年金",
    )

    app._autosave_state(tmp_path)

    fp = tmp_path / app.AUTOSAVE_FILENAME
    assert fp.exists()
    saved = json.loads(fp.read_text(encoding="utf-8"))
    assert saved["article__consult_situation"] == "63歳会社員。給与28万円と賞与があり、年金がどう変わるか知りたい。"
    assert saved["article__consult_question"] == "給与と賞与はどう合算されるか。"
    assert saved["article__main_kw"] == "在職老齢年金"
    assert "openai_api_key" not in saved


def test_autosave_noop_when_article_fields_all_blank(tmp_path):
    _reset_session_state()
    _set_full_article_state()  # 全項目が空

    app._autosave_state(tmp_path)

    fp = tmp_path / app.AUTOSAVE_FILENAME
    assert not fp.exists()


def test_restore_apply_keys_include_plan_and_proof_snapshots():
    # 「前回の入力を復元する」で下書き設計図・確認先snapshotが不自然に
    # 欠けないよう、RESTORE_APPLY_KEYSに追加されたことを確認する。
    for key in (
        "article__plan_result",
        "article__proof_evidence",
        "article__proof_evidence_compact",
        "article__proof_suggest",
        "article__proof_memo",
    ):
        assert key in app.RESTORE_APPLY_KEYS


def test_restore_apply_keys_never_include_api_key_or_copy_text():
    # APIキーは事故防止のため絶対に復元対象へ含めない。
    # copy_text（公開前に自分で直す本文）は今回の対象外のため含めない。
    assert "openai_api_key" not in app.RESTORE_APPLY_KEYS
    assert "article__copy_text" not in app.RESTORE_APPLY_KEYS


def test_restore_apply_keys_does_not_include_form_data_as_flat_string():
    # article__form_dataはdictのため、他のキーのように文字列化して
    # RESTORE_APPLY_KEYSの汎用ループへ混ぜてはいけない
    # （_apply_restore_payload内の専用マージ処理でのみ扱う）。
    assert app.ARTICLE_FORM_DATA_KEY not in app.RESTORE_APPLY_KEYS


def test_autosave_includes_form_data_dict(tmp_path):
    # article__form_data（記事モード入力の正本）がautosave_state.jsonに
    # dictのまま保存されることを確認する。
    _reset_session_state()
    _set_full_article_state(article__main_kw="遺族年金")
    st.session_state[app.ARTICLE_FORM_DATA_KEY] = {
        "consult_situation": "63歳会社員です。",
        "copy_text": "利用者が手直しした本文です。",
    }

    app._autosave_state(tmp_path)

    fp = tmp_path / app.AUTOSAVE_FILENAME
    saved = json.loads(fp.read_text(encoding="utf-8"))
    assert saved[app.ARTICLE_FORM_DATA_KEY] == {
        "consult_situation": "63歳会社員です。",
        "copy_text": "利用者が手直しした本文です。",
    }


def test_autosave_does_not_skip_when_only_form_data_has_content(tmp_path):
    # 非表示ページのwidget key（WORK_SIG_KEYS）がStreamlitの仕様で全て
    # 空になっていても、article__form_dataに実際の入力が残っていれば
    # 「全欄が空」と誤判定して自動保存をスキップしないことを確認する。
    _reset_session_state()
    _set_full_article_state()  # WORK_SIG_KEYSの生キーは全て空
    st.session_state[app.ARTICLE_FORM_DATA_KEY] = {
        "consult_situation": "63歳会社員です。",
    }

    app._autosave_state(tmp_path)

    fp = tmp_path / app.AUTOSAVE_FILENAME
    assert fp.exists()


def test_apply_restore_payload_merges_form_data_dict_without_stringifying():
    _reset_session_state()
    payload = {
        app.ARTICLE_FORM_DATA_KEY: {
            "consult_situation": "復元された状況",
            "copy_text": "復元された手直し本文",
        }
    }

    app._apply_restore_payload(payload)

    restored = st.session_state[app.ARTICLE_FORM_DATA_KEY]
    assert isinstance(restored, dict)
    assert restored["consult_situation"] == "復元された状況"
    assert restored["copy_text"] == "復元された手直し本文"


def test_apply_restore_payload_never_puts_api_key_into_form_data():
    _reset_session_state()
    payload = {
        app.ARTICLE_FORM_DATA_KEY: {
            "consult_situation": "復元された状況",
            "openai_api_key": "sk-should-not-be-restored",
        }
    }

    app._apply_restore_payload(payload)

    restored = st.session_state[app.ARTICLE_FORM_DATA_KEY]
    assert "openai_api_key" not in restored
