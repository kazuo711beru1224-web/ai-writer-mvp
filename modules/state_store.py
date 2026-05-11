# modules/state_store.py
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Iterable, Dict, Any


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def load_state(path: str) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _write_json_atomic(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def extract_keys(session_state: dict, keys: Iterable[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in keys:
        if k in session_state:
            v = session_state.get(k)
            if isinstance(v, (str, int, float, bool)) or v is None:
                out[k] = v
            else:
                out[k] = str(v)
    return out


def restore_missing(session_state: dict, saved: Dict[str, Any], keys: Iterable[str]) -> int:
    """
    現在が空（""）または未定義のときだけ復元する。
    """
    if not saved:
        return 0

    data = saved.get("data") if isinstance(saved, dict) else None
    if not isinstance(data, dict):
        return 0

    restored = 0
    for k in keys:
        if k not in data:
            continue
        cur = session_state.get(k, None)
        if cur is None or (isinstance(cur, str) and cur.strip() == ""):
            session_state[k] = data.get(k, "")
            restored += 1
    return restored


def merge_keep_non_empty(prev_saved: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
    """
    重要：空文字で上書きしない。
    ＝最後の「非空」値を保険箱に残し続ける。
    """
    prev_data = {}
    if isinstance(prev_saved, dict):
        d = prev_saved.get("data")
        if isinstance(d, dict):
            prev_data = dict(d)

    merged = dict(prev_data)

    for k, v in (current or {}).items():
        # 空文字は上書き禁止（保険箱を殺さない）
        if isinstance(v, str):
            if v.strip() != "":
                merged[k] = v
        else:
            # 文字以外は None で上書きしない
            if v is not None:
                merged[k] = v

    return {
        "_meta": {"saved_at": _now_iso()},
        "data": merged,
    }


def save_state_keep_non_empty(path: str, prev_saved: Dict[str, Any], current: Dict[str, Any]) -> None:
    payload = merge_keep_non_empty(prev_saved, current)
    _write_json_atomic(path, payload)
