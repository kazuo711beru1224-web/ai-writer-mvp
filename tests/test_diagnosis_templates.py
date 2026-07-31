from modules.diagnosis_templates import build_buyer_diagnosis

_RULE_KEY = "重要主張の照合未完了"

_OLD_HARD_PHRASES = (
    "重要な数字や計算",
    "主張ごとの照合",
    "制度・法律・医療・金融",
    "公式の対象条件・例外・計算式",
    "対象者・数字・計算式・期限・例外",
)

_MONEY_CONTRACT_ONLY_PHRASES = (
    "カード会社",
    "手数料・請求・返金・契約条件",
)


def test_claim_alignment_pending_returns_new_buyer_facing_text():
    diag = build_buyer_diagnosis(rule_key=_RULE_KEY)

    assert diag["lead"] == "本文に、確認資料に書かれているか確かめたい大事な説明があります。"
    assert diag["issue_label"] == "確認したい内容"
    assert diag["issue_text"] == "数字・条件・理由・対象者などの大事な説明"
    assert diag["reason_text"] == (
        "この説明が、入力された確認資料に本当に書かれているか、まだ一つずつ確認できていません。"
    )
    assert diag["fix_text"] == (
        "確認資料を見直してください。書かれていない内容は削るか、"
        "『詳しくは公式の確認先へお問い合わせください』などの控えめな説明に直してください。"
    )


def test_claim_alignment_pending_issue_text_is_generic_and_understandable():
    diag = build_buyer_diagnosis(rule_key=_RULE_KEY)

    assert diag["issue_text"] == "数字・条件・理由・対象者などの大事な説明"


def test_claim_alignment_pending_drops_old_hard_to_understand_phrases():
    diag = build_buyer_diagnosis(rule_key=_RULE_KEY)
    combined = " ".join(
        [
            str(diag.get("lead", "")),
            str(diag.get("issue_label", "")),
            str(diag.get("issue_text", "")),
            str(diag.get("reason_text", "")),
            str(diag.get("fix_text", "")),
        ]
    )

    for phrase in _OLD_HARD_PHRASES:
        assert phrase not in combined, phrase


def test_claim_alignment_pending_has_no_money_contract_specific_wording():
    diag = build_buyer_diagnosis(rule_key=_RULE_KEY)
    combined = " ".join(
        [
            str(diag.get("lead", "")),
            str(diag.get("issue_label", "")),
            str(diag.get("issue_text", "")),
            str(diag.get("reason_text", "")),
            str(diag.get("fix_text", "")),
        ]
    )

    for phrase in _MONEY_CONTRACT_ONLY_PHRASES:
        assert phrase not in combined, phrase
