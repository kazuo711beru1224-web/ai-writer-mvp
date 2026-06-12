from modules.article_ui import _classify_question_type


def test_promotion_context_is_not_latest_news():
    text = (
        "近くにドラッグストアができてから、コンビニの来店客数が少し減っています。"
        "店頭POPの文章を考えたいです。"
    )
    assert _classify_question_type(text) != "latest_news"
