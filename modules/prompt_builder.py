# modules/prompt_builder.py

def build_series_prompt(
    series_id: str,
    series_yaml: str,
    keyword: str,
    sub_keywords: str = "",
    theme: str = ""
) -> str:
    """
    シリーズYAMLとキーワード類から、GPTに投げるプロンプト全文を組み立てる。
    """
    prompt = f"""
あなたは「{series_id}」シリーズの専属ライターです。

以下のYAML（シリーズルール）に *厳密に従って* 記事を生成してください。

--- シリーズYAML ---
{series_yaml}
--- シリーズYAMLここまで ---

【あなたが従うルール】
1. YAMLの global_style に完全準拠した文体・語尾で書く
2. structure_rules に従い、H2/H3の順序を絶対に崩さない
3. h3_length_rough（目安300字）を守る
4. 必要なキーワードを seo_rules に沿って自然に挿入する
5. series_phrasing.preferred_phrases を適度に使用し、統一感を出す
6. 避ける表現は絶対に使わない
7. 記事目的（target_reader と goal_after_series）を文章の中心に据える

【生成手順】
① タイトル作成（seo_rules.title条件を満たす）
② 導入文（structure_rules.introパターンに沿って約300字）
③ H2-1（基礎理解）＋配下のH3本文
④ H2-2（実践）＋配下のH3本文
⑤ H2-3（継続・応用）＋配下のH3本文
⑥ 結論（structure_rules.conclusion パターンで約200字）
⑦ 最後に series_phrasing.closing_sentence_template を自然に挿入

【出力形式】
H2/H3をMarkdown記法で明確に表示し、
文章は「です・ます調」「一文60字以内」に統一してください。

---
メインキーワード：{keyword}
サブキーワード：{sub_keywords}
記事テーマ：{theme}
"""
    return prompt.strip()
