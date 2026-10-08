"""SQLite-backed local Scene registry."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


def data_root() -> Path:
    return Path(os.getenv("S3D_DATA_DIR", Path.cwd() / "data"))


def inbox_root() -> Path:
    return Path(os.getenv("S3D_INBOX_DIR", Path.cwd() / "inbox"))


@contextmanager
def database():
    root = data_root()
    root.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(root / "s3d.sqlite3", timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS scenes (
            id TEXT PRIMARY KEY, package_sha256 TEXT NOT NULL, status TEXT NOT NULL,
            package_path TEXT NOT NULL, error TEXT
        );
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, scene_id TEXT NOT NULL,
            status TEXT NOT NULL, stage TEXT, error TEXT,
            FOREIGN KEY (scene_id) REFERENCES scenes(id)
        );
        CREATE TABLE IF NOT EXISTS stage_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL,
            stage TEXT NOT NULL, status TEXT NOT NULL, seconds REAL,
            peak_vram_mb REAL, error TEXT, config TEXT
        );
        CREATE TABLE IF NOT EXISTS objects (
            scene_id TEXT NOT NULL, id INTEGER NOT NULL, data TEXT NOT NULL, embedding BLOB, mask BLOB,
            PRIMARY KEY (scene_id, id),
            FOREIGN KEY (scene_id) REFERENCES scenes(id)
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY, scene_id TEXT NOT NULL, last_object_id INTEGER,
            pending_targets TEXT, pending_context TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, scene_id TEXT NOT NULL,
            session_id TEXT, text TEXT NOT NULL, program TEXT, viewpoint TEXT,
            result TEXT, n_solutions INTEGER NOT NULL DEFAULT 0,
            used_tiebreak INTEGER NOT NULL DEFAULT 0,
            json_retry INTEGER NOT NULL DEFAULT 0,
            latency_ms REAL
        );
    """)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(objects)")}
    if "embedding" not in columns:
        connection.execute("ALTER TABLE objects ADD COLUMN embedding BLOB")
    if "mask" not in columns:
        connection.execute("ALTER TABLE objects ADD COLUMN mask BLOB")
    stage_columns = {row[1] for row in connection.execute("PRAGMA table_info(stage_runs)")}
    if "config" not in stage_columns:
        connection.execute("ALTER TABLE stage_runs ADD COLUMN config TEXT")
    session_columns = {row[1] for row in connection.execute("PRAGMA table_info(sessions)")}
    if "pending_context" not in session_columns:
        connection.execute("ALTER TABLE sessions ADD COLUMN pending_context TEXT")
    try:
        yield connection
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
