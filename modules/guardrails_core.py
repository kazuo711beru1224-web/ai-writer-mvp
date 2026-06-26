
from __future__ import annotations

import re
from fractions import Fraction
from typing import List, Tuple, Set

from .guardrails_types import Finding, GuardrailResult, RiskLevel, max_level_from_list


# =========================
# A案：正規化（本文・根拠の両方）
# =========================
_ZEN2HAN_TABLE = str.maketrans({
    "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
    "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
    "％": "%", "．": ".", "，": ",",
    "＋": "+", "－": "-", "−": "-", "―": "-", "ー": "-",
    "／": "/", "　": " ",
})


def _normalize_for_compare(text: str) -> str:
    """
    取りこぼしを減らすための正規化。
    - 改行統一
    - 全角→半角（数字/記号）
    - カンマ削除（1,000→1000）
    - 全角スペース→半角
    - 連続空白を1個に
    """
    if not text:
        return ""
    t = str(text)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = t.translate(_ZEN2HAN_TABLE)
    t = t.replace(",", "")
    t = re.sub(r"[ \t]+", " ", t)
    return t.strip()


def _is_blank(text: str) -> bool:
    return (text is None) or (str(text).strip() == "")


def _canonicalize_token(token: str) -> str:
    """
    トークン同士の比較用に表記ゆれをさらに潰す。
    """
    if not token:
        return ""

    s = str(token).strip()
    s = s.translate(_ZEN2HAN_TABLE)
    s = s.replace(" ", "").replace("　", "")
    s = s.replace(",", "")

    # 単位表記ゆれ
    s = s.replace("ヶ月", "か月")
    s = s.replace("ヵ月", "か月")
    s = s.replace("ケ月", "か月")

    return s


# =========================
# 根拠が URL だけっぽいか（精度低下の検知用）
# =========================
def _evidence_seems_url_only(evidence_text: str) -> bool:
    """
    URLを除去しても文字がほぼ残らないなら「URLだけ」とみなす。
    例：URLだけ貼ってあると、数字照合が当たりにくい。
    """
    t = (evidence_text or "").strip()
    if not t:
        return True
    no_urls = re.sub(r"https?://\S+", "", t)
    no_urls = re.sub(r"\s+", "", no_urls)
    return len(no_urls) < 20


# =========================
# 数字系トークン抽出（正規化後前提）
# =========================
_TOKEN_PATTERNS = [
    # 金額
    r"\d+(?:\.\d+)?\s*円",
    r"\d+(?:\.\d+)?\s*千円",
    r"\d+(?:\.\d+)?\s*万円",
    r"\d+(?:\.\d+)?\s*万",
    r"\d+(?:\.\d+)?\s*億円",
    r"\d+(?:\.\d+)?\s*億",

    # 期限・単位
    r"\d+\s*(?:か月|ヶ月|ヵ月|ケ月|月|年|日|歳)",

    # 税率など
    r"\d+(?:\.\d+)?\s*%",

    # 分数（和文 / スラッシュ）
    r"\d+\s*分の\s*\d+",
    r"\d+\s*/\s*\d+",

    # 西暦（「2026年」「2026」）
    r"\d{4}\s*年",
    r"\b(?:19|20)\d{2}\b",

    # 和暦（令和6年 等）
    r"(?:令和|平成|昭和)\s*\d+\s*年",

    # スポーツやニュースで出やすい成績
    r"\d+\s*打数\s*\d+\s*安打",
    r"\d+\s*回\s*\d+\s*失点",
    r"\d+\s*奪三振",
    r"\d+\s*球",
]


def _extract_tokens(text_norm: str) -> List[str]:
    if not text_norm:
        return []

    hits: List[str] = []
    for pat in _TOKEN_PATTERNS:
        hits.extend(re.findall(pat, text_norm))

    seen = set()
    out: List[str] = []
    for x in hits:
        s = _canonicalize_token(x)
        if not s:
            continue
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


# =========================
# 分数 ↔ パーセント
# =========================
_JP_FRACTION_RE = re.compile(r"^(\d+)分の(\d+)$")
_SLASH_FRACTION_RE = re.compile(r"^(\d+)/(\d+)$")
_PERCENT_RE = re.compile(r"^(\d+(?:\.\d+)?)%$")


def _finite_percent_from_fraction(num: int, den: int) -> str:
    if den == 0:
        return ""

    frac = Fraction(num, den)
    d = frac.denominator
    while d % 2 == 0:
        d //= 2
    while d % 5 == 0:
        d //= 5
    if d != 1:
        return ""

    pct = float(frac * 100)
    s = f"{pct:.6f}".rstrip("0").rstrip(".")
    return f"{s}%"


def _fraction_aliases_from_parts(num: int, den: int) -> Set[str]:
    aliases: Set[str] = set()
    if den == 0:
        return aliases

    frac = Fraction(num, den)
    n = frac.numerator
    d = frac.denominator

    aliases.add(f"{n}/{d}")
    aliases.add(f"{d}分の{n}")

    pct = _finite_percent_from_fraction(n, d)
    if pct:
        aliases.add(pct)

    return aliases


def _aliases_from_percent(token: str) -> Set[str]:
    aliases: Set[str] = set()
    m = _PERCENT_RE.match(token)
    if not m:
        return aliases

    value = m.group(1)
    mapping = {"50": (1, 2), "25": (1, 4), "10": (1, 10)}
    if value in mapping:
        num, den = mapping[value]
        aliases |= _fraction_aliases_from_parts(num, den)

    return aliases


def _aliases_from_fraction(token: str) -> Set[str]:
    aliases: Set[str] = set()

    m1 = _JP_FRACTION_RE.match(token)
    if m1:
        den = int(m1.group(1))
        num = int(m1.group(2))
        aliases |= _fraction_aliases_from_parts(num, den)
        return aliases

    m2 = _SLASH_FRACTION_RE.match(token)
    if m2:
        num = int(m2.group(1))
        den = int(m2.group(2))
        aliases |= _fraction_aliases_from_parts(num, den)
        return aliases

    return aliases


# =========================
# 和暦 ↔ 西暦
# =========================
_ERA_YEAR_RE = re.compile(r"^(令和|平成|昭和)(\d+)年$")
_GREGORIAN_YEAR_RE = re.compile(r"^(19\d{2}|20\d{2})(?:年)?$")


def _era_to_gregorian(era: str, year_num: int) -> int:
    if era == "昭和":
        return 1925 + year_num
    if era == "平成":
        return 1988 + year_num
    if era == "令和":
        return 2018 + year_num
    return 0


def _gregorian_to_era_aliases(year: int) -> Set[str]:
    aliases: Set[str] = set()

    if year == 1989:
        aliases.add("昭和64年")
        aliases.add("平成1年")
        return aliases

    if year == 2019:
        aliases.add("平成31年")
        aliases.add("令和1年")
        return aliases

    if 1926 <= year <= 1988:
        aliases.add(f"昭和{year - 1925}年")
        return aliases

    if 1990 <= year <= 2018:
        aliases.add(f"平成{year - 1988}年")
        return aliases

    if year >= 2020:
        aliases.add(f"令和{year - 2018}年")
        return aliases

    return aliases


def _aliases_from_era_year(token: str) -> Set[str]:
    aliases: Set[str] = set()

    m = _ERA_YEAR_RE.match(token)
    if m:
        era = m.group(1)
        year_num = int(m.group(2))
        west = _era_to_gregorian(era, year_num)
        if west:
            aliases.add(str(west))
            aliases.add(f"{west}年")
        return aliases

    m2 = _GREGORIAN_YEAR_RE.match(token)
    if m2:
        west = int(m2.group(1))
        aliases |= _gregorian_to_era_aliases(west)
        aliases.add(str(west))
        aliases.add(f"{west}年")
        return aliases

    return aliases


def _expand_token_aliases(token: str) -> Set[str]:
    base = _canonicalize_token(token)
    aliases: Set[str] = {base}

    aliases |= _aliases_from_fraction(base)
    aliases |= _aliases_from_percent(base)
    aliases |= _aliases_from_era_year(base)

    return {a for a in aliases if a}


def _build_comparable_token_set(tokens: List[str]) -> Set[str]:
    out: Set[str] = set()
    for t in tokens:
        out |= _expand_token_aliases(t)
    return out


# =========================
# 日付っぽい表現（例示日付の検知）
# =========================
_MONTH_DAY_RE = re.compile(r"\d{1,2}\s*月\s*\d{1,2}\s*日")


def _extract_month_day_tokens(text_norm: str) -> List[str]:
    if not text_norm:
        return []

    hits = _MONTH_DAY_RE.findall(text_norm)
    seen = set()
    out: List[str] = []
    for x in hits:
        s = _canonicalize_token(x)
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _body_has_deadline_example_dates(text_norm: str) -> bool:
    dates = _extract_month_day_tokens(text_norm)
    return len(dates) >= 2


# =========================
# B案：国税庁URLベース許可
# =========================
def _has_nta_url(evidence_text: str) -> bool:
    if not evidence_text:
        return False
    e = str(evidence_text).lower()
    return "nta.go.jp" in e


def _build_missing_finding(*, missing: List[str], nta_allow: bool, url_only: bool) -> Finding:
    if nta_allow:
        if url_only:
            return Finding(
                level="CAUTION",
                code="国税庁URLあり_数字要確認",
                message=(
                    "本文に数字（年号・金額・期限など）が含まれていますが、"
                    "根拠欄がURL中心のため、自動照合では一致を確認しきれないものがあります。"
                    "根拠に国税庁URLがあるため危険判定ではなく注意判定にとどめていますが、"
                    "本文の数字は一次情報と必ず照合してください。"
                ),
                samples=missing[:12],
            )

        return Finding(
            level="CAUTION",
            code="国税庁URLあり_数字要確認",
            message=(
                "本文に数字（年号・金額・期限など）が含まれていますが、"
                "根拠欄との自動照合で一致しないものがあります。"
                "ただし根拠に国税庁URLがあるため、危険判定ではなく注意判定にとどめています。"
                "本文の数字は一次情報と必ず照合してください。"
            ),
            samples=missing[:12],
        )

    return Finding(
        level="RISK",
        code="根拠に数字未記載",
        message=(
            "本文に数字（年号・金額・期限など）が含まれていますが、"
            "根拠欄に同じ表記が見当たりません。"
            "根拠（一次情報URL / 資料名 / 大事な数字 / 要点）を追加するか、"
            "数字を削除・一般論に言い換えてください。"
        ),
        samples=missing[:12],
    )


def _build_url_only_finding() -> Finding:
    return Finding(
        level="CAUTION",
        code="根拠がURL中心",
        message=(
            "根拠欄がURL中心のため、本文中の数字（年号・金額・期限など）を自動照合しにくい状態です。"
            "URLに加えて、一次情報の『大事な数字』や『要点1〜3行』も根拠欄に入れると安全です。"
        ),
        samples=None,
    )


def _build_deadline_example_dates_finding() -> Finding:
    return Finding(
        level="CAUTION",
        code="期限の例示日付あり",
        message=(
            "本文に具体的な月日（例：1月10日、11月10日）が出ています。"
            "根拠に『10か月以内』のような一般ルールしか無い場合、"
            "自動照合では一致を確認しきれません。"
            "例示日付を使うときは、一次情報と計算が合っているか確認してください。"
        ),
        samples=None,
    )


# =========================
# テーマ判定（税・法律 / ニュース・見通し）
# =========================
def _is_tax_or_law_topic(body_text: str, evidence_text: str, suggest_text: str) -> bool:
    blob = "\n".join([
        str(body_text or ""),
        str(evidence_text or ""),
        str(suggest_text or ""),
    ]).lower()

    keywords = (
        "税", "税金", "相続税", "贈与税", "所得税", "法人税", "消費税", "住民税",
        "基礎控除", "控除", "税率", "申告", "期限", "延滞税", "加算税",
        "税制改正", "改正", "見直し", "施行", "令和", "年度",
        "法律", "法", "条文", "判例", "違法", "合法", "罰則", "規制",
    )
    return any(k.lower() in blob for k in keywords)


_LATEST_NEWS_WORDS = (
    "昨日", "今日", "最近", "直近", "速報", "試合結果", "何打数", "何安打",
    "何本", "先発", "登板", "ホームラン", "打率", "防御率", "失点", "奪三振",
    "ニュース", "時事", "進展", "現時点", "政府見解", "会見", "声明",
)

_FORECAST_WORDS = (
    "\u5e02\u5834\u898b\u901a\u3057",
    "\u696d\u7e3e\u898b\u901a\u3057",
    "\u666f\u6c17\u898b\u901a\u3057",
    "\u682a\u4fa1\u898b\u901a\u3057",
    "\u5e02\u5834\u4e88\u6e2c",
    "\u696d\u7e3e\u4e88\u60f3",
    "\u7d4c\u6e08\u898b\u901a\u3057",
)

_SPORTS_WORDS = (
    "打数", "安打", "打点", "本塁打", "ホームラン", "三振", "打率",
    "先発", "登板", "投手", "打者", "奪三振", "失点", "防御率", "球数",
    "大谷", "ドジャース", "試合結果",
)

_BATTING_WORDS = (
    "打数", "安打", "打点", "本塁打", "ホームラン", "打率", "出塁率", "長打率",
    "打撃", "打席", "打者", "ヒット", "猛打賞",
)

_PITCHING_WORDS = (
    "投手", "先発", "登板", "回", "失点", "自責点", "奪三振", "防御率", "球数",
    "クオリティースタート", "QS",
)

_GOVERNMENT_VIEW_WORDS = (
    "政府見解", "政府", "防衛省", "外務省", "内閣", "国家安全保障戦略",
    "方針", "白書", "見解", "声明",
)

_SECURITY_WORDS = (
    "中国", "ロシア", "北朝鮮", "安全保障", "防衛", "国防", "輸出解禁",
    "防衛装備", "武器輸出", "防衛装備移転", "自衛隊", "脅威",
)

_PROMOTION_WORDS = (
    "店頭", "POP", "販促", "売り場", "商品紹介", "来店客", "来店客数", "来店",
    "コンビニ", "おにぎり", "弁当", "パン", "飲み物", "お客様", "ドラッグストア",
    "軽食", "スムージー", "ホットコーヒー", "セール", "半額", "値引き",
)

_NEWS_RECENCY_STRONG_WORDS = (
    "速報", "ニュース", "事故", "転覆", "死傷者", "戦争", "侵攻", "停戦",
    "声明", "会談", "外交", "選挙", "災害", "政治", "政権", "政府", "法改正",
)


def _contains_any_phrase(text: str, phrases: Tuple[str, ...]) -> bool:
    t = str(text or "")
    return any(p in t for p in phrases)


def _is_latest_news_topic(body_text: str, evidence_text: str, suggest_text: str) -> bool:
    blob = "\n".join([
        str(body_text or ""),
        str(evidence_text or ""),
        str(suggest_text or ""),
    ])

    # 店頭POP・販促文脈では、「今」「今後」「必要です」などの弱い語だけで
    # 最新ニュース扱いにしない。ニュース系の強い語がある場合だけ注意を出す。
    if _contains_any_phrase(blob, _PROMOTION_WORDS):
        return _contains_any_phrase(blob, _NEWS_RECENCY_STRONG_WORDS)

    return _contains_any_phrase(blob, _LATEST_NEWS_WORDS) or _contains_any_phrase(blob, _SPORTS_WORDS)


def _is_forecast_topic(body_text: str, evidence_text: str, suggest_text: str) -> bool:
    blob = "\n".join([
        str(body_text or ""),
        str(evidence_text or ""),
        str(suggest_text or ""),
    ])

    # 店頭POP・販促文脈では、「今後」「必要です」「求められます」などを
    # 未来予測・時事見通しとは扱わない。言い回しチェック側に任せる。
    if _contains_any_phrase(blob, _PROMOTION_WORDS):
        return False

    return _contains_any_phrase(blob, _FORECAST_WORDS)


def _is_news_or_forecast_topic(body_text: str, evidence_text: str, suggest_text: str) -> bool:
    return _is_latest_news_topic(body_text, evidence_text, suggest_text) or _is_forecast_topic(body_text, evidence_text, suggest_text)


# =========================
# C案：文脈混同チェック（贈与税110万円 vs 相続税）
# =========================
def _maybe_tax_context_mixup_findings(body_text: str) -> List[Finding]:
    t = str(body_text or "")
    out: List[Finding] = []

    t_norm = _normalize_for_compare(t)
    t_norm_no_space = _canonicalize_token(t_norm)

    has_110man = ("110万円" in t_norm_no_space)
    has_souzoku = ("相続税" in t)
    has_zouyo = ("贈与税" in t) or ("贈与" in t)

    if has_110man and has_souzoku and (not has_zouyo):
        out.append(
            Finding(
                level="CAUTION",
                code="相続税と110万円の混同注意",
                message=(
                    "本文に『110万円』と『相続税』が同時に出ています。"
                    "110万円は贈与税で使われやすい数字です。"
                    "相続税の基礎控除と混同していないか、一次情報で文脈を確認してください。"
                ),
                samples=["110万円 / 相続税"],
            )
        )

    return out


# =========================
# D案：改正・見直し・制度変更トークの黄色信号
# =========================
_REVISION_WORDS = (
    "改正", "見直し", "変更", "制度改正", "最新情報", "近年",
    "新制度", "新しい制度", "改定", "施行", "拡充", "縮小",
    "最近", "最新", "変わる可能性", "影響を受ける", "影響があります",
    "確認することが重要", "常に確認", "変更される場合", "改正され",
)

_REVISION_STRONG_WORDS = (
    "改正", "見直し", "変更", "制度改正", "改定", "施行", "公布", "法改正", "税制改正",
)

_REVISION_VAGUE_WORDS = (
    "最近", "近年", "最新情報", "最新", "変わる可能性", "影響を受ける",
    "影響があります", "確認することが重要", "常に確認", "変更される場合",
)

_REVISION_TARGET_WORDS = (
    "基礎控除", "基礎控除額", "税率", "控除額", "申告期限", "申告", "納税",
    "加算税", "延滞税", "配偶者の税額軽減", "配偶者控除", "小規模宅地",
    "小規模宅地等の特例", "相続時精算課税", "暦年課税", "法定相続人",
)

_TOPIC_DRIFT_WORDS = (
    "申告期限", "申告", "延滞税", "加算税", "ペナルティ",
    "配偶者控除", "配偶者の税額軽減", "小規模宅地", "小規模宅地等の特例",
    "未成年者控除", "障害者控除", "相次相続控除", "外国税額控除",
)


def _find_revision_samples(body_text: str) -> List[str]:
    t = str(body_text or "")
    hits: List[str] = []
    for w in _REVISION_WORDS:
        if w in t and w not in hits:
            hits.append(w)
    return hits[:8]


def _split_text_units(text: str) -> List[str]:
    t = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    raw_parts = re.split(r"[\n。！？]", t)
    out: List[str] = []
    for part in raw_parts:
        s = part.strip()
        if s:
            out.append(s)
    return out


def _extract_revision_units(text: str) -> List[str]:
    units = _split_text_units(text)
    return [u for u in units if _contains_any_phrase(u, _REVISION_WORDS)]


def _extract_topic_targets(text: str) -> List[str]:
    t = str(text or "")
    hits: List[str] = []
    for w in _REVISION_TARGET_WORDS:
        if w in t and w not in hits:
            hits.append(w)
    return hits


def _has_year_or_effective_marker(text: str) -> bool:
    t = str(text or "")
    if re.search(r"(19\d{2}|20\d{2})年", t):
        return True
    if re.search(r"(令和|平成|昭和)\s*\d+\s*年", t):
        return True
    if "施行" in t or "公布" in t or "年度" in t:
        return True
    return False


def _evidence_revision_support_strength(evidence_text: str, required_targets: List[str]) -> str:
    units = _extract_revision_units(evidence_text)
    if not units:
        return "none"

    has_any_revision = False
    has_strong = False

    for u in units:
        if _contains_any_phrase(u, _REVISION_STRONG_WORDS):
            has_any_revision = True

            unit_targets = _extract_topic_targets(u)
            target_match = False
            if required_targets:
                target_match = any(t in unit_targets for t in required_targets)
            else:
                target_match = False

            if _has_year_or_effective_marker(u) and target_match:
                has_strong = True
                break

    if has_strong:
        return "strong"
    if has_any_revision:
        return "weak"
    return "none"


def _maybe_revision_findings(body_text: str, evidence_text: str, suggest_text: str) -> List[Finding]:
    out: List[Finding] = []

    # ニュース系・見通し系には制度改正向けの警告を出さない。
    # ここは税・法律・制度テーマ専用の番兵として扱う。
    if _is_news_or_forecast_topic(body_text, evidence_text, suggest_text):
        return out

    if not _is_tax_or_law_topic(body_text, evidence_text, suggest_text):
        return out

    body = str(body_text or "")
    revision_units = _extract_revision_units(body)
    if not revision_units:
        return out

    body_targets = _extract_topic_targets(body)
    support = _evidence_revision_support_strength(evidence_text, body_targets)

    body_has_vague_revision = any(_contains_any_phrase(u, _REVISION_VAGUE_WORDS) for u in revision_units)
    body_has_strong_revision = any(_contains_any_phrase(u, _REVISION_STRONG_WORDS) for u in revision_units)

    if body_has_vague_revision and support != "strong":
        out.append(
            Finding(
                level="CAUTION",
                code="改正トーク要確認",
                message=(
                    "本文に『最近・近年・最新情報・変わる可能性』など、制度変更をふわっと示す表現があります。"
                    "ただし根拠欄には、同じ改正内容を具体的に裏付ける説明（年号・施行・対象項目など）が十分に見当たりません。"
                    "税・法律テーマでは、改正の話題は一次情報に書かれている内容だけに絞るのが安全です。"
                ),
                samples=_find_revision_samples(body),
            )
        )
        return out

    if body_has_strong_revision and support in ("none", "weak"):
        out.append(
            Finding(
                level="CAUTION",
                code="改正根拠の具体性不足",
                message=(
                    "本文に『改正・見直し・変更』など制度変更を示す表現がありますが、"
                    "根拠欄では改正内容の具体性が足りません。"
                    "『何が・いつ・どう変わったか』が一次情報で確認できる場合だけ書くのが安全です。"
                ),
                samples=_find_revision_samples(body),
            )
        )

    return out


# =========================
# E案：主題からの横滑り（税・法律テーマ）
# =========================
def _main_heading_text(body_text: str) -> str:
    for line in str(body_text or "").splitlines():
        ln = line.strip()
        if not ln:
            continue
        if ln.startswith("#"):
            return ln.lstrip("#").strip()
    return ""


def _find_topic_drift_samples(body_text: str) -> List[str]:
    t = str(body_text or "")
    hits: List[str] = []
    for w in _TOPIC_DRIFT_WORDS:
        if w in t and w not in hits:
            hits.append(w)
    return hits[:8]


def _maybe_topic_drift_findings(body_text: str, evidence_text: str, suggest_text: str) -> List[Finding]:
    out: List[Finding] = []

    if not _is_tax_or_law_topic(body_text, evidence_text, suggest_text):
        return out

    heading = _main_heading_text(body_text)
    body = str(body_text or "")
    ev = str(evidence_text or "")

    if not heading:
        return out

    heading_is_kisokojo = ("基礎控除" in heading)
    body_has_drift = _contains_any_phrase(body, _TOPIC_DRIFT_WORDS)

    if heading_is_kisokojo and body_has_drift:
        out.append(
            Finding(
                level="CAUTION",
                code="主題外論点の混入注意",
                message=(
                    "本文の主題は『基礎控除』ですが、申告・加算税・延滞税・特例など別論点にも話が広がっています。"
                    "補足として触れるのは構いませんが、主題から離れすぎると読者に誤解を与えやすくなります。"
                    "見出し構成や本文の比重を見直してください。"
                ),
                samples=_find_topic_drift_samples(body),
            )
        )

    special_terms = ("小規模宅地等の特例", "配偶者控除", "配偶者の税額軽減")
    body_terms = [w for w in special_terms if w in body]
    ev_terms = [w for w in special_terms if w in ev]
    if body_terms and not ev_terms:
        out.append(
            Finding(
                level="CAUTION",
                code="根拠外の特例言及",
                message=(
                    "本文に特例や控除の名称が出ていますが、根拠欄に同じ名称の説明が見当たりません。"
                    "税・法律テーマでは、制度名や特例名は一次情報にあるものだけを扱うのが安全です。"
                ),
                samples=body_terms[:8],
            )
        )

    return out


# =========================
# F案：ニュース系の根拠一致チェック
# =========================
def _count_contains(text: str, phrases: Tuple[str, ...]) -> int:
    t = str(text or "")
    return sum(1 for p in phrases if p in t)


def _sports_alignment_findings(body_text: str, evidence_text: str) -> List[Finding]:
    out: List[Finding] = []
    body = str(body_text or "")
    ev = str(evidence_text or "")

    body_batting = _count_contains(body, _BATTING_WORDS)
    ev_batting = _count_contains(ev, _BATTING_WORDS)
    ev_pitching = _count_contains(ev, _PITCHING_WORDS)

    if body_batting >= 2 and ev_batting == 0 and ev_pitching >= 2:
        out.append(
            Finding(
                level="CAUTION",
                code="ニュース根拠の主題ずれ",
                message=(
                    "本文では打撃成績や打撃の調子に踏み込んでいますが、根拠欄は投手成績中心です。"
                    "確認先と本文の主題がずれているため、根拠にない打撃情報を補っている可能性があります。"
                    "打撃成績の記事を別に確認するか、『この資料では打撃成績までは確認できません』と控えめに書いてください。"
                ),
                samples=["本文：打撃 / 根拠：投手成績"],
            )
        )

    batting_eval_words = ("上向き", "好調", "改善", "安定感", "フォーム")
    if _contains_any_phrase(body, batting_eval_words) and (not _contains_any_phrase(ev, batting_eval_words)):
        if body_batting >= 1 or ("打撃" in body):
            out.append(
                Finding(
                    level="CAUTION",
                    code="ニュース評価表現の根拠不足",
                    message=(
                        "本文に『上向き』『好調』『改善』などの評価表現がありますが、根拠欄に同じ評価材料が見当たりません。"
                        "ニュース系では、評価よりも確認できた事実を優先し、根拠にない推測は避けるのが安全です。"
                    ),
                    samples=["上向き / 好調 / 改善"],
                )
            )

    return out


def _government_view_alignment_findings(body_text: str, evidence_text: str) -> List[Finding]:
    out: List[Finding] = []
    body = str(body_text or "")
    ev = str(evidence_text or "")

    if _contains_any_phrase(body, _GOVERNMENT_VIEW_WORDS) and not _contains_any_phrase(ev, _GOVERNMENT_VIEW_WORDS):
        out.append(
            Finding(
                level="CAUTION",
                code="政府見解の根拠不足",
                message=(
                    "本文で政府見解や政府方針に触れていますが、根拠欄に政府資料や公式見解の語が十分に見当たりません。"
                    "報道記事だけで政府見解まで言い切るのは危険です。政府資料や白書、公式発表を追加してください。"
                ),
                samples=["政府見解 / 政府方針"],
            )
        )

    return out


def _security_scope_findings(body_text: str, evidence_text: str) -> List[Finding]:
    out: List[Finding] = []
    body = str(body_text or "")
    ev = str(evidence_text or "")

    body_security = _count_contains(body, _SECURITY_WORDS)
    ev_security = _count_contains(ev, _SECURITY_WORDS)

    if body_security >= 4 and ev_security <= 1:
        out.append(
            Finding(
                level="CAUTION",
                code="時事テーマの根拠範囲超過",
                message=(
                    "本文は安全保障・国防・周辺国情勢まで広く扱っていますが、根拠欄はその一部の説明にとどまっています。"
                    "根拠1本で言える範囲を超えて広がると、事実と推測が混ざりやすくなります。"
                    "主題を絞るか、追加の確認先を入れてください。"
                ),
                samples=["安全保障 / 国防 / 周辺国情勢"],
            )
        )

    return out


def _future_tone_findings(body_text: str, evidence_text: str, suggest_text: str) -> List[Finding]:
    out: List[Finding] = []
    body = str(body_text or "")

    if not (_is_latest_news_topic(body_text, evidence_text, suggest_text) or _is_forecast_topic(body_text, evidence_text, suggest_text)):
        return out

    strong_future = ("必要です", "求められます", "不可欠です", "必要となるでしょう", "期待できます", "上向き")
    if _contains_any_phrase(body, strong_future):
        out.append(
            Finding(
                level="CAUTION",
                code="ニュース系の断定調注意",
                message=(
                    "最新ニュース・時事系や見通し系では、断定的な表現を使うと根拠外の推測が混ざりやすくなります。"
                    "『現時点では』『考えられます』『可能性があります』など、慎重な言い方に寄せるのが安全です。"
                ),
                samples=[w for w in strong_future if w in body][:8],
            )
        )

    return out


def _latest_news_minimum_caution_finding() -> Finding:
    return Finding(
        level="CAUTION",
        code="最新情報は最終確認前提",
        message=(
            "\u6700\u65b0\u30cb\u30e5\u30fc\u30b9\u30fb\u6642\u4e8b\u7cfb\u306e\u5185\u5bb9\u306f\u66f4\u65b0\u304c\u65e9\u304f\u3001\u60c5\u5831\u304c\u5909\u308f\u308b\u3053\u3068\u304c\u3042\u308a\u307e\u3059\u3002"
            "\u516c\u958b\u524d\u306b\u3001\u53c2\u7167\u65e5\u3068\u767a\u8868\u5143\u3092\u78ba\u8a8d\u3057\u3001"
            "\u5927\u4f1a\u30fb\u5b98\u516c\u5e81\u306a\u3069\u306e\u516c\u5f0f\u60c5\u5831\u3068\u4fe1\u983c\u3067\u304d\u308b\u5831\u9053\u306a\u3069\u3001"
            "\u8907\u6570\u306e\u78ba\u8a8d\u5148\u3067\u7167\u5408\u3057\u3066\u304f\u3060\u3055\u3044\u3002"
        ),
        samples=None,
    )


def _maybe_news_alignment_findings(body_text: str, evidence_text: str, suggest_text: str) -> List[Finding]:
    out: List[Finding] = []
    is_news = _is_latest_news_topic(body_text, evidence_text, suggest_text)
    is_forecast = _is_forecast_topic(body_text, evidence_text, suggest_text)

    if not (is_news or is_forecast):
        return out

    out.extend(_sports_alignment_findings(body_text, evidence_text))
    out.extend(_government_view_alignment_findings(body_text, evidence_text))
    out.extend(_security_scope_findings(body_text, evidence_text))
    out.extend(_future_tone_findings(body_text, evidence_text, suggest_text))
    out.append(_latest_news_minimum_caution_finding())
    return out



def _has_bonus_divide_by_twelve_evidence(evidence_text: str) -> bool:
    evidence = str(evidence_text or "")
    if "標準賞与額" not in evidence:
        return False
    return bool(re.search(r"(?:÷|/)\s*12|12\s*で\s*割", evidence))


def _split_claim_sentences(text: str) -> List[str]:
    normalized = str(text or "").replace(chr(10), "。")
    return [
        sentence.strip()
        for sentence in normalized.split("。")
        if sentence.strip()
    ]


def _formula_alignment_findings(body_text: str, evidence_text: str) -> List[Finding]:
    if not _has_bonus_divide_by_twelve_evidence(evidence_text):
        return []

    mismatches: List[str] = []
    for sentence in _split_claim_sentences(body_text):
        has_bonus = "賞与" in sentence
        divides_by_count = bool(
            re.search(r"(?:支給)?回数.{0,12}割", sentence)
        )
        if has_bonus and divides_by_count:
            mismatches.append(sentence)

    if not mismatches:
        return []

    return [
        Finding(
            level="RISK",
            code="根拠式との不一致",
            message=(
                "本文の賞与の計算方法が、根拠欄の"
                "「標準賞与額の合計÷12」と一致していません。"
            ),
            samples=mismatches[:8],
        )
    ]


def _is_high_impact_claim_topic(
    body_text: str,
    evidence_text: str,
    suggest_text: str,
) -> bool:
    blob = " ".join(
        [str(body_text or ""), str(evidence_text or ""), str(suggest_text or "")]
    )
    words = (
        "年金", "税", "相続", "贈与", "法律",
        "登記", "保険", "医療", "薬", "診断",
        "治療", "金融", "控除", "給付",
        "基準額",
    )
    return any(word in blob for word in words)


def _claim_alignment_pending_findings(
    body_text: str,
    evidence_text: str,
    suggest_text: str,
) -> List[Finding]:
    if _is_blank(evidence_text):
        return []
    if not _is_high_impact_claim_topic(body_text, evidence_text, suggest_text):
        return []

    body_norm = _normalize_for_compare(body_text)
    has_number = bool(_extract_tokens(body_norm))
    signals = (
        "計算", "算定", "合算", "割",
        "基準額", "税率", "控除",
        "期限", "締切", "対象者",
    )
    has_signal = any(signal in str(body_text or "") for signal in signals)

    if not (has_number or has_signal):
        return []

    return [
        Finding(
            level="CAUTION",
            code="重要主張の照合未完了",
            message=(
                "重要な数字・計算式・条件を扱っていますが、"
                "一次情報との主張単位の照合はまだ実装されていません。"
            ),
            samples=None,
        )
    ]


def _finalize(level: RiskLevel, findings: List[Finding]) -> GuardrailResult:
    return GuardrailResult(level=level, findings=tuple(findings))


def evaluate_guardrails_core(
    body_text: str,
    evidence_text: str = "",
    suggest_text: str = "",
) -> GuardrailResult:
    """
    共通フェンス：
    A) 正規化＋数字照合（表記ゆれ吸収）
    B) 国税庁URLが根拠にある場合は missing を RISK→CAUTION に緩和
    C) 文脈混同（110万円×相続税）を CAUTION で警告
    D) 税・法律テーマでの「改正・見直し・制度変更」トークを CAUTION で警告
    E) 主題からの横滑りや根拠外の特例言及を CAUTION で警告
    F) ニュース系・見通し系の根拠一致チェック
       - 質問や本文の主題と根拠のズレ
       - 根拠にない数字や成績の補完
       - 根拠不足なら控えめに逃がす
       - ニュース系は原則 SAFE にしない
    """
    body_norm = _normalize_for_compare(body_text)
    ev_norm = _normalize_for_compare(evidence_text)

    findings: List[Finding] = []
    body_tokens = _extract_tokens(body_norm)

    if body_tokens and _is_blank(ev_norm):
        findings.append(
            Finding(
                level="RISK",
                code="根拠未入力",
                message=(
                    "本文に数字（年号・金額・期限など）が含まれていますが、根拠メモが空です。"
                    "一次情報（URL / 資料名 / 大事な数字 / 要点）を入力してください。"
                ),
                samples=body_tokens[:12],
            )
        )
        level = max_level_from_list([f.level for f in findings])
        return _finalize(level, findings)

    nta_allow = _has_nta_url(evidence_text)
    url_only = (not _is_blank(ev_norm)) and _evidence_seems_url_only(evidence_text)

    if url_only and body_tokens:
        findings.append(_build_url_only_finding())

    if body_tokens and (not _is_blank(ev_norm)):
        ev_tokens = _extract_tokens(ev_norm)
        ev_token_set = _build_comparable_token_set(ev_tokens)

        missing: List[str] = []
        for tok in body_tokens:
            aliases = _expand_token_aliases(tok)
            if aliases.isdisjoint(ev_token_set):
                missing.append(tok)

        if missing:
            findings.append(
                _build_missing_finding(
                    missing=missing,
                    nta_allow=nta_allow,
                    url_only=url_only,
                )
            )

    if url_only and _body_has_deadline_example_dates(body_norm) and _is_tax_or_law_topic(body_text, evidence_text, suggest_text):
        findings.append(_build_deadline_example_dates_finding())

    findings.extend(_maybe_tax_context_mixup_findings(body_text))
    findings.extend(_maybe_revision_findings(body_text, evidence_text, suggest_text))
    findings.extend(_maybe_topic_drift_findings(body_text, evidence_text, suggest_text))
    findings.extend(_maybe_news_alignment_findings(body_text, evidence_text, suggest_text))

    formula_findings = _formula_alignment_findings(body_text, evidence_text)
    findings.extend(formula_findings)
    if not formula_findings:
        findings.extend(
            _claim_alignment_pending_findings(body_text, evidence_text, suggest_text)
        )

    level = max_level_from_list([f.level for f in findings]) if findings else "SAFE"
    return _finalize(level, findings)


def evaluate_guardrails(
    *,
    body_text: str,
    evidence_text: str = "",
    suggest_text: str = "",
    root_mode: bool = False,
    **kwargs,
) -> GuardrailResult:
    _ = root_mode
    _ = kwargs
    return evaluate_guardrails_core(
        body_text=body_text,
        evidence_text=evidence_text,
        suggest_text=suggest_text,
    )
