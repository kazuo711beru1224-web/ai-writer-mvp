from __future__ import annotations

from typing import Dict, Set, List, Tuple, Any
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import html
import json
import re

import streamlit as st
import streamlit.components.v1 as components

from modules.guardrails_core import evaluate_guardrails
from modules.diagnosis_templates import build_buyer_diagnosis
from modules.quality_ui import KEYS as _QUALITY_KEYS, QUALITY_MENU_LABEL
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

    "tone_reg": "article__tone_regulation",
    "plan_result": "article__plan_result",

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
    KEYS["tone_reg"],
    KEYS["plan_result"],
    KEYS["save_message"],
}

# ページ（旧・ステップ）移動でWidgetが表示されなくなっても入力内容が
# 消えたように見えないよう退避しておく、画面表示専用のシャドウState。
# ファイルへの保存対象（PERSIST_KEYS）にも自動保存ダンプにも含めない、
# セッション内だけの安全網。
# evidence_url/evidence_title/evidence_facts/evidence_pointsは対象外。
# backup/shadowがarticle__form_dataより古い値を持っていると、復元順序
# （backup→shadow→form_data、いずれも「今の値が空のときだけ埋める」）
# の都合でform_dataより古い値が先に埋まって勝ってしまう競合があったため、
# この4項目はform_data（_seed_widget_from_form_data_if_missing /
# _reseed_blank_widget_from_form_data / on_change）だけを正本にする。
SHADOW_KEYS: Dict[str, str] = {
    KEYS["consult_situation"]: "article_shadow__consult_situation",
    KEYS["consult_question"]: "article_shadow__consult_question",
    KEYS["suggest"]: "article_shadow__search_keyword",
    KEYS["tone_reg"]: "article_shadow__tone_reg",
    KEYS["main_kw"]: "article_shadow__main_kw",
    KEYS["sub_kw"]: "article_shadow__sub_kw",
    KEYS["theme"]: "article_shadow__theme",
    KEYS["memo"]: "article_shadow__memo",
}

ARTICLE_AUTOSAVE_FILENAME = "autosave_state.json"

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
    "article__show_reference_hint",
    "article__show_detail_assist_hint",
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

PROMOTION_KW: Tuple[str, ...] = (
    "店頭", "POP", "販促", "売り場", "商品紹介", "来店客", "来店客数", "来店",
    "コンビニ", "おにぎり", "弁当", "パン", "飲み物", "お客様", "ドラッグストア",
)

NEWS_RECENCY_STRONG_KW: Tuple[str, ...] = (
    "速報", "ニュース", "事故", "転覆", "死傷者", "戦争", "侵攻", "停戦",
    "声明", "会談", "外交", "選挙", "災害", "政治", "政権", "政府", "法改正",
)

QUESTION_TYPE_LABELS: Dict[str, str] = {
    "institutional": "制度・法律・お金系",
    "latest_news": "最新ニュース・時事系",
    "background": "背景解説・学習系",
    "advice": "助言・ハウツー系",
    "forecast": "未来予測・見通し系",
    "general": "一般整理系",
}

# 確認先の探し方ヒントの開閉状態。_evidence_inputs_are_thin()に連動させると
# フォーム送信のたびに表示/非表示が切り替わり高さが変わってしまうため、
# ここだけで完結する独立フラグで管理する。
REFERENCE_HINT_OPEN_KEY = "article__show_reference_hint"

# 記事モードのページ区切り型UI（長い1ページ型のスクロールをやめ、
# 1画面あたり数項目だけを表示する6ページ構成で「前へ」「次へ」により
# 表示区画を切り替えるための現在地）。値は入力保存の対象ではなく画面表示
# だけの状態なので、PERSIST_KEYSには含めない（get_article_persist_keys参照）。
ARTICLE_ACTIVE_PAGE_KEY = "article__active_page"
ARTICLE_PAGE_BASIC = 1       # かんたん記事作成
ARTICLE_PAGE_KEYWORD = 2     # 検索キーワード・詳細設定入口
ARTICLE_PAGE_OFFICIAL = 3    # 公式情報・確認先
ARTICLE_PAGE_STYLE = 4       # 書き方の希望
ARTICLE_PAGE_DRAFT = 5       # 下書き作成
ARTICLE_PAGE_PRECHECK = 6    # 下書きの確認・文章チェックへ
ARTICLE_PAGE_COUNT = 6
ARTICLE_PAGE_LABELS: Dict[int, str] = {
    ARTICLE_PAGE_BASIC: "基本入力",
    ARTICLE_PAGE_KEYWORD: "キーワード",
    ARTICLE_PAGE_OFFICIAL: "公式情報",
    ARTICLE_PAGE_STYLE: "書き方",
    ARTICLE_PAGE_DRAFT: "下書き作成",
    ARTICLE_PAGE_PRECHECK: "下書きの確認",
}

# シャドウStateからの復元(_restore_shadow_state_to_blanks)を、実際に
# ページが切り替わった直後だけ行うための「最後に復元した時点のページ番号」。
# 画面表示専用の値なので、PERSIST_KEYSには含めない。
ARTICLE_SHADOW_RESTORED_PAGE_KEY = "article__shadow_restored_page"


def _ensure_active_page_initialized() -> None:
    if ARTICLE_ACTIVE_PAGE_KEY not in st.session_state:
        st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = ARTICLE_PAGE_BASIC


def _go_to_page(page: int) -> None:
    # ページを切り替える前に、今表示している入力内容をシャドウStateへ
    # 退避しておく（切り替え後に表示されない欄の値が消えて見えないように）。
    _backup_shadow_state()
    # article__form_dataが正本のフィールドも、切り替え前に現在のwidget値を
    # 反映しておく（on_changeの保険。既にform_data化済みのconsult_situation/
    # consult_question/copy_textが、ページ移動で消えないようにするため）。
    _sync_form_data_stage1_from_widgets()
    # article__inputs_saved（第1段階の12項目）も同様に、切り替え前の
    # widget値を反映する。ただし対象は「今離れようとしているページ」の
    # 項目だけに限定する（12項目一括同期は非表示ページの空文字で正しい
    # 値を踏み潰す危険があるため、ARTICLE_INPUTS_SAVED_FIELDS_BY_PAGE経由で
    # 現在ページ分だけを同期する）。
    _sync_current_page_inputs_saved_from_widgets()
    st.session_state[ARTICLE_ACTIVE_PAGE_KEY] = page


def _render_page_indicator() -> None:
    page = st.session_state.get(ARTICLE_ACTIVE_PAGE_KEY, ARTICLE_PAGE_BASIC)
    label = ARTICLE_PAGE_LABELS.get(page, "")
    st.caption(f"📍 {page}/{ARTICLE_PAGE_COUNT} {label}")


def _render_page_nav_buttons(*, position: str) -> None:
    page = st.session_state.get(ARTICLE_ACTIVE_PAGE_KEY, ARTICLE_PAGE_BASIC)

    if page <= ARTICLE_PAGE_BASIC:
        st.button(
            "次へ →",
            key=f"btn_article_page_next_{position}",
            use_container_width=True,
            on_click=_go_to_page,
            args=(page + 1,),
        )
    elif page >= ARTICLE_PAGE_COUNT:
        st.button(
            "← 戻る",
            key=f"btn_article_page_back_{position}",
            use_container_width=True,
            on_click=_go_to_page,
            args=(page - 1,),
        )
    else:
        nav_col1, nav_col2 = st.columns([1, 1])
        with nav_col1:
            st.button(
                "← 戻る",
                key=f"btn_article_page_back_{position}",
                use_container_width=True,
                on_click=_go_to_page,
                args=(page - 1,),
            )
        with nav_col2:
            st.button(
                "次へ →",
                key=f"btn_article_page_next_{position}",
                use_container_width=True,
                on_click=_go_to_page,
                args=(page + 1,),
            )


def get_article_persist_keys() -> set[str]:
    return set(PERSIST_KEYS)


def _is_blank(s: object) -> bool:
    return (s is None) or (str(s).strip() == "")


# =========================
# article__form_data（第1段階：単一ソース化の正本）
# =========================
# 6ページUIでは、非表示ページのtext_area/text_input(key=KEYS[...])の値が
# Streamlitの仕様でセッションから消えることがある（非表示widgetの値は
# 実行完了時にsession_stateから削除される）。article__form_dataは通常の
# dictであり、widgetのライフサイクルと無関係なため、この問題の影響を
# 受けない。widget key（KEYS[...]）は今まで通りの名前のまま「表示専用」
# として使う。
#
# 第1段階（consult_situation/consult_question/last_text/plan_result/
# copy_text/copy_last_sig）に続き、第2段階としてメニュー移動（記事モード
# ⇔ 他モード）をまたいでも空にならないよう、基本入力・検索キーワード・
# 確認先・書き方の希望の各欄もform_data化する。
ARTICLE_FORM_DATA_KEY = "article__form_data"

FORM_DATA_STAGE1_FIELDS: Tuple[str, ...] = (
    "consult_situation",
    "consult_question",
    "last_text",
    "plan_result",
    "copy_text",
    "copy_last_sig",
    "main_kw",
    "sub_kw",
    "theme",
    "memo",
    "evidence_url",
    "evidence_title",
    "evidence_facts",
    "evidence_points",
    "evidence",
    "suggest",
    "tone_reg",
)

# form_dataの値を直接編集するwidgetのfield名→widget key。
# last_text/plan_result/copy_last_sigはwidgetを持たない値のため含めない。
FORM_DATA_WIDGET_SYNC_FIELDS: Tuple[str, ...] = (
    "consult_situation",
    "consult_question",
    "copy_text",
    "main_kw",
    "sub_kw",
    "theme",
    "memo",
    "evidence_url",
    "evidence_title",
    "evidence_facts",
    "evidence_points",
    "evidence",
    "suggest",
    "tone_reg",
)

# _get_effective_value()がform_data経由でも値を拾えるようにするための
# widget key→form_dataフィールド名の逆引き。FORM_DATA_WIDGET_SYNC_FIELDSと
# 常に一致させるため、ハードコードせずここから機械的に生成する。
_FORM_DATA_FIELD_BY_WIDGET_KEY: Dict[str, str] = {
    KEYS[field]: field for field in FORM_DATA_WIDGET_SYNC_FIELDS
}


# =========================
# article__inputs_saved（第1段階：文章チェックモード型の正本を12項目だけ導入）
# =========================
# article__form_dataと並行して存在する新しい正本。文章チェックモードの
# 「widget ⇄ saved」1層構成に寄せるための第一歩として、1/6〜4/6の入力材料
# 12項目（相談内容・検索キーワード・公式情報・書き方の希望）だけを対象にする。
# copy_text/evidence/last_text/plan_result/copy_last_signはこの段階では対象外。
#
# article__form_dataは引き続き残し、同期のたびに互換のため同じ値を書く。
# ただし読み取り（_get_effective_value・seed・reseed）は必ずこちらを優先する。
ARTICLE_INPUTS_SAVED_KEY = "article__inputs_saved"

# ページ移動前の同期（widget→inputs_saved）は、現在表示中のページの項目
# だけに限定するために使う。render_article_ui()は非表示ページの分も含めて
# 毎回widget keyをform_dataからseedし直すため、12項目を一括で
# 「widget→inputs_saved」同期すると、非表示ページのwidget keyに残っている
# 空文字でinputs_savedの正しい値を踏み潰してしまう危険がある。
ARTICLE_INPUTS_SAVED_FIELDS_BY_PAGE: Dict[int, Tuple[str, ...]] = {
    ARTICLE_PAGE_BASIC: (
        "consult_situation",
        "consult_question",
    ),
    ARTICLE_PAGE_KEYWORD: (
        "suggest",
    ),
    ARTICLE_PAGE_OFFICIAL: (
        "evidence_url",
        "evidence_title",
        "evidence_facts",
        "evidence_points",
    ),
    ARTICLE_PAGE_STYLE: (
        "memo",
        "tone_reg",
        "main_kw",
        "sub_kw",
        "theme",
    ),
}

# 12項目のフラットな一覧。seed/reseed/クリア処理・テストなど「12項目全部を
# まとめて扱いたい」場面専用。ページ移動前の「widget→inputs_saved」同期には
# 使わない（ARTICLE_INPUTS_SAVED_FIELDS_BY_PAGE経由で現在ページ分だけを使う）。
ARTICLE_INPUTS_SAVED_STAGE1_FIELDS: Tuple[str, ...] = (
    "consult_situation",
    "consult_question",
    "suggest",
    "evidence_url",
    "evidence_title",
    "evidence_facts",
    "evidence_points",
    "memo",
    "tone_reg",
    "main_kw",
    "sub_kw",
    "theme",
)

# _get_effective_value()がinputs_saved経由でも値を拾えるようにするための
# widget key→inputs_savedフィールド名の逆引き。
_INPUTS_SAVED_FIELD_BY_WIDGET_KEY: Dict[str, str] = {
    KEYS[field]: field for field in ARTICLE_INPUTS_SAVED_STAGE1_FIELDS
}


def _ensure_article_form_data() -> None:
    """
    article__form_dataが無ければ作る。
    旧方式（widget keyのみ）からの移行時は、初回だけ既存のsession_state値を
    form_dataへ取り込む（articleモードを開いた直後の1回だけ発生する）。
    """
    if isinstance(st.session_state.get(ARTICLE_FORM_DATA_KEY), dict):
        return

    form_data: Dict[str, str] = {}
    for field in FORM_DATA_STAGE1_FIELDS:
        existing = st.session_state.get(KEYS[field], "")
        if not _is_blank(existing):
            form_data[field] = str(existing)
    st.session_state[ARTICLE_FORM_DATA_KEY] = form_data


def _get_article_form_data() -> Dict[str, str]:
    _ensure_article_form_data()
    return st.session_state[ARTICLE_FORM_DATA_KEY]


def _get_form_data_value(field: str) -> str:
    return str(_get_article_form_data().get(field, "") or "")


def _set_form_data_value(field: str, value: object) -> None:
    _get_article_form_data()[field] = str(value or "")


def _clear_form_data_fields(*fields: str) -> None:
    form_data = _get_article_form_data()
    for field in fields:
        form_data[field] = ""


def _ensure_article_inputs_saved() -> None:
    """article__inputs_savedが無ければ空dictで作る。"""
    if not isinstance(st.session_state.get(ARTICLE_INPUTS_SAVED_KEY), dict):
        st.session_state[ARTICLE_INPUTS_SAVED_KEY] = {}


def _get_article_inputs_saved() -> Dict[str, str]:
    _ensure_article_inputs_saved()
    return st.session_state[ARTICLE_INPUTS_SAVED_KEY]


def _get_inputs_saved_value(field: str) -> str:
    return str(_get_article_inputs_saved().get(field, "") or "")


def _set_inputs_saved_value(field: str, value: object) -> None:
    _get_article_inputs_saved()[field] = str(value or "")


def _clear_inputs_saved_fields(*fields: str) -> None:
    inputs_saved = _get_article_inputs_saved()
    for field in fields:
        inputs_saved[field] = ""


def _seed_widget_from_inputs_saved_if_missing(field: str) -> None:
    """
    widget keyがsession_stateに無い場合だけ、article__inputs_savedの値を
    流し込む。_seed_widget_from_form_data_if_missing()より必ず先に呼び、
    inputs_savedに値がある12項目についてはform_dataより先にwidget keyを
    埋めることで、inputs_savedを優先させる（inputs_saved側が空の場合は
    widget keyを埋めないため、後続のform_data seedがフォールバックできる）。
    """
    widget_key = KEYS[field]
    if widget_key not in st.session_state:
        value = _get_inputs_saved_value(field)
        if not _is_blank(value):
            st.session_state[widget_key] = value


def _seed_widget_from_form_data_if_missing(field: str) -> None:
    """
    widget keyがsession_stateに無い場合（初回描画、またはStreamlitの仕様で
    非表示中に消えた直後）だけ、form_dataの値を流し込む。widget keyが
    既に存在する場合は上書きしない＝利用者が今まさに空にした値を
    古い値で復活させない。
    """
    widget_key = KEYS[field]
    if widget_key not in st.session_state:
        st.session_state[widget_key] = _get_form_data_value(field)


def _sync_form_data_field_from_widget(field: str) -> None:
    """widgetのon_changeから呼ぶ。現在値をそのまま（空文字も含めて）form_dataへ反映する。"""
    widget_key = KEYS[field]
    _set_form_data_value(field, st.session_state.get(widget_key, ""))


def _sync_widget_to_inputs_saved(field: str) -> None:
    """
    widgetのon_changeから呼ぶ。現在値をそのまま（空文字も含めて）
    article__inputs_savedへ反映する。互換のため、従来の正本である
    article__form_dataにも同じ値を書く（article__form_dataは今回廃止しない）。
    """
    widget_key = KEYS[field]
    value = st.session_state.get(widget_key, "")
    _set_inputs_saved_value(field, value)
    _set_form_data_value(field, value)


# st.formの4項目（evidence_url/evidence_title/evidence_facts/
# evidence_points）に限らず、on_changeを持たないwidget（suggest/memo/
# tone_reg/main_kw/sub_kw/theme）も同様に、そのwidgetが描画されないrunが
# あると、スクリプト側でsession_state[widget_key]へ直接値を書き込んでも、
# Streamlit側の実行完了時処理でその値が空文字へ戻ることがある
# （widget keyそのものが消えるのではなく、キーは残ったまま値だけ空文字に
# 戻る）。_seed_widget_from_form_data_if_missing()は「widget keyが無い
# 場合だけ」しか復元しないため、このケースを救えない。
#
# FORM_DATA_WIDGET_SYNC_FIELDS全体に対して、以下のルールで安全に復元する。
# - widget値が空文字で、form_dataに非空値がある → form_dataの値で復元する
# - widget値が非空（編集中の値） → 上書きしない
# - form_dataも空文字（利用者が「入力欄を空にする」等で明示的に空にした
#   ケース） → 復元しない（空のまま）
def _reseed_blank_widget_from_inputs_saved(field: str) -> None:
    """
    widget値が空文字で、article__inputs_savedに非空値がある場合だけ
    復元する。_reseed_blank_widget_from_form_data()より必ず先に呼び、
    inputs_savedを優先させる（inputs_saved側が空の場合はwidgetを空のまま
    にするため、後続のform_data reseedがフォールバックできる）。
    """
    widget_key = KEYS[field]
    current = st.session_state.get(widget_key, "")
    if not _is_blank(current):
        return
    value = _get_inputs_saved_value(field)
    if not _is_blank(value):
        st.session_state[widget_key] = value


def _reseed_blank_widget_from_form_data(field: str) -> None:
    widget_key = KEYS[field]
    current = st.session_state.get(widget_key, "")
    if not _is_blank(current):
        return
    value = _get_form_data_value(field)
    if not _is_blank(value):
        st.session_state[widget_key] = value


def _sync_form_data_stage1_from_widgets() -> None:
    """
    次へ/戻る・下書き作成ボタンなど、明示的なタイミングで呼ぶ保険の同期。
    on_changeで既に同期されているはずだが、二重の安全網として、現在
    session_stateに存在するwidget keyだけを対象に同期する（非表示ページの
    widget keyが既に消えている場合はそのフィールドのform_dataを変更しない
    ＝空で潰さない）。

    ただし、article__inputs_saved化した12項目（ARTICLE_INPUTS_SAVED_STAGE1_FIELDS）
    については、widget keyがsession_stateに存在していても値が空文字なら
    form_dataを上書きしない。6ページ構成では、非表示ページのwidget keyが
    Streamlitの仕様で「キーは残るが値だけ空文字に戻る」ことがあり、この関数を
    ページ移動のたびに呼ぶと、現在表示していない他ページの空文字がform_dataの
    正しい値を踏み潰してしまう事故があったため（本番調査で確認済み）。
    12項目以外（copy_text/evidence）は従来通り空文字も同期する。
    """
    for field in FORM_DATA_WIDGET_SYNC_FIELDS:
        widget_key = KEYS[field]
        if widget_key not in st.session_state:
            continue
        if field in ARTICLE_INPUTS_SAVED_STAGE1_FIELDS:
            current_value = st.session_state.get(widget_key, "")
            if _is_blank(current_value):
                continue
        _sync_form_data_field_from_widget(field)


def _sync_current_page_inputs_saved_from_widgets() -> None:
    """
    _go_to_page()から呼ぶ、ページ移動前の保険同期。現在表示中のページに
    属する項目だけを対象にする。render_article_ui()は非表示ページの分も
    含めて毎回widget keyをform_dataからseedし直すため、12項目を一括で
    「widget→inputs_saved」同期すると、非表示ページのwidget keyに残って
    いる空文字でarticle__inputs_savedの正しい値を踏み潰す危険がある。
    widget keyがまだ一度も描画されていない（session_stateにキー自体が
    無い）場合は同期しない＝空文字で正本を上書きしない。
    """
    page = st.session_state.get(ARTICLE_ACTIVE_PAGE_KEY, ARTICLE_PAGE_BASIC)
    fields = ARTICLE_INPUTS_SAVED_FIELDS_BY_PAGE.get(page, ())
    for field in fields:
        widget_key = KEYS[field]
        if widget_key in st.session_state:
            _sync_widget_to_inputs_saved(field)


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
    # ユーザーが "URL: https://..." 形式で貼り付けた場合にプレフィックスが重複するのを防ぐ
    if u.lower().startswith("url:"):
        u = u[4:].strip()
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
    _ensure_active_page_initialized()
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
        KEYS["tone_reg"]: str(st.session_state.get(KEYS["tone_reg"], "")),
    }


def _ensure_article_input_backup() -> None:
    if not isinstance(st.session_state.get("article__input_backup"), dict):
        st.session_state["article__input_backup"] = {}


# evidence_url/evidence_title/evidence_facts/evidence_pointsは対象外
# （SHADOW_KEYSと同じ理由。article__form_dataだけを正本にする）。
_ARTICLE_INPUT_BACKUP_KEYS: Tuple[str, ...] = (
    KEYS["main_kw"],
    KEYS["sub_kw"],
    KEYS["theme"],
    KEYS["memo"],
    KEYS["consult_situation"],
    KEYS["consult_question"],
    KEYS["evidence"],
    KEYS["suggest"],
    KEYS["tone_reg"],
)


def _backup_article_inputs() -> None:
    """
    主要な入力欄の現在値をarticle__input_backupへ退避する。
    _backup_shadow_state()と同じく、現在値が空文字・Noneの場合は
    既存のバックアップ値を上書きしない（非表示ページのwidget keyが
    Streamlitの仕様で空扱いになった直後の再描画で、既存バックアップまで
    空で潰してしまう事故を防ぐため）。
    """
    existing = st.session_state.get("article__input_backup")
    backup = dict(existing) if isinstance(existing, dict) else {}

    for key in _ARTICLE_INPUT_BACKUP_KEYS:
        current = st.session_state.get(key, "")
        if not _is_blank(current):
            backup[key] = str(current)

    st.session_state["article__input_backup"] = backup


def _restore_article_inputs_from_backup() -> None:
    backup = st.session_state.get("article__input_backup", {}) or {}
    if not isinstance(backup, dict):
        return

    # evidence_url/evidence_title/evidence_facts/evidence_pointsは対象外
    # （_ARTICLE_INPUT_BACKUP_KEYSと同じ理由。article__form_dataだけを正本にする）。
    for k in (
        KEYS["main_kw"], KEYS["sub_kw"], KEYS["theme"], KEYS["memo"],
        KEYS["tone_reg"],
        KEYS["consult_situation"], KEYS["consult_question"],
        KEYS["evidence"], KEYS["suggest"],
    ):
        current = st.session_state.get(k, None)
        if k not in st.session_state or _is_blank(current):
            value = backup.get(k, "")
            if not _is_blank(value):
                st.session_state[k] = str(value)


def _clear_article_input_backup() -> None:
    st.session_state["article__input_backup"] = {}


def _backup_shadow_state() -> None:
    """
    主要な入力欄の現在値をシャドウStateへ退避する。
    on_changeではなく、描画後バックアップやページ移動ボタン押下時にだけ
    呼び出す（副作用を最小限にするため）。
    """
    for widget_key, shadow_key in SHADOW_KEYS.items():
        value = st.session_state.get(widget_key, "")
        if not _is_blank(value):
            st.session_state[shadow_key] = str(value)


def _restore_shadow_state_to_blanks() -> None:
    """Widgetキーが空で、対応するシャドウStateに値があれば戻す。"""
    for widget_key, shadow_key in SHADOW_KEYS.items():
        current = st.session_state.get(widget_key, "")
        if _is_blank(current):
            shadow_value = st.session_state.get(shadow_key, "")
            if not _is_blank(shadow_value):
                st.session_state[widget_key] = str(shadow_value)


def _clear_shadow_state() -> None:
    """シャドウStateを空にする（入力欄クリア系の操作と一緒に呼ぶ）。"""
    for shadow_key in SHADOW_KEYS.values():
        st.session_state[shadow_key] = ""


def _get_effective_value(key: str) -> str:
    """
    読む専用ヘルパー。widgetの現在値が空でも、article__form_data・
    article__input_backup・シャドウStateにある直近の非空値を安全に参照する。
    session_stateへの書き戻しは一切行わない（呼ぶだけでは何も変化しない）。
    利用者が明示的に入力欄を空にした直後は、form_data/backup/shadow側も
    _clear_form_only() / _clear_generated_only() で既に空になっているため、
    ここで古い値が「復活して見える」ことはない。
    """
    current = st.session_state.get(key, "")
    if not _is_blank(current):
        return str(current).strip()

    inputs_saved_field = _INPUTS_SAVED_FIELD_BY_WIDGET_KEY.get(key)
    if inputs_saved_field:
        inputs_saved_value = _get_inputs_saved_value(inputs_saved_field)
        if not _is_blank(inputs_saved_value):
            return str(inputs_saved_value).strip()

    form_data_field = _FORM_DATA_FIELD_BY_WIDGET_KEY.get(key)
    if form_data_field:
        form_data_value = _get_form_data_value(form_data_field)
        if not _is_blank(form_data_value):
            return str(form_data_value).strip()

    backup = st.session_state.get("article__input_backup")
    if isinstance(backup, dict):
        backup_value = backup.get(key, "")
        if not _is_blank(backup_value):
            return str(backup_value).strip()

    shadow_key = SHADOW_KEYS.get(key)
    if shadow_key:
        shadow_value = st.session_state.get(shadow_key, "")
        if not _is_blank(shadow_value):
            return str(shadow_value).strip()

    return ""


def _get_current_consult_values() -> Tuple[str, str]:
    """
    「今の状況」「知りたいこと」の実質的な現在値を返す読む専用ヘルパー。
    5/6ページの「入力あり」表示と、「下書きを作る」ボタンの入力不足判定は、
    表示と判定がずれないよう、必ずこの関数だけを見て一致させる。
    """
    return (
        _get_effective_value(KEYS["consult_situation"]),
        _get_effective_value(KEYS["consult_question"]),
    )


# 下書き作成の直前だけ、widget値が空でbackup/shadow/form_dataに非空値がある
# 場合に限って書き戻す対象のキー（_restore_blank_generation_inputs_from_backup_or_shadow参照）。
# _get_effective_input_evidence_text()はevidence_url/title/facts/pointsの
# 4項目すべてをsession_stateから直接読むため、生成直前の書き戻しも4項目を
# 揃える（evidence_url/titleだけだと、facts/pointsが空文字に戻っていた
# 場合に確認先の要点が生成に反映されない取りこぼしが起きるため）。
_GENERATION_RESTORE_KEYS: Tuple[str, ...] = (
    KEYS["consult_situation"],
    KEYS["consult_question"],
    KEYS["suggest"],
    KEYS["evidence_url"],
    KEYS["evidence_title"],
    KEYS["evidence_facts"],
    KEYS["evidence_points"],
    KEYS["tone_reg"],
)


def _restore_blank_generation_inputs_from_backup_or_shadow() -> None:
    """
    「✨ 下書きを作る」ボタンが押された直後にだけ呼ぶ、書き戻しありの安全復元。
    下書き生成本体（_build_planning_prompt / _build_writing_prompt）はここで
    列挙したキーをsession_stateから直接読むため、表示・判定用の
    _get_effective_value()だけでは実際の生成内容に反映されない。
    そのため、現在値が空で、backupまたはシャドウStateに非空値がある場合だけ、
    ここで一度だけsession_stateへ書き戻す。
    利用者が「入力欄を空にする」などで明示的に空にした直後は、backup/shadowも
    既に空になっているため、ここで古い値が復活することはない。
    """
    for key in _GENERATION_RESTORE_KEYS:
        current = st.session_state.get(key, "")
        if not _is_blank(current):
            continue
        value = _get_effective_value(key)
        if not _is_blank(value):
            st.session_state[key] = value


def _restore_stale_inputs_on_page_change() -> None:
    """
    _restore_shadow_state_to_blanks() / _restore_article_inputs_from_backup() /
    _reseed_blank_widget_from_form_data() はどれも「今のWidget値が空なら、
    退避してあった値で埋める」処理のため、同じページ内の再描画のたびに毎回
    呼び出すと、利用者が今まさに空にした欄へ古い値を書き戻してしまう
    （消したのに戻る）。そのため、実際にページ（active_page）が切り替わった
    直後だけ呼び出す。
    """
    current_page = st.session_state.get(ARTICLE_ACTIVE_PAGE_KEY, ARTICLE_PAGE_BASIC)
    last_restored_page = st.session_state.get(ARTICLE_SHADOW_RESTORED_PAGE_KEY)
    if last_restored_page == current_page:
        return
    _restore_article_inputs_from_backup()
    _restore_shadow_state_to_blanks()
    # 「widget keyは残るが値だけ空文字に戻る」現象（st.form内外を問わず
    # 起こりうる）の復元も、ページが切り替わった直後だけ行う。
    # article__inputs_saved（第1段階の12項目）をform_dataより先に復元し、
    # inputs_savedを優先させる（inputs_savedに値が無い項目だけform_data
    # 側のreseedが後続でフォールバックする）。
    for _field in ARTICLE_INPUTS_SAVED_STAGE1_FIELDS:
        _reseed_blank_widget_from_inputs_saved(_field)
    for _field in FORM_DATA_WIDGET_SYNC_FIELDS:
        _reseed_blank_widget_from_form_data(_field)
    st.session_state[ARTICLE_SHADOW_RESTORED_PAGE_KEY] = current_page


def _save_snapshot() -> None:
    st.session_state[KEYS["snapshot"]] = _take_snapshot()
    st.session_state[KEYS["save_message"]] = "今の状態を控えました。あとで戻したいときに使えます。"


def _reset_copy_state() -> None:
    st.session_state[KEYS["copy_text"]] = ""
    st.session_state[KEYS["copy_last_sig"]] = ""
    st.session_state[KEYS["copy_agree_risk"]] = False
    _clear_form_data_fields("copy_text", "copy_last_sig")


def _set_copy_state_from_text(text: str) -> None:
    body = str(text or "")
    sig = str(hash(body))
    st.session_state[KEYS["copy_text"]] = body
    st.session_state[KEYS["copy_last_sig"]] = sig
    st.session_state[KEYS["copy_agree_risk"]] = False
    _set_form_data_value("copy_text", body)
    _set_form_data_value("copy_last_sig", sig)


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
        KEYS["tone_reg"],
        KEYS["consult_situation"], KEYS["consult_question"],
        KEYS["evidence_url"], KEYS["evidence_title"], KEYS["evidence_facts"], KEYS["evidence_points"],
        KEYS["evidence"], KEYS["suggest"],
    ):
        st.session_state[k] = ""
    _clear_article_input_backup()
    _clear_shadow_state()
    # widget key側で空にしたフィールドは、form_data側も揃えて空にする
    # （widget keyが後でStreamlitの仕様で消えたときに、form_dataの
    #   古い値で復活しないように）。copy_textはこの関数の対象外のため含めない。
    _clear_form_data_fields(
        "main_kw", "sub_kw", "theme", "memo", "tone_reg",
        "consult_situation", "consult_question",
        "evidence_url", "evidence_title", "evidence_facts", "evidence_points",
        "evidence", "suggest",
    )
    # article__inputs_saved（第1段階の12項目）も、明示的に入力欄を空にする
    # 操作のときだけ揃えて空にする（下書きを消す操作では消さない）。
    _clear_inputs_saved_fields(*ARTICLE_INPUTS_SAVED_STAGE1_FIELDS)
    st.session_state[KEYS["save_message"]] = "入力欄を空にしました。最初から整理し直したいときに使えます。"


def _clear_generated_only() -> None:
    """
    「下書きを消す」ボタンの処理。生成結果（下書き本文・設計図・証拠として
    固定した内容・コピー編集欄）とAI確認結果・メッセージだけを消し、
    相談内容・キーワード・確認先・書き方の希望などの入力材料は一切消さない。
    """
    for k in (
        KEYS["last_text"], KEYS["plan_result"],
        KEYS["proof_evidence"], KEYS["proof_evidence_compact"], KEYS["proof_suggest"], KEYS["proof_memo"],
    ):
        st.session_state[k] = ""

    _reset_copy_state()
    # last_text/plan_resultはform_data側も揃えて空にする（widget keyが後で
    # Streamlitの仕様で消えたときに、form_dataの古い値で復活しないように）。
    # copy_text/copy_last_signは_reset_copy_state()が既に処理済み。
    # proof_*はform_data対象外のため含めない。入力材料のform_dataは触らない。
    _clear_form_data_fields("last_text", "plan_result")
    _reset_ui_flags()

    st.session_state["api__status_code"] = ""
    st.session_state["api__status_message"] = ""
    st.session_state["api__status_detail"] = ""
    st.session_state["api__last_runtime_error"] = ""

    st.session_state[KEYS["save_message"]] = "下書きを消しました。入力した内容はそのまま残っています。"


def _restore_snapshot_fill_blanks() -> None:
    snap = st.session_state.get(KEYS["snapshot"], {}) or {}
    if not isinstance(snap, dict):
        st.session_state[KEYS["save_message"]] = "戻せる控えが見つかりませんでした。"
        return

    targets = (
        KEYS["main_kw"], KEYS["sub_kw"], KEYS["theme"], KEYS["memo"],
        KEYS["tone_reg"],
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
    # 復元した値をform_data側にも反映する。ここで揃えておかないと、後で
    # 一度も他ページへ移動しないままメニューをまたいだ場合に、widget keyが
    # Streamlitの仕様で消えた際、form_dataの古い（空の）値で復活してしまう。
    _sync_form_data_stage1_from_widgets()

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

    # 文体・言い回しのルールは「トンマナ・レギュレーション」欄の役割のため、
    # ここでは「誰に向けて書くか」「何を優先して伝えるか」に関する内容だけに絞る。
    bullets: List[str] = [
        "・一般の人にもわかりやすく説明する",
        "・専門用語はかみくだいて説明する",
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


def _apply_consult_to_article_inputs() -> bool:
    """
    「入力内容から詳細設定を自動補助する」ボタンの処理本体。
    戻り値は、実際に反映できたかどうか（呼び出し側でメッセージの出し分けに使う）。
    """
    situation = str(st.session_state.get(KEYS["consult_situation"], "") or "").strip()
    question = str(st.session_state.get(KEYS["consult_question"], "") or "").strip()

    if not situation and not question:
        st.session_state[KEYS["save_message"]] = "相談内容が空のため、整理できませんでした。先に「今の状況」か「知りたいこと」を入力してください。"
        return False

    st.session_state[KEYS["main_kw"]] = _guess_main_kw_from_consult(situation, question)
    guessed_suggest = _guess_suggest_from_consult(situation, question)

    # suggest は標準入力側の widget のため、ここでは上書きしない。
    current_suggest = str(st.session_state.get(KEYS["suggest"], "") or "").strip()
    st.session_state[KEYS["sub_kw"]] = current_suggest or guessed_suggest
    st.session_state[KEYS["theme"]] = _guess_theme_from_consult(situation, question)
    st.session_state[KEYS["memo"]] = _guess_memo_from_consult(situation, question)

    st.session_state["article__show_detail_assist_hint"] = True

    if _is_blank(current_suggest):
        st.session_state[KEYS["save_message"]] = (
            "詳細設定を補助しました。"
            "反映先：読者や書き方のメモ、詳しいキーワード設定（メインキーワード・サブキーワード・記事テーマ）。"
            "検索キーワード欄は自動では上書きしていません。"
            "必要なら次のページで自由に直してください。"
        )
    else:
        st.session_state[KEYS["save_message"]] = (
            "詳細設定を補助しました。"
            "反映先：読者や書き方のメモ、詳しいキーワード設定（メインキーワード・サブキーワード・記事テーマ）。"
            "必要なら次のページで自由に直してください。"
        )
    return True


def _classify_question_type(blob: str) -> str:
    t = str(blob or "").lower().strip()

    if not t:
        return "general"

    if _contains_any(t, TAX_LAW_KW) or _contains_any(t, PENSION_KW) or _contains_any(t, CARE_KW) or _contains_any(t, INSURANCE_KW):
        return "institutional"

    if _contains_any(t, PROMOTION_KW):
        if _contains_any(t, NEWS_RECENCY_KW) and _contains_any(t, NEWS_RECENCY_STRONG_KW):
            return "latest_news"
    else:
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


def _all_primary_inputs_blank() -> bool:
    check_keys = (
        KEYS["main_kw"], KEYS["sub_kw"], KEYS["theme"], KEYS["memo"],
        KEYS["tone_reg"],
        KEYS["consult_situation"], KEYS["consult_question"],
        KEYS["evidence_url"], KEYS["evidence_title"], KEYS["evidence_facts"], KEYS["evidence_points"],
        KEYS["evidence"], KEYS["suggest"],
    )
    return all(_is_blank(st.session_state.get(k, "")) for k in check_keys)


def _get_autosave_last_saved_label(logs_dir: str) -> str:
    try:
        fp = Path(str(logs_dir or "")) / ARTICLE_AUTOSAVE_FILENAME
        if not fp.exists():
            return ""
        dt = datetime.fromtimestamp(fp.stat().st_mtime, tz=ZoneInfo("Asia/Tokyo"))
        return dt.strftime("%H:%M")
    except OSError:
        return ""


def _request_body_autosave_restore() -> None:
    # 本文側の復元ボタンも、サイドバーと同じ既存の復元処理（app.py側の
    # backup__restore_request / backup__restore_target を使う仕組み）に
    # 誘導するだけで、新しい復元方式は作らない。
    st.session_state["backup__restore_request"] = True
    st.session_state["backup__restore_target"] = ARTICLE_AUTOSAVE_FILENAME
    st.session_state["tmp__restore_prompt_dismissed"] = True


def _render_save_restore_notice(*, logs_dir: str) -> None:
    st.caption(
        "前回の入力内容が残っている場合は復元できます。"
        "入力欄が空の場合でも、保存済みデータが残っている可能性があります。"
    )

    last_saved_label = _get_autosave_last_saved_label(logs_dir)
    if last_saved_label:
        st.caption(f"最終保存：{last_saved_label}（日本時間）")

    if last_saved_label and _all_primary_inputs_blank():
        st.warning("入力欄が空ですが、前回の保存データが残っている可能性があります。復元できます。")
        if st.button(
            "前回の保存データを復元する",
            key="btn_article_body_restore_autosave",
            use_container_width=True,
        ):
            _request_body_autosave_restore()
            st.rerun()


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


def _render_reference_hint_section() -> None:
    """
    確認先の探し方ヒントの表示・非表示は、_evidence_inputs_are_thin()に連動させない。
    連動させると、確認先フォームを送信した瞬間に「入力が薄い→濃い」へ切り替わり、
    フォームより上のブロックが縮んでスクロール位置がずれてしまうため、
    ここだけで完結する開閉トグル（REFERENCE_HINT_OPEN_KEY）で表示状態を管理する。
    """
    # ボタンのラベルはクリック結果を反映できない（クリックした回はボタン自体が
    # 押される前のラベルで描画済みのため）。開閉に応じて文言を変えると
    # 「押した直後だけ表示が1回遅れる」ため、ラベルは開閉に依存しない固定文言にする。
    is_open = bool(st.session_state.get(REFERENCE_HINT_OPEN_KEY, False))

    if st.button("🔎 確認先の探し方ヒントを表示/非表示", key="btn_toggle_reference_hint", use_container_width=True):
        is_open = not is_open
        st.session_state[REFERENCE_HINT_OPEN_KEY] = is_open

    if not is_open:
        st.caption("必要なときは上のボタンで、確認先の探し方ヒントを表示できます。")
        return

    if _is_high_risk_topic() or _is_latest_news_topic() or _is_forecast_topic():
        _render_reference_hint_block()
    else:
        st.caption("公式サイトの確認先が必要なテーマでは、ここに探し方のヒントを表示します。")


def _build_copy_button_html(text: str, label: str) -> str:
    """
    コピー用ボタンのHTMLを組み立てる。
    - safe_text はJS文字列リテラルとして埋め込むため json.dumps + html.escape を維持。
    - safe_label は data-label というただのHTML属性値なのでJSON化せず、
      html.escape した通常文字列をそのまま入れる（\\uXXXXエスケープのまま
      表示が戻ってしまう不具合を避けるため）。
    """
    safe_text = html.escape(json.dumps(str(text or "")), quote=True)
    safe_label = html.escape(str(label or ""), quote=True)
    return f"""<button
  data-label="{safe_label}"
  style="margin:2px 0;padding:4px 14px;cursor:pointer;font-size:13px;border:1px solid #d1d5db;border-radius:4px;background:#f9fafb;"
  onclick="(function(b){{var t={safe_text};var orig=b.dataset.label;if(navigator.clipboard){{navigator.clipboard.writeText(t).then(function(){{b.textContent='✓ コピーしました';setTimeout(function(){{b.textContent=orig;}},2000);}},function(){{fb(t,b,orig);}});}}else{{fb(t,b,orig);}}function fb(t2,b2,o){{var a=document.createElement('textarea');a.value=t2;a.style.cssText='position:fixed;opacity:0;top:0;left:0;';document.body.appendChild(a);a.focus();a.select();try{{document.execCommand('copy');b2.textContent='✓ コピーしました';setTimeout(function(){{b2.textContent=o;}},2000);}}catch(e){{}}document.body.removeChild(a);}}}})(this)"
>{label}</button>"""


def _render_copy_button(text: str, label: str) -> None:
    components.html(_build_copy_button_html(text, label), height=42)


# 記事モードのスクロール位置は、Pythonのsession_stateではなくブラウザの
# sessionStorageに持たせる。Streamlitの再実行はページ遷移ではなく同一
# ドキュメント内の差し替えなので、sessionStorageは再実行をまたいで残る。
# キーは記事モード専用（他モードのスクロール復帰は別タスクで扱う）。
ARTICLE_SCROLL_STORAGE_KEY = "ai_writer_scroll_article"
ARTICLE_TOP_ANCHOR_ID = "article-top"

# 復帰スクリプトがアンカー消費やsessionStorage復帰でscrollTopを書き換えた
# 直後、その結果をtrackerがユーザー操作と誤認して保存し直さないよう、
# 保存を一時停止する猶予時間（ミリ秒）。
ARTICLE_SCROLL_SAVE_PAUSE_MS = 800


def _build_article_scroll_tracker_script_html() -> str:
    """
    記事モードの現在のスクロール位置を、スクロールのたびにsessionStorageへ
    保存し続けるリスナーを組み立てる。

    - document のキャプチャフェーズでリッスンするため、Streamlitの再描画で
      スクロールコンテナ(section.stMain)自体が入れ替わっても捕捉し続けられる。
    - window.parent にガードフラグ(__aiWriterArticleScrollInit)を立てて、
      記事モードの再実行のたびにcomponents.htmlが新しいiframeを注入しても
      リスナーが重複登録されないようにする。
    - 記事モード用のアンカー(#article-top)がDOMに無いとき（＝今は他モードを
      見ているとき）は保存しない。リスナー自体はwindow.parentに一度だけ
      付いたまま残るが、他モード表示中のスクロールでは保存対象にならない。
    - このANCHOR_ID判定はscrollイベント発生時（setTimeoutの予約時点）だけで
      なく、150ms後の保存直前にも再チェックする。記事モードを離れた直後の
      debounce待ちタイマーがそのまま残っていると、150ms後に発火した時点では
      既に他モードへ切り替わっていることがあり（section.stMainはモードを
      跨いで使い回される同一要素のため、ev.target.scrollTopはその時点の
      ライブな値を返してしまう）、保存直前の再チェックが無いと他モードの
      scrollTopがarticle用sessionStorageキーへ紛れ込む。
    - 復帰スクリプト側がwin.__aiWriterArticleScrollPauseUntilを立てている間
      （＝アンカー消費やsessionStorage復帰でプログラムがscrollTopを動かした
      直後）は、そのプログラム由来の位置を保存しない。
    """
    safe_key = json.dumps(ARTICLE_SCROLL_STORAGE_KEY)
    safe_anchor = json.dumps(ARTICLE_TOP_ANCHOR_ID)
    return f"""<script>
(function() {{
    var win = window.parent || window;
    var doc = win.document;
    if (win.__aiWriterArticleScrollInit) {{ return; }}
    win.__aiWriterArticleScrollInit = true;

    var KEY = {safe_key};
    var ANCHOR_ID = {safe_anchor};
    var saveTimer = null;

    doc.addEventListener('scroll', function(ev) {{
        var target = ev.target;
        if (!target || !target.matches || !target.matches('section.stMain')) {{ return; }}
        if (!doc.getElementById(ANCHOR_ID)) {{ return; }}
        if (saveTimer) {{ win.clearTimeout(saveTimer); }}
        saveTimer = win.setTimeout(function() {{
            if (!doc.getElementById(ANCHOR_ID)) {{ return; }}
            if (win.__aiWriterArticleScrollPauseUntil && Date.now() < win.__aiWriterArticleScrollPauseUntil) {{ return; }}
            try {{ win.sessionStorage.setItem(KEY, String(target.scrollTop)); }} catch (e) {{}}
        }}, 150);
    }}, true);
}})();
</script>"""


def _build_article_scroll_restore_script_html(
    nonce: str = "",
    *,
    restore_even_if_hash_consumed: bool = False,
) -> str:
    """
    直前にsessionStorageへ保存していた記事モードのスクロール位置へ、
    一度だけ復帰するスクリプトを組み立てる。

    - 記事モード表示中（ANCHOR_ID=article-topがDOMに存在する）にrestoreが
      動く場合、URL hashが残っていれば、既知アンカーかどうかに関わらず
      history.replaceStateで消費してクリアする。Streamlit本体の見出し
      アンカー機能（HeadingWithActionElements）は、script完了の300ms後に
      window.location.hashが自分の見出しidと一致していればscrollIntoView
      を試みるため、hashを空にしておくことでこの判定自体を空振りさせ、
      sessionStorage復帰後に後から位置を上書きされるのを防ぐ。
    - hashクリアはANCHOR_IDがDOM上に存在するとき（＝記事モード表示中）に
      限定する。restoreスクリプトは記事モードからしか呼ばれない前提だが、
      念のため他モードの画面移動サポートのhashを誤って消費しないよう防御する。
    - 画面移動サポートのリンクは通常の<a href="#...">によるブラウザ標準の
      アンカー移動であり、クリックした時点でStreamlitのrerunは発生しない
      （componentsのiframeも再実行されない）。このスクリプトが次回呼ばれる
      までにはブラウザのジャンプは既に完了しているため、hashクリアは
      画面移動サポート自体の動作を妨げない。
    - restore_even_if_hash_consumed=False（既定）の場合、hashが残っていた
      回はhashクリアのみで終え、これまで通りsessionStorage復帰は行わない。
      他モードから記事モードへ戻った直後（just_entered_menu）の呼び出しは
      この既定のままにし、直前の画面移動サポートのアンカー移動を一度だけ
      尊重する挙動を維持する。
    - restore_even_if_hash_consumed=True の場合、hashクリア後もreturnせず
      そのままsessionStorage復帰処理へ進む。画面移動サポートのリンクは
      クリック時点でStreamlitのrerunを伴わないため、このスクリプトが動く
      回はいずれもリンククリックそのものとは無関係なrerunであり、続けて
      sessionStorage復帰を行ってもクリック直後の移動操作を打ち消さない。
      「この確認先を下書きに反映する」ボタン押下後の呼び出しに使う想定
      （フォーム送信後にStreamlit本体がボタンへフォーカスを戻す際、
      preventScroll指定が無くブラウザが自動スクロールしてしまう分を
      sessionStorage復帰で補正するため）。
    - hash消費後・sessionStorage復帰後のいずれも、直後に
      win.__aiWriterArticleScrollPauseUntilを立てて、tracker側が
      このプログラム由来のscrollTopを保存し直さないようにする。
    - nonceはcomponents.htmlへ渡すHTML文字列を毎回変える目的専用の値。
      前回と完全に同じHTMLだとブラウザがiframeの再読み込み（＝script再実行）
      を省略する場合があるため、呼び出しのたびに変えて確実に再実行させる。
    """
    safe_key = json.dumps(ARTICLE_SCROLL_STORAGE_KEY)
    safe_nonce = html.escape(str(nonce or ""), quote=True)
    safe_anchor = json.dumps(ARTICLE_TOP_ANCHOR_ID)
    safe_restore_even_if_hash_consumed = json.dumps(bool(restore_even_if_hash_consumed))
    pause_ms = int(ARTICLE_SCROLL_SAVE_PAUSE_MS)
    return f"""<!-- nonce:{safe_nonce} -->
<script>
(function() {{
    var win = window.parent || window;
    var doc = win.document;

    function pauseTrackerSaves() {{
        win.__aiWriterArticleScrollPauseUntil = Date.now() + {pause_ms};
    }}
    pauseTrackerSaves();

    var ANCHOR_ID = {safe_anchor};
    var RESTORE_EVEN_IF_HASH_CONSUMED = {safe_restore_even_if_hash_consumed};
    var rawHash = (win.location && win.location.hash) ? String(win.location.hash) : "";
    var hashId = rawHash.indexOf('#') === 0 ? rawHash.slice(1) : rawHash;

    if (hashId) {{
        if (doc.getElementById(ANCHOR_ID)) {{
            // 記事モード表示中は、既知アンカーかどうかに関わらずhashを消費して
            // クリアする。残したままだとStreamlit本体の見出しアンカー機能が
            // script完了の300ms後にscrollIntoViewを発火させ、sessionStorage
            // 復帰後の位置を後から上書きすることがあるため。
            try {{
                if (win.history && win.history.replaceState) {{
                    win.history.replaceState(null, '', win.location.pathname + win.location.search);
                }}
            }} catch (e) {{}}
        }}
        if (!RESTORE_EVEN_IF_HASH_CONSUMED) {{ return; }}
    }}

    var KEY = {safe_key};
    var raw = null;
    try {{ raw = win.sessionStorage.getItem(KEY); }} catch (e) {{ return; }}
    if (raw === null || raw === "") {{ return; }}

    var y = parseInt(raw, 10);
    if (isNaN(y)) {{ return; }}

    // 記事モードの中身はこのスクリプト実行後も描画が続いているため、
    // 1回だけの代入だと途中までの高さしか無くscrollTopが頭打ちになる。
    // レイアウトが落ち着くまで、時間を空けて複数回代入し直す。
    function applyScroll() {{
        var el = doc.querySelector('section.stMain');
        if (el) {{ el.scrollTop = y; }}
        pauseTrackerSaves();
    }}
    applyScroll();
    win.setTimeout(applyScroll, 50);
    win.setTimeout(applyScroll, 200);
    win.setTimeout(applyScroll, 500);
    win.setTimeout(applyScroll, 1000);
}})();
</script>"""


def _render_article_scroll_tracker() -> None:
    components.html(_build_article_scroll_tracker_script_html(), height=0)


def _render_article_scroll_restore(*, restore_even_if_hash_consumed: bool = False) -> None:
    nonce = datetime.now().strftime("%Y%m%d%H%M%S%f")
    components.html(
        _build_article_scroll_restore_script_html(
            nonce=nonce,
            restore_even_if_hash_consumed=restore_even_if_hash_consumed,
        ),
        height=0,
    )


def _build_planning_prompt() -> str:
    _sync_evidence_text_from_parts()

    consult_situation = str(st.session_state.get(KEYS["consult_situation"], "") or "").strip()
    consult_question = str(st.session_state.get(KEYS["consult_question"], "") or "").strip()
    main_kw = str(st.session_state.get(KEYS["main_kw"], "") or "").strip()
    if not main_kw:
        main_kw = _guess_main_kw_from_consult(consult_situation, consult_question)
    sub_kw = str(st.session_state.get(KEYS["sub_kw"], "") or "").strip()
    theme = str(st.session_state.get(KEYS["theme"], "") or "").strip()
    evidence = str(_get_generation_evidence_text()).strip()

    today_str = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y年%m月%d日")

    p: list[str] = []
    p.append("あなたは日本語でSEO記事を設計する編集者です。")
    p.append("以下の情報をもとに、記事の設計図を作ってください。")
    p.append("")
    p.append("【絶対ルール】")
    p.append("・根拠に無い数字（年齢・年号・金額・期限・割合）は書かないでください。")
    p.append("・架空の例を作らないでください。")
    p.append("・断定できない内容は『〜とされています』『公式ページで確認が必要です』と書いてください。")
    p.append("")
    p.append(f"今日の日付：{today_str}")
    p.append("・期限・開始日・終了日を書くときは、今日の日付と比較してください。")
    p.append(f"・今日（{today_str}）より前の日付が付いた期限・開始日・終了日は、未来形で書かないでください。")
    p.append(f"・今日（{today_str}）より前の日付が付いた期限は「すでに終了しています」「すでに使用できなくなっています」「すでに有効期限を迎えています」「すでに原則として使えなくなっています」のように、過去形・現在完了で書いてください。")
    p.append(f"・今日より後の日付が付いた期限だけ「終了します」「使用できなくなります」と未来形で書いてください。")
    p.append("・『2025年12月1日で使用できなくなります』のように、過去の日付に『なります』『終了します』『求められます』など未来形をつなげないでください。")
    p.append("・どちらか判断できない場合は断定せず、『公開前に公式情報で確認してください』『制度の対象や例外は公式情報で確認してください』のように確認対象として書いてください。")
    p.append("")
    p.append(f"【読者の状況】{consult_situation}")
    p.append(f"【知りたいこと】{consult_question}")
    p.append(f"【メインキーワード】{main_kw}")
    if sub_kw:
        p.append(f"【サブキーワード】{sub_kw}")
    if theme:
        p.append(f"【記事テーマ】{theme}")
    p.append("")
    p.append("【AIに渡す根拠（優先参照）】")
    p.append(evidence if evidence else "（未入力）")
    p.append("")
    p.append("以下の4項目を順番に出力してください。")
    p.append("")
    p.append("## 読者の困りごと")
    p.append("（1〜2文。読者が今どんな状況で何に困っているかを整理する）")
    p.append("")
    p.append("## 最初に伝える結論")
    p.append("（1文。読者が『これで方針が決まった』と思える核心を先に示す）")
    p.append("")
    p.append("## 読者がまず取る行動")
    p.append("（1〜2文。記事を読み終えた後に読者が最初に取れる具体的な一歩）")
    p.append("")
    p.append("## 見出し構成")
    p.append("（5〜8個の ## 見出し。冒頭の結論セクションから始め、詳細説明を続け、最後に次のステップで締める）")
    p.append("番号付きリストで列挙してください。")
    return "\n".join(p)


def _build_writing_prompt(plan: str) -> str:
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
    tone_reg = str(st.session_state.get(KEYS["tone_reg"], "") or "").strip()

    p: list[str] = []
    p.append("あなたは日本語でSEO記事の下書きを作る編集者です。")
    if plan:
        p.append("")
        p.append("【記事の設計図（必ず従うこと）】")
        p.append("以下の設計図に沿って記事を書いてください。")
        p.append("冒頭では『最初に伝える結論』と『読者がまず取る行動』を先に示してください。")
        p.append("見出し構成は設計図の通りに使ってください。順番を変えないでください。")
        p.append(plan)
        p.append("")
    p.append("専門用語はやさしい言葉に言い換え、初心者にもわかる説明にしてください。")
    p.append("説明書のように固くしすぎず、読者が『なるほど、そういうことか』と理解しやすい自然な文章にしてください。")
    p.append("誇張や断定を避け、根拠が不十分な内容は『〜とされています』など慎重に表現してください。")
    p.append("1文は60文字以内を目安にし、長い場合は2文に分けてください。")
    p.append("出力はMarkdown本文のみで、コードブロックは使わないでください。")
    p.append("")
    p.append("【標準トンマナ】")
    p.append("・一般の読者に向けて、やさしく実用的に書く")
    p.append("・専門用語はかみくだく")
    p.append("・です・ます調を基本にするが、同じ文末を3回以上続けない")
    p.append("・確認項目の羅列で終わらせず、なぜ大事か、次に何を見るかまで書く")
    p.append("・煽り、誇張、断定、薄い一般論を避ける")
    p.append("・事実、推測、意見を分ける")
    p.append("・数字や制度、最新情報は公式情報で確認する前提で書く")
    p.append("")
    if tone_reg:
        p.append("【追加トンマナ・レギュレーション】")
        p.append("以下は文体・表記・読者との距離感に関する追加指定です。")
        p.append("標準トンマナより優先してください。")
        p.append("ただし、事実確認、安全確認、第16条のルールは上書きしないでください。")
        p.append(tone_reg)
        p.append("")
    p.append("【文体・書き方の方針】")
    p.append("・読者が読み終えたあとに『これで分かった、次に何をすればいいか分かった』と思える内容にしてください。確認項目の羅列だけで終わらせないでください。")
    p.append("・なぜその内容が大事なのか、読者が次に見るべきものは何かまで、具体的に書いてください。")
    p.append("・人が書いたような、やさしく温かい文章にしてください。AIが生成したような薄い言い換えや、一般論の羅列は避けてください。")
    p.append("・『です』『ます』など同じ文末を3回以上連続させないでください。体言止め・『〜できます』との組み合わせで単調さを防いでください。")
    p.append("・断定できない内容は『〜とされています』『公式ページで確認してください』など確認を促す表現にしてください。")
    p.append("")
    p.append("【最重要ルール】")
    p.append("1. 『生成に使う要点』に無い数字（年齢・年号・金額・期限・割合）は、本文にも見出しにも書かないでください。")
    p.append("2. 説明のための架空の数字例を作らないでください。")
    p.append("3. 『現在』『最新』『変更』『改正』などの表現は、要点に同じ時期ラベルや変更内容がある場合だけ使ってください。")
    p.append("4. 根拠に現在の基準と過去の基準が並んでいる場合は、時期ごとに分けて書いてください。混ぜて一般論にしないでください。")
    p.append("5. 質問に無い周辺論点へ広げないでください。")
    p.append("")
    today_str = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y年%m月%d日")
    p.append("【日付・期限の表現ルール】")
    p.append(f"今日の日付：{today_str}")
    p.append(f"・今日（{today_str}）より前の日付が付いた期限・開始日・終了日は、未来形で書かないでください。")
    p.append(f"・今日（{today_str}）より前の日付が付いた期限は「すでに終了しています」「すでに使用できなくなっています」「すでに有効期限を迎えています」「すでに原則として使えなくなっています」のように、過去形・現在完了で書いてください。")
    p.append(f"・今日より後の日付が付いた期限だけ「終了します」「使用できなくなります」と未来形で書いてください。")
    p.append("・『2025年12月1日で使用できなくなります』のように、過去の日付に『なります』『終了します』『求められます』など未来形をつなげないでください。")
    p.append("・判断できない場合は断定せず、『公開前に公式情報で確認してください』『制度の対象や例外は公式情報で確認してください』のように確認対象として書いてください。")
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

    p.append("【この記事で最優先する読者の疑問（参考情報）】")
    p.append("下記の読者の疑問を念頭に置いて記事を構成してください。ただし、この文章をそのまま本文に引用したり、見出しにしたりしないでください。")
    if consult_question:
        p.append(f"読者の疑問：{consult_question}")
    else:
        p.append("読者の疑問を優先して答えてください。")
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
    p.append("【仕上げの自動チェック（出力前に必ず確認すること）】")
    p.append("本文を出力する前に、以下の点を自分でチェックして修正してください。")
    p.append("1. 各見出しの末尾が『〜確認しましょう』『〜重要です』だけで終わっていないか。")
    p.append("   → 終わっている場合は、なぜ重要か・次に何をするかを1文加えてください。")
    p.append("2. 薄い一般論（『制度を理解することが大切です』など）が段落の中心になっていないか。")
    p.append("   → 根拠や具体的な状況に置き換えてください。")
    p.append("3. 冒頭の結論と最初の行動が、設計図通りに最初のセクションに入っているか。")
    p.append("4. 過去の日付を未来形で書いていないか。")
    p.append("5. 公式根拠にない数字や期限を断定していないか。")
    p.append("   → 該当があれば、出力前に必ず修正してください。")
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
    empty_placeholder: str = "",
) -> None:
    """
    empty_placeholderを指定した呼び出し元は、本文が空でも「見出し＋文字数＋
    プレビュー枠(st.code)」という同じ構造を保つ。指定が無い呼び出し元は
    従来通り「（未入力）」の1行キャプションのみにする（表示への影響を
    このパラメータを渡す呼び出し元だけに限定するため）。
    """
    text = str(body or "").strip()

    st.markdown(f"**{title}**")
    if not text:
        if empty_placeholder:
            st.caption("文字数：0")
            st.code(empty_placeholder, language="text")
        else:
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
    important_without_quote = {
        "最新情報は最終確認前提",
        "重要主張の照合未完了",
    }

    for f in findings:
        rule_key = str(getattr(f, "code", "") or "")
        samples = getattr(f, "samples", None) or []
        matched_texts = [str(x) for x in samples if str(x).strip()]
        diag = build_buyer_diagnosis(rule_key=rule_key, matched_texts=matched_texts)

        is_generic = (
            diag.get("issue_label") == "\u78ba\u8a8d\u3057\u305f\u3044\u7b87\u6240"
            and diag.get("issue_text") == "\u672c\u6587\u306e\u8868\u73fe\u3092\u78ba\u8a8d\u3057\u3066\u304f\u3060\u3055\u3044\u3002"
        )
        is_risk = str(getattr(f, "level", "") or "") == "RISK"
        has_guidance = bool(
            str(diag.get("reason_text", "")).strip()
            and str(diag.get("fix_text", "")).strip()
        )

        if is_generic or not has_guidance:
            continue
        if not matched_texts and not is_risk and rule_key not in important_without_quote:
            continue

        st.markdown("---")

        if matched_texts:
            st.markdown("**\u554f\u984c\u306e\u6587\u7ae0**")
            for item in matched_texts:
                st.markdown(f"- {item}")
        else:
            st.markdown("**\u78ba\u8a8d\u3059\u308b\u3053\u3068**")
            st.write(str(diag.get("issue_text", "") or ""))

        st.markdown("**\u306a\u305c\u78ba\u8a8d\u3059\u308b\u306e\u304b**")
        st.write(str(diag.get("reason_text", "") or ""))

        st.markdown("**\u3069\u3046\u76f4\u3059\u306e\u304b**")
        st.write(str(diag.get("fix_text", "") or ""))

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


def _render_page_1_basic() -> None:
    st.markdown("## 📝 かんたん記事作成")
    st.write("まずは2つだけで大丈夫です。")

    st.markdown("### 1. 今の状況")
    # article__form_data["consult_situation"]を正本にする。widget keyが
    # 非表示ページで消えていた場合だけform_dataから流し込み、既にあれば
    # 上書きしない（利用者が今まさに空にした値を復活させないため）。
    _seed_widget_from_form_data_if_missing("consult_situation")
    st.text_area(
        "困っていることや背景を書いてください",
        height=120,
        key=KEYS["consult_situation"],
        on_change=_sync_widget_to_inputs_saved,
        args=("consult_situation",),
    )
    st.caption("例：63歳会社員。給与28万円と賞与があり、年金がどう変わるか知りたい。")

    st.markdown("### 2. 知りたいこと")
    _seed_widget_from_form_data_if_missing("consult_question")
    st.text_area(
        "何を知りたいか、どう判断したいかを書いてください",
        height=90,
        key=KEYS["consult_question"],
        on_change=_sync_widget_to_inputs_saved,
        args=("consult_question",),
    )
    st.caption("例：給与と賞与はどう合算されるか。今の基準額は何か。")

    _render_question_type_box()


def _render_page_2_keyword_and_detail_entry() -> None:
    st.markdown("## 🔍 検索キーワード・詳細設定")

    st.markdown("### 3. 検索キーワード（任意）")
    st.caption(
        "検索キーワード、サジェストキーワード、関連キーワードなど、"
        "読者が検索しそうな言葉を入れてください。2〜5個くらいが目安です。空でも進められます。"
    )
    _seed_widget_from_form_data_if_missing("suggest")
    st.text_input(
        "例：在職老齢年金, 支給停止, 65万円基準",
        key=KEYS["suggest"],
        on_change=_sync_widget_to_inputs_saved,
        args=("suggest",),
    )

    if _is_high_risk_topic():
        st.warning("制度や数字が関わるテーマです。次のページで確認先を入れてから進めると安全です。")

    st.markdown("### 詳しく設定しますか？")
    st.caption("通常は空欄のままで大丈夫です。精度を上げたいときだけ、次以降のページで入力してください。")

    if st.button("入力内容から詳細設定を自動補助する", key="btn_apply_consult_into_detail", use_container_width=True):
        # トップの案内メッセージ表示は次の再描画まで出ないため、押した直後に
        # ここでも同じ内容をその場で表示する（購入者が反応に気づけるように）。
        applied = _apply_consult_to_article_inputs()
        inline_msg = str(st.session_state.get(KEYS["save_message"], "") or "").strip()
        if inline_msg:
            if applied:
                st.success(inline_msg)
            else:
                st.warning(inline_msg)
            st.session_state[KEYS["save_message"]] = ""


def _render_page_3_official_info() -> None:
    st.markdown("## 📚 公式情報・確認先")
    st.caption("通常は空欄でも大丈夫です。分かる範囲だけ入力してください。")

    effective_evidence_text = _get_effective_input_evidence_text()
    _render_evidence_compact_guide(effective_evidence_text)

    _render_reference_hint_section()

    st.caption(
        "入力した内容はページを移動しても残ります。"
        "『この確認先を下書きに反映する』は、入力内容を確認先の要約文にまとめるためのボタンです。"
    )

    # st.formは使わず通常widgetとして描画する。入力のたびにon_changeで
    # article__form_dataへ即時同期するため（1/6ページのconsult_situation/
    # consult_questionと同じ方式）、反映ボタンを押さなくてもページ移動で
    # 値が消えない。
    _seed_widget_from_form_data_if_missing("evidence_url")
    st.text_input(
        "すでに見つけた公式URL",
        key=KEYS["evidence_url"],
        on_change=_sync_widget_to_inputs_saved,
        args=("evidence_url",),
    )
    st.caption(
        "AIは公式URLを自動では取得しません。公式ページを見つけた場合は、ここに自分で貼ってください。"
        "分からない場合は空欄で大丈夫です。確認先を探すための検索語やヒントは提案できるので、"
        "下の『書類名・検索語』に思いつく言葉だけ入れてください。"
    )

    _seed_widget_from_form_data_if_missing("evidence_title")
    st.text_input(
        "すでに分かっている書類名・検索語",
        key=KEYS["evidence_title"],
        on_change=_sync_widget_to_inputs_saved,
        args=("evidence_title",),
    )
    st.caption(
        "分かっている書類名や、検索した言葉があれば書いてください。"
        "例：資格確認書、年金事務所、在職老齢年金、代表社員変更、登記申請書"
    )

    _seed_widget_from_form_data_if_missing("evidence_facts")
    st.text_area(
        "大事な数字・期限",
        height=90,
        key=KEYS["evidence_facts"],
        on_change=_sync_widget_to_inputs_saved,
        args=("evidence_facts",),
    )
    st.caption(_get_detail_help_text()["numbers"])

    _seed_widget_from_form_data_if_missing("evidence_points")
    st.text_area(
        "このページでいちばん大事だったこと",
        height=120,
        key=KEYS["evidence_points"],
        on_change=_sync_widget_to_inputs_saved,
        args=("evidence_points",),
    )
    st.caption(_get_detail_help_text()["memo"])

    detail_submitted = st.button(
        "この確認先を下書きに反映する",
        key="btn_article_apply_evidence",
        use_container_width=True,
    )

    if detail_submitted:
        _sync_evidence_text_from_parts()
        # st.success はレイアウトの高さを押し下げてスクロール位置がずれやすいため、
        # 高さに影響しない st.toast で反映完了を伝える。
        st.toast("詳細設定を反映しました。")

    split_mode_on = _has_any_split_evidence_input()
    legacy_evidence_text = str(st.session_state.get(KEYS["evidence"], "") or "").strip()
    if (not split_mode_on) and (not _is_blank(legacy_evidence_text)):
        st.info("以前の保存データの根拠が残っています。分割欄が空の間は、その根拠をそのまま使います。")
        st.code(legacy_evidence_text, language="text")


def _render_page_4_writing_style() -> None:
    st.markdown("## ✏️ 書き方の希望")
    st.caption("通常は空欄でも大丈夫です。必要なときだけ入力してください。")

    show_assist_hint = bool(st.session_state.get("article__show_detail_assist_hint", False))

    memo = str(st.session_state.get(KEYS["memo"], "") or "").strip()
    st.caption("読者や書き方のメモ：誰に向けて書くか、何を優先して伝えるかを書いてください。")
    if not memo:
        st.caption("空でも進められます。必要なら補足してください。")
    elif show_assist_hint:
        st.caption("入力内容から自動補助しました。必要なら自由に直してください。")
    _seed_widget_from_form_data_if_missing("memo")
    st.text_area(
        "読者や書き方のメモ",
        height=110,
        key=KEYS["memo"],
        on_change=_sync_widget_to_inputs_saved,
        args=("memo",),
    )

    _seed_widget_from_form_data_if_missing("tone_reg")
    st.text_area(
        "トンマナ・レギュレーション（任意）",
        height=90,
        key=KEYS["tone_reg"],
        on_change=_sync_widget_to_inputs_saved,
        args=("tone_reg",),
    )
    st.caption("トンマナ・レギュレーション：文体、禁止表現、言い回しのルールを書いてください。空欄なら標準設定で作成します。")

    with st.expander("詳しいキーワード設定（任意）", expanded=show_assist_hint):
        if show_assist_hint:
            st.caption("入力内容から自動補助しました。必要なら自由に直してください。")

        main_kw = str(st.session_state.get(KEYS["main_kw"], "") or "").strip()
        if not main_kw:
            st.caption(f"候補：{_guess_main_kw_from_consult(str(st.session_state.get(KEYS['consult_situation'], '') or ''), str(st.session_state.get(KEYS['consult_question'], '') or ''))}")
        _seed_widget_from_form_data_if_missing("main_kw")
        st.text_input(
            "この記事で中心にする言葉",
            key=KEYS["main_kw"],
            on_change=_sync_widget_to_inputs_saved,
            args=("main_kw",),
        )

        sub_kw = str(st.session_state.get(KEYS["sub_kw"], "") or "").strip()
        if not sub_kw:
            st.caption("候補：検索キーワードの内容や相談文から自動で考えます。必要なら入れてください。")
        _seed_widget_from_form_data_if_missing("sub_kw")
        st.text_input(
            "一緒に入れたい関連語",
            key=KEYS["sub_kw"],
            on_change=_sync_widget_to_inputs_saved,
            args=("sub_kw",),
        )

        theme = str(st.session_state.get(KEYS["theme"], "") or "").strip()
        if not theme:
            st.caption(f"候補：{_guess_theme_from_consult(str(st.session_state.get(KEYS['consult_situation'], '') or ''), str(st.session_state.get(KEYS['consult_question'], '') or ''))}")
        _seed_widget_from_form_data_if_missing("theme")
        st.text_input(
            "記事の仮タイトル・方向性",
            key=KEYS["theme"],
            on_change=_sync_widget_to_inputs_saved,
            args=("theme",),
        )


def _render_pre_generate_input_summary() -> None:
    st.markdown("### 入力内容の簡単な確認")

    situation, question = _get_current_consult_values()
    suggest = str(st.session_state.get(KEYS["suggest"], "") or "").strip()
    evidence_text = _get_effective_input_evidence_text().strip()
    tone_reg = str(st.session_state.get(KEYS["tone_reg"], "") or "").strip()

    st.caption(f"今の状況：{'入力あり' if situation else '未入力'}")
    st.caption(f"知りたいこと：{'入力あり' if question else '未入力'}")
    st.caption(f"検索キーワード：{suggest or '未入力（空欄でも進められます）'}")
    st.caption(f"確認先：{'入力あり' if evidence_text else '未入力（空欄でも進められます）'}")
    st.caption(f"トンマナ・レギュレーション：{'入力あり' if tone_reg else '未入力（標準設定を使用）'}")


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
        st.success("✅ サンプルを表示しました。本番AIはまだ使っていません。")

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
    just_entered_menu: bool = False,
) -> None:
    # _ensure_keys_initialized()はKEYSの各widget keyが無ければ""で埋めるため、
    # 先に呼んでしまうと「非表示ページでStreamlitの仕様により消えた」という
    # 状態と「まだ何も入力していない」状態が区別できなくなり、form_data側の
    # 復元判定（widget keyが本当に無いかどうか）が機能しなくなる。
    # そのため、form_dataの用意とform_data→widgetの流し込みは、
    # _ensure_keys_initialized()より必ず先に行う。
    _ensure_article_form_data()
    _ensure_article_inputs_saved()
    # article__inputs_saved（第1段階の12項目）をform_dataより先にseedし、
    # inputs_savedを優先させる（inputs_savedに値が無い項目だけform_data側の
    # seedが後続でフォールバックする）。
    for _field in ARTICLE_INPUTS_SAVED_STAGE1_FIELDS:
        _seed_widget_from_inputs_saved_if_missing(_field)
    for _field in FORM_DATA_WIDGET_SYNC_FIELDS:
        _seed_widget_from_form_data_if_missing(_field)

    _ensure_keys_initialized()
    _ensure_article_input_backup()
    # 「widget keyは残るが値だけ空文字に戻る」ケース（st.form内外を問わず
    # 起こりうる）の空文字判定reseedは、_restore_stale_inputs_on_page_change()
    # 内で、ページが実際に切り替わった直後だけ行う（同じページ内の
    # 再描画のたびに毎回行うと、利用者が今まさに空にした欄へ古い値を
    # 書き戻してしまうため）。
    _restore_stale_inputs_on_page_change()

    # 記事モードの先頭アンカー。文章チェックモードのページ内リンク
    # （#quality-fix-place等）を踏んだ後に記事モードへ戻ってきても、
    # 下のhashクリア処理がこの要素の有無で「今は記事モード表示中」を
    # 判定できるようにするための目印（表示上は何もしない）。
    st.markdown(f'<div id="{ARTICLE_TOP_ANCHOR_ID}" style="scroll-margin-top: 120px;"></div>', unsafe_allow_html=True)

    # 記事モードの自動スクロール位置復帰（sessionStorageに保存した位置への
    # 自動巻き戻し）はいったん停止中。本番Streamlit Cloudで、入力・クリック・
    # 詳細設定の開閉など通常操作で発生する意図しないscrollイベントまで
    # sessionStorageに保存してしまい、次にmenuへ戻った際に無関係な位置へ
    # 復帰する不安定要因になっていたため（tracker側は今も呼び出さない）。
    # 一方、文章チェックモードなど他モードのページ内リンクを踏んだ後に記事モード
    # へ戻ると、ブラウザのURL hashが残ったままになり、Streamlit本体の見出し
    # アンカー機能が誤って自動で画面を動かす要因になっていた。restore関数は
    # hashクリアとsessionStorage復帰の両方を担うが、restore_even_if_hash_consumed=False
    # （既定）で呼べばhashクリアのみを行いsessionStorage復帰へは進まないため、
    # 不安定要因になったsessionStorage復帰を再開せずにhash残留だけをここで解消する。
    if just_entered_menu:
        _render_article_scroll_restore(restore_even_if_hash_consumed=False)

    _render_save_restore_notice(logs_dir=logs_dir)
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

    # 記事モードのページ区切り型UI：長い1ページ型のスクロールをやめ、
    # 1画面あたり数項目だけの6ページに分け、「前へ」「次へ」で切り替える。
    # 入力値はどのページでも同じsession_state(KEYS)を参照するため、
    # ページを移動しても入力内容は消えない。
    active_page = st.session_state.get(ARTICLE_ACTIVE_PAGE_KEY, ARTICLE_PAGE_BASIC)
    _render_page_indicator()
    # 上部の「次へ」「戻る」ボタンは撤去した。入力欄より前に同種のボタンが
    # 2セット存在する冗長さと、render 1回あたりのボタン/コンポーネント数を
    # 減らす目的。ページ移動は下部ボタンと左サイドバーの画面移動サポートに
    # 一本化する。
    st.divider()

    if active_page == ARTICLE_PAGE_BASIC:
        _render_page_1_basic()
    elif active_page == ARTICLE_PAGE_KEYWORD:
        _render_page_2_keyword_and_detail_entry()
    elif active_page == ARTICLE_PAGE_OFFICIAL:
        _render_page_3_official_info()
    elif active_page == ARTICLE_PAGE_STYLE:
        _render_page_4_writing_style()
    elif active_page == ARTICLE_PAGE_DRAFT:
        _render_page_5_draft(
            outputs_dir=outputs_dir,
            openai_api_key=openai_api_key,
            use_real_api=use_real_api,
        )
    else:
        _render_page_6_precheck()

    st.divider()
    _render_page_nav_buttons(position="bottom")
    _backup_article_inputs()
    _backup_shadow_state()
    _sync_form_data_stage1_from_widgets()

    _render_debug_inputs_saved_panel()


# =========================
# 開発用：入力保持デバッグ（原因特定用の一時機能）
# =========================
# 1/6〜4/6の入力材料12項目について、widget key・article__inputs_saved・
# article__form_data・backup・shadowの各層に値が残っているかを本番画面で
# 確認するための一時デバッグ表示。本文・APIキー・secrets・環境変数は
# 一切表示せず、各値は先頭20文字のpreviewと文字数だけを表示する。
# 原因特定が終わったら、この関数とその呼び出し・チェックボックスごと
# 削除してよい（恒久機能ではない）。
DEBUG_INPUTS_SAVED_TOGGLE_KEY = "article__debug_inputs_saved"
_DEBUG_PREVIEW_CHARS = 20


def _debug_preview_text(value: str) -> str:
    text = str(value or "")
    if len(text) <= _DEBUG_PREVIEW_CHARS:
        return text
    return text[:_DEBUG_PREVIEW_CHARS] + "…"


def _debug_field_status(field: str) -> Dict[str, Any]:
    widget_key = KEYS[field]

    widget_present = widget_key in st.session_state
    widget_value = str(st.session_state.get(widget_key, "") or "") if widget_present else ""
    widget_state = "present" if (widget_present and not _is_blank(widget_value)) else (
        "blank" if widget_present else "missing"
    )

    inputs_saved_value = _get_inputs_saved_value(field)
    inputs_saved_state = "present" if not _is_blank(inputs_saved_value) else "blank"

    form_data_value = _get_form_data_value(field)
    form_data_state = "present" if not _is_blank(form_data_value) else "blank"

    backup = st.session_state.get("article__input_backup")
    backup_value = str(backup.get(widget_key, "") or "") if isinstance(backup, dict) else ""
    has_backup = not _is_blank(backup_value)

    shadow_key = SHADOW_KEYS.get(widget_key)
    shadow_value = str(st.session_state.get(shadow_key, "") or "") if shadow_key else ""
    has_shadow = not _is_blank(shadow_value)

    if widget_state == "missing" and inputs_saved_state == "present":
        judgement = "復元待ち状態"
    elif widget_state == "blank" and inputs_saved_state == "present":
        judgement = "reseed対象"
    elif widget_state in ("missing", "blank") and inputs_saved_state == "blank" and form_data_state == "present":
        judgement = "form_dataだけ残っている"
    elif widget_state in ("missing", "blank") and inputs_saved_state == "blank" and form_data_state == "blank":
        judgement = "正本が消えている"
    elif widget_state == "present" and inputs_saved_state == "blank":
        judgement = "on_change/ページ移動同期の失敗の可能性"
    elif widget_state == "present" and inputs_saved_state == "present":
        judgement = "正常候補"
    else:
        judgement = "-"

    return {
        "項目": field,
        "widget key": widget_key,
        "widgetキー有無": "あり" if widget_present else "なし",
        "widget値": {"present": "非空", "blank": "空", "missing": "(キー無し)"}[widget_state],
        "widget文字数": len(widget_value),
        "widget先頭20文字": _debug_preview_text(widget_value),
        "inputs_saved": "非空" if inputs_saved_state == "present" else "空",
        "inputs_saved文字数": len(inputs_saved_value),
        "inputs_saved先頭20文字": _debug_preview_text(inputs_saved_value),
        "form_data": "非空" if form_data_state == "present" else "空",
        "form_data文字数": len(form_data_value),
        "form_data先頭20文字": _debug_preview_text(form_data_value),
        "backup": "あり" if has_backup else "なし",
        "shadow": "あり" if has_shadow else "なし",
        "簡易判定": judgement,
    }


def _render_debug_inputs_saved_panel() -> None:
    show_debug = st.checkbox("開発用デバッグを表示する", key=DEBUG_INPUTS_SAVED_TOGGLE_KEY)
    if not show_debug:
        return

    with st.expander("開発用：入力保持デバッグ", expanded=True):
        st.caption(
            "本文・APIキー・secrets・環境変数は表示しません。"
            "各値は先頭20文字のプレビューと文字数だけを表示します。"
            "原因特定が終わったら削除する一時機能です。"
        )

        active_page = st.session_state.get(ARTICLE_ACTIVE_PAGE_KEY, "<未初期化>")
        restored_page = st.session_state.get(ARTICLE_SHADOW_RESTORED_PAGE_KEY, "<未初期化>")
        st.write(f"ARTICLE_ACTIVE_PAGE_KEY = {active_page}")
        st.write(f"ARTICLE_SHADOW_RESTORED_PAGE_KEY = {restored_page}")

        rows = [_debug_field_status(field) for field in ARTICLE_INPUTS_SAVED_STAGE1_FIELDS]
        st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_page_5_draft(
    *,
    outputs_dir: str,
    openai_api_key: str,
    use_real_api: bool,
) -> None:
    st.markdown("## ✨ 下書き作成")
    _render_pre_generate_input_summary()

    current_generation_evidence = "\n".join(_normalize_lines(_get_generation_evidence_text()))
    with st.container():
        st.markdown("### AIが生成に使う要点（自動整理）")
        _render_large_text_preview(
            title="生成に使う要点",
            body=current_generation_evidence,
            show_key="article__show_current_evidence_compact",
            preview_chars=PREVIEW_CHARS_EVIDENCE,
            button_key_suffix="generation_compact",
            empty_placeholder="まだ確認先が反映されていません。『公式情報・確認先』ページで確認先を入力し、『この確認先を下書きに反映する』を押すと、ここに表示されます。",
        )

    st.write("入力した内容をもとに、記事の下書きを作ります。あとで見直せるので、まずは出してみる感覚で大丈夫です。")
    st.caption("確認先を入力した場合は、先に『公式情報・確認先』ページで反映ボタンを押してください。")

    if st.button("✨ 下書きを作る", use_container_width=True, key="btn_article_generate"):
        # article__form_dataが正本のフィールド（consult_situation/question）を
        # 現在のwidget値で確実に同期しておく（on_changeの保険）。
        _sync_form_data_stage1_from_widgets()
        # 非表示ページのwidget keyがStreamlitの仕様で空扱いになっていた場合に
        # 備え、下書き生成本体が直接読むキーだけを対象に、form_data/backup/
        # shadowの非空値で安全に埋め直してから判定・生成に入る（明示クリア
        # 直後はform_data/backup/shadowも空のため、古い値は復活しない）。
        _restore_blank_generation_inputs_from_backup_or_shadow()
        situation, question = _get_current_consult_values()

        if not situation or not question:
            st.warning("『今の状況』と『知りたいこと』を入れてください。")
            # st.stop()はスクリプト全体を止め、render_article_ui末尾の
            # 下部ナビゲーション（戻る/次へ）まで止めてしまい、利用者が
            # ページ移動できず詰まる原因になっていた。このページの描画
            # だけを終えるreturnにし、下部ナビゲーションは必ず描画させる。
            return

        _sync_evidence_text_from_parts()

        sensitive_text = _collect_sensitive_scan_text()
        sensitive_check = _detect_sensitive_data(sensitive_text)
        if sensitive_check["risky"]:
            _render_sensitive_block_message(sensitive_check)
            return

        pre_errors = _preflight_block_generate_if_needed()
        if pre_errors:
            for message in pre_errors:
                st.error(message)
            return

        try:
            with st.spinner("構成を考えています..."):
                plan_text = generate_markdown(
                    prompt=_build_planning_prompt(),
                    model="gpt-4o-mini",
                    use_real_api=use_real_api,
                    openai_api_key=openai_api_key,
                    timeout_sec=60,
                )

            with st.spinner("本文を書いています..."):
                raw_text = generate_markdown(
                    prompt=_build_writing_prompt(plan_text),
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

            st.session_state[KEYS["plan_result"]] = plan_text
            st.session_state[KEYS["last_text"]] = text
            st.session_state[KEYS["proof_evidence"]] = str(_get_effective_input_evidence_text())
            st.session_state[KEYS["proof_evidence_compact"]] = str(_get_generation_evidence_text())
            st.session_state[KEYS["proof_suggest"]] = str(st.session_state.get(KEYS["suggest"], ""))
            st.session_state[KEYS["proof_memo"]] = str(st.session_state.get(KEYS["memo"], ""))
            # last_text/plan_resultはarticle__form_dataにも保存する（正本化）。
            # 既存のsession_state側も、当面は互換のためこのまま更新し続ける。
            _set_form_data_value("plan_result", plan_text)
            _set_form_data_value("last_text", text)

            # 公開前に自分で直す本文(copy_text)が既に編集済みの場合、
            # 再生成のたびにAI初稿で勝手に上書きしない。空のときだけ
            # AI初稿からの初回コピーを行う。
            if _is_blank(_get_form_data_value("copy_text")):
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

        with st.expander("AIが最初に作った文章を見る", expanded=False):
            st.caption("見比べたいときだけ開いてください。")
            st.code(last_text, language="text")
            _render_copy_button(text=last_text, label="AI原文をコピー")

        plan_result = str(st.session_state.get(KEYS["plan_result"], "") or "")
        if not _is_blank(plan_result):
            with st.expander("記事の設計図を見る", expanded=False):
                st.caption("AIが本文を書く前に作った設計図です。見出し構成・結論・最初の行動を確認できます。")
                st.markdown(plan_result)

        st.info("次のページ『公開前確認』で、本文の確認と編集ができます。")

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


def _send_last_text_to_check_mode() -> None:
    """
    記事モードのAI下書き(last_text)を、文章チェックモードの入力欄へ渡す。
    手直しと最終確認は文章チェックモード側で行う設計のため、記事モードでは
    本文を書き換えず、そのまま渡すだけにする。
    """
    text = str(st.session_state.get(KEYS["last_text"], "") or "")
    st.session_state[_QUALITY_KEYS["check_text_saved"]] = text
    st.session_state[_QUALITY_KEYS["check_text_widget"]] = text
    st.session_state["menu_request"] = QUALITY_MENU_LABEL


def _render_page_6_precheck() -> None:
    st.markdown("## ✅ 下書きの確認")
    last_text = str(st.session_state.get(KEYS["last_text"], "") or "")

    if _is_blank(last_text):
        st.info("※まだ下書きは作られていません。『下書き作成』ページで『下書きを作る』を押してください。")
        return

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
        st.warning("AIが作った下書きには確認したい点があります。文章チェックモードで直してから、もう一度確認すると安全です。")

    st.markdown("### 📄 AIが作った下書き（読み取り専用）")
    st.caption("この本文はここでは直接編集できません。手直しと最終確認・保存は『文章チェック』モードで行ってください。")
    st.code(last_text, language="text")
    _render_copy_button(text=last_text, label="この下書きをコピー")

    st.divider()
    st.markdown("### 📋 文章チェックへ進む")
    st.caption("下の欄に貼り付けると、文章チェックモードの入力欄にそのまま反映されます。")
    if st.button(
        "📋 文章チェックへ貼り付ける",
        key="btn_article_send_to_check_page6",
        use_container_width=True,
    ):
        _send_last_text_to_check_mode()
        st.success("文章チェックモードへ貼り付けました。左メニューの『文章チェック』を開いてください。")
        st.rerun()
