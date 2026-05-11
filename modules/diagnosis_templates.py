# modules/diagnosis_templates.py
from __future__ import annotations

from typing import Any, Dict, List, Optional


# =========================================
# ランク共通テンプレ
# =========================================
DIAGNOSIS_RANK_TEMPLATES: Dict[str, Dict[str, str]] = {
    "SAFE": {
        "headline": "大きな問題は見つかりませんでした。",
        "lead": "ただし、公開前に確認したい表現がある場合は、下の案内を確認してください。",
    },
    "CAUTION": {
        "headline": "公開前に確認したい点があります。",
        "lead": "次の箇所は、一次情報と表現が少しずれている可能性があります。",
    },
    "RISK": {
        "headline": "一次情報と違う可能性があります。",
        "lead": "公開前に修正してください。",
    },
}


# =========================================
# 内部ログ → 購入者向けテンプレ辞書
# rule_key は guardrails_core.py の Finding.code と一致させる
# =========================================
DIAGNOSIS_RULES: Dict[str, Dict[str, Any]] = {
    "根拠未入力": {
        "rank": "RISK",
        "buyer_conclusion": "根拠が未入力のため、このまま公開するのは危険です。",
        "issue_label": "根拠メモ",
        "issue_template": "本文には数字や制度説明がありますが、根拠メモが空です。",
        "reason_template": (
            "税金・法律・制度テーマでは、一次情報がないまま数字や期限を書くと、"
            "誤情報や思い込みが混ざる危険があります。"
        ),
        "fix_template": (
            "国税庁などの一次情報URL、または資料名と要点を根拠欄に入れてから、"
            "もう一度確認してください。"
        ),
        "example_labels": [],
    },

    "根拠がURL中心": {
        "rank": "CAUTION",
        "buyer_conclusion": "根拠はありますが、数字の照合がしにくい状態です。",
        "issue_label": "根拠メモの内容",
        "issue_template": "根拠欄がURL中心で、数字や期限の抜粋が少ない状態です。",
        "reason_template": (
            "URLだけでは、本文の数字や期限が一次情報のどこに書かれているかを確認しにくく、"
            "自動判定の精度も下がります。"
        ),
        "fix_template": (
            "URLに加えて、一次情報の中の『数字や期限が書かれている部分の抜粋』を"
            "1〜3行ほど根拠欄に追加してください。"
        ),
        "example_labels": [],
    },

    "国税庁URLあり_数字要確認": {
        "rank": "CAUTION",
        "buyer_conclusion": "公開前に確認したい数字があります。",
        "issue_label": "金額・年号・期限",
        "issue_template": "金額・年号・期限に、根拠と照合できない数字があります。",
        "reason_template": (
            "根拠に入っている一次情報では、数字や年号・期限が本文と同じ形では書かれていません。"
            "一次情報にない数字は、誤解の原因になることがあります。"
        ),
        "fix_template": (
            "根拠に書かれている数字だけを使うか、数字を使わない言い方に直してください。"
            "必要な数字が根拠にない場合は、一次情報を追加してから書き加えてください。"
        ),
        "example_labels": ["3000万円", "2023年", "10月", "10%", "15%"],
    },

    "根拠に数字未記載": {
        "rank": "RISK",
        "buyer_conclusion": "一次情報にない数字があります。公開前に修正してください。",
        "issue_label": "本文中の数字",
        "issue_template": "本文の数字が、根拠欄の数字と一致していません。",
        "reason_template": (
            "年号・金額・期限などの数字は、読者の判断に直接影響します。"
            "一次情報にない数字を書くと、誤情報として伝わるおそれがあります。"
        ),
        "fix_template": (
            "数字は一次情報に書かれているものだけに直してください。"
            "根拠にない数字は削除するか、一般的な説明に言い換えてください。"
        ),
        "example_labels": [],
    },

    "相続税と110万円の混同注意": {
        "rank": "CAUTION",
        "buyer_conclusion": "税の種類が混ざっていないか確認したい箇所があります。",
        "issue_label": "110万円と相続税の説明",
        "issue_template": "本文に『110万円』と『相続税』が一緒に出ています。",
        "reason_template": (
            "110万円は贈与税の文脈で使われることが多く、"
            "相続税の基礎控除と混同すると、読者に誤解を与えるおそれがあります。"
        ),
        "fix_template": (
            "110万円の説明が必要な場合は、贈与税の話として分けて書いてください。"
            "相続税の記事では、相続税の基礎控除の説明に絞る方が安全です。"
        ),
        "example_labels": ["110万円", "相続税"],
    },

    "改正トーク要確認": {
        "rank": "CAUTION",
        "buyer_conclusion": "制度の改正に関する表現があります。公開前に確認してください。",
        "issue_label": "制度変更を示す表現",
        "issue_template": "『最近の改正』『最新の税率』『今後変わる』など、制度変更を示す表現があります。",
        "reason_template": (
            "一次情報では、いつ・どの制度が・どう変わったかが具体的に書かれていますが、"
            "本文の表現はそこまで特定できません。"
            "読者に『何か変わったらしい』という印象だけを与えるおそれがあります。"
        ),
        "fix_template": (
            "改正について書く場合は、根拠にある年号・対象・変更点に沿って具体的に書いてください。"
            "それが難しい場合は、『最新の情報は国税庁など公式情報で確認してください』程度の"
            "一般論にとどめてください。"
        ),
        "example_labels": ["最近の改正", "最新の税率", "今後変わる可能性"],
    },

    "改正根拠の具体性不足": {
        "rank": "CAUTION",
        "buyer_conclusion": "改正について書かれていますが、根拠の具体性が足りません。",
        "issue_label": "改正内容の裏付け",
        "issue_template": "改正や見直しの説明がありますが、何がどう変わったかが十分に示されていません。",
        "reason_template": (
            "『税制改正のあらまし』のような一般名だけでは、本文の改正表現をそのまま裏付けるには弱いことがあります。"
            "年号・対象・変更点まで見えると、読者は安心して理解できます。"
        ),
        "fix_template": (
            "改正について触れる場合は、年号・対象制度・変更点が分かる一次情報の説明に合わせてください。"
            "具体的に書けない場合は、改正の話自体を削るか、一般論に弱めてください。"
        ),
        "example_labels": ["改正", "見直し", "変更"],
    },

    "主題外論点の混入注意": {
        "rank": "CAUTION",
        "buyer_conclusion": "記事のテーマから少し広がりすぎている箇所があります。",
        "issue_label": "メインテーマ以外の説明",
        "issue_template": "メインテーマ以外の制度や別の税金の説明が含まれています。",
        "reason_template": (
            "一次情報には関連情報が載っていますが、この記事の主なテーマから説明が広がりすぎると、"
            "読者が『この記事で何を知ればよいか』をつかみにくくなります。"
        ),
        "fix_template": (
            "今回のテーマに直接関係する部分だけを残し、他の制度の詳細な説明は別記事に分けるか、"
            "簡単な言及にとどめてください。"
        ),
        "example_labels": [],
    },

    "根拠外の特例言及": {
        "rank": "CAUTION",
        "buyer_conclusion": "特例や控除の説明に、根拠を確認したい箇所があります。",
        "issue_label": "特例・控除の名称",
        "issue_template": "本文に特例や控除の名称が出ていますが、根拠欄に同じ説明が見当たりません。",
        "reason_template": (
            "税の特例や控除は、名称が似ていても内容が異なることがあります。"
            "根拠にない名称を出すと、読者が制度を取り違えるおそれがあります。"
        ),
        "fix_template": (
            "特例名や制度名は、根拠欄にある一次情報の名称だけを使ってください。"
            "必要な制度を説明したい場合は、その制度の一次情報を根拠に追加してください。"
        ),
        "example_labels": [],
    },

    "用語ブレ_税名": {
        "rank": "CAUTION",
        "buyer_conclusion": "税金の名称に、見直したい表現があります。",
        "issue_label": "税金の名称",
        "issue_template": "本文中の税金の名称が、一般的な正式名称と少し異なっています。",
        "reason_template": (
            "一般には『無申告加算税』『延滞税』という名称が使われます。"
            "名称が違うと、読者が他の資料や税務署の説明と照らし合わせたときに"
            "混乱するおそれがあります。"
        ),
        "fix_template": (
            "税金の名称は、一次情報や国税庁の説明に合わせて、"
            "『無申告加算税』『延滞税』などの正式な言い方に直してください。"
        ),
        "example_labels": ["未申告加算税", "遅延税"],
    },

    "起算点要確認": {
        "rank": "CAUTION",
        "buyer_conclusion": "期限の起算日の説明に、確認したい点があります。",
        "issue_label": "申告期限・納付期限の起算日",
        "issue_template": "申告期限や納付期限の起算日の書き方が、一次情報より簡略化されています。",
        "reason_template": (
            "一次情報では『死亡したことを知った日の翌日から10か月（通常は死亡日）』と書かれています。"
            "本文の表現は『死亡日』だけに見えるため、特殊なケースで誤解が生じるおそれがあります。"
        ),
        "fix_template": (
            "起算日の説明は、"
            "『死亡したことを知った日の翌日から10か月です。通常は、死亡日の翌日から数えます。』"
            "のように、一次情報の表現に合わせて書いてください。"
        ),
        "example_labels": ["死亡日の翌日から10か月", "亡くなった日から10か月"],
    },

    "根拠外の断定表現": {
        "rank": "CAUTION",
        "buyer_conclusion": "一次情報にない内容を言い切っている表現があります。",
        "issue_label": "断定表現",
        "issue_template": "一次情報に書かれていない具体的な金額・条件・影響などを断定している文があります。",
        "reason_template": (
            "根拠に入っている一次情報では、その内容まで書かれていません。"
            "にもかかわらず本文では言い切りになっているため、読者に誤解を与える可能性があります。"
        ),
        "fix_template": (
            "根拠にない内容は、『〜とされています』『〜のこともあると説明されています』など、"
            "一般的な説明に弱めるか、いったん削除してください。"
            "必要な情報がある場合は、一次情報を追加してから書き加えてください。"
        ),
        "example_labels": [],
    },

    "数字ズレ_重大": {
        "rank": "RISK",
        "buyer_conclusion": "一次情報と違う数字があります。公開前に修正してください。",
        "issue_label": "期限・税率・金額などの数字",
        "issue_template": "期限・税率・金額など、一次情報と違う数字があります。",
        "reason_template": (
            "一次情報と本文で数字が一致していません。"
            "期限や税額に関する数字の違いは、読者の判断に直接影響します。"
        ),
        "fix_template": (
            "一次情報に書かれている数字に合わせて修正してください。"
            "数字が分からない場合は、一次情報を確認するか、数字を挙げずに一般的な説明にしてください。"
        ),
        "example_labels": [],
    },
}


def build_buyer_diagnosis(
    rule_key: str,
    matched_texts: Optional[List[str]] = None,
    extra_reason: Optional[str] = None,
    extra_fix: Optional[str] = None,
) -> Dict[str, Any]:
    """
    内部ログ名から、購入者向け診断表示データを組み立てる。
    自由作文は禁止し、この辞書に基づく自動生成を原則とする。
    """
    matched_texts = matched_texts or []

    rule = DIAGNOSIS_RULES.get(rule_key)
    if not rule:
        return {
            "rank": "CAUTION",
            "headline": "公開前に確認したい点があります。",
            "lead": "本文に見直し候補が検出されました。",
            "issue_label": "確認したい箇所",
            "issue_text": "本文の表現を確認してください。",
            "reason_text": "自動判定で見直し候補が検出されました。一次情報と照合して内容を確認してください。",
            "fix_text": "一次情報と本文を見比べて、必要な表現の修正を行ってください。",
            "matched_texts": matched_texts,
        }

    rank: str = rule["rank"]
    rank_template = DIAGNOSIS_RANK_TEMPLATES[rank]

    reason_text = rule["reason_template"]
    if extra_reason:
        reason_text += " " + extra_reason

    fix_text = rule["fix_template"]
    if extra_fix:
        fix_text += " " + extra_fix

    return {
        "rank": rank,
        "headline": rank_template["headline"],
        "lead": rule["buyer_conclusion"],
        "issue_label": rule["issue_label"],
        "issue_text": rule["issue_template"],
        "reason_text": reason_text,
        "fix_text": fix_text,
        "matched_texts": matched_texts,
    }