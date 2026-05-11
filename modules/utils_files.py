# modules/utils_files.py
from __future__ import annotations

import os
import re


def safe_filename(name: str, max_len: int = 60) -> str:
    s = (name or "").strip()
    s = re.sub(r"[\\/:*?\"<>|]", "_", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_len:
        s = s[:max_len].rstrip()
    return s if s else "untitled"


def write_text_file(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
