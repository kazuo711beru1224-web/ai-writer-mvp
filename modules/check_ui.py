from __future__ import annotations

from typing import Dict, Optional, Any, List
import time
import streamlit as st

from modules.guardrails_core import evaluate_guardrails


# =========================
# ベル憲法：状態キー固定
# =========================
KEYS: Dict[str, str] = {
    # 入力
    "check_text": "check__text",

    # 道しるべ（チェック側に保持：記事→チェック貼り付けでコピー）
    "check_evidence": "check__evidence_text",
    "check_suggest": "check__suggest_text",

    # 診断結果（保存して画面に残す：オブジェクトは持たず、文字列のみ）
    "diag_level": "check__diag_level",
    "diag_lines": "check__diag_lines",

    # UI状態
    "show_full_evidence": "check__show_full_evidence",
    "show_full_suggest": "check__show_full_suggest",
    "last_action_sec": "check__last_action_sec",

    # ボタン
    "btn_paste_latest": "btn_paste_latest",
    "btn_clear_check": "btn_clear_check",
    "btn_diagnose": "btn_diagnose",
}

# =========================
# 記事モード側のキー揺れに耐える（保険）
# =========================
# まず「証拠（最後に生成した時点の控え）」を最優先で見る
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

# 次に「入力中の控え（次に生成するときAIに渡す予定）」へフォールバック
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

PREVIEW_CHARS_EVIDENCE = 700
PREVIEW_CHARS_SUGGEST = 300


def _ensure_state() -> None:
    """初期化は if key not in で1回だけ（憲法準拠）"""
    defaults: Dict[str, Any] = {
        KEYS["check_text"]: "",
        KEYS["check_evidence"]: "",
        KEYS["check_suggest"]: "",
        KEYS["diag_level"]: "",
        KEYS["diag_lines"]: "",
        KEYS["show_full_evidence"]: False,
        KEYS["show_full_suggest"]: False,
        KEYS["last_action_sec"]: 0.0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _first_nonempty(keys: List[str]) -> str:
    """候補キーの中から最初の非空文字列を返す（無ければ空文字）"""
    for k in keys:
        v = st.session_state.get(k, "")
        if v and str(v).strip():
            return str(v)
    return ""


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
    記事モード由来の関連KWを、優先順位つきで解決する。
    1) 最後に生成した時点の証拠（proof）
    2) 入力中の控え（suggest）
    """
    sg = _first_nonempty(ARTICLE_PROOF_SUGGEST_KEYS)
    if sg and sg.strip():
        return sg
    return _first_nonempty(ARTICLE_SUGGEST_KEYS)


def _paste_latest_generated() -> None:
    """記事モードの最新生成を、文章チェック欄へ貼り付け（根拠・関連KWもスナップコピー）"""
    _ensure_state()

    latest = st.session_state.get("article__last_text", "")
    st.session_state[KEYS["check_text"]] = str(latest).strip() if (latest and str(latest).strip()) else ""

    # 根拠・関連KW：proof→current の順で解決してコピー
    st.session_state[KEYS["check_evidence"]] = _resolve_article_evidence()
    st.session_state[KEYS["check_suggest"]] = _resolve_article_suggest()

    # 貼り付け時は診断結果をクリア（古い診断の持ち越し事故防止）
    st.session_state[KEYS["diag_level"]] = ""
    st.session_state[KEYS["diag_lines"]] = ""

    # 全文表示トグルは閉じる
    st.session_state[KEYS["show_full_evidence"]] = False
    st.session_state[KEYS["show_full_suggest"]] = False


def _clear_check_text() -> None:
    """文章チェック欄をクリア（道しるべも一緒にクリア）"""
    _ensure_state()
    st.session_state[KEYS["check_text"]] = ""
    st.session_state[KEYS["check_evidence"]] = ""
    st.session_state[KEYS["check_suggest"]] = ""
    st.session_state[KEYS["diag_level"]] = ""
    st.session_state[KEYS["diag_lines"]] = ""
    st.session_state[KEYS["show_full_evidence"]] = False
    st.session_state[KEYS["show_full_suggest"]] = False
    st.session_state[KEYS["last_action_sec"]] = 0.0


def _format_diag_lines(res) -> str:
    """
    GuardrailResult を「画面表示用の文字列」に落とす（session_stateにオブジェクトを入れない）
    """
    lines: List[str] = []
    findings = getattr(res, "findings", None) or []
    for f in findings:
        lvl = getattr(f, "level", "")
        code = getattr(f, "code", "")
        msg = getattr(f, "message", "")
        lines.append(f"- {lvl} / {code}：{msg}")
        samples = getattr(f, "samples", None)
        if samples:
            try:
                ss = [str(x) for x in samples][:12]
                lines.append("  例：" + " / ".join(ss))
            except Exception:
                pass
    return "\n".join(lines).strip()


def _render_badge(level: str) -> None:
    badge_map = {
        "SAFE": "✅ SAFE",
        "CAUTION": "⚠️ CAUTION",
        "RISK": "🛑 RISK",
    }
    st.markdown("### 🛡️ 診断レポート（検疫）")
    st.write(badge_map.get(level or "", "（未診断）"))


def _preview_text(text: str, limit: int) -> str:
    t = str(text or "").strip()
    if len(t) <= limit:
        return t
    return t[:limit] + "\n\n…（続きあり）"


def _render_large_text_block(
    *,
    title: str,
    body: str,
    show_key: str,
    preview_chars: int,
) -> None:
    """
    重い本文は最初から全文を出さず、要約だけ出す。
    必要なときだけ全文を表示する。
    """
    text = str(body or "").strip()

    st.markdown(f"**{title}**")
    if not text:
        st.write("（未入力）")
        return

    st.caption(f"文字数：{len(text)}")

    if len(text) <= preview_chars:
        st.code(text, language="text")
        return

    st.code(_preview_text(text, preview_chars), language="text")

    label = "全文を隠す" if bool(st.session_state.get(show_key, False)) else "全文を表示"
    if st.button(label, key=f"{show_key}__toggle"):
        st.session_state[show_key] = not bool(st.session_state.get(show_key, False))

    if bool(st.session_state.get(show_key, False)):
        st.code(text, language="text")


def render_quality_ui(logs_dir: Optional[str] = None, **kwargs: Any) -> None:
    """
    文章チェック（手動入力）
    - logs_dir を受ける（app.py署名ズレ耐性）
    - **kwargs で将来拡張に耐える
    """
    _ensure_state()

    st.markdown("## 文章チェック（手動入力）")
    st.write("ここでは文章を貼り付けて、ルールに合っているか確認できます。")
    st.write("入力欄はそのまま。下に「診断レポート」を出します。")

    st.divider()

    # ===== 上部ボタン =====
    c1, c2 = st.columns([1, 1])
    with c1:
        paste_clicked = st.button(
            "最新の生成結果を貼り付け（記事モード → チェック）",
            use_container_width=True,
            key=KEYS["btn_paste_latest"],
        )
    with c2:
        clear_clicked = st.button(
            "入力を削除（クリア）",
            use_container_width=True,
            key=KEYS["btn_clear_check"],
        )

    if paste_clicked:
        started = time.perf_counter()
        with st.spinner("記事の本文・根拠・関連キーワードを読み込んでいます…"):
            _paste_latest_generated()
        st.session_state[KEYS["last_action_sec"]] = round(time.perf_counter() - started, 2)
        st.success("貼り付けました。")

    if clear_clicked:
        _clear_check_text()
        st.success("クリアしました。")

    last_action_sec = float(st.session_state.get(KEYS["last_action_sec"], 0.0) or 0.0)
    if last_action_sec > 0:
        st.caption(f"直前の処理時間：{last_action_sec:.2f}秒")

    st.divider()

    # ===== 入力欄 =====
    st.markdown("### チェックしたい文章")
    st.text_area("", key=KEYS["check_text"], height=360)

    body = str(st.session_state.get(KEYS["check_text"], "") or "")
    st.caption(f"本文文字数：{len(body)}")

    st.divider()

    # ===== 道しるべ =====
    st.markdown("### 🔎 修正のための道しるべ（記事モードで入力した根拠）")
    st.caption("※外部検索はしません。記事モードであなたが入力した内容の表示です。")

    # 表示は「チェック側にコピー済み」を優先。空なら記事側（proof→current）でフォールバック。
    evidence = str(st.session_state.get(KEYS["check_evidence"], "") or "").strip()
    suggest = str(st.session_state.get(KEYS["check_suggest"], "") or "").strip()

    if not evidence:
        evidence = _resolve_article_evidence()
    if not suggest:
        suggest = _resolve_article_suggest()

    _render_large_text_block(
        title="根拠メモ（参考URL / 資料名）",
        body=evidence,
        show_key=KEYS["show_full_evidence"],
        preview_chars=PREVIEW_CHARS_EVIDENCE,
    )

    _render_large_text_block(
        title="関連キーワード（サジェスト / 関連語）",
        body=suggest,
        show_key=KEYS["show_full_suggest"],
        preview_chars=PREVIEW_CHARS_SUGGEST,
    )

    st.divider()

    # ===== 診断ボタン（guardrails 接続）=====
    diagnose_clicked = st.button("診断する", use_container_width=True, key=KEYS["btn_diagnose"])
    if diagnose_clicked:
        started = time.perf_counter()
        body_now = str(st.session_state.get(KEYS["check_text"], "") or "").strip()
        ev = str(evidence or "").strip()
        sg = str(suggest or "").strip()

        if not body_now:
            st.session_state[KEYS["diag_level"]] = "CAUTION"
            st.session_state[KEYS["diag_lines"]] = "- CAUTION / EMPTY_BODY：本文が空です。文章を貼り付けてから診断してください。"
        else:
            with st.spinner("診断しています…数字・根拠・文脈のズレを確認中です。"):
                res = evaluate_guardrails(
                    body_text=body_now,
                    evidence_text=ev,
                    suggest_text=sg,
                    root_mode=True,
                )
            st.session_state[KEYS["diag_level"]] = str(getattr(res, "level", "SAFE") or "SAFE")
            st.session_state[KEYS["diag_lines"]] = _format_diag_lines(res)

        st.session_state[KEYS["last_action_sec"]] = round(time.perf_counter() - started, 2)

    # ===== 診断結果の表示（押した後に残る）=====
    level = str(st.session_state.get(KEYS["diag_level"], "") or "")
    diag_lines = str(st.session_state.get(KEYS["diag_lines"], "") or "")

    _render_badge(level)

    if level:
        if level == "RISK":
            st.error("🧯 危険度が高い指摘があります。数字（年号・金額・期限など）は一次情報と必ず照合してください。")
        elif level == "CAUTION":
            st.warning("⚠️ 注意点があります。根拠との一致・文脈を確認してください。")
        else:
            st.success("✅ 重大な問題は検知されませんでした（それでも最終チェックはしてください）。")

    if diag_lines:
        with st.expander("検疫ログ（編集者向け）", expanded=(level in ("CAUTION", "RISK"))):
            st.code(diag_lines, language="text")