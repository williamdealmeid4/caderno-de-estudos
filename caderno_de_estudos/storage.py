"""Local SQLite storage for study subject progress."""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

STATUSES = ("Pendente", "Fazendo", "Resolvido")


def database_path() -> Path:
    """Return the per-user database location for Linux or Windows."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
        return base / "CadernoDeEstudos" / "progress.sqlite3"

    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "caderno-de-estudos" / "progress.sqlite3"


def _connect(path: Path | None = None) -> sqlite3.Connection:
    location = path or database_path()
    location.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(location, timeout=5.0)


def initialize(subjects: Iterable[dict], path: Path | None = None) -> Path:
    """Create the progress table and add new catalog subjects as pending."""
    location = path or database_path()
    connection = _connect(location)
    try:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS progress (
                subject_key TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK (status IN ('Pendente', 'Fazendo', 'Resolvido')),
                updated_at TEXT NOT NULL
            )"""
        )
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        connection.executemany(
            "INSERT INTO progress (subject_key, status, updated_at) VALUES (?, 'Pendente', ?) "
            "ON CONFLICT(subject_key) DO NOTHING",
            [(subject["key"], now) for subject in subjects],
        )
        connection.commit()
    finally:
        connection.close()
    return location


def load_statuses(subjects: Iterable[dict], path: Path | None = None) -> dict[str, str]:
    """Read the saved status for each catalog subject, defaulting safely."""
    keys = [subject["key"] for subject in subjects]
    result = {key: "Pendente" for key in keys}
    if not keys:
        return result

    connection = _connect(path)
    try:
        placeholders = ",".join("?" for _ in keys)
        rows = connection.execute(
            f"SELECT subject_key, status FROM progress WHERE subject_key IN ({placeholders})",
            keys,
        ).fetchall()
        for subject_key, status in rows:
            result[subject_key] = status if status in STATUSES else "Pendente"
    finally:
        connection.close()
    return result


def save_status(subject_key: str, status: str, path: Path | None = None) -> None:
    """Persist one status update immediately."""
    if status not in STATUSES:
        raise ValueError(f"Status inválido: {status!r}")

    connection = _connect(path)
    try:
        connection.execute(
            """INSERT INTO progress (subject_key, status, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(subject_key) DO UPDATE SET
                 status = excluded.status,
                 updated_at = excluded.updated_at""",
            (subject_key, status, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        connection.commit()
    finally:
        connection.close()
