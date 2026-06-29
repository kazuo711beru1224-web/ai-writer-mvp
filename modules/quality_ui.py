from __future__ import annotations

from typing import Dict, Optional, Any, List
import html
import json
import re
import streamlit as st

from modules.guardrails_core import evaluate_guardrails
from modules.style_checker import check_style
from modules.diagnosis_templates import build_buyer_diagnosis


# =========================
# ベル憲法：状態キー固定
# =========================
KEYS: Dict[str, str] = {
    # 入力
    "check_text": "check__text",
    "check_text_widget": "quality__manual_text",
    "check_text_saved": "quality__manual_text_saved",

    # 道しるべ（チェック側に保持：記事→チェック貼り付けでコピー）
    "check_evidence": "check__evidence_text",
    "check_suggest": "check__suggest_text",
    "check_memo": "check__memo_text",

    # 内容チェック結果（guardrails）
    "diag_level": "check__diag_level",
    "diag_lines": "check__diag_lines",
    "diag_payload_json": "check__diag_payload_json",

    # 表記・言い回しチェック結果（style checker）
    "style_level": "check__style_level",
    "style_lines": "check__style_lines",
    "style_payload_json": "check__style_payload_json",

    # メッセージ
    "notice": "check__notice",

    # 手動リライト
    "manual_rewrite_text_widget": "quality__manual_rewrite_text",
    "manual_rewrite_text_saved": "quality__manual_rewrite_text_saved",

    # ボタン
    "btn_paste_latest": "btn_paste_latest",
    "btn_clear_check": "btn_clear_check",
    "btn_diagnose": "btn_diagnose",
}

# =========================
# 記事モード側のキー揺れに耐える（保険）
# =========================
ARTICLE_BODY_KEYS: List[str] = [
    "article__last_text",
    "article__copy_text",
    "article__generated_text",
]

ARTICLE_PROOF_EVIDENCE_KEYS: List[str] = [
    "article__proof_evidence",
    "article__proof_evidence_text",
    "article__proof_ev",
]
ARTICLE_PROOF_SUGGEST_KEYS: List[str] = [
    "article__proof_suggest",
    "article__proof_suggest_text",
    "article__proof_kw",
]
ARTICLE_PROOF_MEMO_KEYS: List[str] = [
    "article__proof_memo",
    "article__proof_memo_text",
    "article__proof_note",
]

ARTICLE_EVIDENCE_KEYS: List[str] = [
    "article__evidence_text",
    "article__evidence",
    "article__evidence_memo",
    "article__evidence_notes",
]
ARTICLE_SUGGEST_KEYS: List[str] = [
    "article__suggest_text",
    "article__suggest",
    "article__related_keywords",
    "article__keywords_related",
    "article__related_kw",
    "article__suggest_kw",
    "article__keywords",
]
ARTICLE_MEMO_KEYS: List[str] = [
    "article__memo",
    "article__memo_text",
    "article__writer_memo",
    "article__note",
]


def _ensure_state() -> None:
    """初期化は if key not in で1回だけ（憲法準拠）"""
    must_init = (
        KEYS["check_text_saved"],
        KEYS["check_text"],
        KEYS["check_evidence"],
        KEYS["check_suggest"],
        KEYS["check_memo"],
        KEYS["diag_level"],
        KEYS["diag_lines"],
        KEYS["diag_payload_json"],
        KEYS["style_level"],
        KEYS["style_lines"],
        KEYS["style_payload_json"],
        KEYS["notice"],
        KEYS["manual_rewrite_text_saved"],
    )
    for k in must_init:
        if k not in st.session_state:
            st.session_state[k] = ""


def _sync_widget_to_saved(widget_key: str, saved_key: str) -> None:
    """Widget の変更内容を保存用 state に同期する。"""
    st.session_state[saved_key] = str(st.session_state.get(widget_key, "") or "")


def _first_nonempty(keys: List[str]) -> str:
    """候補キーの中から最初の非空文字列を返す（無ければ空文字）"""
    for k in keys:
        v = st.session_state.get(k, "")
        if v and str(v).strip():
            return str(v)
    return ""


def _resolve_article_body() -> str:
    """記事モード由来の最新本文を解決する。"""
    body = _first_nonempty(ARTICLE_BODY_KEYS)
    return body.strip() if body else ""


def _resolve_article_evidence() -> str:
    """
    記事モード由来の根拠を、優先順位つきで解決する。
    1) 最後に生成した時点の証拠（proof）
    2) 入力中の控え（evidence）
    """
    ev = _first_nonempty(ARTICLE_PROOF_EVIDENCE_KEYS)
    if ev and ev.strip():
        return ev
    return _first_nonempty(ARTICLE_EVIDENCE_KEYS)


def _resolve_article_suggest() -> str:
    """
    記事モード由来の関連語を、優先順位つきで解決する。
    1) 最後に生成した時点の証拠（proof）
    2) 入力中の控え（suggest）
    """
    sg = _first_nonempty(ARTICLE_PROOF_SUGGEST_KEYS)
    if sg and sg.strip():
        return sg
    return _first_nonempty(ARTICLE_SUGGEST_KEYS)


def _resolve_article_memo() -> str:
    """
    記事モード由来のメモを、優先順位つきで解決する。
    1) 最後に生成した時点の控え（proof_memo）
    2) 入力中のメモ（memo）
    """
    memo = _first_nonempty(ARTICLE_PROOF_MEMO_KEYS)
    if memo and memo.strip():
        return memo
    return _first_nonempty(ARTICLE_MEMO_KEYS)


def _extract_style_preferences_from_memo(memo_text: str) -> Dict[str, Any]:
    """
    読者や書き方のメモから、案件ルールを人間語ベースで読み取る。
    ここでは完璧判定ではなく、分かりやすい明示指示だけを拾う。
    """
    memo = str(memo_text or "").strip()
    if not memo:
        return {
            "preferred_tone": None,
            "prefer_halfwidth_percent": False,
            "prefer_kagetsu_style": None,
            "prefer_kudasai": False,
            "prefer_dekiru": False,
        }

    normalized = memo.replace("　", " ")
    compact = re.sub(r"\s+", "", normalized)

    preferred_tone: Optional[str] = None
    prefer_halfwidth_percent = False
    prefer_kagetsu_style: Optional[str] = None
    prefer_kudasai = False
    prefer_dekiru = False

    # -------------------------
    # 1. 文体
    # -------------------------
    if any(x in compact for x in (
        "ですます調",
        "です・ます調",
        "ですますで",
        "です・ますで",
        "敬体で",
        "敬体に統一",
        "ですますに統一",
        "です・ますに統一",
    )):
        preferred_tone = "desu_masu"

    elif any(x in compact for x in (
        "だである調",
        "だ・である調",
        "常体で",
        "常体に統一",
        "である調に統一",
        "だであるに統一",
        "だ・であるに統一",
    )):
        preferred_tone = "dearu"

    # -------------------------
    # 2. % は半角
    # -------------------------
    if any(x in compact for x in (
        "%は半角",
        "％は使わない",
        "パーセントは半角",
        "パーセント記号は半角",
        "半角%で統一",
        "半角％でなく%を使う",
        "%で統一",
    )):
        prefer_halfwidth_percent = True

    # -------------------------
    # 3. か月表記
    # -------------------------
    kagetsu_patterns = ("か月", "ヶ月", "ヵ月", "ケ月", "カ月")
    for target in kagetsu_patterns:
        if any(x in compact for x in (
            f"{target}に統一",
            f"{target}で統一",
            f"{target}表記",
            f"{target}を使う",
            f"{target}を使用",
        )):
            prefer_kagetsu_style = target
            break

    # -------------------------
    # 4. ください表記
    # -------------------------
    if any(x in compact for x in (
        "くださいに統一",
        "くださいで統一",
        "『ください』に統一",
        "下さいは使わない",
        "ください表記",
    )):
        prefer_kudasai = True

    # -------------------------
    # 5. できる表記
    # -------------------------
    if any(x in compact for x in (
        "できるに統一",
        "できるで統一",
        "『できる』に統一",
        "出来るは使わない",
        "できる表記",
    )):
        prefer_dekiru = True

    return {
        "preferred_tone": preferred_tone,
        "prefer_halfwidth_percent": prefer_halfwidth_percent,
        "prefer_kagetsu_style": prefer_kagetsu_style,
        "prefer_kudasai": prefer_kudasai,
        "prefer_dekiru": prefer_dekiru,
    }


def _paste_latest_generated() -> None:
    """記事モードの最新生成を、文章チェック欄へ貼り付け（根拠・関連語・メモも一緒にコピー）"""
    _ensure_state()

    latest = _resolve_article_body()
    st.session_state[KEYS["check_text_saved"]] = latest if latest else ""
    st.session_state[KEYS["check_text_widget"]] = latest if latest else ""

    st.session_state[KEYS["check_evidence"]] = _resolve_article_evidence()
    st.session_state[KEYS["check_suggest"]] = _resolve_article_suggest()
    st.session_state[KEYS["check_memo"]] = _resolve_article_memo()

    st.session_state[KEYS["diag_level"]] = ""
    st.session_state[KEYS["diag_lines"]] = ""
    st.session_state[KEYS["diag_payload_json"]] = ""
    st.session_state[KEYS["style_level"]] = ""
    st.session_state[KEYS["style_lines"]] = ""
    st.session_state[KEYS["style_payload_json"]] = ""

    if latest:
        st.session_state[KEYS["notice"]] = "最新の下書きを貼り付けました。ここから確認を進められます。"
    else:
        st.session_state[KEYS["notice"]] = (
            "記事モードの最新本文が見つかりませんでした。"
            "先に記事モードで下書きを作るか、復元後にもう一度お試しください。"
        )


def _clear_check_text() -> None:
    """文章チェック欄をクリア（道しるべも一緒にクリア）"""
    _ensure_state()
    st.session_state[KEYS["check_text_saved"]] = ""
    st.session_state[KEYS["check_text_widget"]] = ""
    st.session_state[KEYS["check_evidence"]] = ""
    st.session_state[KEYS["check_suggest"]] = ""
    st.session_state[KEYS["check_memo"]] = ""
    st.session_state[KEYS["manual_rewrite_text_saved"]] = ""
    st.session_state[KEYS["manual_rewrite_text_widget"]] = ""
    st.session_state[KEYS["diag_level"]] = ""
    st.session_state[KEYS["diag_lines"]] = ""
    st.session_state[KEYS["diag_payload_json"]] = ""
    st.session_state[KEYS["style_level"]] = ""
    st.session_state[KEYS["style_lines"]] = ""
    st.session_state[KEYS["style_payload_json"]] = ""
    st.session_state[KEYS["notice"]] = ""


def _format_diag_lines(res) -> str:
    """
    Result を画面表示用の文字列に落とす。
    session_state にオブジェクトを入れない。
    """
    lines: List[str] = []
    findings = getattr(res, "findings", None) or []
    for f in findings:
        msg = getattr(f, "message", "")
        if not str(msg).strip():
            continue
        code = getattr(f, "code", "")
        if code == "便利表現チェック":
            continue
        lines.append(f"- {msg}")
        samples = getattr(f, "samples", None)
        if samples:
            try:
                ss = [str(x) for x in samples][:12]
                lines.append("  例：" + " / ".join(ss))
            except Exception:
                pass
    return "\n".join(lines).strip()


def _serialize_guardrail_payload(res) -> str:
    """
    GuardrailResult.findings を、購入者向け表示用のJSON文字列へ変換する。
    session_state には文字列だけを保存する。
    """
    findings = getattr(res, "findings", None) or []
    items: List[Dict[str, Any]] = []

    for f in findings:
        rule_key = str(getattr(f, "code", "") or "")
        samples = getattr(f, "samples", None) or []
        matched_texts = [str(x) for x in samples if str(x).strip()]

        diag = build_buyer_diagnosis(
            rule_key=rule_key,
            matched_texts=matched_texts,
        )

        level = str(getattr(f, "level", "") or "")
        allow_without_quote = rule_key in {
            "最新情報は最終確認前提",
            "重要主張の照合未完了",
        }
        if level != "RISK" and (
            (not matched_texts and not allow_without_quote)
            or not str(diag.get("reason_text", "")).strip()
            or not str(diag.get("fix_text", "")).strip()
        ):
            continue

        rewrite_example = ""

        items.append({
            "rank": str(diag.get("rank", "CAUTION")),
            "headline": str(diag.get("headline", "")),
            "lead": str(diag.get("lead", "")),
            "issue_label": str(diag.get("issue_label", "")),
            "issue_text": str(diag.get("issue_text", "")),
            "reason_text": str(diag.get("reason_text", "")),
            "fix_text": str(diag.get("fix_text", "")),
            "rewrite_example": rewrite_example,
            "matched_texts": [str(x) for x in diag.get("matched_texts", []) if str(x).strip()],
        })

    items = _group_similar_diagnosis_items(items)

    try:
        return json.dumps(items, ensure_ascii=False)
    except Exception:
        return "[]"


def _serialize_style_payload(res, body_text: str = "") -> str:
    """
    style_checker の結果を、購入者向け表示用のJSON文字列へ変換する。
    """
    findings = getattr(res, "findings", None) or []
    items: List[Dict[str, Any]] = []

    for f in findings:
        code = str(getattr(f, "code", "") or "")
        samples = getattr(f, "samples", None) or []
        matched_texts = [str(x) for x in samples if str(x).strip()]

        headline = "表記や言い回しを整えたい箇所があります。"
        lead = "内容の安全性とは別に、文章の見た目や読み心地を整えるための確認です。"
        issue_label = "表記・言い回し"
        issue_text = "表記ゆれや文体の混在、誤字候補などが見つかりました。"
        reason_text = "公開前にそろえておくと、読みやすく信頼感のある文章になりやすくなります。"
        fix_text = "気になる箇所だけ見直して、表記や言い回しをそろえてください。"
        rewrite_example = ""

        if code == "文体混在_ですますとだである":
            headline = "文体の言い方が少し混ざっています。"
            lead = "『です・ます調』と『だ・である調』が混ざると、読み味がぶれやすくなります。"
            issue_label = "文体"
            issue_text = "文の終わり方に統一感がない箇所があります。"
            reason_text = "文体が混ざると、文章全体の印象が不安定に見えることがあります。"
            fix_text = "どちらかの文体にそろえると、読みやすくなります。"

        elif code == "語尾3連続":
            headline = "少し読みやすくできる箇所があります。"
            lead = "同じ終わり方の文が続いています。内容の間違いではありません。"
            issue_label = "文の終わり方"
            issue_text = "同じような終わり方の文が続いています。"
            reason_text = "同じ調子の文が続くと、少し機械的に見えることがあります。"
            fix_text = "気になる文だけ、言い方を少し変えると読みやすくなります。"
            rewrite_example = (
                "例：『各ケースでの計算方法が異なるため、慎重に確認する必要があります。』"
                "→『ケースごとに計算が変わるため、一次情報や専門家への確認が大切です。』"
            )

        elif code == "一文が長い":
            headline = "一文が長めの箇所があります。"
            lead = "長い一文は、意味が追いにくくなることがあります。"
            issue_label = "一文の長さ"
            issue_text = "一息で読み切りにくい文があります。"
            reason_text = "一文が長いと、伝えたいことがぼやけやすくなります。"
            fix_text = "2つの文に分けると、読みやすくなります。"

        elif code == "表記ゆれ候補":
            headline = "表記をそろえたい箇所があります。"
            lead = "同じ意味でも書き方が揺れると、文章全体が少し散らかって見えます。"
            issue_label = "表記"
            issue_text = "そろえておきたい書き方があります。"
            reason_text = "表記が統一されると、読みやすさと信頼感が上がります。"
            fix_text = "記事全体で同じ書き方にそろえてください。"

        elif code == "記号表記のゆれ":
            headline = "記号や単位の書き方をそろえたい箇所があります。"
            lead = "記号や単位の表記が混ざると、見た目の統一感が落ちやすくなります。"
            issue_label = "記号・単位"
            issue_text = "記号や単位の書き方がそろっていない箇所があります。"
            reason_text = "細かな表記の統一は、完成度を上げるのに役立ちます。"
            fix_text = "％やか月などの表記を、記事全体でそろえてください。"

        elif code == "便利表現チェック":
            headline = "少し直した方がよい言い方があります。"
            lead = "文章としては読めますが、『なぜ大事なのか』が少し伝わりにくいかもしれません。"
            issue_label = "理由が少し足りない言い方"
            issue_text = "『なぜそうなのか』がわかりにくい言い方があります。"
            reason_text = (
                "この言葉だけでは、読者が「なぜ大事なのか」「次に何をすればよいのか」を"
                "分かりにくく感じることがあります。"
            )
            fix_text = (
                "理由や具体例を一文足してください。読者が次に何をすればよいかも書きましょう。"
            )
            rewrite_example = ""

        elif code == "誤字候補":
            headline = "誤字や言い間違いの可能性がある箇所があります。"
            lead = "内容は合っていても、文字のミスで伝わり方が弱くなることがあります。"
            issue_label = "誤字候補"
            issue_text = "誤字や不自然な言い回しの可能性がある表現があります。"
            reason_text = "小さな文字のミスでも、読者には違和感として伝わることがあります。"
            fix_text = "公開前に一度見直して、自然な表現へ整えてください。"

        elif code == "重複語候補":
            headline = "同じ言葉が重なっている箇所があります。"
            lead = "文字が続けて入ると、誤字に見えやすくなります。"
            issue_label = "重複語"
            issue_text = "同じ語が重なっている可能性があります。"
            reason_text = "細かな重複でも、読者には違和感として伝わることがあります。"
            fix_text = "言葉が重なっていないか確認して、自然な形に整えてください。"

        elif code == "案件ルール_文体指定":
            headline = "この案件で決めた文体と違う書き方が混ざっています。"
            lead = "書き方のルールに合わせると、記事全体の統一感が上がります。"
            issue_label = "案件ルール（文体）"
            issue_text = "指定した文体とは別の文体が混ざっている可能性があります。"
            reason_text = "案件ごとの文体ルールを守ると、仕上がりのばらつきを減らせます。"
            fix_text = "指定した文体にそろえてください。"

        elif code == "案件ルール_パーセント半角":
            headline = "パーセント記号の書き方をそろえたい箇所があります。"
            lead = "この案件では、% の書き方を決めてそろえる前提です。"
            issue_label = "案件ルール（%）"
            issue_text = "全角の『％』が混ざっている可能性があります。"
            reason_text = "記号の書き方を統一すると、見た目が整いやすくなります。"
            fix_text = "半角の『%』にそろえてください。"

        elif code == "案件ルール_か月表記":
            headline = "期間の書き方をそろえたい箇所があります。"
            lead = "この案件では、『か月 / ヶ月 / ヵ月』などの書き方をそろえる前提です。"
            issue_label = "案件ルール（か月表記）"
            issue_text = "指定した期間表記とは別の書き方が混ざっている可能性があります。"
            reason_text = "期間表記が統一されると、文章の完成度が上がります。"
            fix_text = "指定した形にそろえてください。"

        elif code == "案件ルール_ください表記":
            headline = "『ください』の書き方をそろえたい箇所があります。"
            lead = "この案件では、『ください』の表記を統一する前提です。"
            issue_label = "案件ルール（ください）"
            issue_text = "漢字の『下さい』が混ざっている可能性があります。"
            reason_text = "同じ意味でも表記が混ざると、見た目にばらつきが出やすくなります。"
            fix_text = "『ください』にそろえてください。"

        elif code == "案件ルール_できる表記":
            headline = "『できる』の書き方をそろえたい箇所があります。"
            lead = "この案件では、『できる』の表記を統一する前提です。"
            issue_label = "案件ルール（できる）"
            issue_text = "漢字の『出来る』が混ざっている可能性があります。"
            reason_text = "細かな表記の統一は、文章の読みやすさにつながります。"
            fix_text = "『できる』にそろえてください。"

        items.append({
            "rank": "CAUTION",
            "headline": headline,
            "lead": lead,
            "issue_label": issue_label,
            "issue_text": issue_text,
            "reason_text": reason_text,
            "fix_text": fix_text,
            "rewrite_example": rewrite_example,
            "matched_texts": matched_texts,
            "code": code,
        })

    items.extend(_build_common_kanji_misuse_items(body_text))

    # グループ化処理：同じ説明を持つ診断をまとめる
    items = _group_similar_diagnosis_items(items)

    try:
        return json.dumps(items, ensure_ascii=False)
    except Exception:
        return "[]"


def _build_common_kanji_misuse_items(body_text: str) -> List[Dict[str, Any]]:
    """
    同音異義語・漢字誤用を検出し、文脈に応じた候補を提示する。
    ベル憲法準拠：「間違い」と断定せず、「確認してください」と表示。
    複数の候補は1つのアイテムにまとめる。
    """
    items: List[Dict[str, Any]] = []

    if not isinstance(body_text, str):
        return items

    found_terms: List[str] = []
    rules = [
        {
            "base_term": "進める",
            "replacement": "勧める",
            "variants": ["進める", "進めます", "進め"],
            "context_keywords": ["お客様", "商品", "購入", "対象商品", "新商品", "販売", "接客", "提案"],
        },
        {
            "base_term": "意志",
            "replacement": "意思",
            "variants": ["意志"],
            "context_keywords": ["本人", "お客様", "利用者", "家族", "顧客"],
        },
        {
            "base_term": "向かえる",
            "replacement": "迎える",
            "variants": ["向かえる", "向かえます", "向かえ"],
            "context_keywords": ["お客様", "来店客", "利用者", "読者", "相手", "人"],
        },
        {
            "base_term": "向かい入れる",
            "replacement": "迎え入れる",
            "variants": ["向かい入れる", "向かい入れます", "向かい入れ"],
            "context_keywords": ["お客様", "来店客", "利用者", "読者", "相手", "人"],
        },
    ]

    lines = body_text.split('\n')
    for line in lines:
        if not line.strip():
            continue

        for rule in rules:
            if any(term in line for term in rule["variants"]):
                if not any(keyword in line for keyword in rule["context_keywords"]):
                    continue

                example_text = f"{rule['base_term']} → {rule['replacement']}"
                if example_text not in found_terms:
                    found_terms.append(example_text)

    if found_terms:
        items.append({
            "rank": "CAUTION",
            "headline": "見直したい言葉があります。",
            "lead": "本文の中に、意味が近い漢字と迷いやすい言葉があります。",
            "issue_label": "同音異義語候補",
            "issue_text": "確認したい箇所",
            "reason_text": "意味によって、使う漢字が変わります。",
            "fix_text": "前後の意味を確認して、必要な場合だけ直してください。",
            "rewrite_example": "",
            "matched_texts": found_terms,
            "code": "漢字誤用_同音異義語",
        })

    return items


def _group_similar_diagnosis_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    同じ headline/lead/reason_text/fix_text を持つ診断をグループ化する。
    ベル憲法準拠：同じ種類の注意は1つにまとめて表示。
    """
    def _to_list(value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(x) for x in value if str(x).strip()]
        if value is None:
            return []
        value_str = str(value).strip()
        return [value_str] if value_str else []

    def _uniq(values: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for value in values:
            if value not in seen:
                seen.add(value)
                out.append(value)
        return out

    grouped: Dict[str, Dict[str, Any]] = {}

    for item in items:
        key = (
            str(item.get("headline", "")),
            str(item.get("lead", "")),
            str(item.get("reason_text", "")),
            str(item.get("fix_text", "")),
        )

        if key not in grouped:
            grouped[key] = item.copy()
            grouped[key]["matched_texts"] = _to_list(grouped[key].get("matched_texts", []))
            grouped[key]["issue_label"] = _to_list(grouped[key].get("issue_label", []))
            grouped[key]["issue_text"] = _to_list(grouped[key].get("issue_text", []))
            grouped[key]["rewrite_example"] = _to_list(grouped[key].get("rewrite_example", []))
        else:
            existing = grouped[key]
            existing_matched = _to_list(existing.get("matched_texts", []))
            new_matched = _to_list(item.get("matched_texts", []))
            existing["matched_texts"] = _uniq(existing_matched + new_matched)

            existing_labels = _to_list(existing.get("issue_label", []))
            new_labels = _to_list(item.get("issue_label", []))
            merged_labels = _uniq(existing_labels + new_labels)
            existing["issue_label"] = merged_labels if len(merged_labels) > 1 else (merged_labels[0] if merged_labels else "")

            existing_texts = _to_list(existing.get("issue_text", []))
            new_texts = _to_list(item.get("issue_text", []))
            merged_texts = _uniq(existing_texts + new_texts)
            existing["issue_text"] = merged_texts if len(merged_texts) > 1 else (merged_texts[0] if merged_texts else "")

            existing_rewrites = _to_list(existing.get("rewrite_example", []))
            new_rewrites = _to_list(item.get("rewrite_example", []))
            merged_rewrites = _uniq(existing_rewrites + new_rewrites)
            existing["rewrite_example"] = merged_rewrites if len(merged_rewrites) > 1 else (merged_rewrites[0] if merged_rewrites else "")

    # 1つだけのリストは文字列に戻す
    for item in grouped.values():
        for field in ("issue_label", "issue_text", "rewrite_example"):
            value = item.get(field)
            if isinstance(value, list) and len(value) == 1:
                item[field] = value[0]

    return list(grouped.values())


def _load_payload(raw_text: str) -> List[Dict[str, Any]]:
    raw = str(raw_text or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            out: List[Dict[str, Any]] = []
            for item in data:
                if isinstance(item, dict):
                    out.append(item)
            return out
        return []
    except Exception:
        return []


def _escape_and_mark(text: str, highlights: List[str]) -> str:
    escaped = html.escape(str(text or ""))
    if not highlights:
        return escaped.replace("\n", "<br>")
    ordered = sorted({str(h) for h in highlights if str(h).strip()}, key=len, reverse=True)
    for highlight in ordered:
        safe_highlight = html.escape(highlight)
        if not safe_highlight:
            continue
        escaped = escaped.replace(safe_highlight, f"<mark>{safe_highlight}</mark>")
    return escaped.replace("\n", "<br>")


def _suggest_rewrite_text(body: str, highlights: List[str]) -> str:
    # 単純な語句置換は不自然なAI語になりやすいため行わない。
    # 将来的に高品質な自動言い換えを導入する場合はここに実装する。
    return ""


def _render_badge(title: str, level: str) -> None:
    badge_map = {
        "SAFE": "✅ SAFE",
        "CAUTION": "⚠️ CAUTION",
        "RISK": "🛑 RISK",
    }
    if title == "\u8868\u8a18\u30fb\u8a00\u3044\u56de\u3057\u306e\u78ba\u8a8d":
        st.markdown('<div id="quality-wording" style="scroll-margin-top: 120px;"></div>', unsafe_allow_html=True)
    st.markdown(f"### {title}")
    st.write(badge_map.get(level or "", "（未診断）"))


def _render_buyer_diagnosis_blocks(items: List[Dict[str, Any]]) -> None:
    """
    購入者向け診断ブロックを表示する。
    結論 → 該当箇所 → 理由 → 直し方
    """
    for item in items:
        code = str(item.get("code", "") or "").strip()
        headline = str(item.get("headline", "") or "").strip()
        lead = str(item.get("lead", "") or "").strip()
        issue_label_raw = item.get("issue_label", "") or ""
        issue_text_raw = item.get("issue_text", "") or ""
        reason_text = str(item.get("reason_text", "") or "").strip()
        fix_text = str(item.get("fix_text", "") or "").strip()
        rewrite_example = item.get("rewrite_example", "") or ""
        matched_texts = item.get("matched_texts", []) or []

        def normalize_list(value: Any) -> List[str]:
            if isinstance(value, list):
                return [str(x).strip() for x in value if str(x).strip()]
            text = str(value).strip()
            return [text] if text else []

        issue_labels = normalize_list(issue_label_raw)
        issue_texts = normalize_list(issue_text_raw)

        st.markdown("---")

        if headline:
            st.markdown(f"**{headline}**")
        if lead:
            st.write(lead)

        if code == "便利表現チェック":
            body = str(st.session_state.get(KEYS["check_text_saved"], "") or "")
            if body and matched_texts:
                st.markdown('<div id="quality-fix-place" style="scroll-margin-top: 120px;"></div>', unsafe_allow_html=True)
                st.markdown("#### \u76f4\u3059\u5834\u6240\u304c\u308f\u304b\u308b\u672c\u6587")
                safe_body = _escape_and_mark(
                    body,
                    [str(text) for text in matched_texts if str(text).strip()],
                )

                st.markdown(
                    f"""
<div style="
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 14px 16px;
    background-color: #ffffff;
    color: #111827;
    font-size: 15px;
    line-height: 1.8;
    white-space: pre-wrap;
    max-height: 320px;
    overflow-y: auto;
">
{safe_body}
</div>
""",
                    unsafe_allow_html=True,
                )

            if matched_texts:
                st.markdown("**直した方がよい言葉**")
                for text in matched_texts:
                    st.markdown(f"- {html.escape(str(text))}")

            if reason_text:
                st.markdown("**なぜ直すのか**")
                st.write(reason_text)

            if fix_text:
                st.markdown("**直し方**")
                st.write(fix_text)

            if body and matched_texts:
                # 汎用的な修正の考え方を提示
                st.markdown("**修正の考え方**")
                st.write("この文章は、言葉を置き換えるだけでは自然になりません。")
                st.write("")
                st.write("次の2つを足すと、読みやすくなります。")
                st.write("")
                st.markdown("- なぜ大事なのか")
                st.markdown("- 読者が次に何をすればよいのか")
                st.write("")

                st.markdown("**直し方の例**")
                pension_keywords = ("在職老齢年金", "標準賞与額", "賞与", "12で割る")
                if any(keyword in body for keyword in pension_keywords):
                    original_example = "計算方法を確認することは重要です。"
                    rewrite_example_text = (
                        "在職老齢年金の説明では、賞与を支給回数で割るのではなく、"
                        "その月以前1年間の標準賞与額の合計を12で割る考え方を、"
                        "一次情報で確認してから書きましょう。"
                    )
                else:
                    original_example = "制度の内容を確認することは重要です。"
                    rewrite_example_text = (
                        "読者が誤解しないように、制度の条件や数字は"
                        "一次情報で確認してから説明しましょう。"
                    )

                st.write("元の文：")
                st.markdown(_escape_and_mark(original_example, []), unsafe_allow_html=True)
                st.write("")
                st.write("直し方：")
                st.markdown(_escape_and_mark(rewrite_example_text, []), unsafe_allow_html=True)
                st.write("")

                # ユーザが自分で修正案を書くための空欄（初期値は空）
                st.markdown("**自分で直した文章を書く欄**")
                manual_rewrite_widget = KEYS["manual_rewrite_text_widget"]
                manual_rewrite_saved = KEYS["manual_rewrite_text_saved"]
                if manual_rewrite_widget not in st.session_state:
                    st.session_state[manual_rewrite_widget] = st.session_state.get(manual_rewrite_saved, "")

                st.text_area(
                    "",
                    key=manual_rewrite_widget,
                    height=240,
                    help="書き直した文章をここに入力し、上の『確認したい文章』に貼り直して再確認してください。",
                    label_visibility="collapsed",
                    on_change=_sync_widget_to_saved,
                    kwargs={"widget_key": manual_rewrite_widget, "saved_key": manual_rewrite_saved},
                )

                st.markdown("**次の確認**")
                st.write("上の考え方を参考にして文章を直してください。")
                st.write("直した文章を『確認したい文章』に貼り直して、もう一度確認してください。")

        else:
            generic_fallback = (
                issue_labels == ["確認したい箇所"]
                and issue_texts == ["本文の表現を確認してください。"]
            )

            if generic_fallback and matched_texts:
                st.markdown("**見直したい言葉**")
                for t in matched_texts:
                    st.markdown(f"- {t}")
            else:
                if issue_labels:
                    st.markdown("**確認したい箇所**")
                    for label in issue_labels:
                        if label != "確認したい箇所":
                            st.markdown(f"- {label}")
                    if issue_texts:
                        for text in issue_texts:
                            st.write(text)
                elif issue_texts:
                    st.markdown("**確認したい箇所**")
                    for text in issue_texts:
                        st.write(text)

                if matched_texts:
                    st.markdown("**本文の該当箇所**")
                    for t in matched_texts:
                        st.markdown(f"- {t}")

            if reason_text:
                st.markdown("**理由**")
                st.write(reason_text)

            if fix_text:
                st.markdown("**直し方**")
                st.write(fix_text)

            if rewrite_example:
                st.markdown("**言い換え例**")
                st.write(rewrite_example)


def render_quality_ui(logs_dir: Optional[str] = None, **kwargs: Any) -> None:
    """
    文章チェック（手動入力）
    - logs_dir を受ける（app.py署名ズレ耐性）
    - **kwargs で将来拡張に耐える
    - ウィジェットに value などの初期値パラメータを渡さない（憲法準拠）
    """
    _ = logs_dir
    _ = kwargs
    _ensure_state()

    st.markdown('<div id="quality-top" style="scroll-margin-top: 120px;"></div>', unsafe_allow_html=True)
    st.markdown("## 文章チェック（手動入力）")
    st.write("ここでは、公開前に気になる点を確認できます。")
    st.write("どこを見直すと安心かを、下に分かりやすく表示します。")

    st.divider()

    c1, c2 = st.columns([1, 1])
    with c1:
        st.button(
            "最新の下書きを貼り付ける（記事モード → チェック）",
            on_click=_paste_latest_generated,
            use_container_width=True,
            key=KEYS["btn_paste_latest"],
        )
    with c2:
        st.button(
            "入力を空にする",
            on_click=_clear_check_text,
            use_container_width=True,
            key=KEYS["btn_clear_check"],
        )

    notice = str(st.session_state.get(KEYS["notice"], "") or "")
    if notice:
        if "見つかりません" in notice:
            st.warning(notice)
        else:
            st.success(notice)

    st.divider()

    st.markdown('<div id="quality-text" style="scroll-margin-top: 120px;"></div>', unsafe_allow_html=True)
    st.markdown("### 確認したい文章")
    st.caption("公開前に見直したい本文をここへ入れてください。")
    st.caption("例：記事モードで作った下書き / 外部で整えた本文 / 公開前の最終稿")

    check_text_widget = KEYS["check_text_widget"]
    check_text_saved = KEYS["check_text_saved"]
    if check_text_widget not in st.session_state:
        st.session_state[check_text_widget] = st.session_state.get(check_text_saved, "")

    st.text_area(
        "文章入力欄",
        key=check_text_widget,
        height=360,
        label_visibility="collapsed",
        on_change=_sync_widget_to_saved,
        kwargs={"widget_key": check_text_widget, "saved_key": check_text_saved},
    )

    st.divider()

    st.markdown('<div id="quality-guide" style="scroll-margin-top: 120px;"></div>', unsafe_allow_html=True)
    st.markdown("### 🔎 確認の道しるべ")
    st.write("ここでは、記事モードで入れた根拠メモや関連語を確認できます。")
    st.write("本文にない数字、言い過ぎ、根拠のない断定がないかを見直してください。")

    evidence = str(st.session_state.get(KEYS["check_evidence"], "") or "")
    suggest = str(st.session_state.get(KEYS["check_suggest"], "") or "")
    memo = str(st.session_state.get(KEYS["check_memo"], "") or "")

    if not evidence.strip():
        evidence = _resolve_article_evidence()
    if not suggest.strip():
        suggest = _resolve_article_suggest()
    if not memo.strip():
        memo = _resolve_article_memo()

    st.markdown('<div id="quality-evidence" style="scroll-margin-top: 120px;"></div>', unsafe_allow_html=True)
    st.markdown("**根拠メモ（参考URL / 資料名 / 大事な数字）**")
    if evidence.strip():
        st.write(evidence)
    else:
        st.write("未入力です。必要な数字や資料名がある場合は、記事モードで入力してください。")

    st.markdown("**読者が一緒に検索しそうな言葉**")
    if suggest.strip():
        st.write(suggest)
    else:
        st.write("未入力です。読者が検索しそうな言葉があれば、記事モードで入力してください。")

    st.markdown("**読者や書き方のメモ**")
    if memo.strip():
        st.write(memo)
    else:
        st.write("未入力です。書き方のルールがある場合は、記事モードで入力してください。")

    st.divider()

    st.write("準備ができたら、気になる点がないか確認します。")
    if st.button("公開前の確認をする", use_container_width=True, key=KEYS["btn_diagnose"]):
        body = str(st.session_state.get(KEYS["check_text_saved"], "") or "").strip()

        ev = str(evidence or "").strip()
        sg = str(suggest or "").strip()
        memo_text = str(memo or "").strip()

        if not body:
            st.session_state[KEYS["diag_level"]] = "CAUTION"
            st.session_state[KEYS["diag_lines"]] = "- CAUTION / EMPTY_BODY：本文が空です。文章を貼り付けてから確認してください。"
            st.session_state[KEYS["diag_payload_json"]] = json.dumps(
                [{
                    "rank": "CAUTION",
                    "headline": "公開前に確認したい点があります。",
                    "lead": "本文が空のため確認できません。",
                    "issue_label": "本文",
                    "issue_text": "確認したい文章が入力されていません。",
                    "reason_text": "本文が空のため、内容の確認を行えません。",
                    "fix_text": "文章を貼り付けてから、もう一度確認してください。",
                    "rewrite_example": "",
                    "matched_texts": [],
                }],
                ensure_ascii=False,
            )

            st.session_state[KEYS["style_level"]] = ""
            st.session_state[KEYS["style_lines"]] = ""
            st.session_state[KEYS["style_payload_json"]] = ""
        else:
            style_prefs = _extract_style_preferences_from_memo(memo_text)

            guardrail_res = evaluate_guardrails(
                body_text=body,
                evidence_text=ev,
                suggest_text=sg,
                root_mode=True,
            )
            style_res = check_style(
                text=body,
                max_sentence_len=80,
                preferred_tone=style_prefs.get("preferred_tone"),
                prefer_halfwidth_percent=bool(style_prefs.get("prefer_halfwidth_percent", False)),
                prefer_kagetsu_style=style_prefs.get("prefer_kagetsu_style"),
                prefer_kudasai=bool(style_prefs.get("prefer_kudasai", False)),
                prefer_dekiru=bool(style_prefs.get("prefer_dekiru", False)),
            )



            st.session_state[KEYS["diag_level"]] = str(getattr(guardrail_res, "level", "SAFE") or "SAFE")
            st.session_state[KEYS["diag_lines"]] = _format_diag_lines(guardrail_res)
            st.session_state[KEYS["diag_payload_json"]] = _serialize_guardrail_payload(guardrail_res)

            style_level = str(getattr(style_res, "level", "SAFE") or "SAFE")
            st.session_state[KEYS["style_lines"]] = _format_diag_lines(style_res)
            st.session_state[KEYS["style_payload_json"]] = _serialize_style_payload(style_res, body)
            if style_level != "RISK":
                style_items = _load_payload(st.session_state[KEYS["style_payload_json"]])
                if any(item.get("rank") == "CAUTION" for item in style_items):
                    style_level = "CAUTION"
            st.session_state[KEYS["style_level"]] = style_level

    # -------------------------
    # A. 内容の安全チェック
    # -------------------------
    level = str(st.session_state.get(KEYS["diag_level"], "") or "")
    diag_lines = str(st.session_state.get(KEYS["diag_lines"], "") or "")
    diag_items = _load_payload(st.session_state.get(KEYS["diag_payload_json"], ""))

    _render_badge("公開前の確認", level)

    if level:
        if level == "RISK":
            st.error("そのまま出す前に、根拠との照合が必要です。直せば前に進めます。")
        elif level == "CAUTION":
            st.warning("公開前に見直したい点があります。今のうちに確認すると安心です。")
        else:
            st.success("大きな問題は見つかっていません。公開前の最終確認がしやすい状態です。")

    if diag_items:
        _render_buyer_diagnosis_blocks(diag_items)


    # -------------------------
    # B. 表記・言い回しチェック
    # -------------------------
    style_level = str(st.session_state.get(KEYS["style_level"], "") or "")
    style_lines = str(st.session_state.get(KEYS["style_lines"], "") or "")
    style_items = _load_payload(st.session_state.get(KEYS["style_payload_json"], ""))

    if style_level or style_items or style_lines:
        st.divider()
        _render_badge("表記・言い回しの確認", style_level)

        if style_level == "CAUTION":
            st.info("内容の正しさとは別に、表記や言い回しを整えると、さらに読みやすくなります。")
        elif style_level == "SAFE":
            st.success("表記や言い回しにも大きな問題は見つかっていません。")

        if style_items:
            _render_buyer_diagnosis_blocks(style_items)
