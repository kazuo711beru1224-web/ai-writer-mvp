from modules.article_ui import (
    _classify_question_type,
    _build_scroll_to_anchor_script_html,
    DETAIL_EVIDENCE_ANCHOR_ID,
    SCROLL_TO_EVIDENCE_FLAG_KEY,
)


def test_promotion_context_is_not_latest_news():
    text = (
        "近くにドラッグストアができてから、コンビニの来店客数が少し減っています。"
        "店頭POPの文章を考えたいです。"
    )
    assert _classify_question_type(text) != "latest_news"


def test_scroll_flag_key_is_a_temporary_session_key():
    # 自動保存やPERSIST_KEYSに紛れ込まないよう、tmp__ prefixの一時キーであることを確認する。
    assert SCROLL_TO_EVIDENCE_FLAG_KEY.startswith("tmp__")


def test_detail_evidence_anchor_id_matches_expected_name():
    assert DETAIL_EVIDENCE_ANCHOR_ID == "detail-evidence-anchor"


def test_scroll_script_html_targets_the_evidence_anchor_via_parent_document():
    html_out = _build_scroll_to_anchor_script_html(DETAIL_EVIDENCE_ANCHOR_ID)

    assert "<script>" in html_out
    assert "window.parent" in html_out
    assert "scrollIntoView" in html_out
    assert '"detail-evidence-anchor"' in html_out


def test_scroll_script_html_escapes_anchor_id_as_json_string():
    html_out = _build_scroll_to_anchor_script_html('"; alert(1); //')

    # JSON文字列として埋め込まれ、スクリプトを閉じたり注入したりできないこと
    assert 'var id = "\\"; alert(1); //"' in html_out


def test_scroll_script_html_differs_by_nonce_to_force_iframe_reload():
    # anchor_idは常に同じ文字列のため、nonce無しだと2回目以降components.htmlへ渡す
    # HTMLが前回と完全に同一になり、ブラウザがiframeの再読み込み（＝script再実行）を
    # 省略してしまう（＝2回目以降スクロールが発火しない）。nonceを変えることで
    # 毎回異なるHTMLにし、確実に再読み込み・再実行させる。
    html_1 = _build_scroll_to_anchor_script_html(DETAIL_EVIDENCE_ANCHOR_ID, nonce="1")
    html_2 = _build_scroll_to_anchor_script_html(DETAIL_EVIDENCE_ANCHOR_ID, nonce="2")

    assert html_1 != html_2
