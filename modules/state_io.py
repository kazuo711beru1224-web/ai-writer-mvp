# modules/state_io.py
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, Iterable, Optional, Set

import streamlit as st

# 絶対に保存・復元しない（事故防止）
EXCLUDE_KEYS = {
    "openai_api_key",
}

# 内部制御用は保存しない（ループ事故防止）
EXCLUDE_PREFIXES = ("_", "tmp__")

# これらは「セッション中だけ」で十分
EXCLUDE_EPHEMERAL = {
    "menu_request",
}

# Streamlitが内部で session_state に作る widget キー等は保存しない
EXCLUDE_WIDGET_PREFIXES = (
    "btn_",
)


def _is_empty(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    if isinstance(v, (list, dict)) and len(v) == 0:
        return True
    return False


def _latest_state_file(logs_dir: str) -> str | None:
    if not os.path.isdir(logs_dir):
        return None
    files = [f for f in os.listdir(logs_dir) if f.startswith("state_") and f.endswith(".json")]
    if not files:
        return None
    files.sort()
    return os.path.join(logs_dir, files[-1])


def _should_exclude_key(k: str) -> bool:
    if k in EXCLUDE_KEYS:
        return True
    if k in EXCLUDE_EPHEMERAL:
        return True
    if k.startswith(EXCLUDE_PREFIXES):
        return True
    if k.startswith(EXCLUDE_WIDGET_PREFIXES):
        return True
    return False


def sanitize_session_state_inplace(session_state: Dict[str, Any] | None = None) -> None:
    """旧ネスト系キーが混入したら削除（clearは絶対しない）"""
    ss = session_state if session_state is not None else st.session_state
    legacy_forbidden = {"article", "check", "saved_at"}
    for k in list(ss.keys()):
        if k in legacy_forbidden:
            try:
                del ss[k]
            except Exception:
                pass


def save_state_safe(*, logs_dir: str) -> None:
    """
    ベル憲法２：
    - APIキーは保存しない
    - 内部キー（_ / tmp__）は保存しない
    - 一時キー（menu_request等）は保存しない
    - widgetキー（btn_）は保存しない
    - 空値は保存しない（空上書き事故を防ぐ）
    - 明示イベントでのみ呼ぶ
    """
    os.makedirs(logs_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(logs_dir, f"state_{ts}.json")

    data: dict[str, Any] = {}
    for k, v in st.session_state.items():
        if not isinstance(k, str):
            continue
        if _should_exclude_key(k):
            continue
        if _is_empty(v):
            continue
        data[k] = v

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_state_safe(*, logs_dir: str, only_keys: Optional[Set[str]] = None) -> None:
    """
    ベル憲法２（超重要）：
    - clear() しない
    - 既存キーは一切上書きしない（= 消したものが復活しない）
    - 復元は「キーが存在しない」場合だけ
    - only_keys が指定されたら、そのキーだけ復元
    """
    path = _latest_state_file(logs_dir)
    if not path:
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return

    if not isinstance(data, dict):
        return

    for k, v in data.items():
        if not isinstance(k, str):
            continue
        if _should_exclude_key(k):
            continue
        if only_keys is not None and k not in only_keys:
            continue
        if _is_empty(v):
            continue

        # ✅ 既存キーは上書きしない（ここが“削除できない”の根本対策）
        if k in st.session_state:
            continue

        st.session_state[k] = v
