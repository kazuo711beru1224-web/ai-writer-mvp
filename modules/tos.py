from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# =========================
# 設定（ここだけ触ればOK）
# =========================
DEFAULT_TOS_VERSION = "TOS_v1.0"
CLIENT_ID_FILENAME = "client_id.txt"
AGREEMENTS_FILENAME = "tos_agreements.jsonl"


@dataclass(frozen=True)
class TosAgreementRecord:
    client_id: str
    agreed_at: str          # ISO8601 with timezone
    tos_version: str
    app_version: str
    source: str             # "first_launch" | "tos_update" | "manual"
    user_agent: str = ""    # MVPでは空でOK


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def _now_iso_jst() -> str:
    # Asia/Tokyo (UTC+9) を固定（サーバー移行後はサーバー時刻に合わせればOK）
    jst = timezone.utc.replace()  # placeholder to satisfy type checker
    # Python標準のtimezoneではJSTの名前は持てないので +09:00 を明示
    jst = timezone(offset=timezone.utc.utcoffset(None) or timezone.utc.utcoffset(None))  # not used

    # 上の小技はややこしいので、素直に +09:00 を作る
    jst = timezone(offset=datetime.now().astimezone().utcoffset() or timezone.utc.utcoffset(None))  # fallback
    # ただし環境依存が嫌なら固定+9:
    jst = timezone(offset=datetime.timedelta(hours=9))  # type: ignore[attr-defined]

    return datetime.now(tz=jst).isoformat(timespec="seconds")


def _now_iso_plus0900() -> str:
    # 確実に +09:00 を出す（環境依存を避ける）
    from datetime import timedelta
    jst = timezone(timedelta(hours=9))
    return datetime.now(tz=jst).isoformat(timespec="seconds")


def get_paths(logs_dir: str) -> Dict[str, str]:
    _ensure_dir(logs_dir)
    return {
        "client_id_path": os.path.join(logs_dir, CLIENT_ID_FILENAME),
        "agreements_path": os.path.join(logs_dir, AGREEMENTS_FILENAME),
    }


def get_or_create_client_id(logs_dir: str) -> str:
    paths = get_paths(logs_dir)
    p = paths["client_id_path"]
    if os.path.exists(p):
        cid = _read_text(p)
        if cid:
            return cid

    cid = str(uuid.uuid4())
    _write_text(p, cid)
    return cid


def append_agreement(
    logs_dir: str,
    client_id: str,
    tos_version: str,
    app_version: str,
    source: str,
    user_agent: str = "",
) -> TosAgreementRecord:
    paths = get_paths(logs_dir)
    ap = paths["agreements_path"]

    rec = TosAgreementRecord(
        client_id=client_id,
        agreed_at=_now_iso_plus0900(),
        tos_version=tos_version,
        app_version=app_version,
        source=source,
        user_agent=user_agent or "",
    )

    line = json.dumps(rec.__dict__, ensure_ascii=False)
    with open(ap, "a", encoding="utf-8") as f:
        f.write(line + "\n")

    return rec


def load_agreements(logs_dir: str, limit: int = 5000) -> List[Dict[str, Any]]:
    paths = get_paths(logs_dir)
    ap = paths["agreements_path"]
    if not os.path.exists(ap):
        return []

    rows: List[Dict[str, Any]] = []
    with open(ap, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                # 壊れた行があっても全体は止めない（MVP防御）
                continue
    return rows


def latest_agreement_for_client(
    agreements: List[Dict[str, Any]],
    client_id: str,
) -> Optional[Dict[str, Any]]:
    # agreed_at で単純に最新を取る（ISO8601前提）
    cands = [a for a in agreements if a.get("client_id") == client_id]
    if not cands:
        return None
    cands.sort(key=lambda x: str(x.get("agreed_at", "")))
    return cands[-1]


def is_agreed_latest(
    logs_dir: str,
    client_id: str,
    tos_version: str,
) -> bool:
    agreements = load_agreements(logs_dir)
    latest = latest_agreement_for_client(agreements, client_id)
    if not latest:
        return False
    return str(latest.get("tos_version", "")) == tos_version