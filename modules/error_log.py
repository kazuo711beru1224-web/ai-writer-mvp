from __future__ import annotations

import os
import traceback
from datetime import datetime


def log_error(logs_dir: str, where: str, err: Exception) -> str:
    os.makedirs(logs_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(logs_dir, f"error_{ts}.log")

    body = []
    body.append(f"[when] {ts}")
    body.append(f"[where] {where}")
    body.append(f"[type] {type(err).__name__}")
    body.append(f"[message] {err}")
    body.append("")
    body.append("[traceback]")
    body.append(traceback.format_exc())

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(body))

    return path
