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

    "evidence_url": "article__evidence_url",
    "evidence_title": "article__evidence_title",
    "evidence_facts": "article__evidence_facts",
    "evidence_points": "article__evidence_points",

    "evidence": "article__evidence_text",
    "suggest": "article__suggest_text",

    "last_text": "article__last_text",

    "snapshot": "article__snapshot",

    "proof_evidence": "article__proof_evidence",
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
    KEYS["evidence_url"],
    KEYS["evidence_title"],
    KEYS["evidence_facts"],
    KEYS["evidence_points"],
    KEYS["evidence"],
    KEYS["suggest"],
    KEYS["last_text"],
    KEYS["snapshot"],
    KEYS["proof_evidence"],
    KEYS["proof_suggest"],
    KEYS["proof_memo"],
    KEYS["save_message"],
}

UI_FLAG_KEYS: Tuple[str, ...] = (
    "article__show_current_evidence",
    "article__show_current_suggest",
    "article__show_proof_evidence",
    "article__show_proof_suggest",
    "article__legacy_migrated",
    "article__show_legacy_evidence_help",
)

EVIDENCE_WARN_CHARS = 2500
EVIDENCE_HARD_CHARS = 8000
PREVIEW_CHARS_EVIDENCE = 700
PREVIEW_CHARS_SUGGEST = 300

REQUIRE_EVIDENCE_FOR_TAX_LAW = True

YEAR_RE = re.compile(r"(19\d{2}|20\d{2})")
MONEY_RE = re.compile(r"(?<![0-9])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(?:円|万円|万|億円|億)")
PERCENT_RE = re.compile(r"(?<![0-9])(?:\d{1,3}(?:\.\d+)?)\s*(?:%|％)")
MONTH_RE = re.compile(r"(?<![0-9])(?:\d{1,2})\s*(?:ヶ月|か月|ヵ月)")
FORMULA_MARK_RE = re.compile(r"[＝=＋+×*－\-÷/]")
INVALID_FILE_CHARS_RE = re.compile(r'[\\/:*?"<>|]+')


def get_article_persist_keys() -> set[str]:
    return set(PERSIST_KEYS)


def _is_blank(s: object) -> bool:
    return (s is None) or (str(s).strip() == "")


def _ensure_ui_flags_initialized() -> None:
    for k in UI_FLAG_KEYS:
        if k not in st.session_state:
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
    """
    旧形式の根拠テキストを、分割欄へ安全に分解する。
    - URL:
    - 資料名:
    - 重要数字・期限:
    - 要点:
    の各見出しを正しく扱う
    """
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
            # 資料名が複数行だった旧データを救済
            title = f"{title} {line}".strip() if title else line
        elif current_section == "url":
            # URLの次行に余計なものが来た場合は無視
            continue
        else:
            # ラベルなし旧データの救済
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

        # どうしても資料名が取れない旧データの最後の救済
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
        KEYS["evidence_url"]: str(st.session_state.get(KEYS["evidence_url"], "")),
        KEYS["evidence_title"]: str(st.session_state.get(KEYS["evidence_title"], "")),
        KEYS["evidence_facts"]: str(st.session_state.get(KEYS["evidence_facts"], "")),
        KEYS["evidence_points"]: str(st.session_state.get(KEYS["evidence_points"], "")),
        KEYS["evidence"]: str(st.session_state.get(KEYS["evidence"], "")),
        KEYS["suggest"]: str(st.session_state.get(KEYS["suggest"], "")),
    }


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
        st.session_state[KEYS["save_message"]] = "仕上げ用テキストに反映できる本文がありません。先に下書きを作ってください。"
        return

    _set_copy_state_from_text(text)
    st.session_state[KEYS["save_message"]] = "仕上げ用テキストを最新の本文にそろえました。"


def _clear_form_only() -> None:
    for k in (
        KEYS["main_kw"],
        KEYS["sub_kw"],
        KEYS["theme"],
        KEYS["memo"],
        KEYS["evidence_url"],
        KEYS["evidence_title"],
        KEYS["evidence_facts"],
        KEYS["evidence_points"],
        KEYS["evidence"],
        KEYS["suggest"],
    ):
        st.session_state[k] = ""
    st.session_state[KEYS["save_message"]] = "入力欄を空にしました。最初から整理し直したいときに使えます。"


def _clear_generated_only() -> None:
    st.session_state[KEYS["last_text"]] = ""
    _reset_copy_state()
    st.session_state[KEYS["save_message"]] = "下書きを消しました。入力欄はそのまま残っています。"


def _restore_snapshot_fill_blanks() -> None:
    snap = st.session_state.get(KEYS["snapshot"], {}) or {}
    if not isinstance(snap, dict):
        st.session_state[KEYS["save_message"]] = "戻せる控えが見つかりませんでした。"
        return

    targets = (
        KEYS["main_kw"],
        KEYS["sub_kw"],
        KEYS["theme"],
        KEYS["memo"],
        KEYS["evidence_url"],
        KEYS["evidence_title"],
        KEYS["evidence_facts"],
        KEYS["evidence_points"],
        KEYS["evidence"],
        KEYS["suggest"],
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
    main_kw = str(st.session_state.get(KEYS["main_kw"], "")).strip()
    sub_kw = str(st.session_state.get(KEYS["sub_kw"], "")).strip()
    theme = str(st.session_state.get(KEYS["theme"], "")).strip()
    memo = str(st.session_state.get(KEYS["memo"], "")).strip()
    evidence = str(_get_effective_input_evidence_text()).strip()
    suggest = str(st.session_state.get(KEYS["suggest"], "")).strip()
    return "\n".join([main_kw, sub_kw, theme, memo, evidence, suggest]).lower()


def _contains_any(text: str, keywords: Tuple[str, ...]) -> bool:
    t = (text or "").lower()
    return any(k.lower() in t for k in keywords)


def _count_contains(text: str, keywords: Tuple[str, ...]) -> int:
    t = (text or "").lower()
    return sum(1 for k in keywords if k.lower() in t)


def _is_tax_or_law_topic() -> bool:
    blob = _topic_blob()
    kw = (
        "税", "税金", "相続税", "贈与税", "所得税", "法人税", "消費税", "住民税",
        "基礎控除", "控除", "税率", "申告", "期限", "延滞税", "加算税",
        "税制改正", "改正", "大綱", "施行", "令和", "年度",
        "法律", "法", "条文", "判例", "違法", "合法", "罰則", "規制",
    )
    return _contains_any(blob, kw)


def _is_medical_topic() -> bool:
    blob = _topic_blob()

    strong_kw = (
        "病気", "症状", "診断", "治療", "薬", "副作用", "用量", "用法", "禁忌",
        "検査", "手術", "ワクチン", "感染", "ウイルス", "細菌",
        "メンタル", "うつ", "不眠", "発達", "ストレス", "不安",
        "がん", "糖尿病", "高血圧", "心筋梗塞", "脳梗塞",
        "クリニック", "病院", "医師", "看護師", "服薬", "処方",
    )

    medical_phrase_kw = (
        "医療機関", "医療現場", "医療相談", "医療情報", "医療保険",
        "健康診断", "診療", "受診",
    )

    non_medical_context_kw = (
        "医療法人", "税額控除", "相続税", "贈与税", "法人税", "所得税",
        "消費税", "住民税", "基礎控除", "控除", "税率", "申告", "期限",
    )

    if _count_contains(blob, strong_kw) >= 1:
        return True

    if _count_contains(blob, medical_phrase_kw) >= 1 and _count_contains(blob, non_medical_context_kw) == 0:
        return True

    return False


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
    if _is_tax_or_law_topic():
        ev = str(_get_effective_input_evidence_text()).strip()
        if REQUIRE_EVIDENCE_FOR_TAX_LAW and _is_blank(ev):
            errors.append(
                "税金・法律・制度改正に関わる可能性があるテーマです。根拠メモが未入力のため、誤情報を防ぐ目的で下書き作成を止めました。"
                "まずは一次情報URLや資料名を入れてください。"
            )
    return errors


def _post_generation_warnings(text: str) -> List[str]:
    warns: List[str] = []
    t = (text or "")
    evidence = str(st.session_state.get(KEYS["proof_evidence"], "") or "").strip()

    if _is_tax_or_law_topic():
        missing_years = _years_not_in_evidence(generated_text=t, evidence_text=evidence)
        if missing_years:
            warns.append(
                "本文に西暦年が出ていますが、根拠欄に同じ年号が見当たりません。"
                f"対象の年号：{', '.join(missing_years)}。"
                "根拠に書かれていない年号は、削除するか一般論に言い換えるのが安全です。"
            )

        if _evidence_seems_url_only(evidence):
            warns.append(
                "根拠欄がURL中心のため、本文中の数字（期限・金額・税率など）を自動照合しづらい状態です。"
                "数字チェックを強めたい場合は、一次情報から『数字を含む部分の抜粋（1〜3行）』も根拠欄に入れてください。"
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

        years_markers = ("2026", "2027", "2028", "令和", "年度")
        future_words = ("予定", "予想", "見込", "議論", "検討", "見直し", "改正", "変更")
        if any(y in t for y in years_markers) and any(w in t for w in future_words):
            warns.append(
                "本文に『年度・年号』と『予定・予想・議論・検討』などの未来推測が見えます。"
                "根拠に書かれていない場合は削除・言い換え（一般論化）が安全です。"
            )

        suspicious_phrases = [
            "発表されました",
            "決定しました",
            "確定しました",
            "行われました",
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
                "税・法律テーマでは、式や計算方法が一次情報と一致しているか確認してください。"
            )

    if _is_medical_topic():
        hard_assert = ("必ず治る", "確実に治る", "絶対", "100%", "副作用はありません", "診断します", "処方します")
        if any(w in t for w in hard_assert):
            warns.append(
                "医療テーマで強い断定（必ず・確実・絶対・100% など）が見えます。"
                "一般情報に留め、個別の診断・治療の断定は避けてください。"
            )

    return warns


def _build_prompt() -> str:
    _sync_evidence_text_from_parts()

    main_kw = str(st.session_state.get(KEYS["main_kw"], "")).strip()
    sub_kw = str(st.session_state.get(KEYS["sub_kw"], "")).strip()
    theme = str(st.session_state.get(KEYS["theme"], "")).strip()
    memo = str(st.session_state.get(KEYS["memo"], "")).strip()

    evidence = str(_get_effective_input_evidence_text()).strip()
    suggest = str(st.session_state.get(KEYS["suggest"], "")).strip()

    p: list[str] = []
    p.append("あなたは日本語でSEO記事の下書きを作る編集者です。")
    p.append("専門用語はやさしい言葉に言い換え、初心者にもわかる説明にしてください。")
    p.append("誇張や断定を避け、根拠が不十分な内容は『〜とされています』など慎重に表現してください。")
    p.append("1文は60文字以内を目安にし、長い場合は2文に分けてください。")
    p.append("医療の内容は一般情報として書き、個別の診断・治療を断定しないでください。")
    p.append("税金や法律の内容は、根拠欄にある制度名・年度・金額・税率・期限だけを使い、それ以外は推測で書かないでください。")
    p.append("根拠欄に存在しない金額・税率・期限・計算式（例：3,000万円、10%、10か月、〇〇＝〇〇＋…）を本文に書かないでください。")
    p.append("具体的な日付や年号の例は、根拠欄にそのまま書かれている場合だけ使用してください。")
    p.append("出力はMarkdown本文のみで、コードブロックは使わないでください。")
    p.append("")
    p.append(f"【メインキーワード】{main_kw}")
    if sub_kw:
        p.append(f"【サブキーワード】{sub_kw}")
    if theme:
        p.append(f"【記事テーマ】{theme}")
    if memo:
        p.append(f"【追加メモ（読者指定 / 書き方 / 外部指示）】{memo}")
    p.append("")
    p.append("【出力形式】Markdown（見出しは # / ## / ### を使う）")
    p.append("【文字数目安】約4000字（±15%まで許容）")
    p.append("")
    p.append("【AIに渡す根拠（優先参照）】")
    p.append(evidence if evidence else "（未入力）")
    p.append("")
    p.append("【読者が一緒に検索しそうな言葉（キーワード）】")
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


def _has_url_like(text: str) -> bool:
    t = (text or "")
    return ("http://" in t) or ("https://" in t)


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

        diag = build_buyer_diagnosis(
            rule_key=rule_key,
            matched_texts=matched_texts,
        )

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
        st.error("そのまま出す前に、根拠との照合が必要です。直せば前に進めます。")
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


def _render_evidence_compact_guide(evidence_text: str) -> None:
    ev_len = len((evidence_text or "").strip())

    st.info(
        "根拠メモは、長文をそのまま貼らなくても大丈夫です。"
        "『URL』『資料名』『大事な数字』『要点1〜3行』だけで十分です。"
    )

    with st.expander("短く残す例を見る", expanded=False):
        st.write("良い例")
        st.code(
            "URL: https://example.jp/page\n\n"
            "資料名: 国税庁 相続税の申告\n\n"
            "重要数字・期限:\n"
            "・申告期限：10か月以内\n"
            "・基礎控除：3,000万円＋600万円×法定相続人\n\n"
            "要点:\n"
            "・期限を過ぎると加算税や延滞税の可能性\n"
            "・詳細は一次情報で確認する",
            language="text",
        )
        st.write("避けたい例")
        st.code(
            "ページ全文を数千字そのまま貼る\n"
            "関係ない説明まで全部貼る\n"
            "URLだけ大量に並べる",
            language="text",
        )

    st.caption("迷ったら、本文の丸写しではなく『結論だけ』を短く残してください。")
    st.caption("要点メモは3行を超えるなら、さらに短くしてOKです。")

    if ev_len >= EVIDENCE_HARD_CHARS:
        st.error(
            "根拠メモがかなり長いです。"
            "表示や下書きづくりが重くなる原因になります。"
            "必要な数字と要点だけを残し、それ以外は削るのがおすすめです。"
        )
    elif ev_len >= EVIDENCE_WARN_CHARS:
        st.warning(
            "根拠メモが長めです。"
            "URL＋資料名＋数字＋要点だけにすると、かなり軽くなります。"
        )


def render_article_ui(
    *,
    outputs_dir: str,
    logs_dir: str,
    openai_api_key: str,
    use_real_api: bool,
) -> None:
    _ = logs_dir
    _ensure_keys_initialized()

    st.markdown("## 記事モード（SEOライティング）")
    st.write("ここでは、書きたい内容を整理しながら記事の下書きを作れます。")
    st.write("完璧に入れなくても大丈夫です。分かるところから埋めれば前に進めます。")
    st.caption("※自動で勝手に入力を戻さない設計です。復元や仕上げ用テキストの更新は、必要なときだけボタンで行います。")
    st.divider()

    msg = str(st.session_state.get(KEYS["save_message"], "") or "").strip()
    if msg:
        st.success(msg)
        st.session_state[KEYS["save_message"]] = ""

    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    with c1:
        st.button(
            "今の状態を控える",
            on_click=_save_snapshot,
            use_container_width=True,
            key="btn_article_save_snapshot",
        )
    with c2:
        st.button(
            "入力欄を空にする",
            on_click=_clear_form_only,
            use_container_width=True,
            key="btn_article_clear_form",
        )
    with c3:
        st.button(
            "下書きを消す",
            on_click=_clear_generated_only,
            use_container_width=True,
            key="btn_article_clear_generated",
        )
    with c4:
        st.button(
            "前の入力を空欄へ戻す",
            on_click=_restore_snapshot_fill_blanks,
            use_container_width=True,
            key="btn_article_restore_fill",
        )

    st.divider()

    st.text_input("いちばん伝えたい言葉（メインキーワード）", key=KEYS["main_kw"])
    st.caption("この記事の中心になる言葉です。検索されたいテーマを1つ入れてください。")
    st.caption("例：相続税 基礎控除 / 国産ウイスキー 歴史 / セールスライティング コツ")

    st.text_input("読者が一緒に調べそうな言葉（サブキーワード・カンマ区切り）", key=KEYS["sub_kw"])
    st.caption("読者が続けて検索しそうな言葉を入れると、記事の方向が整理しやすくなります。")
    st.caption("例：相続税 申告期限, 配偶者控除, 贈与税 110万円")

    st.text_input("この記事で伝えたいこと（主題・ヘッドラインの芯）", key=KEYS["theme"])
    st.caption("この記事を読んだ人に、何を持ち帰ってほしいかを短く入れてください。")
    st.caption("例：基礎控除の考え方を初心者にも分かるように整理する")

    st.text_area("読者や書き方のメモ（任意）", height=110, key=KEYS["memo"])
    st.caption("たとえば、誰に向けて、どんな言い方で書くかを短く残せます。外部企業から指定されたレギュレーションやトンマナがある場合も、ここに要点だけ入れてください。")
    st.caption("長い指示はそのまま全部貼らず、要点だけ短くまとめて入れてください。")
    st.caption("この欄に書いた内容は、下書き作成と公開前チェックの両方で参考にされます。")

    st.caption("例：初心者向け / やさしく説明 / 不安を減らす / 専門用語をかみくだく")
    st.caption("例：40代女性向け / です・ます調 / 誇張表現を避ける / 信頼感重視")
    st.caption("例：法人向け / かための文体 / 自社名は正式名称で統一 / 強い売り込みは避ける")

    st.markdown("**書き方ルールの書き方例**")
    st.caption("例：です・ます調に統一")
    st.caption("例：%は半角 / パーセントは半角")
    st.caption("例：か月に統一")
    st.caption("例：くださいに統一")
    st.caption("例：できるに統一")

    with st.expander("どんな書き方なら伝わるかを見る", expanded=False):
        st.code(
            "初心者向け / です・ます調に統一 / %は半角 / か月に統一 / くださいに統一 / できるに統一",
            language="text",
        )
        st.code(
            "法人向け / だ・である調に統一 / 誇張表現を避ける / 自社名は正式名称で統一",
            language="text",
        )
        st.caption("迷ったら、細かく全部書かなくても大丈夫です。守りたいルールだけ短く入れれば十分です。")
    

    st.markdown("### 🔎 根拠メモ（公開前に確認しやすくするための欄）")
    st.write("数字や制度の説明に不安があるときは、ここに根拠を短く残してください。")
    st.write("公開前に見直しやすくなり、本文の思い込みも減らしやすくなります。")

    effective_evidence_text = _get_effective_input_evidence_text()
    _render_evidence_compact_guide(effective_evidence_text)

    st.text_input(
        "参照URL（確認先）",
        key=KEYS["evidence_url"],
        on_change=_sync_evidence_text_from_parts,
    )
    st.caption("あとで見直せるように、元のページのURLを入れてください。")
    st.caption("例：https://www.nta.go.jp/taxes/shiraberu/taxanswer/sozoku/4152.htm")

    st.text_input(
        "資料名・ページ名",
        key=KEYS["evidence_title"],
        on_change=_sync_evidence_text_from_parts,
    )
    st.caption("どの資料を見たか分かるように、名前を短く残してください。")
    st.caption("例：国税庁 相続税の基礎控除")

    st.text_area(
        "大事な数字・期限",
        height=90,
        key=KEYS["evidence_facts"],
        on_change=_sync_evidence_text_from_parts,
    )
    st.caption("期限、金額、税率、年号など、あとで見直したいものだけを短く残してください。")
    st.caption("例：申告期限 10か月以内 / 基礎控除 3,000万円＋600万円×法定相続人")

    st.text_area(
        "要点メモ（1〜3行）",
        height=120,
        key=KEYS["evidence_points"],
        on_change=_sync_evidence_text_from_parts,
    )
    st.caption("その資料で特に大事だった点だけを短く残してください。")
    st.caption("例：期限を過ぎると加算税や延滞税の可能性がある / 詳細は一次情報で確認する")
    st.caption("3行を超えるなら、さらに短くしてOKです。本文の丸写しは不要です。")

    split_mode_on = _has_any_split_evidence_input()
    legacy_evidence_text = str(st.session_state.get(KEYS["evidence"], "") or "").strip()

    if (not split_mode_on) and (not _is_blank(legacy_evidence_text)):
        st.info(
            "以前の保存データの根拠が残っています。"
            "分割欄が空の間は、その根拠をそのまま使います。"
        )
        with st.expander("以前の根拠を見る", expanded=bool(st.session_state.get("article__show_legacy_evidence_help", False))):
            st.code(legacy_evidence_text, language="text")

    st.markdown("### 🔎 読者が一緒に検索しそうな言葉")
    st.caption("読者の迷いや疑問を先回りして整理するための欄です。思いつく言葉をいくつか入れてください。")
    st.caption("URLや資料名ではなく、検索で使う単語を書く欄です。")
    st.caption("例：相続税 基礎控除 / 相続税 申告期限 / 配偶者控除 / 贈与税 110万円")
    st.caption("例：SEO タイトル / 見出し / 読みやすい文章")

    suggest_text = st.text_area(
        "キーワード（単語）",
        height=120,
        key=KEYS["suggest"],
    )
    st.caption("ここはURLではなく、検索で使う単語を書く欄です。URLは上の『参照URL（確認先）』に入れてください。")
    st.caption("『No.4301』のような資料名やページ名は、上の『資料名・ページ名』に入れてください。")

    if _has_url_like(suggest_text):
        st.warning(
            "⚠ この欄は『単語（キーワード）』を書く場所です。URLは上の『参照URL（確認先）』に入れてください。",
            icon="⚠️",
        )

    st.markdown("#### 次に下書きを作るときに使う根拠")
    _render_large_text_preview(
        title="現在AIに渡す根拠",
        body="\n".join(_normalize_lines(_get_effective_input_evidence_text())),
        show_key="article__show_current_evidence",
        preview_chars=PREVIEW_CHARS_EVIDENCE,
        button_key_suffix="effective_preview",
    )

    is_taxlaw = _is_tax_or_law_topic()
    is_med = _is_medical_topic()
    ev_now = str(_get_effective_input_evidence_text()).strip()

    if is_taxlaw:
        if _is_blank(ev_now):
            st.warning(
                "🧯 税金・法律・制度改正の可能性があるテーマです。"
                "根拠メモが未入力だと誤情報リスクが上がります。まずは一次情報を短く入れてください。"
            )
        else:
            st.success(
                "✅ 根拠が入力されています。"
                "本文の『数字・年度・税率・期限』は、この根拠と必ず照合してください。"
            )

    suggest_years = _extract_years(suggest_text or "")
    if suggest_years:
        st.info(
            "ℹ キーワード欄に年号が含まれています。"
            "この欄は検索語の例であり、年号は根拠にある場合のみ本文に書かれます。"
        )

    if is_med:
        st.warning(
            "🩺 医療・健康の可能性があるテーマです。"
            "この記事は一般情報に留め、個別の診断・治療の断定は避けてください。"
            "重要な判断は公的機関や医療専門家の情報で確認してください。"
        )

    st.divider()

    st.write("入力した内容をもとに、記事の下書きを作ります。あとで見直せるので、まずは出してみる感覚で大丈夫です。")
    if st.button("記事の下書きを作る", use_container_width=True, key="btn_article_generate"):
        _sync_evidence_text_from_parts()

        pre_errors = _preflight_block_generate_if_needed()
        if pre_errors:
            for message in pre_errors:
                st.error(message)
        else:
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

                st.session_state[KEYS["last_text"]] = text
                st.session_state[KEYS["proof_evidence"]] = str(_get_effective_input_evidence_text())
                st.session_state[KEYS["proof_suggest"]] = str(st.session_state.get(KEYS["suggest"], ""))
                st.session_state[KEYS["proof_memo"]] = str(st.session_state.get(KEYS["memo"], ""))

                _set_copy_state_from_text(text)
                _save_snapshot()

                warns = _post_generation_warnings(text)
                if warns:
                    st.warning("公開前に見直したい点があります。根拠と照合すると安心です。")
                    for warning_text in warns:
                        st.write(f"- {warning_text}")
                else:
                    st.success("下書きを作りました。内容を確認しながら仕上げに進めます。")

            except OpenAIRuntimeError as e:
                st.error("❌ 下書き作成中に問題が起きました。")
                st.write("原因は画面に表示されたメッセージにあります（APIキーは表示しません）。")
                st.write(str(e))

    st.markdown("### 📄 生成された記事（プレビュー／仕上げ用）")
    last_text = str(st.session_state.get(KEYS["last_text"], "") or "")

    if _is_blank(last_text):
        st.info("※まだ下書きは作られていません。上の『記事の下書きを作る』を押してください。")
    else:
        proof_evidence = str(st.session_state.get(KEYS["proof_evidence"], "") or "").strip()
        current_evidence = str(_get_effective_input_evidence_text()).strip()
        guardrail_evidence, used_current_fallback = _effective_guardrail_evidence()

        if used_current_fallback:
            st.info(
                "最後に下書きを作った時点の根拠が空のため、現在入力中の根拠を使って確認しています。"
                "この根拠を本文にも正式に反映したい場合は、必要に応じてもう一度下書きを作ってください。"
            )

        if _is_blank(proof_evidence) and not _is_blank(current_evidence):
            st.caption("※『②この下書きを作ったときに使った内容』は空ですが、『①次に下書きを作るときに使う内容』には根拠があります。")

        level = _render_guardrail_meter(body_text=last_text, evidence_text=guardrail_evidence)

        save_col1, save_col2 = st.columns([2, 1])
        with save_col1:
            st.caption("内容に問題がなければ、記事を保存してあとで見直せます。")
        with save_col2:
            if st.button("記事を保存する", key="btn_article_save_file", use_container_width=True):
                ok, message = _save_article_file(outputs_dir=outputs_dir, body_text=last_text)
                if ok:
                    st.success(message)
                else:
                    st.error(message)

        st.markdown("#### プレビュー（見直し用）")
        st.code(last_text, language="markdown")

        st.markdown("#### 仕上げ用テキスト")
        copy_col1, copy_col2 = st.columns([2, 1])
        with copy_col1:
            st.caption("公開前の見直しや、外部エディタでの仕上げに使える本文です。必要なときだけ最新にそろえられます。")
        with copy_col2:
            st.button(
                "仕上げ用テキストを最新にする",
                on_click=_copy_last_text_to_copy_area,
                use_container_width=True,
                key="btn_article_refresh_copy",
            )

        copy_disabled = False
        if level == "RISK":
            st.error("⚠️ このまま使う前に、数字・年号・期限・税率などを一次情報と照合してください。直せば前に進めます。")
            st.checkbox(
                "注意事項を理解しました。根拠と照合した上で自己責任で使います。",
                key=KEYS["copy_agree_risk"],
            )
            copy_disabled = not bool(st.session_state.get(KEYS["copy_agree_risk"], False))
            if copy_disabled:
                st.info("チェックを入れると、仕上げ用テキストを編集できます。")

        current_copy_text = str(st.session_state.get(KEYS["copy_text"], "") or "")
        current_copy_sig = str(st.session_state.get(KEYS["copy_last_sig"], "") or "")
        expected_sig = str(hash(last_text))

        if _is_blank(current_copy_text) or current_copy_sig != expected_sig:
            st.info("仕上げ用テキストが最新本文と一致していない場合は、『仕上げ用テキストを最新にする』を押してください。")

        st.text_area(
            "仕上げ用テキスト",
            key=KEYS["copy_text"],
            height=380,
            disabled=copy_disabled,
        )

    st.markdown("### 🔎 AIが参考にしている内容")

    st.markdown("**① 次に下書きを作るときに使う内容**")
    current_ev = str(_get_effective_input_evidence_text() or "")
    current_sg = str(st.session_state.get(KEYS["suggest"], "") or "")

    _render_large_text_preview(
        title="根拠",
        body="\n".join(_normalize_lines(current_ev)),
        show_key="article__show_current_evidence",
        preview_chars=PREVIEW_CHARS_EVIDENCE,
        button_key_suffix="transparency_current",
    )

    _render_large_text_preview(
        title="読者が一緒に検索しそうな言葉",
        body="\n".join(_normalize_lines(current_sg)),
        show_key="article__show_current_suggest",
        preview_chars=PREVIEW_CHARS_SUGGEST,
        button_key_suffix="transparency_current_suggest",
    )

    st.markdown("**② この下書きを作ったときに使った内容（証拠として固定）**")
    proof_ev = str(st.session_state.get(KEYS["proof_evidence"], "") or "")
    proof_sg = str(st.session_state.get(KEYS["proof_suggest"], "") or "")

    _render_large_text_preview(
        title="根拠",
        body="\n".join(_normalize_lines(proof_ev)),
        show_key="article__show_proof_evidence",
        preview_chars=PREVIEW_CHARS_EVIDENCE,
        button_key_suffix="transparency_proof",
    )

    _render_large_text_preview(
        title="読者が一緒に検索しそうな言葉",
        body="\n".join(_normalize_lines(proof_sg)),
        show_key="article__show_proof_suggest",
        preview_chars=PREVIEW_CHARS_SUGGEST,
        button_key_suffix="transparency_proof_suggest",
    )
