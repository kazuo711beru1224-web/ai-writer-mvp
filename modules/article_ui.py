from __future__ import annotations

from typing import Dict, Set, List, Tuple, Any
from pathlib import Path
from datetime import datetime
import re

import streamlit as st

from modules.guardrails_core import evaluate_guardrails
from modules.diagnosis_templates import build_buyer_diagnosis
from openai_runtime import generate_markdown, OpenAIRuntimeError


# =========================
# ベル憲法：状態キーは固定
# =========================
KEYS: Dict[str, str] = {
    "main_kw": "article__main_kw",
    "sub_kw": "article__sub_kw",
    "theme": "article__theme",
    "memo": "article__memo",

    "consult_situation": "article__consult_situation",
    "consult_question": "article__consult_question",

    "evidence_url": "article__evidence_url",
    "evidence_title": "article__evidence_title",
    "evidence_facts": "article__evidence_facts",
    "evidence_points": "article__evidence_points",

    "evidence": "article__evidence_text",
    "suggest": "article__suggest_text",

    "last_text": "article__last_text",
    "snapshot": "article__snapshot",

    "proof_evidence": "article__proof_evidence",
    "proof_evidence_compact": "article__proof_evidence_compact",
    "proof_suggest": "article__proof_suggest",
    "proof_memo": "article__proof_memo",

    "copy_agree_risk": "article__copy_agree_risk",
    "copy_text": "article__copy_text",
    "copy_last_sig": "article__copy_last_sig",

    "save_message": "article__save_message",
}

PERSIST_KEYS: Set[str] = {
    KEYS["main_kw"],
    KEYS["sub_kw"],
    KEYS["theme"],
    KEYS["memo"],
    KEYS["consult_situation"],
    KEYS["consult_question"],
    KEYS["evidence_url"],
    KEYS["evidence_title"],
    KEYS["evidence_facts"],
    KEYS["evidence_points"],
    KEYS["evidence"],
    KEYS["suggest"],
    KEYS["last_text"],
    KEYS["snapshot"],
    KEYS["proof_evidence"],
    KEYS["proof_evidence_compact"],
    KEYS["proof_suggest"],
    KEYS["proof_memo"],
    KEYS["save_message"],
}

UI_FLAG_KEYS: Tuple[str, ...] = (
    "article__show_current_evidence",
    "article__show_current_suggest",
    "article__show_current_memo",
    "article__show_current_evidence_compact",
    "article__show_proof_evidence",
    "article__show_proof_evidence_compact",
    "article__show_proof_suggest",
    "article__show_proof_memo",
    "article__legacy_migrated",
    "article__show_legacy_evidence_help",
)

EVIDENCE_WARN_CHARS = 2500
EVIDENCE_HARD_CHARS = 8000
PREVIEW_CHARS_EVIDENCE = 700
PREVIEW_CHARS_SUGGEST = 300

YEAR_RE = re.compile(r"(19\d{2}|20\d{2})")
MONEY_RE = re.compile(r"(?<![0-9])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(?:円|万円|万|億円|億)")
PERCENT_RE = re.compile(r"(?<![0-9])(?:\d{1,3}(?:\.\d+)?)\s*(?:%|％)")
MONTH_RE = re.compile(r"(?<![0-9])(?:\d{1,2})\s*(?:ヶ月|か月|ヵ月)")
FORMULA_MARK_RE = re.compile(r"[＝=＋+×*－\-÷/]")
INVALID_FILE_CHARS_RE = re.compile(r'[\\/:*?"<>|]+')

PENSION_KW: Tuple[str, ...] = (
    "年金", "厚生年金", "国民年金", "老齢厚生年金", "老齢基礎年金",
    "在職老齢年金", "繰下げ受給", "繰上げ受給", "支給停止", "日本年金機構",
)
TAX_LAW_KW: Tuple[str, ...] = (
    "税", "税金", "相続税", "贈与税", "所得税", "法人税", "消費税", "住民税",
    "基礎控除", "控除", "税率", "申告", "期限", "延滞税", "加算税",
    "税制改正", "改正", "大綱", "施行", "令和", "年度",
    "法律", "法", "条文", "判例", "違法", "合法", "罰則", "規制",
)
MEDICAL_STRONG_KW: Tuple[str, ...] = (
    "病気", "症状", "診断", "治療", "薬", "副作用", "用量", "用法", "禁忌",
    "検査", "手術", "ワクチン", "感染", "ウイルス", "細菌",
    "メンタル", "うつ", "不眠", "発達", "ストレス",
    "がん", "糖尿病", "高血圧", "心筋梗塞", "脳梗塞",
    "クリニック", "病院", "医師", "看護師", "服薬", "処方",
)
MEDICAL_PHRASE_KW: Tuple[str, ...] = (
    "医療機関", "医療現場", "医療相談", "医療情報",
    "健康診断", "診療", "受診",
)
MEDICAL_NON_CONTEXT_KW: Tuple[str, ...] = (
    "医療法人", "税額控除", "相続税", "贈与税", "法人税", "所得税",
    "消費税", "住民税", "基礎控除", "控除", "税率", "申告", "期限",
)
CARE_KW: Tuple[str, ...] = (
    "介護", "要介護", "要支援", "介護保険", "ケアマネ", "認定調査",
    "介護サービス", "訪問介護", "デイサービス", "施設入所",
    "地域包括支援センター",
)
INSURANCE_KW: Tuple[str, ...] = (
    "保険", "生命保険", "医療保険", "がん保険", "自動車保険", "火災保険",
    "社会保険", "保障", "保険料", "免責", "給付金", "約款", "告知義務",
)

NEWS_RECENCY_KW: Tuple[str, ...] = (
    "昨日", "今日", "最新", "いま", "今", "今後", "進展", "現在", "速報",
    "何打数", "何安打", "試合結果", "ニュース", "戦争", "侵攻", "停戦",
    "事故", "転覆", "死傷者", "外交", "会談", "声明",
)
FORECAST_KW: Tuple[str, ...] = (
    "どうなる", "今後", "見通し", "予想", "可能性", "シナリオ", "将来",
)
ADVICE_KW: Tuple[str, ...] = (
    "どうすれば", "なりたい", "方法", "コツ", "始め方", "練習", "改善",
    "対策", "おすすめ", "習慣",
)
BACKGROUND_KW: Tuple[str, ...] = (
    "なぜ", "理由", "背景", "仕組み", "どういうこと", "要因", "比較",
    "違い", "わかりやすく", "解説",
)

QUESTION_TYPE_LABELS: Dict[str, str] = {
    "institutional": "制度・法律・お金系",
    "latest_news": "最新ニュース・時事系",
    "background": "背景解説・学習系",
    "advice": "助言・ハウツー系",
    "forecast": "未来予測・見通し系",
    "general": "一般整理系",
}

DETAIL_OPEN_KEY = "article__detail_open"


def _ensure_detail_open_initialized() -> None:
    if DETAIL_OPEN_KEY not in st.session_state:
        st.session_state[DETAIL_OPEN_KEY] = False


def _open_detail_settings() -> None:
    st.session_state[DETAIL_OPEN_KEY] = True


def _close_detail_settings() -> None:
    st.session_state[DETAIL_OPEN_KEY] = False


def _has_any_detail_values() -> bool:
    detail_keys = (
        KEYS["main_kw"], KEYS["sub_kw"], KEYS["theme"], KEYS["memo"],
        KEYS["evidence_url"], KEYS["evidence_title"], KEYS["evidence_facts"], KEYS["evidence_points"],
    )
    return any(not _is_blank(st.session_state.get(k, "")) for k in detail_keys)


def _should_expand_detail_settings() -> bool:
    return bool(st.session_state.get(DETAIL_OPEN_KEY, False)) or _has_any_detail_values()


def _sync_evidence_and_keep_detail_open() -> None:
    _open_detail_settings()
    _sync_evidence_text_from_parts()


def _keep_detail_open() -> None:
    _open_detail_settings()


def get_article_persist_keys() -> set[str]:
    return set(PERSIST_KEYS)


def _is_blank(s: object) -> bool:
    return (s is None) or (str(s).strip() == "")


def _ensure_ui_flags_initialized() -> None:
    for k in UI_FLAG_KEYS:
        if k not in st.session_state:
            st.session_state[k] = False


def _reset_ui_flags() -> None:
    for k in UI_FLAG_KEYS:
        st.session_state[k] = False


def _has_any_split_evidence_input() -> bool:
    return any(
        not _is_blank(st.session_state.get(k, ""))
        for k in (
            KEYS["evidence_url"],
            KEYS["evidence_title"],
            KEYS["evidence_facts"],
            KEYS["evidence_points"],
        )
    )


def _normalize_multiline(text: str) -> str:
    lines = [ln.strip() for ln in str(text or "").splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines).strip()


def build_evidence_text(url: str, title: str, facts: str, points: str) -> str:
    parts: List[str] = []

    u = str(url or "").strip()
    t = str(title or "").strip()
    f = _normalize_multiline(str(facts or ""))
    p = _normalize_multiline(str(points or ""))

    if u:
        parts.append(f"URL: {u}")
    if t:
        parts.append(f"資料名: {t}")
    if f:
        parts.append(f"重要数字・期限:\n{f}")
    if p:
        parts.append(f"要点:\n{p}")

    return "\n\n".join(parts).strip()


def _extract_urls(text: str) -> List[str]:
    return re.findall(r"https?://\S+", str(text or ""))


def _is_section_header_line(line: str) -> bool:
    s = str(line or "").strip()
    return s in ("重要数字・期限:", "要点:")


def _strip_section_prefix(line: str, prefix: str) -> str:
    s = str(line or "").strip()
    if s.startswith(prefix):
        return s[len(prefix):].strip()
    return s


def _parse_legacy_evidence_sections(text: str) -> Tuple[str, str, str, str]:
    url = ""
    title = ""
    facts_lines: List[str] = []
    points_lines: List[str] = []

    current_section = ""

    raw_lines = str(text or "").splitlines()
    for raw in raw_lines:
        line = str(raw or "").strip()
        if not line:
            continue

        if line.startswith("URL:"):
            current_section = "url"
            value = _strip_section_prefix(line, "URL:")
            if value:
                url = value
            continue

        if line.startswith("資料名:"):
            current_section = "title"
            value = _strip_section_prefix(line, "資料名:")
            if value:
                title = value
            continue

        if line.startswith("重要数字・期限:"):
            current_section = "facts"
            value = _strip_section_prefix(line, "重要数字・期限:")
            if value:
                facts_lines.append(value)
            continue

        if line.startswith("要点:"):
            current_section = "points"
            value = _strip_section_prefix(line, "要点:")
            if value:
                points_lines.append(value)
            continue

        if current_section == "facts":
            facts_lines.append(line)
        elif current_section == "points":
            points_lines.append(line)
        elif current_section == "title":
            title = f"{title} {line}".strip() if title else line
        elif current_section == "url":
            continue
        else:
            if (not title) and (not re.search(r"https?://", line)) and (not _is_section_header_line(line)):
                title = line

    facts = _normalize_multiline("\n".join(facts_lines))
    points = _normalize_multiline("\n".join(points_lines))
    return url.strip(), title.strip(), facts, points


def _guess_title_from_legacy_evidence(text: str) -> str:
    url, title, _, _ = _parse_legacy_evidence_sections(text)
    _ = url
    if title:
        return title

    lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
    for ln in lines:
        if ln.startswith("URL:"):
            continue
        if ln.startswith("資料名:"):
            continue
        if ln.startswith("重要数字・期限:"):
            continue
        if ln.startswith("要点:"):
            continue
        if re.search(r"https?://", ln):
            continue
        if len(ln) <= 100:
            return ln
    return ""


def _migrate_legacy_keys_once() -> None:
    migrated_flag = "article__legacy_migrated"
    if bool(st.session_state.get(migrated_flag, False)):
        return

    legacy_map = {
        KEYS["evidence"]: ("article__evidence", "article__evidence_memo"),
        KEYS["suggest"]: ("article__suggest", "article__keywords", "article__related_kw", "article__suggest_kw"),
        KEYS["proof_evidence"]: ("article__proof_evidence_text", "article__proof_ev"),
        KEYS["proof_suggest"]: ("article__proof_suggest_text", "article__proof_kw"),
        KEYS["proof_memo"]: ("article__proof_memo_text", "article__proof_note"),
    }

    for correct, legacy_candidates in legacy_map.items():
        cur = st.session_state.get(correct, "")
        if not _is_blank(cur):
            continue
        for lk in legacy_candidates:
            lv = st.session_state.get(lk, "")
            if not _is_blank(lv):
                st.session_state[correct] = str(lv)
                break

    if (not _has_any_split_evidence_input()) and (not _is_blank(st.session_state.get(KEYS["evidence"], ""))):
        legacy_ev = str(st.session_state.get(KEYS["evidence"], "") or "")
        parsed_url, parsed_title, parsed_facts, parsed_points = _parse_legacy_evidence_sections(legacy_ev)

        if parsed_url and _is_blank(st.session_state.get(KEYS["evidence_url"], "")):
            st.session_state[KEYS["evidence_url"]] = parsed_url
        if parsed_title and _is_blank(st.session_state.get(KEYS["evidence_title"], "")):
            st.session_state[KEYS["evidence_title"]] = parsed_title
        if parsed_facts and _is_blank(st.session_state.get(KEYS["evidence_facts"], "")):
            st.session_state[KEYS["evidence_facts"]] = parsed_facts
        if parsed_points and _is_blank(st.session_state.get(KEYS["evidence_points"], "")):
            st.session_state[KEYS["evidence_points"]] = parsed_points

        if _is_blank(st.session_state.get(KEYS["evidence_title"], "")):
            guessed_title = _guess_title_from_legacy_evidence(legacy_ev)
            if guessed_title:
                st.session_state[KEYS["evidence_title"]] = guessed_title

    st.session_state[migrated_flag] = True


def _ensure_keys_initialized() -> None:
    for k in KEYS.values():
        if k not in st.session_state:
            if k == KEYS["snapshot"]:
                st.session_state[k] = {}
            elif k in (KEYS["copy_agree_risk"],):
                st.session_state[k] = False
            else:
                st.session_state[k] = ""

    if st.session_state.get(KEYS["copy_last_sig"]) is None:
        st.session_state[KEYS["copy_last_sig"]] = ""

    _ensure_ui_flags_initialized()
    _ensure_detail_open_initialized()
    _migrate_legacy_keys_once()


def _get_effective_input_evidence_text() -> str:
    built = build_evidence_text(
        url=str(st.session_state.get(KEYS["evidence_url"], "") or ""),
        title=str(st.session_state.get(KEYS["evidence_title"], "") or ""),
        facts=str(st.session_state.get(KEYS["evidence_facts"], "") or ""),
        points=str(st.session_state.get(KEYS["evidence_points"], "") or ""),
    ).strip()

    if built:
        return built

    return str(st.session_state.get(KEYS["evidence"], "") or "").strip()


def _extract_key_fact_lines(text: str) -> List[str]:
    src = str(text or "")
    if not src.strip():
        return []

    raw_lines = [ln.strip() for ln in src.splitlines() if ln.strip()]
    noise_words = (
        "ホーム >", "ページの先頭", "別ウィンドウ", "Copyright", "政策について",
        "分野別の政策一覧", "関連リンク", "情報配信サービス", "ソーシャルメディア",
        "御意見募集", "国民参加の場", "Adobe Reader", "PDFファイル", "一覧",
        "著作権", "個人情報保護方針", "利用規約", "サイトの使い方", "RSSについて",
        "厚生労働省について", "統計情報・白書", "所管の法令等", "申請・募集・情報公開",
        "他府省", "所管の法人等", "図書館利用案内", "クローズアップ厚生労働省一覧",
        "情報配信サービスメルマガ登録", "WEBマガジン", "facebook", "Ｘ（旧Twitter）", "SNS一覧",
        "電話番号", "法人番号", "〒", "ページの先頭へ", "テーマ別に探す", "報道・広報",
    )

    filtered_lines: List[str] = []
    for ln in raw_lines:
        if any(noise in ln for noise in noise_words):
            continue
        if re.search(r"\[(?:\d+(?:\.\d+)?)(?:KB|MB)\]", ln):
            continue
        filtered_lines.append(ln)

    important_rows: List[str] = []

    def add_unique(bucket: List[str], value: str) -> None:
        v = re.sub(r"\s+", " ", str(value or "")).strip()
        if v and v not in bucket:
            bucket.append(v)

    for prefix in ("資料名:", "URL:"):
        for ln in filtered_lines:
            if ln.startswith(prefix):
                add_unique(important_rows, ln)

    priority_terms = (
        "要件", "条件", "期限", "基礎控除", "税率", "支給停止", "総報酬月額相当額",
        "標準賞与額", "4分の3", "2分の1", "300月", "65万円", "47万円", "28万円",
        "65歳", "70歳", "老齢厚生年金", "老齢基礎年金", "遺族厚生年金",
        "比較し、高い方", "差額", "合算", "受給要件",
    )

    for ln in filtered_lines:
        if any(term in ln for term in priority_terms):
            add_unique(important_rows, ln)

    if not important_rows:
        important_rows = filtered_lines[:20]

    return important_rows[:30]


def _get_generation_evidence_text() -> str:
    raw = _get_effective_input_evidence_text()
    compact_lines = _extract_key_fact_lines(raw)
    if compact_lines:
        return "\n".join(compact_lines).strip()
    return raw.strip()


def _sync_evidence_text_from_parts() -> None:
    built = build_evidence_text(
        url=str(st.session_state.get(KEYS["evidence_url"], "") or ""),
        title=str(st.session_state.get(KEYS["evidence_title"], "") or ""),
        facts=str(st.session_state.get(KEYS["evidence_facts"], "") or ""),
        points=str(st.session_state.get(KEYS["evidence_points"], "") or ""),
    ).strip()

    if built:
        st.session_state[KEYS["evidence"]] = built


def _take_snapshot() -> Dict[str, str]:
    _sync_evidence_text_from_parts()
    return {
        KEYS["main_kw"]: str(st.session_state.get(KEYS["main_kw"], "")),
        KEYS["sub_kw"]: str(st.session_state.get(KEYS["sub_kw"], "")),
        KEYS["theme"]: str(st.session_state.get(KEYS["theme"], "")),
        KEYS["memo"]: str(st.session_state.get(KEYS["memo"], "")),
        KEYS["consult_situation"]: str(st.session_state.get(KEYS["consult_situation"], "")),
        KEYS["consult_question"]: str(st.session_state.get(KEYS["consult_question"], "")),
        KEYS["evidence_url"]: str(st.session_state.get(KEYS["evidence_url"], "")),
        KEYS["evidence_title"]: str(st.session_state.get(KEYS["evidence_title"], "")),
        KEYS["evidence_facts"]: str(st.session_state.get(KEYS["evidence_facts"], "")),
        KEYS["evidence_points"]: str(st.session_state.get(KEYS["evidence_points"], "")),
        KEYS["evidence"]: str(st.session_state.get(KEYS["evidence"], "")),
        KEYS["suggest"]: str(st.session_state.get(KEYS["suggest"], "")),
    }


def _ensure_article_input_backup() -> None:
    if not isinstance(st.session_state.get("article__input_backup"), dict):
        st.session_state["article__input_backup"] = {}


def _backup_article_inputs() -> None:
    st.session_state["article__input_backup"] = {
        KEYS["main_kw"]: str(st.session_state.get(KEYS["main_kw"], "")),
        KEYS["sub_kw"]: str(st.session_state.get(KEYS["sub_kw"], "")),
        KEYS["theme"]: str(st.session_state.get(KEYS["theme"], "")),
        KEYS["memo"]: str(st.session_state.get(KEYS["memo"], "")),
        KEYS["consult_situation"]: str(st.session_state.get(KEYS["consult_situation"], "")),
        KEYS["consult_question"]: str(st.session_state.get(KEYS["consult_question"], "")),
        KEYS["evidence_url"]: str(st.session_state.get(KEYS["evidence_url"], "")),
        KEYS["evidence_title"]: str(st.session_state.get(KEYS["evidence_title"], "")),
        KEYS["evidence_facts"]: str(st.session_state.get(KEYS["evidence_facts"], "")),
        KEYS["evidence_points"]: str(st.session_state.get(KEYS["evidence_points"], "")),
        KEYS["evidence"]: str(st.session_state.get(KEYS["evidence"], "")),
        KEYS["suggest"]: str(st.session_state.get(KEYS["suggest"], "")),
    }


def _restore_article_inputs_from_backup() -> None:
    backup = st.session_state.get("article__input_backup", {}) or {}
    if not isinstance(backup, dict):
        return

    for k in (
        KEYS["main_kw"], KEYS["sub_kw"], KEYS["theme"], KEYS["memo"],
        KEYS["consult_situation"], KEYS["consult_question"],
        KEYS["evidence_url"], KEYS["evidence_title"], KEYS["evidence_facts"], KEYS["evidence_points"],
        KEYS["evidence"], KEYS["suggest"],
    ):
        current = st.session_state.get(k, None)
        if k not in st.session_state or _is_blank(current):
            value = backup.get(k, "")
            if not _is_blank(value):
                st.session_state[k] = str(value)


def _clear_article_input_backup() -> None:
    st.session_state["article__input_backup"] = {}


def _save_snapshot() -> None:
    st.session_state[KEYS["snapshot"]] = _take_snapshot()
    st.session_state[KEYS["save_message"]] = "今の状態を控えました。あとで戻したいときに使えます。"


def _reset_copy_state() -> None:
    st.session_state[KEYS["copy_text"]] = ""
    st.session_state[KEYS["copy_last_sig"]] = ""
    st.session_state[KEYS["copy_agree_risk"]] = False


def _set_copy_state_from_text(text: str) -> None:
    body = str(text or "")
    st.session_state[KEYS["copy_text"]] = body
    st.session_state[KEYS["copy_last_sig"]] = str(hash(body))
    st.session_state[KEYS["copy_agree_risk"]] = False


def _copy_last_text_to_copy_area() -> None:
    text = str(st.session_state.get(KEYS["last_text"], "") or "")
    if _is_blank(text):
        st.session_state[KEYS["save_message"]] = "編集欄に反映できる本文がありません。先に下書きを作ってください。"
        return
    _set_copy_state_from_text(text)
    st.session_state[KEYS["save_message"]] = "編集欄にAIが作った本文を入れました。"


def _clear_form_only() -> None:
    for k in (
        KEYS["main_kw"], KEYS["sub_kw"], KEYS["theme"], KEYS["memo"],
        KEYS["consult_situation"], KEYS["consult_question"],
        KEYS["evidence_url"], KEYS["evidence_title"], KEYS["evidence_facts"], KEYS["evidence_points"],
        KEYS["evidence"], KEYS["suggest"],
    ):
        st.session_state[k] = ""
    _clear_article_input_backup()
    _close_detail_settings()
    st.session_state[KEYS["save_message"]] = "入力欄を空にしました。最初から整理し直したいときに使えます。"


def _clear_generated_only() -> None:
    for k in (
        KEYS["last_text"], KEYS["consult_situation"], KEYS["consult_question"],
        KEYS["main_kw"], KEYS["sub_kw"], KEYS["theme"], KEYS["memo"],
        KEYS["evidence_url"], KEYS["evidence_title"], KEYS["evidence_facts"], KEYS["evidence_points"],
        KEYS["evidence"], KEYS["suggest"],
        KEYS["proof_evidence"], KEYS["proof_evidence_compact"], KEYS["proof_suggest"], KEYS["proof_memo"],
    ):
        st.session_state[k] = ""

    _clear_article_input_backup()
    st.session_state[KEYS["snapshot"]] = {}
    _reset_copy_state()
    _reset_ui_flags()

    st.session_state["api__status_code"] = ""
    st.session_state["api__status_message"] = ""
    st.session_state["api__status_detail"] = ""
    st.session_state["api__last_runtime_error"] = ""

    _close_detail_settings()
    st.session_state[KEYS["save_message"]] = "下書きと入力内容を消しました。新しい内容で始められます。"


def _restore_snapshot_fill_blanks() -> None:
    snap = st.session_state.get(KEYS["snapshot"], {}) or {}
    if not isinstance(snap, dict):
        st.session_state[KEYS["save_message"]] = "戻せる控えが見つかりませんでした。"
        return

    targets = (
        KEYS["main_kw"], KEYS["sub_kw"], KEYS["theme"], KEYS["memo"],
        KEYS["consult_situation"], KEYS["consult_question"],
        KEYS["evidence_url"], KEYS["evidence_title"], KEYS["evidence_facts"], KEYS["evidence_points"],
        KEYS["evidence"], KEYS["suggest"],
    )

    restored_any = False
    for k in targets:
        cur = st.session_state.get(k, "")
        if _is_blank(cur):
            val = snap.get(k, "")
            if not _is_blank(val):
                st.session_state[k] = str(val)
                restored_any = True

    _sync_evidence_text_from_parts()
    _reset_copy_state()

    if restored_any:
        st.session_state[KEYS["save_message"]] = "空欄だけ前の状態を戻しました。続きを進めやすくなります。"
    else:
        st.session_state[KEYS["save_message"]] = "戻せる空欄はありませんでした。"


def _topic_blob() -> str:
    return "\n".join([
        str(st.session_state.get(KEYS["main_kw"], "")).strip(),
        str(st.session_state.get(KEYS["sub_kw"], "")).strip(),
        str(st.session_state.get(KEYS["theme"], "")).strip(),
        str(st.session_state.get(KEYS["memo"], "")).strip(),
        str(_get_generation_evidence_text()).strip(),
        str(st.session_state.get(KEYS["suggest"], "")).strip(),
        str(st.session_state.get(KEYS["consult_situation"], "")).strip(),
        str(st.session_state.get(KEYS["consult_question"], "")).strip(),
    ]).lower()


def _contains_any(text: str, keywords: Tuple[str, ...]) -> bool:
    t = (text or "").lower()
    return any(k.lower() in t for k in keywords)


def _count_contains(text: str, keywords: Tuple[str, ...]) -> int:
    t = (text or "").lower()
    return sum(1 for k in keywords if k.lower() in t)


def _split_keywords(text: str) -> List[str]:
    raw = re.split(r"[,\n、/]+", str(text or ""))
    out: List[str] = []
    seen: set[str] = set()
    for item in raw:
        s = item.strip()
        if not s:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _clip_main_kw(text: str) -> str:
    parts = _split_keywords(text)
    if not parts:
        t = str(text or "").strip()
        return t[:40].strip()
    return " ".join(parts[:3]).strip()


def _detect_consult_domain(blob: str) -> str:
    if _contains_any(blob, PENSION_KW):
        return "pension"
    if _contains_any(blob, TAX_LAW_KW):
        return "tax_law"
    if _contains_any(blob, CARE_KW):
        return "care"
    if _contains_any(blob, INSURANCE_KW):
        return "insurance"
    if _count_contains(blob, MEDICAL_STRONG_KW) >= 1 or (
        _count_contains(blob, MEDICAL_PHRASE_KW) >= 1 and _count_contains(blob, MEDICAL_NON_CONTEXT_KW) == 0
    ):
        return "medical"
    return "general"


def _guess_main_kw_from_consult(situation: str, question: str) -> str:
    blob = f"{situation}\n{question}"
    domain = _detect_consult_domain(blob)

    if domain == "pension":
        if "遺族厚生年金" in blob:
            return "遺族厚生年金 老齢年金 併給"
        if "在職老齢年金" in blob:
            return "在職老齢年金 給与 賞与"
        return "年金 受給 働き方"
    if domain == "tax_law":
        if "相続税" in blob:
            return "相続税 基礎控除 申告期限"
        return "税金 制度 申告"
    if domain == "medical":
        return "症状 治療 注意点"
    if domain == "care":
        return "介護保険 要介護認定 サービス"
    if domain == "insurance":
        return "保険 保障内容 給付条件"
    return _clip_main_kw(question or situation)


def _guess_suggest_from_consult(situation: str, question: str) -> str:
    blob = f"{situation}\n{question}"
    domain = _detect_consult_domain(blob)

    if domain == "pension":
        if "遺族厚生年金" in blob:
            return ", ".join([
                "遺族厚生年金", "老齢年金 併給", "遺族年金 調整", "年金 選択", "年金 どちらが多い",
            ])
        if "在職老齢年金" in blob:
            return ", ".join([
                "在職老齢年金", "支給停止 条件", "給与 賞与 合算", "65万円基準", "47万円 28万円 旧基準",
            ])
        return ", ".join(["年金 受給", "支給条件", "基準額", "制度の違い", "確認先"])

    if domain == "tax_law":
        return ", ".join(["配偶者控除", "贈与税 110万円", "申告期限", "税率", "特例 条件"])
    if domain == "medical":
        return ", ".join(["副作用", "受診目安", "禁忌", "検査", "公式情報"])
    if domain == "care":
        return ", ".join(["要介護認定", "要支援", "ケアマネ", "介護サービス", "自己負担"])
    if domain == "insurance":
        return ", ".join(["免責", "給付金", "告知義務", "約款", "保険料 比較"])

    raw = _split_keywords(question)
    return ", ".join(raw[:6]).strip()


def _guess_theme_from_consult(situation: str, question: str) -> str:
    blob = f"{situation}\n{question}".strip()
    domain = _detect_consult_domain(blob)

    if domain == "pension":
        if "遺族厚生年金" in blob:
            return "遺族厚生年金と自分の老齢年金の関係を、併給と調整の考え方に絞って分かりやすく整理する"
        if "在職老齢年金" in blob:
            return "在職老齢年金の基準額と給与・賞与の合算方法を、今の基準と昔の基準に分けて分かりやすく整理する"
        return "働き方によって年金がどう変わるのかを、制度の違いも含めて分かりやすく整理する"

    if domain == "tax_law":
        return "税金の基本ルールや申告の注意点を、制度の違いとよくある誤解も含めて分かりやすく整理する"
    if domain == "medical":
        return "医療や健康に関する基本情報を、一般向けに分かりやすく整理しつつ、自己判断しすぎないための注意点も伝える"
    if domain == "care":
        return "介護保険や介護サービスの基本を、認定や費用、利用の流れも含めて分かりやすく整理する"
    if domain == "insurance":
        return "保険の保障内容や給付条件を、商品や制度の違いに注意しながら分かりやすく整理する"

    q = str(question or "").strip()
    if q:
        return f"{q} という疑問を、初心者にも分かりやすく整理する"
    return "相談内容を分かりやすく整理する"


def _guess_memo_from_consult(situation: str, question: str) -> str:
    blob = f"{situation}\n{question}".strip()
    domain = _detect_consult_domain(blob)

    bullets: List[str] = [
        "・一般の人にもわかりやすく説明する",
        "・専門用語はかみくだいて説明する",
        "・です・ます調に統一する",
    ]

    if domain == "pension":
        bullets += ["・制度の誤解を避ける", "・数字は根拠ベースで確認する"]
    elif domain == "tax_law":
        bullets += [
            "・制度名を正確に書く",
            "・金額、税率、期限は根拠ベースで確認する",
            "・改正や見直しは具体的に確認できる場合だけ触れる",
        ]
    elif domain == "medical":
        bullets += [
            "・個別の診断や治療を断定しない",
            "・一般情報として整理する",
            "・強い断定表現を避ける",
            "・受診や相談の目安を丁寧に示す",
        ]
    elif domain == "care":
        bullets += [
            "・家族が読んでも分かる言葉で説明する",
            "・制度の流れを順番に整理する",
            "・費用や負担割合は根拠ベースで確認する",
        ]
    elif domain == "insurance":
        bullets += [
            "・商品説明と制度説明を混同しない",
            "・約款や公式案内を前提にする",
            "・条件や例外を省略しすぎない",
        ]
    else:
        if any(k in blob for k in ("年金", "税", "法律", "医療", "介護", "保険", "申請", "届出")):
            bullets += [
                "・数字や制度の説明は、根拠ベースで確認する",
                "・誤解しやすい点や注意点を明確にする",
            ]

    q = str(question or "").strip()
    if q:
        bullets.append(f"・知りたいこと：{q}")

    return "\n".join(bullets).strip()


def _ensure_basic_fields_from_standard_inputs() -> None:
    situation = str(st.session_state.get(KEYS["consult_situation"], "") or "").strip()
    question = str(st.session_state.get(KEYS["consult_question"], "") or "").strip()
    suggest = str(st.session_state.get(KEYS["suggest"], "") or "").strip()

    if _is_blank(st.session_state.get(KEYS["main_kw"], "")):
        st.session_state[KEYS["main_kw"]] = _guess_main_kw_from_consult(situation, question)

    if _is_blank(st.session_state.get(KEYS["sub_kw"], "")):
        st.session_state[KEYS["sub_kw"]] = suggest or _guess_suggest_from_consult(situation, question)

    if _is_blank(st.session_state.get(KEYS["theme"], "")):
        st.session_state[KEYS["theme"]] = _guess_theme_from_consult(situation, question)

    if _is_blank(st.session_state.get(KEYS["memo"], "")):
        st.session_state[KEYS["memo"]] = _guess_memo_from_consult(situation, question)


def _apply_consult_to_article_inputs() -> None:
    situation = str(st.session_state.get(KEYS["consult_situation"], "") or "").strip()
    question = str(st.session_state.get(KEYS["consult_question"], "") or "").strip()

    if not situation and not question:
        st.session_state[KEYS["save_message"]] = "相談内容が空のため、整理できませんでした。"
        return

    _open_detail_settings()

    st.session_state[KEYS["main_kw"]] = _guess_main_kw_from_consult(situation, question)
    guessed_suggest = _guess_suggest_from_consult(situation, question)

    # suggest は標準入力側の widget のため、ここでは上書きしない。
    current_suggest = str(st.session_state.get(KEYS["suggest"], "") or "").strip()
    st.session_state[KEYS["sub_kw"]] = current_suggest or guessed_suggest
    st.session_state[KEYS["theme"]] = _guess_theme_from_consult(situation, question)
    st.session_state[KEYS["memo"]] = _guess_memo_from_consult(situation, question)

    if _is_blank(current_suggest):
        st.session_state[KEYS["save_message"]] = (
            "相談内容を整理して詳細設定に反映しました。"
            "検索キーワード欄は標準入力側のため自動では上書きしていません。必要なら手で追加してください。"
        )
    else:
        st.session_state[KEYS["save_message"]] = "相談内容を整理して、詳細設定に反映しました。必要なときだけ開いて確認してください。"


def _classify_question_type(blob: str) -> str:
    t = str(blob or "").lower().strip()

    if not t:
        return "general"

    if _contains_any(t, TAX_LAW_KW) or _contains_any(t, PENSION_KW) or _contains_any(t, CARE_KW) or _contains_any(t, INSURANCE_KW):
        return "institutional"

    if _contains_any(t, NEWS_RECENCY_KW):
        return "latest_news"

    if _contains_any(t, FORECAST_KW):
        return "forecast"

    if _contains_any(t, ADVICE_KW):
        return "advice"

    if _contains_any(t, BACKGROUND_KW):
        return "background"

    return "general"


def _get_question_type_label(qtype: str) -> str:
    return QUESTION_TYPE_LABELS.get(qtype, QUESTION_TYPE_LABELS["general"])


def _get_question_type_guidance(qtype: str) -> Tuple[str, str]:
    if qtype == "institutional":
        return (
            "この質問は、制度やお金に関する確認が必要です。",
            "公的機関や公式サイトの確認先を入れてから進めると、安全に整理できます。",
        )
    if qtype == "latest_news":
        return (
            "この質問は、最新情報の確認が必要です。",
            "昨日・今日・今後・進展などを含む内容は、参照日つきで確認する前提で扱います。",
        )
    if qtype == "background":
        return (
            "この質問は、背景や理由の整理が中心です。",
            "事実と考え方を分けて説明すると、分かりやすくなります。",
        )
    if qtype == "advice":
        return (
            "この質問は、助言ややり方の整理が中心です。",
            "個別診断ではなく、一般的な考え方や進め方としてまとめます。",
        )
    if qtype == "forecast":
        return (
            "この質問は、今後の見通しを含みます。",
            "断定ではなく、現時点の状況と考えられる流れを分けて扱うのが安全です。",
        )
    return (
        "この質問は、一般的な整理として扱います。",
        "必要に応じて、確認先や補足情報を足すと、さらに正確になります。",
    )


def _render_question_type_box() -> None:
    blob = "\n".join([
        str(st.session_state.get(KEYS["consult_situation"], "") or ""),
        str(st.session_state.get(KEYS["consult_question"], "") or ""),
        str(st.session_state.get(KEYS["suggest"], "") or ""),
    ]).strip()

    if _is_blank(blob):
        return

    qtype = _classify_question_type(blob)
    label = _get_question_type_label(qtype)
    title, body = _get_question_type_guidance(qtype)

    st.markdown("### この質問の扱い方")
    st.info(f"自動判定：{label}")
    st.write(title)
    st.caption(body)


def _current_question_type() -> str:
    blob = "\n".join([
        str(st.session_state.get(KEYS["consult_situation"], "") or ""),
        str(st.session_state.get(KEYS["consult_question"], "") or ""),
        str(st.session_state.get(KEYS["suggest"], "") or ""),
    ]).strip()
    return _classify_question_type(blob)


def _is_latest_news_topic() -> bool:
    return _current_question_type() == "latest_news"


def _is_forecast_topic() -> bool:
    return _current_question_type() == "forecast"


def _render_sensitive_notice_box() -> None:
    with st.expander("📋 AI送信前のご確認（重要）", expanded=False):
        st.markdown(
            "AIに送る前にご確認ください。  \n"
            "・個人情報、APIキー、パスワード、社外秘、未公開資料は入力しないでください。  \n"
            "・必要な要点だけを入れると、安全に使いやすくなります。  \n\n"
            "このアプリは、入力内容をAI処理のため外部APIへ送信します。  \n"
            "公開はされませんが、送信した内容は処理対象になります。"
        )


def _collect_sensitive_scan_text() -> str:
    """
    機密チェックは、いま画面で使っている入力だけを対象にする。
    legacy の evidence 全文まで巻き込むと、見えていない古い内容で誤判定しやすいため、
    分割入力欄 + 現在の有効根拠だけを見る。
    """
    effective_evidence = str(_get_effective_input_evidence_text() or "")
    parts = [
        str(st.session_state.get(KEYS["consult_situation"], "") or ""),
        str(st.session_state.get(KEYS["consult_question"], "") or ""),
        str(st.session_state.get(KEYS["main_kw"], "") or ""),
        str(st.session_state.get(KEYS["sub_kw"], "") or ""),
        str(st.session_state.get(KEYS["theme"], "") or ""),
        str(st.session_state.get(KEYS["memo"], "") or ""),
        str(st.session_state.get(KEYS["evidence_url"], "") or ""),
        str(st.session_state.get(KEYS["evidence_title"], "") or ""),
        str(st.session_state.get(KEYS["evidence_facts"], "") or ""),
        str(st.session_state.get(KEYS["evidence_points"], "") or ""),
        effective_evidence,
        str(st.session_state.get(KEYS["suggest"], "") or ""),
    ]
    return "\n".join(parts).strip()


def _detect_sensitive_data(text: str) -> dict:
    """
    本当に止めたい情報だけを検出する。
    - 公式URLや資料URLは危険扱いしない
    - 制度説明の数字・式・資料番号は危険扱いしない
    """
    raw_text = str(text or "")

    # URLは制度系の根拠として普通に入るため、非URL系パターンの前処理では除外する
    text_wo_urls = re.sub(r"https?://\S+", " ", raw_text)

    patterns = {
        "api_key": r"sk-[A-Za-z0-9_-]{20,}",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "phone": r"(?:\b0\d{1,4}-\d{1,4}-\d{3,4}\b)|(?:\b0\d{9,10}\b)",
        "postal": r"\b\d{3}-\d{4}\b",
        "password_like": r"(?:password|passwd|pw|pass)\s*[:=]\s*[^\s,;:]{3,}",
        "confidential_word": r"(社外秘|機密|未公開|社内限定|秘密情報|confidential)",
        "account_like": r"(口座番号|契約番号|カード番号|マイナンバー|会員ID)\s*[:：]?\s*[\dA-Za-z-]+",
        "customer_data": r"(顧客名簿|取引先一覧|売上明細|住所録|個人情報一覧)",
    }

    findings: Dict[str, List[str]] = {}
    risky_types: List[str] = []

    for key, pattern in patterns.items():
        target_text = raw_text if key == "api_key" else text_wo_urls
        matches = re.finditer(pattern, target_text, re.IGNORECASE)
        values: List[str] = []
        for m in matches:
            val = str(m.group()).strip()
            if not val:
                continue
            if val not in values:
                values.append(val)
        findings[key] = values
        if values:
            risky_types.append(key)

    return {
        "risky": bool(risky_types),
        "items": findings,
        "risky_types": risky_types,
    }


def _render_sensitive_block_message(sensitive_check: dict) -> None:
    _ = sensitive_check
    st.error("この内容には、AIに送らない方がよい情報が含まれている可能性があります。")
    st.write("次のような情報を消してから、もう一度お試しください。")
    st.write("・APIキー（sk-で始まる文字列）")
    st.write("・メールアドレス")
    st.write("・電話番号")
    st.write("・住所や郵便番号")
    st.write("・パスワードや契約情報")
    st.write("・『社外秘』『機密』『未公開』などの文言")
    st.caption("必要な要点だけを残し、個人情報や秘密情報を消してから進めてください。")


def _is_tax_or_law_topic() -> bool:
    blob = _topic_blob()
    return _contains_any(blob, TAX_LAW_KW)


def _is_medical_topic() -> bool:
    blob = _topic_blob()

    if _contains_any(blob, PENSION_KW) or _contains_any(blob, CARE_KW) or _contains_any(blob, INSURANCE_KW):
        return False

    if _count_contains(blob, MEDICAL_STRONG_KW) >= 1:
        return True

    if _count_contains(blob, MEDICAL_PHRASE_KW) >= 1 and _count_contains(blob, MEDICAL_NON_CONTEXT_KW) == 0:
        return True

    return False


def _is_pension_topic() -> bool:
    blob = _topic_blob()
    return _contains_any(blob, PENSION_KW)


def _is_pension_topic_strict() -> bool:
    blob = _topic_blob()
    pension_strong_kw = (
        "厚生年金", "国民年金", "老齢厚生年金", "老齢基礎年金",
        "在職老齢年金", "繰下げ受給", "繰上げ受給", "日本年金機構",
    )
    return _contains_any(blob, pension_strong_kw)


def _is_care_topic() -> bool:
    blob = _topic_blob()
    return _contains_any(blob, CARE_KW)


def _is_insurance_topic() -> bool:
    blob = _topic_blob()
    return _contains_any(blob, INSURANCE_KW)


def _is_high_risk_topic() -> bool:
    return (
        _is_tax_or_law_topic()
        or _is_medical_topic()
        or _is_pension_topic()
        or _is_care_topic()
        or _is_insurance_topic()
    )


def _extract_years(text: str) -> List[str]:
    if not text:
        return []
    years = YEAR_RE.findall(text)
    if not years:
        return []
    return sorted({y for y in years})


def _years_not_in_evidence(generated_text: str, evidence_text: str) -> List[str]:
    gen_years = set(_extract_years(generated_text))
    if not gen_years:
        return []
    ev_years = set(_extract_years(evidence_text))
    return sorted(gen_years - ev_years)


def _evidence_seems_url_only(evidence_text: str) -> bool:
    t = (evidence_text or "").strip()
    if not t:
        return True
    no_urls = re.sub(r"https?://\S+", "", t)
    no_urls = re.sub(r"\s+", "", no_urls)
    return len(no_urls) < 20


def _evidence_inputs_are_thin() -> bool:
    url = str(st.session_state.get(KEYS["evidence_url"], "") or "").strip()
    title = str(st.session_state.get(KEYS["evidence_title"], "") or "").strip()
    facts = str(st.session_state.get(KEYS["evidence_facts"], "") or "").strip()
    points = str(st.session_state.get(KEYS["evidence_points"], "") or "").strip()

    if url or title or facts or points:
        return False

    ev = str(_get_effective_input_evidence_text() or "").strip()
    return _is_blank(ev)


def _normalize_token(s: str) -> str:
    if not s:
        return ""
    t = s.strip()
    t = t.translate(str.maketrans({
        "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
        "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
        "％": "%", "，": ",", "．": ".",
        "＋": "+", "－": "-", "＝": "=",
    }))
    t = t.replace(" ", "").replace("\u3000", "")
    t = t.replace(",", "")
    return t


def _extract_numeric_claims(text: str) -> List[str]:
    if not text:
        return []

    raw: List[str] = []
    raw += MONEY_RE.findall(text)
    raw += PERCENT_RE.findall(text)
    raw += MONTH_RE.findall(text)

    seen: set[str] = set()
    out: List[str] = []
    for tok in raw:
        nt = _normalize_token(tok)
        if not nt:
            continue
        if nt in seen:
            continue
        seen.add(nt)
        out.append(nt)
    return out


def _numeric_claims_not_in_evidence(generated_text: str, evidence_text: str) -> List[str]:
    claims = _extract_numeric_claims(generated_text)
    if not claims:
        return []

    ev_norm = _normalize_token(evidence_text or "")
    if not ev_norm:
        return []

    missing: List[str] = []
    for c in claims:
        if c not in ev_norm:
            missing.append(c)
    return missing


def _count_formula_marks(text: str) -> int:
    if not text:
        return 0
    return len(FORMULA_MARK_RE.findall(text))


def _looks_like_formula_expression(text: str) -> bool:
    t = text or ""
    mark_count = _count_formula_marks(t)

    if mark_count >= 2:
        return True
    if "=" in t or "＝" in t:
        return True

    formula_like_patterns = (
        r"\d[\d,]*(?:円|万円|万|億円|億)?\s*[+\-×÷*/]\s*\d",
        r"[+\-×÷*/]\s*\d[\d,]*(?:円|万円|万|億円|億)?\s*[+\-×÷*/]",
    )
    return any(re.search(p, t) for p in formula_like_patterns)


def _preflight_block_generate_if_needed() -> List[str]:
    errors: List[str] = []

    if _is_high_risk_topic() and _evidence_inputs_are_thin():
        errors.append(
            "公的機関や公式サイトの確認先が入っていないため、まだ下書きは作れません。"
            "年金・税金・法律・医療・介護・保険など、数字や制度が関わる内容は、"
            "公式サイトのページや資料名を入れてから進んでください。"
        )

    if (_is_latest_news_topic() or _is_forecast_topic()) and _evidence_inputs_are_thin():
        errors.append(
            "最新ニュース・時事・今後の見通しを扱う内容は、確認先がないままでは下書きを作れません。"
            "まずは1本だけでよいので、報道機関や公的機関などの確認先URLとページ名を入れてください。"
        )

    return errors


def _post_generation_warnings(text: str) -> List[str]:
    warns: List[str] = []
    t = (text or "")
    evidence = str(st.session_state.get(KEYS["proof_evidence"], "") or "").strip()

    if _is_high_risk_topic():
        missing_years = _years_not_in_evidence(generated_text=t, evidence_text=evidence)
        if missing_years:
            warns.append(
                "本文に年号が出ていますが、根拠欄に同じ年号が見当たりません。"
                f"対象の年号：{', '.join(missing_years)}。"
                "根拠に書かれていない年号は、削除するか一般論に言い換えるのが安全です。"
            )

        if _evidence_seems_url_only(evidence):
            warns.append(
                "根拠欄がURL中心のため、本文中の数字や条件を自動照合しづらい状態です。"
                "数字チェックを強めたい場合は、公式ページから『数字を含む部分の抜粋（1〜3行）』も根拠欄に入れてください。"
            )
        else:
            missing_nums = _numeric_claims_not_in_evidence(generated_text=t, evidence_text=evidence)
            if missing_nums:
                show = missing_nums[:12]
                tail = "" if len(missing_nums) <= 12 else f" …ほか{len(missing_nums) - 12}件"
                warns.append(
                    "本文に『金額・税率・期限』などの数字が出ていますが、根拠欄に同じ表記が見当たりません。"
                    f"対象：{', '.join(show)}{tail}。"
                    "根拠にない数字は削除するか、数字を使わない一般論に言い換えるのが安全です。"
                )

    if _is_tax_or_law_topic() or _is_pension_topic_strict():
        future_words = ("予定", "予想", "見込", "議論", "検討", "見直し", "改正", "変更", "最新", "現在")
        if any(w in t for w in future_words) and ("令和" not in t and "年度" not in t and "以前" not in t):
            warns.append(
                "本文に『現在・最新・変更・改正』などの表現がありますが、時期ラベルが十分でない可能性があります。"
                "時期を根拠に沿って具体化するか、一般論に言い換えてください。"
            )

    if _is_tax_or_law_topic():
        suspicious_phrases = [
            "発表されました", "決定しました", "確定しました", "行われました",
        ]
        if any(s in t for s in suspicious_phrases):
            warns.append(
                "税・法律テーマで『発表・決定・確定・行われました』などの断定が出ています。"
                "根拠と一致しているか確認してください。"
            )

        if "110万円" in t and ("相続税" in t):
            warns.append(
                "本文に『110万円』と『相続税』が同居しています。"
                "110万円は贈与税側の文脈で出やすく、相続税の基礎控除と混同していないか確認してください。"
            )

        if _looks_like_formula_expression(t):
            warns.append(
                "本文に計算式や計算手順の可能性がある表記が見えます。"
                "税・法律テーマでは、式や計算方法が公式の案内と一致しているか確認してください。"
            )

    if _is_medical_topic():
        hard_assert = ("必ず治る", "確実に治る", "絶対", "100%", "副作用はありません", "診断します", "処方します")
        if any(w in t for w in hard_assert):
            warns.append(
                "医療テーマで強い断定（必ず・確実・絶対・100% など）が見えます。"
                "一般情報に留め、個別の診断・治療の断定は避けてください。"
            )

    return warns


def _cleanup_generated_text(text: str) -> str:
    t = str(text or "")

    replacements = {
        "适用": "適用",
        "减額": "減額",
        "减": "減",
        "现行": "現行",
        "旧基準について（令和4年3月以前の基準）": "昔の基準について（令和4年3月以前の基準）",
        "現行基準について（令和8年度の基準）": "今の基準について（令和8年度の基準）",
    }

    for old, new in replacements.items():
        t = t.replace(old, new)

    return t


def _has_any_visible_generation_material() -> bool:
    return any(
        not _is_blank(x) for x in (
            _get_generation_evidence_text(),
            _get_effective_input_evidence_text(),
            st.session_state.get(KEYS["suggest"], ""),
            st.session_state.get(KEYS["memo"], ""),
            st.session_state.get(KEYS["proof_evidence"], ""),
            st.session_state.get(KEYS["proof_evidence_compact"], ""),
            st.session_state.get(KEYS["proof_suggest"], ""),
            st.session_state.get(KEYS["proof_memo"], ""),
        )
    )

def _get_detail_help_text() -> Dict[str, str]:
    qtype = _current_question_type()

    if qtype == "latest_news":
        return {
            "url": "まずは1本だけ。試合速報や公式発表のページを入れてください。",
            "numbers": "打数、安打、得点、球数、失点など、今回の記事に関係する数字だけで十分です。",
            "memo": "このページで確認できた結果を、1〜2文で短く入れてください。",
            "example": (
                "URL: https://example.jp/game\n\n"
                "資料名: 試合速報\n\n"
                "重要数字・期限:\n"
                "・4打数1安打\n"
                "・チームは3対2で勝利\n\n"
                "要点:\n"
                "・この資料では打撃成績を確認できる\n"
                "・評価は足さず、結果だけを書く"
            ),
        }

    if qtype == "forecast":
        return {
            "url": "まずは1本だけ。官公庁、主要報道機関、公式発表のページを入れてください。",
            "numbers": "年号、発表日、会議名、声明の数字など、根拠にあるものだけに絞ってください。",
            "memo": "事実、政府見解、見通しを混ぜずに、確認できたことだけを1〜2文で入れてください。",
            "example": (
                "URL: https://example.jp/report\n\n"
                "資料名: 公式発表\n\n"
                "重要数字・期限:\n"
                "・2026年4月30日発表\n\n"
                "要点:\n"
                "・この資料では政府方針が確認できる\n"
                "・今後の断定は避ける"
            ),
        }

    if qtype == "institutional":
        return {
            "url": "まずは1本だけ。国税庁や e-Gov などの該当ページを入れてください。",
            "numbers": "期限、控除額、税率、割合など、今回の制度説明に必要な数字だけで十分です。",
            "memo": "このページでいちばん大事だったルールを、1〜2文で短く入れてください。",
            "example": (
                "URL: https://example.jp/page\n\n"
                "資料名: 国税庁 相続税の申告\n\n"
                "重要数字・期限:\n"
                "・申告期限：10か月以内\n"
                "・基礎控除：3,000万円＋600万円×法定相続人\n\n"
                "要点:\n"
                "・基礎控除は法定相続人の人数で決まる\n"
                "・申告前に人数確認が必要"
            ),
        }

    return {
        "url": "まずは1本だけ。このテーマでいちばん大事なページを入れてください。",
        "numbers": "今回の記事に必要な数字だけで十分です。",
        "memo": "このページでいちばん大事だったことを、短く1〜2文で入れてください。",
        "example": (
            "URL: https://example.jp/page\n\n"
            "資料名: 参考ページ\n\n"
            "重要数字・期限:\n"
            "・必要な数字だけ\n\n"
            "要点:\n"
            "・結論だけを短く書く"
        ),
    }

def _render_evidence_compact_guide(evidence_text: str) -> None:
    ev_len = len((evidence_text or "").strip())
    help_text = _get_detail_help_text()

    st.info(help_text["url"])
    st.caption("足りないときだけ2本目を足せば十分です。最初からたくさん入れなくて大丈夫です。")
    st.caption("迷ったら、本文の丸写しではなく『結論だけ』を短く残してください。")
    st.markdown("**短く残す例**")
    st.code(help_text["example"], language="text")

    if ev_len >= EVIDENCE_HARD_CHARS:
        st.error("根拠メモがかなり長いです。必要な数字と要点だけを残すと、下書きが安定しやすくなります。")
    elif ev_len >= EVIDENCE_WARN_CHARS:
        st.warning("根拠メモが長めです。結論だけ短くすると、かなり使いやすくなります。")


def _render_reference_hint_block() -> None:
    st.info("AIが確認先を選ぶ前に、自分で1本だけ入れたい場合は、下のような公式サイトから始めると探しやすいです。")

    if _is_pension_topic():
        st.markdown("**年金テーマで確認しやすい公式サイトの例**")
        st.markdown("- 日本年金機構")
        st.markdown("- 厚生労働省")
        st.markdown("- e-Gov法令検索")
        st.markdown("- 市区町村の公式サイト")
        st.caption("検索のヒント")
        st.code(
            "site:nenkin.go.jp 遺族厚生年金 併給調整\n"
            "site:nenkin.go.jp 在職老齢年金\n"
            "site:mhlw.go.jp 年金\n"
            "site:elaws.e-gov.go.jp 厚生年金保険法",
            language="text",
        )

    elif _is_tax_or_law_topic():
        st.markdown("**税金・法律テーマで確認しやすい公式サイトの例**")
        st.markdown("- 国税庁")
        st.markdown("- 財務省")
        st.markdown("- e-Gov法令検索")
        st.markdown("- 自治体の公式サイト")
        st.caption("検索のヒント")
        st.code(
            "site:nta.go.jp 相続税 申告期限\n"
            "site:nta.go.jp 贈与税 110万円\n"
            "site:nta.go.jp 所得税 控除\n"
            "site:elaws.e-gov.go.jp 相続税法",
            language="text",
        )

    elif _is_medical_topic():
        st.markdown("**医療・健康テーマで確認しやすい公式サイトの例**")
        st.markdown("- 厚生労働省")
        st.markdown("- PMDA")
        st.markdown("- 国立感染症関連機関")
        st.markdown("- 自治体の保健所や公式案内")
        st.markdown("- 学会の公式資料")

    elif _is_care_topic():
        st.markdown("**介護テーマで確認しやすい公式サイトの例**")
        st.markdown("- 厚生労働省")
        st.markdown("- 自治体の介護保険案内")
        st.markdown("- 地域包括支援センターの公式情報")
        st.markdown("- e-Gov法令検索")

    elif _is_insurance_topic():
        st.markdown("**保険テーマで確認しやすい公式サイトの例**")
        st.markdown("- 金融庁")
        st.markdown("- 各保険会社の公式案内")
        st.markdown("- 約款")
        st.markdown("- 自治体や公的制度の案内")
        st.markdown("- 業界団体の公式情報")

    elif _is_latest_news_topic() or _is_forecast_topic():
        st.markdown("**時事・今後の見通しテーマで確認しやすい情報源の例**")
        st.markdown("- 官公庁や政府の公式発表")
        st.markdown("- 主要報道機関の記事")
        st.markdown("- 防衛省・外務省・首相官邸などの公式資料")
        st.caption("検索のヒント")
        st.code(
            "site:mod.go.jp 防衛装備移転 三原則\n"
            "site:mofa.go.jp 日本 安全保障\n"
            "site:cas.go.jp 国家安全保障戦略\n"
            "site:nhk.or.jp 武器輸出 解禁 日本",
            language="text",
        )

    st.caption("これは確認先の候補です。ページ名と対象制度を見てから使ってください。")


def _render_theme_input_tips() -> None:
    help_text = _get_detail_help_text()
    st.markdown("**このテーマで入れるとよいものの例**")
    st.caption(f"参照URL：{help_text['url']}")
    st.caption(f"大事な数字：{help_text['numbers']}")
    st.caption(f"要点メモ：{help_text['memo']}")


def _build_prompt() -> str:
    _sync_evidence_text_from_parts()

    consult_situation = str(st.session_state.get(KEYS["consult_situation"], "") or "").strip()
    consult_question = str(st.session_state.get(KEYS["consult_question"], "") or "").strip()
    suggest = str(st.session_state.get(KEYS["suggest"], "") or "").strip()

    main_kw = str(st.session_state.get(KEYS["main_kw"], "") or "").strip()
    if not main_kw:
        main_kw = _guess_main_kw_from_consult(consult_situation, consult_question)

    sub_kw = str(st.session_state.get(KEYS["sub_kw"], "") or "").strip()
    if not sub_kw:
        sub_kw = suggest or _guess_suggest_from_consult(consult_situation, consult_question)

    theme = str(st.session_state.get(KEYS["theme"], "") or "").strip()
    if not theme:
        theme = _guess_theme_from_consult(consult_situation, consult_question)

    memo = str(st.session_state.get(KEYS["memo"], "") or "").strip()
    if not memo:
        memo = _guess_memo_from_consult(consult_situation, consult_question)

    evidence = str(_get_generation_evidence_text()).strip()

    p: list[str] = []
    p.append("あなたは日本語でSEO記事の下書きを作る編集者です。")
    p.append("専門用語はやさしい言葉に言い換え、初心者にもわかる説明にしてください。")
    p.append("説明書のように固くしすぎず、読者が『なるほど、そういうことか』と理解しやすい自然な文章にしてください。")
    p.append("誇張や断定を避け、根拠が不十分な内容は『〜とされています』など慎重に表現してください。")
    p.append("1文は60文字以内を目安にし、長い場合は2文に分けてください。")
    p.append("出力はMarkdown本文のみで、コードブロックは使わないでください。")
    p.append("")
    p.append("【最重要ルール】")
    p.append("1. 『生成に使う要点』に無い数字（年齢・年号・金額・期限・割合）は、本文にも見出しにも書かないでください。")
    p.append("2. 説明のための架空の数字例を作らないでください。")
    p.append("3. 『現在』『最新』『変更』『改正』などの表現は、要点に同じ時期ラベルや変更内容がある場合だけ使ってください。")
    p.append("4. 根拠に現在の基準と過去の基準が並んでいる場合は、時期ごとに分けて書いてください。混ぜて一般論にしないでください。")
    p.append("5. 質問に無い周辺論点へ広げないでください。")
    p.append("")

    if _is_pension_topic_strict():
        p.append("【年金テーマの追加ルール】")
        p.append("・年齢や時期は、要点にある数字だけを使ってください。")
        p.append("・年齢を一般化する場合は『高齢期』『年金受給中』『受給開始後』などを使ってください。")
        p.append("・在職老齢年金では、まず『総報酬月額相当額とは何か』『賞与はどう合算されるか』を説明してください。")
        p.append("・遺族厚生年金では、まず『併給か調整か』『高い方を優先するか』『差額があるか』を説明してください。")
        p.append("")

    if _is_latest_news_topic():
        p.append("【最新ニュース・時事テーマの追加ルール】")
        p.append("・根拠に書かれている内容だけを使ってください。")
        p.append("・事実、政府見解、解釈を分けて書いてください。")
        p.append("・参照日が必要な話題では『現時点』『最近』などを多用せず、根拠にある時期だけを使ってください。")
        p.append("・根拠に無い断定や、軍事・外交の強い言い切りは避けてください。")
        p.append("")

    if _is_forecast_topic():
        p.append("【今後の見通しテーマの追加ルール】")
        p.append("・未来を断定しないでください。")
        p.append("・『考えられる流れ』『可能性』として整理してください。")
        p.append("・事実、政府見解、推測を分けて書いてください。")
        p.append("")

    p.append("【この記事で最優先する読者の疑問】")
    p.append(consult_question if consult_question else "読者の疑問を優先して答えてください。")
    p.append("")
    p.append("【避けること】")
    p.append("・一般的な雑談に広げること")
    p.append("・制度一般の紹介だけで終わること")
    p.append("・根拠に無い年齢、金額、例示を書くこと")
    p.append("・最新ニュースや今後の見通しを、確認先なしで断定すること")
    p.append("・次のようなAIっぽい便利表現は、できるだけ使わないでください。「重要です」「必要です」「可能になります」「求められます」「これにより」「〜することができます」「と言えるでしょう」")
    p.append("・使う場合は、理由や具体例を添えてください。できるだけ読者が実際に取れる行動や目に浮かぶ具体的な表現に置き換えてください。")
    p.append("")
    p.append(f"【メインキーワード】{main_kw}")
    if sub_kw:
        p.append(f"【サブキーワード】{sub_kw}")
    if theme:
        p.append(f"【記事テーマ】{theme}")
    if memo:
        p.append(f"【追加メモ】{memo}")
    if consult_situation:
        p.append(f"【今の状況】{consult_situation}")
    if consult_question:
        p.append(f"【知りたいこと】{consult_question}")
    p.append("")
    p.append("【出力形式】Markdown（見出しは # / ## / ### を使う）")
    p.append("【文字数目安】約4000字（±15%まで許容）")
    p.append("")
    p.append("【AIに渡す根拠（優先参照）】")
    p.append(evidence if evidence else "（未入力）")
    p.append("")
    p.append("【読者が一緒に検索しそうな言葉】")
    p.append(suggest if suggest else "（未入力）")
    p.append("")
    p.append("では、記事本文を出力してください。")
    return "\n".join(p)


def _normalize_lines(text: str) -> List[str]:
    lines = [ln.strip() for ln in (text or "").splitlines()]
    seen: set[str] = set()
    out: List[str] = []
    for ln in lines:
        if not ln:
            continue
        if ln in seen:
            continue
        seen.add(ln)
        out.append(ln)
    return out


def _preview_text(text: str, limit: int) -> str:
    t = str(text or "").strip()
    if len(t) <= limit:
        return t
    return t[:limit] + "\n\n…（続きあり）"


def _render_large_text_preview(
    *,
    title: str,
    body: str,
    show_key: str,
    preview_chars: int,
    button_key_suffix: str = "",
) -> None:
    text = str(body or "").strip()

    st.markdown(f"**{title}**")
    if not text:
        st.caption("（未入力）")
        return

    st.caption(f"文字数：{len(text)}")

    if len(text) <= preview_chars:
        st.code(text, language="text")
        return

    st.code(_preview_text(text, preview_chars), language="text")

    suffix = f"__{button_key_suffix}" if button_key_suffix else ""
    toggle_key = f"{show_key}__toggle{suffix}"

    label = "全文を隠す" if bool(st.session_state.get(show_key, False)) else "全文を表示"
    if st.button(label, key=toggle_key):
        st.session_state[show_key] = not bool(st.session_state.get(show_key, False))

    if bool(st.session_state.get(show_key, False)):
        st.code(text, language="text")


def _strip_outer_code_fence(text: str) -> str:
    s = (text or "").strip()
    if not s.startswith("```"):
        return text or ""

    lines = s.splitlines()
    if len(lines) < 3:
        return text or ""

    first = lines[0].strip()
    last = lines[-1].strip()

    if not first.startswith("```"):
        return text or ""
    if last != "```":
        return text or ""

    inner = "\n".join(lines[1:-1]).strip("\n")
    return inner


def _render_buyer_diagnosis_blocks(res: Any) -> None:
    findings = getattr(res, "findings", None) or []
    if not findings:
        return

    for f in findings:
        rule_key = str(getattr(f, "code", "") or "")
        samples = getattr(f, "samples", None) or []
        matched_texts = [str(x) for x in samples if str(x).strip()]

        diag = build_buyer_diagnosis(rule_key=rule_key, matched_texts=matched_texts)

        st.markdown("---")
        st.markdown(f"**{diag['headline']}**")
        st.write(diag["lead"])
        st.markdown("**確認したい箇所**")
        st.write(f"・{diag['issue_label']}")
        st.write(diag["issue_text"])

        if diag["matched_texts"]:
            st.markdown("**本文の該当箇所**")
            for t in diag["matched_texts"]:
                st.markdown(f"- {t}")

        st.markdown("**理由**")
        st.write(diag["reason_text"])
        st.markdown("**直し方**")
        st.write(diag["fix_text"])


def _effective_guardrail_evidence() -> tuple[str, bool]:
    proof_ev = str(st.session_state.get(KEYS["proof_evidence"], "") or "").strip()
    current_ev = str(_get_effective_input_evidence_text()).strip()

    if not _is_blank(proof_ev):
        return proof_ev, False
    if not _is_blank(current_ev):
        return current_ev, True
    return "", False


def _render_guardrail_meter(*, body_text: str, evidence_text: str) -> str:
    res = evaluate_guardrails(body_text=body_text, evidence_text=evidence_text, root_mode=True)

    st.markdown("### 公開前の確認")
    badge = {"SAFE": "✅ SAFE", "CAUTION": "⚠️ CAUTION", "RISK": "🛑 RISK"}[res.level]
    st.write(badge)

    if res.level == "RISK":
        st.error("そのまま出す前に、確認先との照合が必要です。直せば前に進めます。")
    elif res.level == "CAUTION":
        st.warning("公開前に見直したい点があります。今のうちに確認すると安心です。")
    else:
        st.success("大きな問題は見つかっていません。公開前の最終確認がしやすい状態です。")

    _render_buyer_diagnosis_blocks(res)

    if getattr(res, "findings", None):
        with st.expander("確認の詳細（編集者向け）", expanded=(res.level != "SAFE")):
            for f in res.findings:
                st.write(f"- **{f.level} / {f.code}**：{f.message}")
                samples = getattr(f, "samples", None)
                if samples:
                    st.caption("例：" + " / ".join(samples))

    return res.level


def _derive_article_title(body_text: str) -> str:
    text = str(body_text or "").strip()

    for line in text.splitlines():
        ln = line.strip()
        if not ln:
            continue
        if ln.startswith("#"):
            title = ln.lstrip("#").strip()
            if title:
                return title

    theme = str(st.session_state.get(KEYS["theme"], "") or "").strip()
    if theme:
        return theme

    main_kw = str(st.session_state.get(KEYS["main_kw"], "") or "").strip()
    if main_kw:
        return main_kw

    return "保存した記事"


def _sanitize_filename_part(name: str, max_len: int = 60) -> str:
    t = str(name or "").strip()
    t = INVALID_FILE_CHARS_RE.sub("_", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = t.replace(".", "。")
    t = t.strip(" ._")
    if not t:
        t = "保存した記事"
    if len(t) > max_len:
        t = t[:max_len].rstrip(" ._")
    return t or "保存した記事"


def _save_article_file(*, outputs_dir: str, body_text: str) -> tuple[bool, str]:
    text = str(body_text or "").strip()
    if not text:
        return False, "保存する記事がありません。先に下書きを作ってください。"

    try:
        out_dir = Path(outputs_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        title = _sanitize_filename_part(_derive_article_title(text))
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"output_{stamp}_{title}.md"
        path = out_dir / filename

        path.write_text(text, encoding="utf-8")
        return True, "記事を保存しました。あとで見直したり戻したりできます。"
    except Exception:
        return False, "記事の保存に失敗しました。保存先フォルダや権限を確認してください。"


def _render_standard_inputs() -> None:
    st.markdown("## 📝 かんたん記事作成")
    st.write("まずは3つだけで大丈夫です。細かい設定はあとから確認できます。")

    st.markdown("### 1. 今の状況")
    st.text_area(
        "困っていることや背景を書いてください",
        height=120,
        key=KEYS["consult_situation"],
    )
    st.caption("例：63歳会社員。給与28万円と賞与があり、年金がどう変わるか知りたい。")

    st.markdown("### 2. 知りたいこと")
    st.text_area(
        "何を知りたいか、どう判断したいかを書いてください",
        height=90,
        key=KEYS["consult_question"],
    )
    st.caption("例：給与と賞与はどう合算されるか。今の基準額は何か。")

    st.markdown("### 3. 検索キーワード（任意）")
    st.caption("思いつく言葉があれば、2〜5個くらい入れてください。空でも進められます。")
    st.text_input(
        "例：在職老齢年金, 支給停止, 65万円基準",
        key=KEYS["suggest"],
    )

    _render_question_type_box()

    if _is_high_risk_topic():
        st.warning("制度や数字が関わるテーマです。必要に応じて、下の『詳細設定』で確認先を入れてから進めると安全です。")


def _render_detail_settings() -> None:
    with st.expander("🔧 詳細設定（必要なときだけ）", expanded=_should_expand_detail_settings()):
        st.caption("※通常は自動で十分です。精度を上げたいときだけ使ってください。")

        if st.button("入力内容から詳細設定を自動補助する", key="btn_apply_consult_into_detail", use_container_width=True):
            _apply_consult_to_article_inputs()

        _render_theme_input_tips()

        st.markdown("### 記事の芯（AIが下書きに使う内容）")

        main_kw = str(st.session_state.get(KEYS["main_kw"], "") or "").strip()
        if not main_kw:
            st.caption(f"メインキーワード候補：{_guess_main_kw_from_consult(str(st.session_state.get(KEYS['consult_situation'], '') or ''), str(st.session_state.get(KEYS['consult_question'], '') or ''))}")
        st.text_input("メインキーワード", key=KEYS["main_kw"], on_change=_keep_detail_open)

        sub_kw = str(st.session_state.get(KEYS["sub_kw"], "") or "").strip()
        if not sub_kw:
            st.caption("サブキーワード候補：検索キーワードの内容や相談文から自動で考えます。必要なら入れてください。")
        st.text_input("サブキーワード", key=KEYS["sub_kw"], on_change=_keep_detail_open)

        theme = str(st.session_state.get(KEYS["theme"], "") or "").strip()
        if not theme:
            st.caption(f"記事テーマ候補：{_guess_theme_from_consult(str(st.session_state.get(KEYS['consult_situation'], '') or ''), str(st.session_state.get(KEYS['consult_question'], '') or ''))}")
        st.text_input("記事テーマ", key=KEYS["theme"], on_change=_keep_detail_open)

        memo = str(st.session_state.get(KEYS["memo"], "") or "").strip()
        if not memo:
            st.caption("読者や書き方のメモは空でも進められます。必要なら補足してください。")
        st.text_area("読者や書き方のメモ", height=110, key=KEYS["memo"], on_change=_keep_detail_open)

        st.markdown("### 確認先")
        effective_evidence_text = _get_effective_input_evidence_text()
        _render_evidence_compact_guide(effective_evidence_text)

        if (_is_high_risk_topic() or _is_latest_news_topic() or _is_forecast_topic()) and _evidence_inputs_are_thin():
            _render_reference_hint_block()

        st.text_input(
            "参照URL（確認先）",
            key=KEYS["evidence_url"],
            on_change=_sync_evidence_and_keep_detail_open,
        )
        st.caption("まずは1本だけで大丈夫です。足りないときだけ後で追加してください。")

        st.text_input(
            "資料名・ページ名",
            key=KEYS["evidence_title"],
            on_change=_sync_evidence_and_keep_detail_open,
        )

        st.text_area(
            "大事な数字・期限",
            height=90,
            key=KEYS["evidence_facts"],
            on_change=_sync_evidence_and_keep_detail_open,
        )
        st.caption(_get_detail_help_text()["numbers"])

        st.text_area(
            "このページでいちばん大事だったこと",
            height=120,
            key=KEYS["evidence_points"],
            on_change=_sync_evidence_and_keep_detail_open,
        )
        st.caption(_get_detail_help_text()["memo"])

        split_mode_on = _has_any_split_evidence_input()
        legacy_evidence_text = str(st.session_state.get(KEYS["evidence"], "") or "").strip()
        if (not split_mode_on) and (not _is_blank(legacy_evidence_text)):
            st.info("以前の保存データの根拠が残っています。分割欄が空の間は、その根拠をそのまま使います。")
            st.code(legacy_evidence_text, language="text")

        current_generation_evidence = "\n".join(_normalize_lines(_get_generation_evidence_text()))
        if not _is_blank(current_generation_evidence):
            st.markdown("### AIが生成に使う要点（自動整理）")
            _render_large_text_preview(
                title="生成に使う要点",
                body=current_generation_evidence,
                show_key="article__show_current_evidence_compact",
                preview_chars=PREVIEW_CHARS_EVIDENCE,
                button_key_suffix="generation_compact",
            )


def _render_generation_summary(*, use_real_api: bool) -> None:
    proof_ev = str(st.session_state.get(KEYS["proof_evidence"], "") or "")
    proof_ev_compact = str(st.session_state.get(KEYS["proof_evidence_compact"], "") or "")
    used_sources = []
    used_points = []

    for ln in _normalize_lines(proof_ev):
        if ln.startswith("URL:") or ln.startswith("資料名:"):
            used_sources.append(ln)

    for ln in _normalize_lines(proof_ev_compact):
        if not ln.startswith("URL:") and not ln.startswith("資料名:"):
            used_points.append(ln)

    if use_real_api:
        st.success("✅ 下書きができました")
    else:
        st.success("✅ デモ下書きを表示しました。本番AIは使っていません。")

    if used_sources:
        st.markdown("### 📚 今回使った確認先")
        for item in used_sources[:6]:
            st.markdown(f"- {item}")

    if used_points:
        st.markdown("### 💡 今回使った要点")
        for item in used_points[:8]:
            st.markdown(f"- {item}")




def _render_edited_text_check_result(*, edited_text: str, evidence_text: str) -> str:
    st.markdown("### 🤖 編集した文章の確認結果")
    return _render_guardrail_meter(body_text=edited_text, evidence_text=evidence_text)

def render_article_ui(
    *,
    outputs_dir: str,
    logs_dir: str,
    openai_api_key: str,
    use_real_api: bool,
) -> None:
    _ = logs_dir
    _ensure_keys_initialized()
    _ensure_article_input_backup()
    _restore_article_inputs_from_backup()

    _render_sensitive_notice_box()

    msg = str(st.session_state.get(KEYS["save_message"], "") or "").strip()
    if msg:
        st.success(msg)
        st.session_state[KEYS["save_message"]] = ""

    top_c1, top_c2, top_c3 = st.columns([1, 1, 1])
    with top_c1:
        st.button("今の状態を控える", on_click=_save_snapshot, use_container_width=True, key="btn_article_save_snapshot")
    with top_c2:
        st.button("入力欄を空にする", on_click=_clear_form_only, use_container_width=True, key="btn_article_clear_form")
    with top_c3:
        st.button("下書きを消す", on_click=_clear_generated_only, use_container_width=True, key="btn_article_clear_generated")

    st.divider()

    _render_standard_inputs()
    _render_detail_settings()

    st.divider()
    st.write("入力した内容をもとに、記事の下書きを作ります。あとで見直せるので、まずは出してみる感覚で大丈夫です。")

    if st.button("✨ 下書きを作る", use_container_width=True, key="btn_article_generate"):
        situation = str(st.session_state.get(KEYS["consult_situation"], "") or "").strip()
        question = str(st.session_state.get(KEYS["consult_question"], "") or "").strip()

        if not situation or not question:
            st.warning("『今の状況』と『知りたいこと』を入れてください。")
            st.stop()

        _sync_evidence_text_from_parts()

        sensitive_text = _collect_sensitive_scan_text()
        sensitive_check = _detect_sensitive_data(sensitive_text)
        if sensitive_check["risky"]:
            _render_sensitive_block_message(sensitive_check)
            st.stop()

        pre_errors = _preflight_block_generate_if_needed()
        if pre_errors:
            for message in pre_errors:
                st.error(message)
            st.stop()

        prompt = _build_prompt()
        try:
            raw_text = generate_markdown(
                prompt=prompt,
                model="gpt-4o-mini",
                use_real_api=use_real_api,
                openai_api_key=openai_api_key,
                timeout_sec=180,
            )

            text = _strip_outer_code_fence(raw_text)
            text = _cleanup_generated_text(text)

            st.session_state["api__status_code"] = ""
            st.session_state["api__status_message"] = ""
            st.session_state["api__status_detail"] = ""
            st.session_state["api__last_runtime_error"] = ""

            st.session_state[KEYS["last_text"]] = text
            st.session_state[KEYS["proof_evidence"]] = str(_get_effective_input_evidence_text())
            st.session_state[KEYS["proof_evidence_compact"]] = str(_get_generation_evidence_text())
            st.session_state[KEYS["proof_suggest"]] = str(st.session_state.get(KEYS["suggest"], ""))
            st.session_state[KEYS["proof_memo"]] = str(st.session_state.get(KEYS["memo"], ""))

            _set_copy_state_from_text(text)
            _save_snapshot()

            warns = _post_generation_warnings(text)
            if warns:
                st.warning("公開前に見直したい点があります。確認先と照合すると安心です。")
                for warning_text in warns:
                    st.write(f"- {warning_text}")

        except OpenAIRuntimeError as e:
            st.session_state["api__status_code"] = str(getattr(e, "error_code", "") or "unknown_error")
            st.session_state["api__status_message"] = str(getattr(e, "user_message", "") or "AI下書きを始められませんでした。")
            st.session_state["api__status_detail"] = str(getattr(e, "detail", "") or str(e))
            st.session_state["api__last_runtime_error"] = str(e)

            st.error("本番のAI下書きを始められませんでした。")

            user_message = str(getattr(e, "user_message", "") or "").strip()
            if user_message:
                st.write(user_message)

            code = str(getattr(e, "error_code", "") or "").strip()

            if code == "api_key_missing":
                st.write("1. この画面の『OpenAI APIキー』欄を確認します。")
                st.write("2. 保存してあるAPIキーを貼り付けます。")
                st.write("3. アプリを開き直して、もう一度お試しください。")
            elif code == "auth_error":
                st.write("1. 保存してあるAPIキーと、この画面に貼った文字が同じか見比べます。")
                st.write("2. APIキーが見つからない場合は、新しいAPIキーを作って貼り付けます。")
                st.write("3. アプリを開き直して、もう一度お試しください。")
            elif code == "rate_limit_or_quota":
                st.write("1. OpenAIの請求画面で残高を確認します。")
                st.write("2. 少し時間をおいて、もう一度お試しください。")
            elif code in ("connection_error", "timeout"):
                st.write("1. 少し時間をおいて、もう一度お試しください。")
                st.write("2. アプリを閉じて、もう一度開きます。")
                st.write("3. それでも直らないときは、OpenAIの残高も確認してください。")
            elif code == "model_error":
                st.write("AIの呼び出し設定に問題がある可能性があります。")
                st.write("まずはアプリを開き直し、それでも直らなければ開発用の詳細を確認してください。")
            else:
                st.write("1. この画面の『OpenAI APIキー』欄に文字が入っているか確認します。")
                st.write("2. アプリを閉じて、もう一度開きます。")
                st.write("3. それでも直らないときは、OpenAIの残高を確認してください。")

            with st.expander("確認の詳細（開発用）", expanded=False):
                st.code(str(getattr(e, "detail", "") or str(e)), language="text")

    st.divider()
    st.markdown("### 📄 生成された記事")
    last_text = str(st.session_state.get(KEYS["last_text"], "") or "")

    if _is_blank(last_text):
        st.info("※まだ下書きは作られていません。上の『下書きを作る』を押してください。")
    else:
        _render_generation_summary(use_real_api=use_real_api)

        proof_evidence = str(st.session_state.get(KEYS["proof_evidence"], "") or "").strip()
        current_evidence = str(_get_effective_input_evidence_text()).strip()
        guardrail_evidence, used_current_fallback = _effective_guardrail_evidence()

        if used_current_fallback:
            st.info(
                "最後に下書きを作った時点の根拠が空のため、現在入力中の根拠を使って確認しています。"
                "この根拠を本文にも正式に反映したい場合は、必要に応じてもう一度下書きを作ってください。"
            )

        if _is_blank(proof_evidence) and not _is_blank(current_evidence):
            st.caption("※『今回使った確認先』は、現在入力中の根拠を使って表示している場合があります。")

        level = _render_guardrail_meter(body_text=last_text, evidence_text=guardrail_evidence)

        if level == "RISK":
            st.warning("AIが作った下書きには確認したい点があります。下の本文欄で直してから、もう一度AI確認をすると安全です。")

        st.markdown("### ✍ 公開前に自分で直す本文")
        st.caption("この欄で文章を直せます。編集前の本文を残したい場合は、先にWordなどへコピーして保管してください。")
        st.caption("直したあとは『この文章をAIに確認してもらう』で、気になる箇所をもう一度確認できます。")

        current_copy_text = str(st.session_state.get(KEYS["copy_text"], "") or "")
        current_copy_sig = str(st.session_state.get(KEYS["copy_last_sig"], "") or "")
        expected_sig = str(hash(last_text))

        if _is_blank(current_copy_text):
            _set_copy_state_from_text(last_text)
            current_copy_text = str(st.session_state.get(KEYS["copy_text"], "") or "")
            current_copy_sig = str(st.session_state.get(KEYS["copy_last_sig"], "") or "")

        if current_copy_sig != expected_sig:
            st.info("この欄の文章は、いまのAI下書きとは別に編集されています。続けて直して大丈夫です。")

        st.text_area("公開前に自分で直す本文", key=KEYS["copy_text"], height=420)

        action_col1, action_col2 = st.columns([1, 1])
        with action_col1:
            check_edited = st.button(
                "この文章をAIに確認してもらう",
                key="btn_article_check_edited_text",
                use_container_width=True,
            )
        with action_col2:
            if st.button("💾 この文章を保存する", key="btn_article_save_file", use_container_width=True):
                save_target = str(st.session_state.get(KEYS["copy_text"], "") or "").strip() or last_text
                ok, message = _save_article_file(outputs_dir=outputs_dir, body_text=save_target)
                if ok:
                    st.success(message)
                else:
                    st.error(message)

        with st.expander("AIが最初に作った文章を見る", expanded=False):
            st.caption("見比べたいときだけ開いてください。通常は上の本文欄だけで進められます。")
            st.code(last_text, language="markdown")

        if check_edited:
            edited_text = str(st.session_state.get(KEYS["copy_text"], "") or "").strip()
            if _is_blank(edited_text):
                st.warning("確認する文章が空です。上の本文欄に文章を入れてください。")
            else:
                edited_level = _render_edited_text_check_result(edited_text=edited_text, evidence_text=guardrail_evidence)
                if _is_latest_news_topic() and ("打撃" in edited_text or "打率" in edited_text or "出塁率" in edited_text or "安打" in edited_text):
                    proof_ev_lower = str(guardrail_evidence or "")
                    if ("打数" not in proof_ev_lower and "安打" not in proof_ev_lower and "打率" not in proof_ev_lower and "出塁率" not in proof_ev_lower):
                        st.warning(
                            "打撃まで書きたいときは、打数・安打・打率などが確認できる別の試合速報や成績ページを追加してください。"
                            "追加できない場合は、『この資料では打撃成績までは確認できません』と控えめに書くのが安全です。"
                        )
                if edited_level == "SAFE":
                    st.success("編集した文章は、大きな問題が見つかりにくい状態です。公開前に最終確認して保存できます。")

    if _has_any_visible_generation_material():
        with st.expander("🔎 AIが参考にしている内容", expanded=False):
            current_ev = str(_get_effective_input_evidence_text() or "")
            current_sg = str(st.session_state.get(KEYS["suggest"], "") or "")
            current_memo = str(st.session_state.get(KEYS["memo"], "") or "")

            if not _is_blank(current_ev) or not _is_blank(current_sg) or not _is_blank(current_memo):
                st.markdown("**① 次に下書きを作るときに使う内容**")

                if not _is_blank(current_ev):
                    _render_large_text_preview(
                        title="根拠",
                        body="\n".join(_normalize_lines(current_ev)),
                        show_key="article__show_current_evidence",
                        preview_chars=PREVIEW_CHARS_EVIDENCE,
                        button_key_suffix="transparency_current",
                    )

                current_compact = str(_get_generation_evidence_text() or "")
                if not _is_blank(current_compact):
                    _render_large_text_preview(
                        title="生成に使う要点（自動整理）",
                        body="\n".join(_normalize_lines(current_compact)),
                        show_key="article__show_current_evidence_compact",
                        preview_chars=PREVIEW_CHARS_EVIDENCE,
                        button_key_suffix="transparency_current_compact",
                    )

                if not _is_blank(current_sg):
                    _render_large_text_preview(
                        title="読者が一緒に検索しそうな言葉",
                        body="\n".join(_normalize_lines(current_sg)),
                        show_key="article__show_current_suggest",
                        preview_chars=PREVIEW_CHARS_SUGGEST,
                        button_key_suffix="transparency_current_suggest",
                    )

                if not _is_blank(current_memo):
                    _render_large_text_preview(
                        title="読者や書き方のメモ",
                        body="\n".join(_normalize_lines(current_memo)),
                        show_key="article__show_current_memo",
                        preview_chars=PREVIEW_CHARS_SUGGEST,
                        button_key_suffix="transparency_current_memo",
                    )

            proof_ev = str(st.session_state.get(KEYS["proof_evidence"], "") or "")
            proof_ev_compact = str(st.session_state.get(KEYS["proof_evidence_compact"], "") or "")
            proof_sg = str(st.session_state.get(KEYS["proof_suggest"], "") or "")
            proof_memo = str(st.session_state.get(KEYS["proof_memo"], "") or "")

            if not _is_blank(proof_ev) or not _is_blank(proof_ev_compact) or not _is_blank(proof_sg) or not _is_blank(proof_memo):
                st.markdown("**② この下書きを作ったときに使った内容（証拠として固定）**")

                if not _is_blank(proof_ev):
                    _render_large_text_preview(
                        title="根拠",
                        body="\n".join(_normalize_lines(proof_ev)),
                        show_key="article__show_proof_evidence",
                        preview_chars=PREVIEW_CHARS_EVIDENCE,
                        button_key_suffix="transparency_proof",
                    )

                if not _is_blank(proof_ev_compact):
                    _render_large_text_preview(
                        title="生成に使う要点（自動整理）",
                        body="\n".join(_normalize_lines(proof_ev_compact)),
                        show_key="article__show_proof_evidence_compact",
                        preview_chars=PREVIEW_CHARS_EVIDENCE,
                        button_key_suffix="transparency_proof_compact",
                    )

                if not _is_blank(proof_sg):
                    _render_large_text_preview(
                        title="読者が一緒に検索しそうな言葉",
                        body="\n".join(_normalize_lines(proof_sg)),
                        show_key="article__show_proof_suggest",
                        preview_chars=PREVIEW_CHARS_SUGGEST,
                        button_key_suffix="transparency_proof_suggest",
                    )

                if not _is_blank(proof_memo):
                    _render_large_text_preview(
                        title="読者や書き方のメモ",
                        body="\n".join(_normalize_lines(proof_memo)),
                        show_key="article__show_proof_memo",
                        preview_chars=PREVIEW_CHARS_SUGGEST,
                        button_key_suffix="transparency_proof_memo",
                    )
    _backup_article_inputs()