# modules/backup_restore.py
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import streamlit as st


BACKUP_PREFIX = "state_"
BACKUP_SUFFIX = ".json"


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _is_jsonable(v: Any) -> bool:
    try:
        json.dumps(v, ensure_ascii=False)
        return True
    except TypeError:
        return False


def safe_dump_session_state(
    deny_keys: Set[str],
) -> Dict[str, Any]:
    """
    session_state を安全にダンプする。
    - deny_keys は必ず除外（例：openai_api_key）
    - JSON化できない値は str 化
    """
    out: Dict[str, Any] = {}
    for k, v in st.session_state.items():
        if not isinstance(k, str):
            continue
        if k.startswith("_"):
            continue
        if k in deny_keys:
            continue
        out[k] = v if _is_jsonable(v) else str(v)
    return out


def find_latest_backup(logs_dir: Path) -> Optional[Path]:
    files = sorted(
        logs_dir.glob(f"{BACKUP_PREFIX}*{BACKUP_SUFFIX}"),
        key=lambda p: p.stat().st_mtime,
    )
    return files[-1] if files else None


def backup_save(
    logs_dir: Path,
    deny_keys: Set[str],
) -> Path:
    """
    バックアップ保存（APIキーは保存しない）。
    """
    payload = safe_dump_session_state(deny_keys=deny_keys)
    fp = logs_dir / f"{BACKUP_PREFIX}{_now_stamp()}{BACKUP_SUFFIX}"
    fp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return fp


def _read_backup_file(fp: Path) -> Dict[str, Any]:
    raw = json.loads(fp.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("バックアップ形式が不正です（dictではありません）。")
    return raw


def backup_restore_latest(
    logs_dir: Path,
    allow_keys: Set[str],
    deny_keys: Set[str],
    menu_options: Set[str],
) -> Tuple[str, List[str]]:
    """
    最新バックアップから安全復元。
    - allow_keys: 復元してよいキー（ホワイトリスト）
    - deny_keys : 絶対に触らないキー（サイドバーウィジェット等）
    - menu は st.session_state["menu_request"] に積む（menu直書き禁止）
    戻り値: (ファイル名, 適用キー一覧)
    """
    latest = find_latest_backup(logs_dir)
    if latest is None:
        raise FileNotFoundError("バックアップが見つかりません。先に保存してください。")

    raw = _read_backup_file(latest)

    applied: List[str] = []
    restored_menu: Optional[str] = None

    for k, v in raw.items():
        if not isinstance(k, str):
            continue
        if k.startswith("_"):
            continue
        if k in deny_keys:
            continue

        # menuは復元OKだが、直書きせず request に積む
        if k == "menu" and isinstance(v, str) and v in menu_options:
            restored_menu = v
            continue

        # ★ホワイトリスト以外は復元しない（事故防止）
        if k not in allow_keys:
            continue

        st.session_state[k] = v
        applied.append(k)

    if restored_menu in menu_options:
        st.session_state["menu_request"] = restored_menu

    return latest.name, applied
