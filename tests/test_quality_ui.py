from modules.quality_ui import _build_common_kanji_misuse_items


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
