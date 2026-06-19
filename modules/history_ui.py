from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

import streamlit as st


TEXT_VIEW_EXTS = {".md", ".txt"}
ARTICLE_EXTS = (".md", ".txt", ".docx")
STATE_EXTS = (".json", ".csv", ".log")

ARTICLE_INITIAL_LIMIT = 10
STATE_INITIAL_LIMIT = 8
LOAD_MORE_STEP = 10


def _list_files(dir_path: str, exts: tuple[str, ...]) -> list[Path]:
    p = Path(dir_path)
    if not p.exists():
        return []

    files: list[Path] = []
    for ext in exts:
        files.extend(p.rglob(f"*{ext}"))

    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return files


def _fmt_mtime(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "-"


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.1f} GB"


def _is_text_viewable(path: Path) -> bool:
    return path.suffix.lower() in TEXT_VIEW_EXTS


def _read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="utf-8-sig")
        except Exception:
            return "このファイルは読み込めませんでした。"
    except Exception:
        return "このファイルは読み込めませんでした。"


def _read_bytes_safe(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except Exception:
        return b""


def _friendly_article_title(path: Path) -> str:
    name = path.stem

    if name.startswith("output_"):
        parts = name.split("_", 3)
        if len(parts) >= 4:
            title = parts[3].strip()
            return title if title else "保存した記事"

    if name == "backup_last":
        return "直近の保存データ"

    if not name.strip():
        return "保存した記事"

    if set(name) == {"a"}:
        return "無題の記事"

    return name or "保存した記事"


def _preview_text(text: str, limit: int = 3500) -> str:
    t = str(text or "")
    if len(t) <= limit:
        return t
    return t[:limit] + "\n\n…（続きがあります）"


def _request_restore(filename: str) -> None:
    """
    app.py が受け取る正式キーへ復元要求を書き込む。
    旧キーも残しておくが、主役は backup__restore_*。
    """
    safe_name = str(filename or "").strip()
    if not safe_name:
        return

    # 正式キー
    st.session_state["backup__restore_target"] = safe_name
    st.session_state["backup__restore_request"] = True

    # 互換用キー
    st.session_state["history__restore_target"] = safe_name
    st.session_state["history__restore_request"] = True
    st.session_state["history__restore_file_request"] = safe_name


def _ensure_history_state() -> None:
    defaults = {
        "history__restore_file_request": "",
        "history__restore_target": "",
        "history__restore_request": False,
        "history__article_limit": ARTICLE_INITIAL_LIMIT,
        "history__state_limit": STATE_INITIAL_LIMIT,
        "history__delete_confirm_kind": "",
        "history__delete_confirm_target": "",
        "history__delete_confirm_label": "",
        "history__delete_confirm_mtime": "",
        "history__delete_confirm_seen_mtime": "",
        "history__flash_message": "",
        "history__flash_level": "",
        "history__last_deleted_label": "",
        "history__last_deleted_kind": "",
        "history__last_deleted_mtime": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _set_flash(message: str, level: str = "info") -> None:
    st.session_state["history__flash_message"] = str(message or "")
    st.session_state["history__flash_level"] = str(level or "info")


def _render_flash() -> None:
    msg = str(st.session_state.get("history__flash_message") or "").strip()
    lvl = str(st.session_state.get("history__flash_level") or "info").strip()

    if not msg:
        return

    if lvl == "success":
        st.success(msg)
    elif lvl == "warning":
        st.warning(msg)
    elif lvl == "error":
        st.error(msg)
    else:
        st.info(msg)

    st.session_state["history__flash_message"] = ""
    st.session_state["history__flash_level"] = ""


def _read_json_safe(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
        return {}
    except Exception:
        return {}


def _friendly_state_summary(path: Path) -> tuple[str, str]:
    """
    購入者向けに見せる要約だけを返す。
    返り値:
      title: 例「3月10日の作業記録」
      subtitle: 例「相続税の基礎控除はいくら？計算方法と注意点」
    """
    stat = path.stat()
    dt = datetime.fromtimestamp(stat.st_mtime)
    title = f"{dt.month}月{dt.day}日の作業記録"

    data = _read_json_safe(path)

    theme = str(data.get("article__theme", "") or "").strip()
    main_kw = str(data.get("article__main_kw", "") or "").strip()
    memo = str(data.get("article__memo", "") or "").strip()
    last_text = str(data.get("article__last_text", "") or "").strip()

    subtitle = ""
    if theme:
        subtitle = theme
    elif main_kw:
        subtitle = main_kw
    elif last_text:
        first_line = last_text.splitlines()[0].strip()
        if first_line.startswith("#"):
            subtitle = first_line.lstrip("#").strip()
    elif memo:
        subtitle = memo

    if not subtitle:
        subtitle = "前に保存した作業内容"

    subtitle = subtitle.replace(" 追加メモ", "").strip()

    return title, subtitle


def _begin_delete_confirm(
    *,
    kind: str,
    target: str,
    label: str,
    mtime_text: str = "",
    seen_mtime_text: str = "",
) -> None:
    st.session_state["history__delete_confirm_kind"] = kind
    st.session_state["history__delete_confirm_target"] = target
    st.session_state["history__delete_confirm_label"] = label
    st.session_state["history__delete_confirm_mtime"] = str(mtime_text or "")
    st.session_state["history__delete_confirm_seen_mtime"] = str(seen_mtime_text or mtime_text or "")


def _clear_delete_confirm() -> None:
    st.session_state["history__delete_confirm_kind"] = ""
    st.session_state["history__delete_confirm_target"] = ""
    st.session_state["history__delete_confirm_label"] = ""
    st.session_state["history__delete_confirm_mtime"] = ""
    st.session_state["history__delete_confirm_seen_mtime"] = ""


def _delete_file_safe(path: Path) -> bool:
    try:
        if path.exists() and path.is_file():
            path.unlink()
            return True
        return False
    except Exception:
        return False


def _resolve_delete_target(
    *,
    outputs_dir: Optional[str],
    logs_dir: Optional[str],
    kind: str,
    target: str,
) -> Optional[Path]:
    if not target:
        return None

    if kind == "article" and outputs_dir:
        p = Path(outputs_dir) / target
        if p.exists() and p.is_file():
            return p

    if kind == "state" and logs_dir:
        p = Path(logs_dir) / target
        if p.exists() and p.is_file():
            return p

    return None


def _remember_deleted(*, kind: str, label: str, mtime_text: str) -> None:
    st.session_state["history__last_deleted_kind"] = str(kind or "")
    st.session_state["history__last_deleted_label"] = str(label or "")
    st.session_state["history__last_deleted_mtime"] = str(mtime_text or "")


def _build_delete_success_message(*, kind: str, label: str, mtime_text: str) -> str:
    safe_label = str(label or "この記録").strip()
    safe_time = str(mtime_text or "-").strip()

    if kind == "article":
        return (
            f"{safe_label}（{safe_time}）を削除しました。\n\n"
            "続けて整理する場合は、次に削除する記事の題名と日時を確認してください。"
        )

    if kind == "state":
        return (
            f"{safe_label}（{safe_time}）を削除しました。\n\n"
            "続けて整理する場合は、次に削除する作業記録の日付と時刻を確認してください。"
        )

    return (
        f"{safe_label}（{safe_time}）を削除しました。\n\n"
        "続けて整理する場合は、削除対象の名前と日時を確認してください。"
    )


def _render_last_deleted_notice() -> None:
    label = str(st.session_state.get("history__last_deleted_label") or "").strip()
    kind = str(st.session_state.get("history__last_deleted_kind") or "").strip()
    mtime_text = str(st.session_state.get("history__last_deleted_mtime") or "").strip()

    if not label:
        return

    if kind == "article":
        head = "直前に削除した記事"
        tail = "同じような題名が続く場合は、削除前に日時も確認すると安心です。"
    elif kind == "state":
        head = "直前に削除した作業記録"
        tail = "続けて整理する場合は、次に削除する日付と時刻を確認してください。"
    else:
        head = "直前に削除したもの"
        tail = "続けて整理する場合は、削除対象を確認してください。"

    st.info(
        f"**{head}**\n\n"
        f"- {label}（{mtime_text or '-'}）\n\n"
        f"{tail}"
    )


def _build_target_line(label: str, mtime_text: str) -> str:
    safe_label = str(label or "この記録").strip()
    safe_time = str(mtime_text or "").strip()
    return f"{safe_label}（{safe_time}）" if safe_time else safe_label


def _render_delete_confirm_bar(*, outputs_dir: Optional[str], logs_dir: Optional[str]) -> bool:
    kind = str(st.session_state.get("history__delete_confirm_kind") or "").strip()
    target = str(st.session_state.get("history__delete_confirm_target") or "").strip()
    label = str(st.session_state.get("history__delete_confirm_label") or "この記録").strip()
    shown_mtime_text = str(st.session_state.get("history__delete_confirm_mtime") or "").strip()
    seen_mtime_text = str(st.session_state.get("history__delete_confirm_seen_mtime") or "").strip()

    if not kind or not target:
        return False

    target_path = _resolve_delete_target(
        outputs_dir=outputs_dir,
        logs_dir=logs_dir,
        kind=kind,
        target=target,
    )

    current_mtime_text = ""
    if target_path is not None:
        try:
            current_mtime_text = _fmt_mtime(target_path.stat().st_mtime)
        except Exception:
            current_mtime_text = ""

    display_mtime_text = shown_mtime_text or seen_mtime_text or current_mtime_text
    target_line = _build_target_line(label, display_mtime_text)

    st.warning(
        f"**削除の確認**\n\n"
        f"{target_line}を削除すると元に戻せません。"
        f"必要な内容は、削除前にコピーして保管してください。削除してもよろしいですか？",
        icon="⚠️",
    )

    if display_mtime_text and current_mtime_text and display_mtime_text != current_mtime_text:
        st.warning(
            "一覧で見えていた日時と、現在のファイル日時に違いがあります。"
            " いったん削除を中止して、一覧を見直してから操作すると安全です。"
        )
        st.caption(f"確認中の表示日時：{display_mtime_text}")
        st.caption(f"現在のファイル日時：{current_mtime_text}")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("本当に削除する", key="history__delete_confirm_yes", use_container_width=True):
            _clear_delete_confirm()

            if target_path is None:
                _set_flash("削除対象が見つかりませんでした。", "error")
                st.rerun()
                return True

            actual_mtime_text = ""
            try:
                actual_mtime_text = _fmt_mtime(target_path.stat().st_mtime)
            except Exception:
                actual_mtime_text = display_mtime_text or "-"

            ok = _delete_file_safe(target_path)
            if ok:
                _remember_deleted(kind=kind, label=label, mtime_text=actual_mtime_text)

                if display_mtime_text and actual_mtime_text and display_mtime_text != actual_mtime_text:
                    _set_flash(
                        f"{_build_target_line(label, actual_mtime_text)}を削除しました。\n\n"
                        "なお、一覧で見えていた日時と削除時の日時に違いがありました。"
                        " 続けて整理する前に、一覧を確認してください。",
                        "warning",
                    )
                else:
                    _set_flash(
                        _build_delete_success_message(
                            kind=kind,
                            label=label,
                            mtime_text=actual_mtime_text,
                        ),
                        "success",
                    )
            else:
                _set_flash("削除できませんでした。もう一度お試しください。", "error")

            st.rerun()
            return True

    with c2:
        if st.button("キャンセル", key="history__delete_confirm_no", use_container_width=True):
            _clear_delete_confirm()
            st.rerun()
            return True

    return True


def _render_article_file_card(path: Path, idx: int) -> None:
    stat = path.stat()
    mtime_text = _fmt_mtime(stat.st_mtime)
    title = _friendly_article_title(path)

    with st.expander(f"\U0001f4c4 {title}\uff5c{mtime_text}\uff5c{_fmt_size(stat.st_size)}", expanded=False):
        st.write("\u4f5c\u6210\u3057\u3066\u4fdd\u5b58\u3057\u305f\u8a18\u4e8b\u3092\u78ba\u8a8d\u3067\u304d\u307e\u3059\u3002\u516c\u958b\u524d\u306e\u898b\u76f4\u3057\u3084\u4fdd\u7ba1\u306b\u4f7f\u3048\u307e\u3059\u3002")

        text_content = None

        if _is_text_viewable(path):
            content = _read_text_safe(path)
            text_content = content
            st.markdown("**\u8a18\u4e8b\u5185\u5bb9**")
            st.code(_preview_text(content), language="markdown" if path.suffix.lower() == ".md" else "text")
            st.caption("\u30b9\u30de\u30db\u3084Google\u30c9\u30e9\u30a4\u30d6\u3067\u958b\u304d\u305f\u3044\u5834\u5408\u306f\u3001\u4e0b\u306e\u300e\u30b9\u30de\u30db\u7528TXT\u3067\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9\u300f\u304c\u304a\u3059\u3059\u3081\u3067\u3059\u3002")
        else:
            st.info("\u3053\u306e\u5f62\u5f0f\u306f\u753b\u9762\u3067\u8868\u793a\u3067\u304d\u307e\u305b\u3093\u3002\u5fc5\u8981\u306a\u5834\u5408\u306f\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9\u3057\u3066\u78ba\u8a8d\u3057\u3066\u304f\u3060\u3055\u3044\u3002")

        c1, c2, c3 = st.columns(3)

        with c1:
            data = _read_bytes_safe(path)
            if data:
                st.download_button(
                    "\u5143\u306e\u5f62\u5f0f\u3067\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9",
                    data=data,
                    file_name=path.name,
                    mime="text/markdown" if path.suffix.lower() == ".md" else "application/octet-stream",
                    key=f"history_download_article_{idx}",
                    use_container_width=True,
                )
            else:
                st.warning("\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9\u306e\u6e96\u5099\u306b\u5931\u6557\u3057\u307e\u3057\u305f\u3002")

        with c2:
            if text_content:
                txt_name = path.with_suffix(".txt").name
                st.download_button(
                    "\u30b9\u30de\u30db\u7528TXT\u3067\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9",
                    data=text_content.encode("utf-8-sig"),
                    file_name=txt_name,
                    mime="text/plain",
                    key=f"history_download_article_txt_{idx}",
                    use_container_width=True,
                )

        with c3:
            if st.button("\u524a\u9664\u3059\u308b", key=f"history_delete_article_{idx}", use_container_width=True):
                _begin_delete_confirm(
                    kind="article",
                    target=path.name,
                    label=f"\u8a18\u4e8b\u300c{title}\u300d",
                    mtime_text=mtime_text,
                    seen_mtime_text=mtime_text,
                )
                st.rerun()

def _render_state_file_card(path: Path, idx: int) -> None:
    stat = path.stat()
    mtime_text = _fmt_mtime(stat.st_mtime)
    title, subtitle = _friendly_state_summary(path)
    is_restore_target = path.suffix.lower() == ".json" and path.name.startswith("state_")

    with st.container(border=True):
        st.markdown(f"**🧰 {title}**")
        st.caption(mtime_text)
        st.write(subtitle)

        c1, c2 = st.columns(2)

        with c1:
            if is_restore_target:
                if st.button("この状態に戻す", key=f"history_restore_{idx}", use_container_width=True):
                    _request_restore(path.name)
                    st.rerun()
            else:
                st.caption("この記録は復元には使えません。")

        with c2:
            if st.button("削除する", key=f"history_delete_state_{idx}", use_container_width=True):
                _begin_delete_confirm(
                    kind="state",
                    target=path.name,
                    label=f"{title}",
                    mtime_text=mtime_text,
                    seen_mtime_text=mtime_text,
                )
                st.rerun()


def _render_load_more(*, state_key: str, current_limit: int, total_count: int) -> None:
    if total_count <= current_limit:
        return

    remain = total_count - current_limit
    label = f"もっと見る（あと{remain}件）"
    if st.button(label, key=f"{state_key}__more", use_container_width=True):
        st.session_state[state_key] = current_limit + LOAD_MORE_STEP
        st.rerun()


def render_history_ui(*, outputs_dir: Optional[str] = None, logs_dir: Optional[str] = None, **kwargs: Any) -> None:
    """
    購入者向けの履歴画面。
    - 保存した記事は確認できる
    - 作業記録は「戻すための取っ手」だけ見せる
    - JSON本文、内部キー、保存名、パスは見せない
    """
    _ = kwargs
    _ensure_history_state()

    st.markdown("## 保存した記事と作業記録")
    st.write("ここでは、保存した記事を見返したり、前に作業していた状態へ戻したりできます。")
    st.write("途中までの内容を見直したいときや、前の続きから再開したいときに使います。")

    # 削除確認バーを最優先表示
    if _render_delete_confirm_bar(outputs_dir=outputs_dir, logs_dir=logs_dir):
        return

    _render_flash()
    _render_last_deleted_notice()

    st.divider()

    if not outputs_dir:
        st.error("保存した記事を表示できません。")
        return

    st.markdown("### 📄 保存した記事")
    st.caption("作成して保存した記事を確認できます。必要に応じて内容を見たり、ファイルとしてダウンロードできます。")

    out_files = _list_files(outputs_dir, ARTICLE_EXTS)
    article_limit = int(st.session_state.get("history__article_limit", ARTICLE_INITIAL_LIMIT))

    if not out_files:
        st.info("保存された記事はまだありません。")
    else:
        for idx, f in enumerate(out_files[:article_limit], start=1):
            _render_article_file_card(f, idx)

        _render_load_more(
            state_key="history__article_limit",
            current_limit=article_limit,
            total_count=len(out_files),
        )

    st.divider()

    st.markdown("### 🧰 作業を戻すための記録")
    st.caption("前に作業していた状態へ戻したいときに使います。記事本文だけでなく、入力していたキーワードやメモもまとめて復元します。")
    st.info("戻す前に、今の状態を保存しておくと安心です。")

    if not logs_dir:
        st.info("作業記録はまだ表示できません。")
        return

    log_files = [f for f in _list_files(logs_dir, STATE_EXTS) if f.suffix.lower() == ".json" and f.name.startswith("state_")]
    state_limit = int(st.session_state.get("history__state_limit", STATE_INITIAL_LIMIT))

    if not log_files:
        st.info("戻せる作業記録はまだありません。")
    else:
        for idx, f in enumerate(log_files[:state_limit], start=1):
            _render_state_file_card(f, idx)

        _render_load_more(
            state_key="history__state_limit",
            current_limit=state_limit,
            total_count=len(log_files),
        )
