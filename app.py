from __future__ import annotations

import inspect
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

import streamlit as st

# =========================
# 画面モジュール
# =========================
from modules.article_ui import render_article_ui
from modules.home_ui import render_home_ui
from modules.quality_ui import render_quality_ui

try:
    from modules.history_ui import render_history_ui
except Exception:
    render_history_ui = None

try:
    from modules.terms_ui import render_terms_ui
except Exception:
    render_terms_ui = None

try:
    from modules.consent_admin_ui import render_consent_admin_ui
except Exception:
    render_consent_admin_ui = None


APP_TITLE = "AIライティング自動化アプリ - 明元楽市版"
APP_VERSION = "MVP v1.1"

BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs" / "prod"
LOGS_DIR = BASE_DIR / "logs"

BACKUP_PREFIX = "state_"
BACKUP_SUFFIX = ".json"

MENU_HOME = "ホーム"
MENU_ARTICLE = "記事モード（SEOライティング）"
MENU_CHECK = "文章チェック（手動入力）"
MENU_HISTORY = "生成履歴"
MENU_TERMS = "利用規約"
MENU_CONSENT = "同意履歴（管理）"

MENU_OPTIONS = [
    MENU_HOME,
    MENU_ARTICLE,
    MENU_CHECK,
    MENU_HISTORY,
    MENU_TERMS,
]

# =========================
# ベル憲法：状態キーは固定
# =========================
SS_DEFAULTS: Dict[str, Any] = {
    "app__bootstrapped": False,
    "app__menu": MENU_HOME,
    "menu_request": "",
    "openai_api_key": "",
    "use_real_api": False,
    "backup__save_request": False,
    "backup__status_kind": "",
    "backup__status_text": "",
    "backup__last_file": "",
    "backup__at": "",
    "backup__last_sig": "",
    "backup__last_saved_work_at": "",
    "backup__refresh_sig_after_render": False,
    "backup__restore_request": False,
    "backup__restore_target": "",
    "backup__restore_status_kind": "",
    "backup__restore_status_text": "",
    "api__status_code": "",
    "api__status_message": "",
    "api__status_detail": "",
    "api__last_runtime_error": "",
}

WORK_SIG_KEYS = [
    "article__main_kw",
    "article__sub_kw",
    "article__theme",
    "article__memo",
    "article__evidence_text",
    "article__suggest_text",
    "article__last_text",
    "check__text",
]

RESTORE_REQUEST_KEYS = [
    "backup__restore_request",
    "history__restore_request",
    "restore_request",
]

RESTORE_TARGET_KEYS = [
    "backup__restore_target",
    "history__restore_target",
    "backup__restore_file",
    "history__restore_file",
    "history__restore_file_request",
    "restore_target",
    "restore_file",
]

RESTORE_APPLY_KEYS = [
    "article__main_kw",
    "article__sub_kw",
    "article__theme",
    "article__memo",
    "article__evidence_text",
    "article__suggest_text",
    "article__last_text",
    "check__text",
]

SNAPSHOT_FALLBACK_MAP = {
    "main_kw": "article__main_kw",
    "sub_kw": "article__sub_kw",
    "theme": "article__theme",
    "memo": "article__memo",
    "evidence_text": "article__evidence_text",
    "suggest_text": "article__suggest_text",
    "last_text": "article__last_text",
    "check_text": "check__text",
    "article__main_kw": "article__main_kw",
    "article__sub_kw": "article__sub_kw",
    "article__theme": "article__theme",
    "article__memo": "article__memo",
    "article__evidence_text": "article__evidence_text",
    "article__suggest_text": "article__suggest_text",
    "article__last_text": "article__last_text",
    "check__text": "check__text",
}


def _ensure_dirs() -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _init_session_state() -> None:
    for key, value in SS_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _normalize_menu() -> None:
    current = str(st.session_state.get("app__menu") or MENU_HOME)
    if current not in MENU_OPTIONS:
        st.session_state["app__menu"] = MENU_HOME

    requested = str(st.session_state.get("menu_request") or "").strip()
    if requested:
        if requested in MENU_OPTIONS:
            st.session_state["app__menu"] = requested
        st.session_state["menu_request"] = ""


def _safe_json_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_safe_json_value(v) for v in value]
    if isinstance(value, tuple):
        return [_safe_json_value(v) for v in value]
    if isinstance(value, dict):
        safe: Dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(k, str):
                safe[k] = _safe_json_value(v)
        return safe
    return str(value)


STATE_EXCLUDE_KEYS = {
    "openai_api_key",
    "app__openai_api_key",
    "api__status_code",
    "api__status_message",
    "api__status_detail",
    "api__last_runtime_error",
    "menu_request",
}

STATE_EXCLUDE_PREFIXES = (
    "_",
    "btn_",
    "tmp__",
)


def _inject_global_style() -> None:
    css = """
    <style>
    :root {
      color-scheme: dark light;
    }

    .stTextInput>div>div>input,
    .stTextArea>div>div>textarea,
    .stSelectbox>div>div>div>div,
    .stMultiSelect>div>div>div>div,
    .stNumberInput>div>div>input,
    .stRadio>div>label,
    .stCheckbox>label {
      border: 1.9px solid rgba(140, 140, 140, 0.9) !important;
      border-radius: 12px !important;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,0.08);
      background-color: rgba(255,255,255,0.04) !important;
      padding: 0.4rem 0.65rem !important;
    }

    button[data-baseweb="base-button"],
    .stButton>button {
      border: 1.8px solid #2563eb !important;
      background-color: #2563eb !important;
      color: #f8fafc !important;
      font-weight: 600 !important;
      box-shadow: 0 4px 12px rgba(0,0,0,0.18);
      min-height: 2.9rem;
    }

    button[data-baseweb="base-button"]:hover,
    .stButton>button:hover {
      background-color: #1d4ed8 !important;
      border-color: #1d4ed8 !important;
    }

    .stExpander {
      border: 1.4px solid rgba(140, 140, 140, 0.8) !important;
      border-radius: 12px !important;
      background-color: rgba(255,255,255,0.03) !important;
      padding: 0.4rem 0.55rem !important;
    }

    .streamlit-expanderHeader {
      font-weight: 700 !important;
    }

    .stCaption {
      background-color: rgba(100, 116, 139, 0.15) !important;
      border: 1px solid rgba(148, 163, 184, 0.35) !important;
      border-radius: 10px !important;
      padding: 0.8rem 1rem !important;
      margin: 0.45rem 0 0.9rem 0 !important;
      color: #e5e7eb !important;
      display: block;
    }

    .stAlert[data-testid="stWarning"] > div,
    .stWarning > div > div {
      border: 1.6px solid #f59e0b !important;
      background-color: rgba(251, 191, 36, 0.16) !important;
      color: #f8e3a0 !important;
    }

    .stAlert[data-testid="stError"] > div,
    .stError > div > div {
      border: 1.6px solid #dc2626 !important;
      background-color: rgba(220, 38, 38, 0.16) !important;
      color: #fee2e2 !important;
    }

    .stAlert[data-testid="stSuccess"] > div,
    .stSuccess > div > div {
      border: 1.6px solid #16a34a !important;
      background-color: rgba(22, 163, 74, 0.15) !important;
      color: #d1fae5 !important;
    }

    .css-1kyxreq, .css-1d391kg {
      color: #e5e7eb !important;
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def _should_save_state_key(key: str, value: Any) -> bool:
    if key in STATE_EXCLUDE_KEYS:
        return False
    if key.startswith(STATE_EXCLUDE_PREFIXES):
        return False
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    if isinstance(value, (list, dict, tuple)) and len(value) == 0:
        return False
    return True


def _safe_dump_state() -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for key, value in st.session_state.items():
        key_str = str(key)
        if not _should_save_state_key(key_str, value):
            continue
        payload[key_str] = _safe_json_value(value)
    return payload


def _work_signature_payload() -> Dict[str, str]:
    payload: Dict[str, str] = {}
    for key in WORK_SIG_KEYS:
        payload[key] = str(st.session_state.get(key) or "").strip()
    return payload


def _compute_work_signature() -> str:
    payload = _work_signature_payload()
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _fmt_mtime(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def _iter_backup_files(logs_dir: Path) -> Iterable[Path]:
    if not logs_dir.exists():
        return []
    files = sorted(
        logs_dir.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return files


def _find_backup_by_name(logs_dir: Path, filename: str) -> Optional[Path]:
    filename = str(filename or "").strip()
    if not filename:
        return None
    fp = logs_dir / filename
    if fp.exists() and fp.is_file():
        return fp
    return None


def _find_duplicate_backup_by_sig(logs_dir: Path, work_sig: str) -> Optional[Path]:
    for fp in _iter_backup_files(logs_dir):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue

        meta_sig = str(data.get("__meta__work_sig") or "").strip()
        if meta_sig and meta_sig == work_sig:
            return fp

        probe: Dict[str, str] = {}
        for key in WORK_SIG_KEYS:
            probe[key] = str(data.get(key) or "").strip()
        if json.dumps(probe, ensure_ascii=False, sort_keys=True, separators=(",", ":")) == work_sig:
            return fp
    return None


def _clear_backup_status() -> None:
    st.session_state["backup__status_kind"] = ""
    st.session_state["backup__status_text"] = ""


def _clear_restore_status() -> None:
    st.session_state["backup__restore_status_kind"] = ""
    st.session_state["backup__restore_status_text"] = ""


def _set_api_status(*, code: str, message: str, detail: str = "", raw_error: str = "") -> None:
    st.session_state["api__status_code"] = str(code or "").strip()
    st.session_state["api__status_message"] = str(message or "").strip()
    st.session_state["api__status_detail"] = str(detail or "").strip()
    st.session_state["api__last_runtime_error"] = str(raw_error or "").strip()


def _clear_api_status() -> None:
    st.session_state["api__status_code"] = ""
    st.session_state["api__status_message"] = ""
    st.session_state["api__status_detail"] = ""
    st.session_state["api__last_runtime_error"] = ""


def _backup_save(logs_dir: Path) -> Tuple[bool, Path]:
    payload = _safe_dump_state()
    work_sig = _compute_work_signature()

    # まずは直前保存と同一かを最優先で判定する
    last_sig = str(st.session_state.get("backup__last_sig") or "").strip()
    last_file = str(st.session_state.get("backup__last_file") or "").strip()

    if last_sig and work_sig == last_sig and last_file:
        latest_fp = _find_backup_by_name(logs_dir, last_file)
        if latest_fp is not None:
            latest_mtime = _fmt_mtime(latest_fp.stat().st_mtime)
            st.session_state["backup__last_file"] = latest_fp.name
            st.session_state["backup__at"] = latest_mtime
            st.session_state["backup__last_sig"] = work_sig
            st.session_state["backup__last_saved_work_at"] = latest_mtime
            st.session_state["backup__refresh_sig_after_render"] = False
            return False, latest_fp

    # 直前保存と違うときだけ、過去全体から重複を探す
    dup = _find_duplicate_backup_by_sig(logs_dir, work_sig)
    if dup is not None:
        dup_mtime = _fmt_mtime(dup.stat().st_mtime)
        st.session_state["backup__last_file"] = dup.name
        st.session_state["backup__at"] = dup_mtime
        st.session_state["backup__last_sig"] = work_sig
        st.session_state["backup__last_saved_work_at"] = dup_mtime
        st.session_state["backup__refresh_sig_after_render"] = False
        return False, dup

    payload["__meta__work_sig"] = work_sig
    fp = logs_dir / f"{BACKUP_PREFIX}{_now_stamp()}{BACKUP_SUFFIX}"
    fp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    saved_at = _fmt_mtime(fp.stat().st_mtime)
    st.session_state["backup__last_file"] = fp.name
    st.session_state["backup__at"] = saved_at
    st.session_state["backup__last_sig"] = work_sig
    st.session_state["backup__last_saved_work_at"] = saved_at
    st.session_state["backup__refresh_sig_after_render"] = False
    return True, fp


def _handle_pending_backup_save(logs_dir: Path) -> None:
    if not bool(st.session_state.get("backup__save_request")):
        return

    st.session_state["backup__save_request"] = False
    _clear_restore_status()

    try:
        created, _fp = _backup_save(logs_dir)
        if created:
            when = str(st.session_state.get("backup__at") or "").strip()
            st.session_state["backup__status_kind"] = "success"
            st.session_state["backup__status_text"] = f"今の状態を保存しました。（保存日時：{when}）"
        else:
            when = str(st.session_state.get("backup__at") or "").strip()
            st.session_state["backup__status_kind"] = "info"
            st.session_state["backup__status_text"] = f"この状態はすでに保存されています。（最新の保存日時：{when}）"
        st.rerun()
    except Exception as e:
        st.session_state["backup__status_kind"] = "error"
        st.session_state["backup__status_text"] = f"保存に失敗しました。{e}"
        st.rerun()


def _show_backup_status() -> None:
    kind = str(st.session_state.get("backup__status_kind") or "").strip()
    text = str(st.session_state.get("backup__status_text") or "").strip()
    if not text:
        return

    if kind == "success":
        st.success(text)
    elif kind == "info":
        st.info(text)
    elif kind == "error":
        st.error(text)
    else:
        st.write(text)


def _show_restore_status() -> None:
    kind = str(st.session_state.get("backup__restore_status_kind") or "").strip()
    text = str(st.session_state.get("backup__restore_status_text") or "").strip()
    if not text:
        return

    if kind == "success":
        st.success(text)
    elif kind == "info":
        st.info(text)
    elif kind == "error":
        st.error(text)
    else:
        st.write(text)


def _call_ui(func: Any, **kwargs: Any) -> None:
    if func is None:
        return
    sig = inspect.signature(func)
    accepted = {
        key: value
        for key, value in kwargs.items()
        if key in sig.parameters
    }
    func(**accepted)


def _has_restore_request() -> bool:
    for key in RESTORE_REQUEST_KEYS:
        value = st.session_state.get(key)
        if value is True:
            return True
        if isinstance(value, str) and value.strip():
            return True

    for key in RESTORE_TARGET_KEYS:
        value = st.session_state.get(key)
        if isinstance(value, str) and value.strip():
            return True

    return False


def _extract_restore_target() -> str:
    for key in RESTORE_TARGET_KEYS:
        value = st.session_state.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _clear_restore_request() -> None:
    for key in RESTORE_REQUEST_KEYS:
        if key in st.session_state:
            current = st.session_state.get(key)
            st.session_state[key] = False if isinstance(current, bool) else ""

    for key in RESTORE_TARGET_KEYS:
        if key in st.session_state:
            st.session_state[key] = ""


def _apply_restore_payload(payload: Dict[str, Any]) -> None:
    # まず新形式の current 値を復元
    for key in RESTORE_APPLY_KEYS:
        if key in payload:
            st.session_state[key] = str(payload.get(key) or "")

    # 旧形式 snapshot しかない場合の安全補完
    snapshot = payload.get("snapshot")
    if isinstance(snapshot, dict):
        for src_key, dest_key in SNAPSHOT_FALLBACK_MAP.items():
            current = str(st.session_state.get(dest_key) or "").strip()
            snap_val = snapshot.get(src_key)
            if (not current) and snap_val is not None:
                st.session_state[dest_key] = str(snap_val)

    # 復元後の実データそのものからシグネチャを再計算する
    st.session_state["backup__last_sig"] = _compute_work_signature()


def _handle_pending_restore(logs_dir: Path) -> None:
    if not _has_restore_request():
        return

    target = _extract_restore_target()
    _clear_restore_request()
    _clear_backup_status()

    if not target:
        st.session_state["backup__restore_status_kind"] = "error"
        st.session_state["backup__restore_status_text"] = "復元する作業記録が見つかりませんでした。"
        st.rerun()

    fp = _find_backup_by_name(logs_dir, target)
    if fp is None:
        st.session_state["backup__restore_status_kind"] = "error"
        st.session_state["backup__restore_status_text"] = "指定された作業記録が見つかりませんでした。"
        st.rerun()

    try:
        payload = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        st.session_state["backup__restore_status_kind"] = "error"
        st.session_state["backup__restore_status_text"] = f"作業記録の読み込みに失敗しました。{e}"
        st.rerun()

    try:
        _apply_restore_payload(payload)
        restored_at = _fmt_mtime(fp.stat().st_mtime)
        st.session_state["backup__last_file"] = fp.name
        st.session_state["backup__at"] = restored_at
        st.session_state["backup__last_saved_work_at"] = restored_at
        st.session_state["backup__restore_status_kind"] = "success"
        st.session_state["backup__restore_status_text"] = f"保存していた状態に戻しました。（記録日時：{restored_at}）"
        st.session_state["menu_request"] = MENU_ARTICLE
        st.rerun()
    except Exception as e:
        st.session_state["backup__restore_status_kind"] = "error"
        st.session_state["backup__restore_status_text"] = f"復元に失敗しました。{e}"
        st.rerun()


def _render_sidebar() -> str:
    with st.sidebar:
        st.markdown(f"## {APP_TITLE}")
        st.caption(f"バージョン：{APP_VERSION}")

        st.markdown("### 🔐 AI下書き作成の設定")
        st.text_input(
            "OpenAI APIキー",
            key="openai_api_key",
            type="password",
            help="AIで下書きを作成するときだけ入力します。",
        )
        st.write("APIキーは、AI下書きを使うための大事な鍵です。")
        st.warning("人に見せたり、LINEやメールで送ったりしないでください。")
        with st.expander("APIキーを安全に使うために"):
            st.markdown(
                "- APIキーは作成した直後しか表示されません。\n"
                "- 作ったら、すぐに安全な場所へ保存してください。\n"
                "- おすすめは、iPhoneのパスワード管理機能、iCloudキーチェーン、1Password、Bitwarden、ロック付きメモなどです。\n"
                "- LINE、メール、SNS、スクリーンショット、GitHub、共有メモには保存しないでください。\n"
                "- スマホでOpenAIの画面を開くときは、SafariまたはChromeを使ってください。\n"
                "- LINE、Gmail、Googleアプリ、ChatGPTアプリ内のブラウザでは、ログインが止まる場合があります。"
            )
            st.error(
                "もしAPIキーを人に見せた、外に出した、貼ってしまった可能性がある場合は、そのキーを削除して新しく作り直してください。"
            )

        api_key = str(st.session_state.get("openai_api_key") or "").strip()
        use_real_api = bool(api_key)
        st.session_state["use_real_api"] = use_real_api

        # APIキーが空なら、状態も「キー未入力」にそろえる
        if not use_real_api:
            _set_api_status(
                code="api_key_missing",
                message="この画面の『OpenAI APIキー』欄に、保存してあるAPIキーを貼り付けてください。",
                detail="OpenAI APIキーが未入力です。",
                raw_error="",
            )
        else:
            # 以前の「キー未入力」状態だけは消してよい
            if str(st.session_state.get("api__status_code") or "") == "api_key_missing":
                _clear_api_status()

        api_status_code = str(st.session_state.get("api__status_code") or "").strip()
        api_status_message = str(st.session_state.get("api__status_message") or "").strip()

        if use_real_api and not api_status_code:
            st.write("現在：本番のAI下書きが使えます")
        elif not use_real_api:
            st.write("現在：本番のAI下書きはまだ使えません")
            st.caption("この画面の『OpenAI APIキー』欄に、保存してあるAPIキーを貼り付けてください。")
            st.markdown("[OpenAI のAPIキー画面を開く](https://platform.openai.com/settings/organization/api-keys)")
        else:
            st.write("現在：本番のAI下書きが使えていません")
            if api_status_message:
                st.caption(api_status_message)
            else:
                st.caption("AI下書きを始められませんでした。時間をおいてもう一度お試しください。")
            st.markdown("[OpenAI のAPIキー画面を開く](https://platform.openai.com/settings/organization/api-keys)")
            st.markdown("[OpenAI の請求画面を開く](https://platform.openai.com/settings/organization/billing/overview)")

        st.divider()
        st.markdown("### 💾 作業データ")
        st.write("今の入力内容や生成結果を保存したり、前回の保存内容を戻したりできます。")
        st.write("途中まででも保存できるので、安心して進められます。")

        if st.button("今の状態を保存", use_container_width=True):
            st.session_state["backup__save_request"] = True

        _show_backup_status()
        _show_restore_status()

        st.divider()
        st.markdown("### メニュー")

        current_menu = str(st.session_state.get("app__menu") or MENU_HOME)
        default_index = MENU_OPTIONS.index(current_menu) if current_menu in MENU_OPTIONS else 0
        chosen = st.radio(
            "移動",
            MENU_OPTIONS,
            index=default_index,
            label_visibility="collapsed",
            key="sidebar__menu_radio",
        )
        if chosen != current_menu:
            st.session_state["menu_request"] = chosen
            st.rerun()

    return str(st.session_state.get("app__menu") or MENU_HOME)


def _render_current_page(menu: str) -> None:
    common_kwargs = {
        "outputs_dir": str(OUTPUTS_DIR),
        "logs_dir": str(LOGS_DIR),
        "openai_api_key": str(st.session_state.get("openai_api_key") or ""),
        "use_real_api": bool(st.session_state.get("use_real_api")),
    }

    if menu == MENU_HOME:
        _call_ui(render_home_ui, **common_kwargs)
        return

    if menu == MENU_ARTICLE:
        _call_ui(render_article_ui, **common_kwargs)
        return

    if menu == MENU_CHECK:
        _call_ui(render_quality_ui, **common_kwargs)
        return

    if menu == MENU_HISTORY:
        if render_history_ui is None:
            st.markdown("## 生成履歴")
            st.info("保存した記事や作業記録は、ここで確認できます。")
        else:
            _call_ui(render_history_ui, **common_kwargs)
        return

    if menu == MENU_TERMS:
        if render_terms_ui is None:
            st.markdown("## 利用規約")
            st.info("このアプリを安心して使うための考え方を、ここで確認できます。")
        else:
            _call_ui(render_terms_ui, **common_kwargs)
        return

    if menu == MENU_CONSENT:
        if render_consent_admin_ui is None:
            st.markdown("## 同意履歴（管理）")
            st.info("利用前に確認しておきたい内容を、ここでまとめて確認できます。")
        else:
            _call_ui(render_consent_admin_ui, **common_kwargs)
        return

    st.markdown("## ホーム")
    st.info("見たい画面をメニューから選んでください。")


def main() -> None:
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="📝",
        layout="wide",
    )

    _inject_global_style()
    _ensure_dirs()
    _init_session_state()
    _normalize_menu()

    menu = _render_sidebar()
    _render_current_page(menu)

    # サイドバーで押された保存は、本文描画後に実行する
    _handle_pending_backup_save(LOGS_DIR)

    # 履歴画面からの復元要求も、本文描画後に実行する
    _handle_pending_restore(LOGS_DIR)


if __name__ == "__main__":
    main()
