import re

from modules.quality_ui import _build_copy_button_html as quality_build_copy_button_html
from modules.article_ui import _build_copy_button_html as article_build_copy_button_html


def _extract_data_label(html_out: str) -> str:
    m = re.search(r'data-label="([^"]*)"', html_out)
    assert m is not None
    return m.group(1)


def test_quality_ui_data_label_has_no_unicode_escape():
    html_out = quality_build_copy_button_html("本文サンプル", "指摘付き本文をコピー")

    data_label = _extract_data_label(html_out)
    assert "\\u" not in data_label
    assert data_label == "指摘付き本文をコピー"
    assert "指摘付き本文をコピー" in html_out


def test_article_ui_data_label_has_no_unicode_escape():
    html_out = article_build_copy_button_html("本文サンプル", "この本文をコピー")

    data_label = _extract_data_label(html_out)
    assert "\\u" not in data_label
    assert data_label == "この本文をコピー"


def test_data_label_escapes_double_quotes_safely():
    html_out = quality_build_copy_button_html("本文", 'コピー"用"ラベル')

    # ラベル中の " が &quot; にエスケープされ、属性が途中で終わらないこと
    assert 'コピー&quot;用&quot;ラベル' in html_out
    data_label = _extract_data_label(html_out)
    assert data_label == "コピー&quot;用&quot;ラベル"


def test_copy_text_js_literal_still_uses_json_dumps_escaping():
    # クリップボードにコピーされる本文側は、JS文字列リテラルとして
    # そのまま埋め込むため json.dumps によるエスケープ（改行→\n、"→&quot;）を維持している。
    html_out = quality_build_copy_button_html('改行\nと"引用符"を含む本文', "コピー")

    assert "var t=" in html_out
    assert "\\n" in html_out
    assert "&quot;" in html_out
