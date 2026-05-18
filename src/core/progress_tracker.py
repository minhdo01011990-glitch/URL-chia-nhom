"""Session-based checkpoint và resume logic."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional


SESSION_DIR = Path.home() / ".url-labeler"


def _session_path(session_id: str) -> Path:
    return SESSION_DIR / session_id


def new_session() -> str:
    session_id = str(uuid.uuid4())[:8]
    _session_path(session_id).mkdir(parents=True, exist_ok=True)
    return session_id


def save_progress(session_id: str, **kwargs) -> None:
    """Lưu bất kỳ field nào vào progress.json (merge với state hiện tại)."""
    path = _session_path(session_id) / "progress.json"
    current = load_progress(session_id) or {}
    current.update(kwargs)
    current["updated_at"] = datetime.utcnow().isoformat()
    path.write_text(json.dumps(current, indent=2, ensure_ascii=False))


def load_progress(session_id: str) -> Optional[dict]:
    path = _session_path(session_id) / "progress.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_label_config(session_id: str, taxonomy: dict) -> Path:
    path = _session_path(session_id) / "label_config.json"
    path.write_text(json.dumps(taxonomy, indent=2, ensure_ascii=False))
    return path


def load_label_config(session_id: str) -> Optional[dict]:
    path = _session_path(session_id) / "label_config.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_dataframe(session_id: str, df, name: str) -> Path:
    """Lưu DataFrame dưới dạng parquet (gzip)."""
    path = _session_path(session_id) / f"{name}.parquet"
    df.to_parquet(path, compression="gzip", index=True)
    return path


def load_dataframe(session_id: str, name: str):
    """Đọc parquet checkpoint."""
    import pandas as pd

    path = _session_path(session_id) / f"{name}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"Checkpoint '{name}' không tồn tại cho session {session_id}")
    return pd.read_parquet(path)


def list_sessions() -> list[dict]:
    """Liệt kê tất cả sessions hiện có."""
    if not SESSION_DIR.exists():
        return []

    sessions = []
    for d in SESSION_DIR.iterdir():
        if d.is_dir():
            progress = load_progress(d.name)
            sessions.append({
                "session_id": d.name,
                "updated_at": progress.get("updated_at") if progress else None,
                "status": progress.get("status") if progress else "unknown",
                "source": progress.get("source") if progress else None,
            })

    sessions.sort(key=lambda s: s.get("updated_at") or "", reverse=True)
    return sessions


def session_exists(session_id: str) -> bool:
    return (_session_path(session_id) / "progress.json").exists()
