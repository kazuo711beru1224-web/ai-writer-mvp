from __future__ import annotations

import re
from typing import List, Sequence, Tuple

from .guardrails_types import Finding, GuardrailResult, RiskLevel, max_level_from_list


# =========================================
# 基本設定
# =========================================
DEFAULT_MAX_SENTENCE_LEN = 80

# 表記ゆれ：左が検出対象、右が推奨表記
CANONICAL_REPLACEMENTS: Tuple[Tuple[str, str], ...] = (
    ("下さい", "ください"),
    ("出来る", "できる"),
    ("及び", "および"),
    ("又は", "または"),
    ("様々", "さまざま"),
    ("有る", "ある"),
    ("無い", "ない"),
    ("頂く", "いただく"),
    ("致します", "いたします"),
    ("ケ月", "か月"),
    ("ヶ月", "か月"),
    ("ヵ月", "か月"),
    ("カ月", "か月"),
    ("１つ", "1つ"),
)

# 誤字・不自然表現候補：左が検出対象、右が修正候補
TYPO_SUSPECTS: Tuple[Tuple[str, str], ...] = (
    ("本正確", "正確"),
    ("専攻の知識", "専門の知識"),
    ("それぞれの住所に適用される税率", "それぞれの取得金額に適用される税率"),
    ("相続税税", "相続税"),
)

# 文末カテゴリ
DESU_MASU_PATTERNS: Tuple[str, ...] = (
    "です",
    "ます",
    "でした",
    "ました",
    "ください",
    "でしょう",
    "ません",
)
DEARU_PATTERNS: Tuple[str, ...] = (
    "である",
    "だ",
    "だった",
    "であった",
)

# 箇条書きの頭
BULLET_RE = re.compile(r"^\s*(?:[-・●■□▲△▶▷]|[0-9０-９]+[.)）])\s*")

# 案件ルール用
VALID_TONES = {"desu_masu", "dearu"}
KAGETSU_VARIANTS: Tuple[str, ...] = ("ヶ月", "ヵ月", "ケ月", "カ月", "か月")
KUDASAI_KANJI = "下さい"
KUDASAI_HIRAGANA = "ください"
DEKIRU_KANJI = "出来る"
DEKIRU_HIRAGANA = "できる"


# =========================================
# 小道具
# =========================================
def _is_blank(text: str) -> bool:
    return (text is None) or (str(text).strip() == "")


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    t = str(text)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    return t


def _split_sentences(text: str) -> List[str]:
    t = _normalize_text(text)

    out: List[str] = []
    for raw_line in t.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # 箇条書きは1文として扱う
        if BULLET_RE.match(line):
            out.append(line)
            continue

        parts = re.split(r"(?<=[。！？!?])", line)
        for part in parts:
            s = str(part).strip()
            if s:
                out.append(s)
    return out


def _trim_sample(text: str, limit: int = 60) -> str:
    s = str(text or "").strip()
    if len(s) <= limit:
        return s
    return s[:limit] + "…"


def _sentence_style_label(sentence: str) -> str:
    s = str(sentence or "").strip()
    s = re.sub(r"[。！？!?]+$", "", s)

    for pat in DESU_MASU_PATTERNS:
        if s.endswith(pat):
            return "desu_masu"

    for pat in DEARU_PATTERNS:
        if s.endswith(pat):
            return "dearu"

    return "other"


def _sentence_tail_key(sentence: str) -> str:
    s = str(sentence or "").strip()
    s = re.sub(r"[。！？!?]+$", "", s)
    s = BULLET_RE.sub("", s).strip()

    for pat in (
        "しています",
        "となります",
        "できます",
        "ください",
        "でしょう",
        "されています",
        "なります",
        "あります",
        "です",
        "ます",
        "である",
        "だ",
    ):
        if s.endswith(pat):
            return pat

    return s[-4:] if len(s) >= 4 else s


def _is_list_like(sentence: str) -> bool:
    return bool(BULLET_RE.match(str(sentence or "").strip()))


def _make_finding(
    *,
    level: RiskLevel,
    code: str,
    message: str,
    samples: Sequence[str] | None = None,
) -> Finding:
    return Finding(
        level=level,
        code=code,
        message=message,
        samples=tuple(samples) if samples else None,
    )


def _normalize_preferred_tone(preferred_tone: str | None) -> str | None:
    if not preferred_tone:
        return None

    v = str(preferred_tone).strip().lower()
    aliases = {
        "desu_masu": "desu_masu",
        "ですます": "desu_masu",
        "です・ます": "desu_masu",
        "ですます調": "desu_masu",
        "です・ます調": "desu_masu",
        "dearu": "dearu",
        "だである": "dearu",
        "だ・である": "dearu",
        "だである調": "dearu",
        "だ・である調": "dearu",
    }
    normalized = aliases.get(v)
    if normalized in VALID_TONES:
        return normalized
    return None


# =========================================
# A. 文体チェック
# =========================================
def _check_style_mixed(text: str) -> List[Finding]:
    findings: List[Finding] = []

    sentences = _split_sentences(text)
    if not sentences:
        return findings

    labels = [_sentence_style_label(s) for s in sentences]
    has_desu_masu = "desu_masu" in labels
    has_dearu = "dearu" in labels

    if has_desu_masu and has_dearu:
        samples: List[str] = []
        for s, label in zip(sentences, labels):
            if label in ("desu_masu", "dearu"):
                samples.append(_trim_sample(s))
            if len(samples) >= 6:
                break

        findings.append(
            _make_finding(
                level="CAUTION",
                code="文体混在_ですますとだである",
                message=(
                    "本文の中で『です・ます調』と『だ・である調』が混ざっています。"
                    "読み味がぶれやすいため、どちらかにそろえるのがおすすめです。"
                ),
                samples=samples,
            )
        )

    return findings


def _check_tail_repetition(text: str) -> List[Finding]:
    findings: List[Finding] = []

    sentences = _split_sentences(text)
    if len(sentences) < 3:
        return findings

    repeated_groups: List[str] = []

    for i in range(len(sentences) - 2):
        s1, s2, s3 = sentences[i], sentences[i + 1], sentences[i + 2]

        # 箇条書き3連続は拾わない
        if _is_list_like(s1) or _is_list_like(s2) or _is_list_like(s3):
            continue

        t1 = _sentence_tail_key(s1)
        t2 = _sentence_tail_key(s2)
        t3 = _sentence_tail_key(s3)

        # 語尾一致
        if not (t1 and t1 == t2 == t3):
            continue

        # あまりに短い尾や「る」だけ等は除外
        if len(t1) < 2:
            continue

        # 文体が全部 other の場合は拾わない
        labels = (
            _sentence_style_label(s1),
            _sentence_style_label(s2),
            _sentence_style_label(s3),
        )
        if labels == ("other", "other", "other"):
            continue

        sample = " / ".join([
            _trim_sample(s1, 30),
            _trim_sample(s2, 30),
            _trim_sample(s3, 30),
        ])
        if sample not in repeated_groups:
            repeated_groups.append(sample)

    if repeated_groups:
        findings.append(
            _make_finding(
                level="CAUTION",
                code="語尾3連続",
                message=(
                    "同じ語尾が続いています。単調に見えやすいので、"
                    "一部の文を言い換えると読みやすくなります。"
                ),
                samples=repeated_groups[:5],
            )
        )

    return findings


def _check_long_sentences(text: str, max_len: int = DEFAULT_MAX_SENTENCE_LEN) -> List[Finding]:
    findings: List[Finding] = []

    long_sentences: List[str] = []
    for s in _split_sentences(text):
        if _is_list_like(s):
            continue
        if len(s) > max_len:
            long_sentences.append(f"{len(s)}文字：{_trim_sample(s)}")

    if long_sentences:
        findings.append(
            _make_finding(
                level="CAUTION",
                code="一文が長い",
                message=(
                    f"一文が長めです。{max_len}文字を超える文は、"
                    "2つに分けると読みやすくなります。"
                ),
                samples=long_sentences[:8],
            )
        )

    return findings


# =========================================
# B. 表記ゆれチェック
# =========================================
def _check_canonical_replacements(text: str) -> List[Finding]:
    findings: List[Finding] = []

    found: List[str] = []
    for src, dst in CANONICAL_REPLACEMENTS:
        if src in text:
            found.append(f"{src} → {dst}")

    if found:
        findings.append(
            _make_finding(
                level="CAUTION",
                code="表記ゆれ候補",
                message=(
                    "表記をそろえたい箇所があります。"
                    "記事全体で同じ書き方にすると、読みやすくなります。"
                ),
                samples=found[:12],
            )
        )

    return findings


def _check_symbol_rules(text: str) -> List[Finding]:
    findings: List[Finding] = []

    symbol_samples: List[str] = []

    if "％" in text:
        symbol_samples.append("％ → %")

    if "(" in text or ")" in text:
        symbol_samples.append("( ) → （ ）")

    if "ヶ月" in text:
        symbol_samples.append("ヶ月 → か月")
    if "ヵ月" in text:
        symbol_samples.append("ヵ月 → か月")
    if "ケ月" in text:
        symbol_samples.append("ケ月 → か月")

    if symbol_samples:
        findings.append(
            _make_finding(
                level="CAUTION",
                code="記号表記のゆれ",
                message=(
                    "記号や単位の表記にゆれがあります。"
                    "表記をそろえると、文章全体が整って見えます。"
                ),
                samples=symbol_samples[:12],
            )
        )

    return findings


# =========================================
# C. 誤字候補チェック
# =========================================
def _check_typo_suspects(text: str) -> List[Finding]:
    findings: List[Finding] = []

    found: List[str] = []
    for bad, good in TYPO_SUSPECTS:
        if bad in text:
            found.append(f"{bad} → {good}")

    if found:
        findings.append(
            _make_finding(
                level="CAUTION",
                code="誤字候補",
                message=(
                    "誤字や不自然な言い回しの可能性がある箇所があります。"
                    "公開前に一度見直すと安心です。"
                ),
                samples=found[:12],
            )
        )

    return findings


def _check_duplicate_word_suspects(text: str) -> List[Finding]:
    findings: List[Finding] = []

    suspects: List[str] = []

    # 漢字語の重複（例：相続税税）
    for m in re.finditer(r"([一-龥ぁ-んァ-ヶA-Za-z]+)\1", text):
        token = m.group(0).strip()
        if len(token) >= 4:
            suspects.append(token)

    # 既知の重複っぽい語を優先補足
    for known in ("相続税税", "消費税税", "法人税税", "所得税税"):
        if known in text and known not in suspects:
            suspects.append(known)

    if suspects:
        findings.append(
            _make_finding(
                level="CAUTION",
                code="重複語候補",
                message=(
                    "同じ語が重なっている可能性があります。"
                    "誤字のことがあるため、公開前に見直すと安心です。"
                ),
                samples=suspects[:8],
            )
        )

    return findings


# =========================================
# D. 案件ルールチェック
# =========================================
def _check_preferred_tone(text: str, preferred_tone: str | None) -> List[Finding]:
    findings: List[Finding] = []

    tone = _normalize_preferred_tone(preferred_tone)
    if tone is None:
        return findings

    sentences = _split_sentences(text)
    if not sentences:
        return findings

    wrong_samples: List[str] = []

    for s in sentences:
        if _is_list_like(s):
            continue

        label = _sentence_style_label(s)
        if label == "other":
            continue

        if label != tone:
            wrong_samples.append(_trim_sample(s))
            if len(wrong_samples) >= 8:
                break

    if not wrong_samples:
        return findings

    expected = "です・ます調" if tone == "desu_masu" else "だ・である調"
    findings.append(
        _make_finding(
            level="CAUTION",
            code="案件ルール_文体指定",
            message=(
                f"この案件は『{expected}』でそろえたい設定です。"
                "別の文体が混ざっていないか確認してください。"
            ),
            samples=wrong_samples,
        )
    )
    return findings


def _check_preferred_percent_style(text: str, prefer_halfwidth_percent: bool) -> List[Finding]:
    findings: List[Finding] = []

    if not prefer_halfwidth_percent:
        return findings

    if "％" not in text:
        return findings

    findings.append(
        _make_finding(
            level="CAUTION",
            code="案件ルール_パーセント半角",
            message=(
                "この案件はパーセント記号を半角の『%』でそろえたい設定です。"
                "全角の『％』が混ざっていないか確認してください。"
            ),
            samples=["％ → %"],
        )
    )
    return findings


def _check_preferred_kagetsu_style(text: str, prefer_kagetsu_style: str | None) -> List[Finding]:
    findings: List[Finding] = []

    target = str(prefer_kagetsu_style or "").strip()
    if target == "":
        return findings

    if target not in KAGETSU_VARIANTS:
        return findings

    found: List[str] = []
    for variant in KAGETSU_VARIANTS:
        if variant == target:
            continue
        if variant in text:
            found.append(f"{variant} → {target}")

    if found:
        findings.append(
            _make_finding(
                level="CAUTION",
                code="案件ルール_か月表記",
                message=(
                    f"この案件は期間表記を『{target}』でそろえたい設定です。"
                    "別の書き方が混ざっていないか確認してください。"
                ),
                samples=found[:12],
            )
        )

    return findings


def _check_preferred_kudasai_style(text: str, prefer_kudasai: bool) -> List[Finding]:
    findings: List[Finding] = []

    if not prefer_kudasai:
        return findings

    if KUDASAI_KANJI not in text:
        return findings

    findings.append(
        _make_finding(
            level="CAUTION",
            code="案件ルール_ください表記",
            message=(
                "この案件は『ください』でそろえたい設定です。"
                "漢字の『下さい』が混ざっていないか確認してください。"
            ),
            samples=[f"{KUDASAI_KANJI} → {KUDASAI_HIRAGANA}"],
        )
    )
    return findings


def _check_preferred_dekiru_style(text: str, prefer_dekiru: bool) -> List[Finding]:
    findings: List[Finding] = []

    if not prefer_dekiru:
        return findings

    if DEKIRU_KANJI not in text:
        return findings

    findings.append(
        _make_finding(
            level="CAUTION",
            code="案件ルール_できる表記",
            message=(
                "この案件は『できる』でそろえたい設定です。"
                "漢字の『出来る』が混ざっていないか確認してください。"
            ),
            samples=[f"{DEKIRU_KANJI} → {DEKIRU_HIRAGANA}"],
        )
    )
    return findings


# =========================================
# 実行本体
# =========================================
def check_style_core(
    text: str,
    *,
    max_sentence_len: int = DEFAULT_MAX_SENTENCE_LEN,
    preferred_tone: str | None = None,
    prefer_halfwidth_percent: bool = False,
    prefer_kagetsu_style: str | None = None,
    prefer_kudasai: bool = False,
    prefer_dekiru: bool = False,
) -> GuardrailResult:
    """
    軽い日本語番兵。
    - 文体混在
    - 同語尾3連続
    - 長文
    - 表記ゆれ
    - 記号ゆれ
    - 誤字候補
    - 重複語候補
    - 案件ルール（文体、%、か月、ください、できる）
    """
    if _is_blank(text):
        return GuardrailResult(level="SAFE", findings=())

    findings: List[Finding] = []

    # 固定ルール
    findings.extend(_check_style_mixed(text))
    findings.extend(_check_tail_repetition(text))
    findings.extend(_check_long_sentences(text, max_len=max_sentence_len))
    findings.extend(_check_canonical_replacements(text))
    findings.extend(_check_symbol_rules(text))
    findings.extend(_check_typo_suspects(text))
    findings.extend(_check_duplicate_word_suspects(text))

    # 案件ルール
    findings.extend(_check_preferred_tone(text, preferred_tone))
    findings.extend(_check_preferred_percent_style(text, prefer_halfwidth_percent))
    findings.extend(_check_preferred_kagetsu_style(text, prefer_kagetsu_style))
    findings.extend(_check_preferred_kudasai_style(text, prefer_kudasai))
    findings.extend(_check_preferred_dekiru_style(text, prefer_dekiru))

    level: RiskLevel = max_level_from_list([f.level for f in findings]) if findings else "SAFE"
    return GuardrailResult(level=level, findings=tuple(findings))


def check_style(
    *,
    text: str,
    max_sentence_len: int = DEFAULT_MAX_SENTENCE_LEN,
    preferred_tone: str | None = None,
    prefer_halfwidth_percent: bool = False,
    prefer_kagetsu_style: str | None = None,
    prefer_kudasai: bool = False,
    prefer_dekiru: bool = False,
    **kwargs,
) -> GuardrailResult:
    """
    UIから呼ぶ入口。
    kwargs は将来拡張用に受ける。
    """
    _ = kwargs
    return check_style_core(
        text=text,
        max_sentence_len=max_sentence_len,
        preferred_tone=preferred_tone,
        prefer_halfwidth_percent=prefer_halfwidth_percent,
        prefer_kagetsu_style=prefer_kagetsu_style,
        prefer_kudasai=prefer_kudasai,
        prefer_dekiru=prefer_dekiru,
    )