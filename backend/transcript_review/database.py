from __future__ import annotations

import json
import os
import platform
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _default_data_dir() -> Path:
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Transcript Review Studio"
    if system == "Windows":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Transcript Review Studio"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "transcript-review-studio"


DATA_DIR = Path(os.environ.get("TRS_DATA_DIR", _default_data_dir())).expanduser().resolve()
PROJECTS_DIR = DATA_DIR / "projects"
DATABASE_PATH = DATA_DIR / "studio.sqlite3"


def _private_mode(path: Path, mode: int) -> None:
    """Best-effort Unix permissions; Windows uses its own ACL model."""
    if os.name == "nt":
        return
    try:
        path.chmod(mode)
    except OSError:
        pass


def harden_data_permissions() -> None:
    """Research media and transcripts are private to the current OS account by default."""
    _private_mode(DATA_DIR, 0o700)
    _private_mode(PROJECTS_DIR, 0o700)
    for root, directories, files in os.walk(PROJECTS_DIR):
        root_path = Path(root)
        _private_mode(root_path, 0o700)
        for directory in directories:
            _private_mode(root_path / directory, 0o700)
        for filename in files:
            _private_mode(root_path / filename, 0o600)
    for database_file in (DATABASE_PATH, Path(f"{DATABASE_PATH}-wal"), Path(f"{DATABASE_PATH}-shm")):
        if database_file.exists():
            _private_mode(database_file, 0o600)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def initialize() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    with connection() as db:
        db.executescript(
            """
            PRAGMA journal_mode = WAL;
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recordings (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                media_path TEXT NOT NULL,
                source_path TEXT,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'imported',
                processing_stage TEXT NOT NULL DEFAULT 'Ready to process',
                processed_percent INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS speaker_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recording_id TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
                speaker TEXT NOT NULL,
                path TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recording_id TEXT NOT NULL REFERENCES recordings(id) ON DELETE CASCADE,
                cue_index INTEGER NOT NULL,
                start_ms INTEGER NOT NULL,
                end_ms INTEGER NOT NULL,
                source_text TEXT NOT NULL DEFAULT '',
                stt_a_text TEXT NOT NULL DEFAULT '',
                stt_b_text TEXT NOT NULL DEFAULT '',
                final_text TEXT NOT NULL DEFAULT '',
                speaker TEXT NOT NULL DEFAULT 'Unknown speaker',
                confidence_a REAL,
                confidence_b REAL,
                ambiguity_score INTEGER NOT NULL DEFAULT 0,
                ambiguity_reasons TEXT NOT NULL DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'pending',
                updated_at TEXT NOT NULL,
                UNIQUE(recording_id, cue_index)
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cue_id INTEGER NOT NULL REFERENCES cues(id) ON DELETE CASCADE,
                action TEXT NOT NULL,
                before_json TEXT NOT NULL,
                after_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_recordings_project ON recordings(project_id);
            CREATE INDEX IF NOT EXISTS idx_cues_recording ON cues(recording_id, cue_index);
            CREATE INDEX IF NOT EXISTS idx_cues_status ON cues(recording_id, status);
            CREATE INDEX IF NOT EXISTS idx_audit_cue ON audit_log(cue_id, created_at);
            """
        )
        project_columns = {row["name"] for row in db.execute("PRAGMA table_info(projects)").fetchall()}
        if "reviewer" not in project_columns:
            db.execute("ALTER TABLE projects ADD COLUMN reviewer TEXT NOT NULL DEFAULT ''")
        cue_columns = {row["name"] for row in db.execute("PRAGMA table_info(cues)").fetchall()}
        if "revision" not in cue_columns:
            db.execute("ALTER TABLE cues ADD COLUMN revision INTEGER NOT NULL DEFAULT 0")
        audit_columns = {row["name"] for row in db.execute("PRAGMA table_info(audit_log)").fetchall()}
        if "reviewer" not in audit_columns:
            db.execute("ALTER TABLE audit_log ADD COLUMN reviewer TEXT NOT NULL DEFAULT 'Not recorded'")
        # A computer shutdown or force-quit can stop a local model mid-pass. The
        # previous cues remain transactionally intact, so surface a retryable state
        # instead of leaving the recording permanently labelled "processing".
        db.execute(
            """
            UPDATE recordings
            SET status = 'error', processing_stage = 'Processing was interrupted',
                error = 'The local app closed before processing finished. Existing transcript data is safe; choose Try again.',
                processed_percent = 0, updated_at = ?
            WHERE status = 'processing'
            """,
            (utc_now(),),
        )
    harden_data_permissions()


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATABASE_PATH, timeout=30)
    _private_mode(DATABASE_PATH, 0o600)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
        for sidecar in (Path(f"{DATABASE_PATH}-wal"), Path(f"{DATABASE_PATH}-shm")):
            if sidecar.exists():
                _private_mode(sidecar, 0o600)


def has_human_work(db: sqlite3.Connection, recording_id: str) -> bool:
    return bool(db.execute(
        """SELECT 1 FROM cues c WHERE c.recording_id = ? AND
        (c.status IN ('verified', 'unclear') OR EXISTS
            (SELECT 1 FROM audit_log a WHERE a.cue_id = c.id)) LIMIT 1""",
        (recording_id,),
    ).fetchone())


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [row_to_dict(row) for row in rows]


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    for key in ("metadata_json", "ambiguity_reasons"):
        if key in result:
            try:
                result[key.removesuffix("_json")] = json.loads(result.pop(key))
            except (json.JSONDecodeError, TypeError):
                result[key.removesuffix("_json")] = {} if key == "metadata_json" else []
    return result


def fetch_project(project_id: str) -> dict[str, Any] | None:
    with connection() as db:
        project = row_to_dict(db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())
        if not project:
            return None
        recordings = rows_to_dicts(
            db.execute(
                """
                SELECT r.*,
                       COUNT(c.id) AS cue_count,
                       SUM(CASE WHEN c.status = 'verified' THEN 1 ELSE 0 END) AS verified_count,
                       SUM(CASE WHEN c.status = 'flagged' THEN 1 ELSE 0 END) AS flagged_count
                FROM recordings r
                LEFT JOIN cues c ON c.recording_id = r.id
                WHERE r.project_id = ?
                GROUP BY r.id
                ORDER BY r.created_at
                """,
                (project_id,),
            ).fetchall()
        )
        project["recordings"] = recordings
        return project
