"""Local SQLite storage for subject progress, notes, and study time."""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

STATUSES = ("Pendente", "Fazendo", "Resolvido")
TIME_MODES = ("sessions", "manual", "date")


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
    """Create local tables and add catalog subjects without changing saved progress."""
    location = path or database_path()
    keys = [subject["key"] for subject in subjects]
    connection = _connect(location)
    try:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS progress (
                subject_key TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK (status IN ('Pendente', 'Fazendo', 'Resolvido')),
                updated_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS subject_details (
                subject_key TEXT PRIMARY KEY,
                notes TEXT NOT NULL DEFAULT '',
                time_mode TEXT NOT NULL DEFAULT 'sessions'
                    CHECK (time_mode IN ('sessions', 'manual', 'date')),
                planned_minutes INTEGER CHECK (planned_minutes IS NULL OR planned_minutes >= 0),
                manual_remaining_minutes INTEGER
                    CHECK (manual_remaining_minutes IS NULL OR manual_remaining_minutes >= 0),
                target_date TEXT
            )"""
        )
        connection.execute(
            """CREATE TABLE IF NOT EXISTS study_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_key TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
                studied_at TEXT NOT NULL
            )"""
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_study_sessions_subject_date "
            "ON study_sessions (subject_key, studied_at DESC, session_id DESC)"
        )
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        connection.executemany(
            "INSERT INTO progress (subject_key, status, updated_at) VALUES (?, 'Pendente', ?) "
            "ON CONFLICT(subject_key) DO NOTHING",
            [(key, now) for key in keys],
        )
        connection.executemany(
            "INSERT INTO subject_details (subject_key) VALUES (?) "
            "ON CONFLICT(subject_key) DO NOTHING",
            [(key,) for key in keys],
        )
        connection.commit()
    finally:
        connection.close()
    return location


def load_subject_details(
    subject_keys: Iterable[str], path: Path | None = None
) -> dict[str, dict]:
    """Read notes and time settings for the requested subjects."""
    keys = list(subject_keys)
    result = {
        key: {
            "notes": "",
            "time_mode": "sessions",
            "planned_minutes": None,
            "manual_remaining_minutes": None,
            "target_date": None,
        }
        for key in keys
    }
    if not keys:
        return result

    connection = _connect(path)
    try:
        placeholders = ",".join("?" for _ in keys)
        rows = connection.execute(
            f"""SELECT subject_key, notes, time_mode, planned_minutes,
                       manual_remaining_minutes, target_date
                FROM subject_details WHERE subject_key IN ({placeholders})""",
            keys,
        ).fetchall()
        for subject_key, notes, mode, planned, remaining, target_date in rows:
            result[subject_key] = {
                "notes": notes or "",
                "time_mode": mode if mode in TIME_MODES else "sessions",
                "planned_minutes": planned,
                "manual_remaining_minutes": remaining,
                "target_date": target_date,
            }
    finally:
        connection.close()
    return result


def _ensure_details_row(connection: sqlite3.Connection, subject_key: str) -> None:
    connection.execute(
        "INSERT INTO subject_details (subject_key) VALUES (?) "
        "ON CONFLICT(subject_key) DO NOTHING",
        (subject_key,),
    )


def save_notes(subject_key: str, notes: str, path: Path | None = None) -> None:
    """Persist the free-form notes for one subject."""
    connection = _connect(path)
    try:
        _ensure_details_row(connection, subject_key)
        connection.execute(
            "UPDATE subject_details SET notes = ? WHERE subject_key = ?",
            (notes, subject_key),
        )
        connection.commit()
    finally:
        connection.close()


def save_time_settings(
    subject_key: str,
    time_mode: str,
    value: int | str | None,
    path: Path | None = None,
) -> None:
    """Save one mode and its value, keeping the other modes' values intact."""
    if time_mode not in TIME_MODES:
        raise ValueError(f"Modo de tempo inválido: {time_mode!r}")

    connection = _connect(path)
    try:
        _ensure_details_row(connection, subject_key)
        if time_mode == "sessions":
            _validate_minutes(value, "Tempo previsto")
            connection.execute(
                "UPDATE subject_details SET time_mode = ?, planned_minutes = ? WHERE subject_key = ?",
                (time_mode, value, subject_key),
            )
        elif time_mode == "manual":
            _validate_minutes(value, "Tempo restante")
            connection.execute(
                "UPDATE subject_details SET time_mode = ?, manual_remaining_minutes = ? WHERE subject_key = ?",
                (time_mode, value, subject_key),
            )
        else:
            if value is not None:
                if not isinstance(value, str):
                    raise ValueError("A data de conclusão precisa estar no formato AAAA-MM-DD.")
                try:
                    value = date.fromisoformat(value).isoformat()
                except ValueError as error:
                    raise ValueError("A data de conclusão precisa estar no formato AAAA-MM-DD.") from error
            connection.execute(
                "UPDATE subject_details SET time_mode = ?, target_date = ? WHERE subject_key = ?",
                (time_mode, value, subject_key),
            )
        connection.commit()
    finally:
        connection.close()


def _validate_minutes(value: int | str | None, label: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} deve ser informado em minutos inteiros e não negativos.")


def load_sessions(subject_key: str, path: Path | None = None) -> list[dict]:
    """Read one subject's sessions, newest date and entry first."""
    connection = _connect(path)
    try:
        rows = connection.execute(
            """SELECT session_id, duration_minutes, studied_at
               FROM study_sessions WHERE subject_key = ?
               ORDER BY studied_at DESC, session_id DESC""",
            (subject_key,),
        ).fetchall()
        return [
            {"session_id": session_id, "duration_minutes": duration, "studied_at": studied_at}
            for session_id, duration, studied_at in rows
        ]
    finally:
        connection.close()


def load_session_totals(
    subject_keys: Iterable[str], path: Path | None = None
) -> dict[str, int]:
    """Sum logged minutes by subject without reading the complete history."""
    keys = list(subject_keys)
    totals = {key: 0 for key in keys}
    if not keys:
        return totals

    connection = _connect(path)
    try:
        placeholders = ",".join("?" for _ in keys)
        rows = connection.execute(
            f"""SELECT subject_key, SUM(duration_minutes)
                FROM study_sessions WHERE subject_key IN ({placeholders})
                GROUP BY subject_key""",
            keys,
        ).fetchall()
        totals.update({subject_key: minutes or 0 for subject_key, minutes in rows})
    finally:
        connection.close()
    return totals


def add_session(
    subject_key: str,
    duration_minutes: int,
    studied_at: str,
    path: Path | None = None,
) -> int:
    """Insert one positive-duration session with an ISO calendar date."""
    _validate_minutes(duration_minutes, "Duração da sessão")
    if duration_minutes == 0:
        raise ValueError("A sessão precisa ter duração maior que zero.")
    if not isinstance(studied_at, str):
        raise ValueError("A data da sessão precisa estar no formato AAAA-MM-DD.")
    try:
        studied_at = date.fromisoformat(studied_at).isoformat()
    except ValueError as error:
        raise ValueError("A data da sessão precisa estar no formato AAAA-MM-DD.") from error

    connection = _connect(path)
    try:
        cursor = connection.execute(
            "INSERT INTO study_sessions (subject_key, duration_minutes, studied_at) VALUES (?, ?, ?)",
            (subject_key, duration_minutes, studied_at),
        )
        connection.commit()
        return int(cursor.lastrowid)
    finally:
        connection.close()


def delete_session(session_id: int, path: Path | None = None) -> None:
    """Remove a single session entry."""
    connection = _connect(path)
    try:
        connection.execute("DELETE FROM study_sessions WHERE session_id = ?", (session_id,))
        connection.commit()
    finally:
        connection.close()


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
