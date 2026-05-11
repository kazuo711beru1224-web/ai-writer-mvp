# modules/quality_checker.py
from __future__ import annotations
from typing import Dict, List, Optional
import re


def split_sentences(text: str) -> List[str]:
    """
    文章をざっくり文ごとに分割する簡易関数。
    精度よりも「軽くて速いこと」を優先しています。
    """
    raw = re.split(r"[。！？\?！]", text)
    return [s.strip() for s in raw if s.strip()]


def check_sentence_length(sentences: List[str], max_len: int = 60) -> Dict:
    """
    一文60文字ルールのチェック。
    長すぎる文があれば位置と文字数、頭40文字を返す。
    """
    too_long = []
    for idx, s in enumerate(sentences):
        if len(s) > max_len:
            too_long.append(
                {
                    "index": idx,
                    "length": len(s),
                    "text": s[:40] + "..." if len(s) > 40 else s,
                }
            )

    return {
        "ok": len(too_long) == 0,
        "too_long_sentences": too_long,
    }


def check_duplicate_endings(sentences: List[str], limit: int = 3) -> Dict:
    """
    語尾（です／ます／だ／である等）の3連続チェック。
    ざっくり検出して「リズムが単調になっていないか」を見る。
    """
    endings_pattern = r"(です|ます|だ|である)$"

    endings: List[str] = []
    for s in sentences:
        m = re.search(endings_pattern, s)
        endings.append(m.group(1) if m else "その他")

    duplicates: List[Dict] = []
    count = 1
    for i in range(1, len(endings)):
        if endings[i] == endings[i - 1]:
            count += 1
        else:
            if count >= limit and endings[i - 1] != "その他":
                duplicates.append(
                    {
                        "ending": endings[i - 1],
                        "count": count,
                        "last_sentence_index": i - 1,
                    }
                )
            count = 1

    if endings:
        if count >= limit and endings[-1] != "その他":
            duplicates.append(
                {
                    "ending": endings[-1],
                    "count": count,
                    "last_sentence_index": len(endings) - 1,
                }
            )

    return {
        "ok": len(duplicates) == 0,
        "duplicates": duplicates,
    }


def count_keyword(text: str, keyword: Optional[str]) -> int:
    """
    メインキーワード出現回数（単純な部分一致カウント）。
    厳密な形態素解析は行わず、まずは軽く動くことを優先。
    """
    if not keyword:
        return 0
    return text.count(keyword)


def analyze_quality(
    text: str,
    main_keyword: Optional[str] = None,
    max_sentence_len: int = 60,
) -> Dict:
    """
    品質チェックのメイン関数（第一段階プロトタイプ）

    - 一文60文字ルール
    - 語尾3連続ルール
    - キーワード出現回数
    などをチェックして dict で返す。
    """
    sentences = split_sentences(text)

    length_result = check_sentence_length(sentences, max_sentence_len)
    ending_result = check_duplicate_endings(sentences)
    keyword_count = count_keyword(text, main_keyword)

    # 簡易スコア（ルール遵守度の目安）
    score = 100
    comments: List[str] = []

    if not length_result["ok"]:
        score -= 10
        comments.append("一文が60文字を超える箇所があります。文を分けて読みやすくしましょう。")

    if not ending_result["ok"]:
        score -= 5
        comments.append("同じ語尾が3文以上続く箇所があります。語尾や文のリズムを変えてください。")

    if main_keyword:
        if keyword_count < 3:
            score -= 5
            comments.append(f"メインキーワード「{main_keyword}」の出現回数が少なめです（目安3〜5回）。")
        elif keyword_count > 10:
            score -= 5
            comments.append(f"メインキーワード「{main_keyword}」の出現回数が多すぎる可能性があります。自然さを優先してください。")

    if score < 0:
        score = 0

    if not comments:
        comments.append("大きな問題はありません。構成や言い回しを整えると、さらに読みやすくなります。")

    return {
        "score": score,
        "sentence_length": length_result,
        "duplicate_endings": ending_result,
        "keyword": main_keyword,
        "keyword_count": keyword_count,
        "comments": comments,
    }
