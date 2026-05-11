# modules/manual_check_ui.py
from __future__ import annotations

import re
from typing import List, Dict, Any

import streamlit as st

MAX_SENTENCE_LEN = 60


def _split_sentences(text: str) -> List[str]:
    text = text.replace("\r\n", "\n")
    parts = re.split(r"(?:。|\n)+", text)
    return [p.strip() for p in parts if p.strip()]


def _find_long_sentences(text: str, limit: int = MAX_SENTENCE_LEN) -> List[Dict[str, Any]]:
    sentences = _split_sentences(text)
    res = []
    for i, s in enumerate(sentences, start=1):
        if len(s) > limit:
            res.append({"no": i, "length": len(s), "text": s})
    return res


def _find_repeated_endings(text: str) -> List[Dict[str, Any]]:
    endings = []
    sentences = _split_sentences(text)

    def ending_of(s: str) -> str:
        s = s.strip()
        for e in ["です", "ます", "でした", "ました", "である", "だ"]:
            if s.endswith(e):
                return e
        return ""

    for s in sentences:
        endings.append(ending_of(s))

    res = []
    run = 1
    for i in range(1, len(endings)):
        if endings[i] and endings[i] == endings[i - 1]:
            run += 1
        else:
            if run >= 3 and endings[i - 1]:
                res.append({"ending": endings[i - 1], "count": run})
            run = 1
    if run >= 3 and endings and endings[-1]:
        res.append({"ending": endings[-1], "count": run})

    return res


def _find_too_many_no(text: str) -> int:
    return text.count("の")


def render_manual_check_ui() -> None:
    st.markdown(
        """
<style>
.stTextArea textarea {
  color: #111 !important;
  caret-color: #111 !important;
  font-size: 14px !important;
  line-height: 1.6 !important;
}
small, .stCaption { color: rgba(17,17,17,0.75) !important; }
</style>
""",
        unsafe_allow_html=True,
    )

    st.markdown("## 文章チェック（手動入力）")
    st.write("ここは「文章の事故を減らす場所」です。下の箱に文章を貼って、チェックを押してください。")

    st.session_state.setdefault("manual_check_text", "")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("📥 記事モードの直近結果を貼る", use_container_width=True):
            last = st.session_state.get("article__copybox", "") or st.session_state.get("article__last_text", "")
            if last and str(last).strip():
                st.session_state["manual_check_text"] = last
            else:
                st.session_state.pop("manual_check_text", None)
    with col2:
        if st.button("🧹 入力を空にする", use_container_width=True):
            st.session_state.pop("manual_check_text", None)

    text = st.text_area(
        "チェックしたい文章",
        key="manual_check_text",
        height=320,
        placeholder="ここに文章を貼り付けます。",
    )

    st.divider()

    if st.button("✅ チェックする", type="primary", use_container_width=True):
        if not str(text).strip():
            st.error("文章が空です。貼り付けてからチェックしてください。")
            return

        long_sentences = _find_long_sentences(text)
        repeated_endings = _find_repeated_endings(text)
        no_count = _find_too_many_no(text)

        st.subheader("結果（ざっくりチェック）")

        st.markdown(f"### 1) 一文の長さ（目安：{MAX_SENTENCE_LEN}文字以内）")
        if not long_sentences:
            st.success("OK：長すぎる文は見つかりませんでした。")
        else:
            st.warning(f"注意：長い文が {len(long_sentences)} 件あります。")
            for item in long_sentences[:20]:
                st.write(f"- 文{item['no']}：{item['length']}文字")
                st.code(item["text"], language="text")
            if len(long_sentences) > 20:
                st.info("※表示は20件までです。")

        st.markdown("### 2) 語尾の同じ形が3回以上続く")
        if not repeated_endings:
            st.success("OK：語尾の同形3連続は見つかりませんでした。")
        else:
            st.warning("注意：語尾が同じ形で続いている可能性があります。")
            for r in repeated_endings:
                st.write(f"- 「{r['ending']}」が {r['count']} 回以上続いている可能性")

        st.markdown("### 3) 「の」の回数（参考）")
        st.write(f"「の」の回数：**{no_count} 回**")
        st.caption("※多い＝悪いではありません。ただし続くと読みづらくなるので参考にしてください。")

        st.divider()
        st.info("次にやること：直した文章をもう一回チェックして、OKなら記事として仕上げに進みます。")
