# modules/log_manager.py
from __future__ import annotations

import csv
import json
import os
import datetime as dt
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

ARTICLE_LOG_CSV = LOG_DIR / "article_log.csv"
QUALITY_LOG_JSON = LOG_DIR / "quality_log.json"


def _now_str() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _append_json_list(json_path: Path, json_entry: Dict[str, Any]) -> None:
    """
    JSON配列ファイルに1件追記する。
    datetime等が混ざっても落ちないように default=str で安全に書き込む。
    """
    json_path.parent.mkdir(exist_ok=True)

    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            data = []
    else:
        data = []

    if not isinstance(data, list):
        data = []

    data.append(json_entry)

    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def append_article_log(keyword: str, num_articles: int, output_files: List[str]) -> None:
    """
    生成履歴（記録用）
    """
    is_new = not ARTICLE_LOG_CSV.exists()
    with open(ARTICLE_LOG_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["datetime", "keyword", "num_articles", "output_files"])
        w.writerow([_now_str(), keyword, num_articles, ";".join(output_files)])


def read_article_log_dataframe() -> Optional[pd.DataFrame]:
    if not ARTICLE_LOG_CSV.exists():
        return None
    try:
        return pd.read_csv(ARTICLE_LOG_CSV)
    except Exception:
        return None


def append_quality_log(
    article_id: str,
    main_keyword: str,
    structure_score: int,
    keyword_score: int,
    fact_score: int,
    readability_score: int,
    value_score: int,
    memo: str,
    total_score: int,
) -> None:
    """
    品質ログ（自己採点）
    """
    entry = {
        "datetime": _now_str(),  # ← datetimeオブジェクトは使わない（落ちる原因なので）
        "article_id": article_id,
        "main_keyword": main_keyword,
        "structure_score": int(structure_score),
        "keyword_score": int(keyword_score),
        "fact_score": int(fact_score),
        "readability_score": int(readability_score),
        "value_score": int(value_score),
        "memo": memo or "",
        "total_score": int(total_score),
    }
    _append_json_list(QUALITY_LOG_JSON, entry)
