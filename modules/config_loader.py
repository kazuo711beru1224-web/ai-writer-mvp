"""
config_loader.py

AI_WRITER_MVP 用の設定読み込みユーティリティ。

- config/thresholds.json
- config/app_version.json
- config/legal_notice.md

を安全に読み込んで、他のモジュールから使えるようにする。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

# このファイルは modules/ の中に置く前提
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"


class ConfigError(Exception):
    """設定ファイル読み込み時のエラー用の独自例外。"""
    pass


def _safe_read_text(path: Path) -> str:
    """テキストファイルを安全に読み込む。存在しなければ空文字。"""
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception as e:
        raise ConfigError(f"設定ファイルの読み込みに失敗しました: {path} ({e})")


def _safe_read_json(path: Path) -> Dict[str, Any]:
    """JSONファイルを安全に読み込む。存在しなければ空dict。"""
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"JSONの形式が不正です: {path} ({e})")
    except Exception as e:
        raise ConfigError(f"JSONの読み込みに失敗しました: {path} ({e})")


@lru_cache(maxsize=1)
def load_thresholds() -> Dict[str, Any]:
    """
    CCDやmini-auditで使うしきい値設定を読み込む。

    戻り値例:
    {
        "version": "1.0.0",
        "similarity_thresholds": {...},
        "mini_audit": {...},
        "updated_at": "2025-02-xx"
    }
    """
    path = CONFIG_DIR / "thresholds.json"
    data = _safe_read_json(path)
    if not data:
        # 最低限のデフォルト（ファイルが無い・壊れているとき用）
        return {
            "version": "0.0.0",
            "similarity_thresholds": {
                "safe": 0.45,
                "warning": 0.70,
                "danger": 0.82,
            },
            "mini_audit": {
                "structure": 25,
                "seo": 25,
                "readability": 25,
                "credibility": 25,
            },
            "updated_at": "unknown",
        }
    return data


@lru_cache(maxsize=1)
def load_app_version() -> Dict[str, Any]:
    """
    アプリ全体のバージョン情報を読み込む。

    config/app_version.json を想定。
    """
    path = CONFIG_DIR / "app_version.json"
    data = _safe_read_json(path)
    if not data:
        # 最低限のデフォルト
        return {
            "app_name": "AI Writer MVP - Meigen Rakuichi",
            "version": "0.0.0",
            "major_features": [],
            "last_updated": "unknown",
        }
    return data


@lru_cache(maxsize=1)
def load_legal_notice_text() -> str:
    """
    免責文（legal_notice.md）の全文テキストを取得する。

    Quality Gateで表示したり、ログにバージョン番号だけ残したりする用途。
    """
    path = CONFIG_DIR / "legal_notice.md"
    text = _safe_read_text(path)
    return text


def get_legal_version() -> Optional[str]:
    """
    legal_version.json から免責文のバージョン番号だけを取り出す。
    """
    path = CONFIG_DIR / "legal_version.json"
    data = _safe_read_json(path)
    version = data.get("version")
    if isinstance(version, str):
        return version
    return None


def debug_print_all() -> None:
    """
    デバッグ用：ターミナルで設定の中身を確認したいときに使う。
    """
    print("=== thresholds.json ===")
    print(load_thresholds())
    print("=== app_version.json ===")
    print(load_app_version())
    print("=== legal_version ===")
    print(get_legal_version())
    print("=== legal_notice.md (先頭200文字) ===")
    ln = load_legal_notice_text()
    print(ln[:200] + ("..." if len(ln) > 200 else ""))
