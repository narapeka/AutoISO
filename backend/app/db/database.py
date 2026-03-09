import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.models import EventRecord, JobCreate, JobRecord, JobSourceType, JobStatus, JobUpdate


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


TERMINAL_STATES = (
    JobStatus.completed.value,
    JobStatus.failed.value,
    JobStatus.cancelled.value,
)


class Database:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            self._migrate_jobs_table(connection)
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS processed_sources (
                    source_fingerprint TEXT PRIMARY KEY,
                    last_job_id INTEGER NOT NULL,
                    last_status TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def _migrate_jobs_table(self, connection: sqlite3.Connection) -> None:
        existing = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
        ).fetchone()
        if not existing:
            connection.executescript(self._jobs_schema())
            return

        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
        }
        required = {"source_type", "source_key", "source_fingerprint", "auto_upload"}
        if not required.issubset(columns):
            connection.execute("ALTER TABLE jobs RENAME TO jobs_legacy")
            connection.executescript(self._jobs_schema())
            legacy_rows = connection.execute("SELECT * FROM jobs_legacy").fetchall()
            for row in legacy_rows:
                torrent_hash = row["torrent_hash"]
                source_fingerprint = f"qb_auto:{torrent_hash}"
                connection.execute(
                    """
                    INSERT INTO jobs (
                        id, source_type, source_key, source_fingerprint, torrent_hash, torrent_name,
                        source_path, category, tags_json, auto_upload, status, iso_path, iso_size_bytes,
                        upload_target_path, clouddrive_task_key, upload_bytes, upload_total_bytes,
                        pack_progress_percent, manual_repack, manual_reupload, pack_log,
                        error_message, completed_at, pack_started_at, pack_finished_at, upload_started_at,
                        upload_finished_at, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["id"],
                        JobSourceType.qb_auto.value,
                        torrent_hash,
                        source_fingerprint,
                        torrent_hash,
                        row["torrent_name"],
                        row["source_path"],
                        row["category"],
                        row["tags_json"],
                        1,
                        row["status"],
                        row["iso_path"],
                        row["iso_size_bytes"],
                        row["upload_target_path"],
                        row["clouddrive_task_key"],
                        None,
                        None,
                        None,
                        row["manual_repack"],
                        row["manual_reupload"],
                        row["pack_log"],
                        row["error_message"],
                        row["completed_at"],
                        row["pack_started_at"],
                        row["pack_finished_at"],
                        row["upload_started_at"],
                        row["upload_finished_at"],
                        row["created_at"],
                        row["updated_at"],
                    ),
                )
            connection.execute("DROP TABLE jobs_legacy")
        else:
            # Incremental migrations for new columns on existing schema
            if "upload_bytes" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN upload_bytes INTEGER")
            if "upload_total_bytes" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN upload_total_bytes INTEGER")
            if "pack_progress_percent" not in columns:
                connection.execute("ALTER TABLE jobs ADD COLUMN pack_progress_percent INTEGER")

    @staticmethod
    def _jobs_schema() -> str:
        return """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_type TEXT NOT NULL,
                source_key TEXT NOT NULL,
                source_fingerprint TEXT NOT NULL,
                torrent_hash TEXT,
                torrent_name TEXT NOT NULL,
                source_path TEXT NOT NULL,
                category TEXT,
                tags_json TEXT NOT NULL DEFAULT '[]',
                auto_upload INTEGER NOT NULL DEFAULT 1,
                status TEXT NOT NULL,
                iso_path TEXT,
                iso_size_bytes INTEGER,
                upload_target_path TEXT,
                clouddrive_task_key TEXT,
                upload_bytes INTEGER,
                upload_total_bytes INTEGER,
                pack_progress_percent INTEGER,
                manual_repack INTEGER NOT NULL DEFAULT 0,
                manual_reupload INTEGER NOT NULL DEFAULT 0,
                pack_log TEXT,
                error_message TEXT,
                completed_at TEXT,
                pack_started_at TEXT,
                pack_finished_at TEXT,
                upload_started_at TEXT,
                upload_finished_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_jobs_source_fingerprint ON jobs(source_fingerprint);
            CREATE INDEX IF NOT EXISTS idx_jobs_torrent_hash ON jobs(torrent_hash);
        """

    def list_jobs(self) -> list[JobRecord]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM jobs ORDER BY updated_at DESC, id DESC").fetchall()
        return [self._job_from_row(row) for row in rows]

    def list_jobs_by_status(self, statuses: list[JobStatus]) -> list[JobRecord]:
        if not statuses:
            return []
        placeholders = ",".join("?" for _ in statuses)
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM jobs WHERE status IN ({placeholders}) ORDER BY created_at ASC, id ASC",
                [status.value for status in statuses],
            ).fetchall()
        return [self._job_from_row(row) for row in rows]

    def get_job(self, job_id: int) -> JobRecord | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._job_from_row(row) if row else None

    def find_active_job_by_fingerprint(self, source_fingerprint: str) -> JobRecord | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM jobs
                WHERE source_fingerprint = ?
                AND status NOT IN (?, ?, ?)
                ORDER BY id DESC
                LIMIT 1
                """,
                (source_fingerprint, *TERMINAL_STATES),
            ).fetchone()
        return self._job_from_row(row) if row else None

    def find_latest_job_by_fingerprint(self, source_fingerprint: str) -> JobRecord | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE source_fingerprint = ? ORDER BY id DESC LIMIT 1",
                (source_fingerprint,),
            ).fetchone()
        return self._job_from_row(row) if row else None

    def has_processed_source(self, source_fingerprint: str) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT source_fingerprint FROM processed_sources WHERE source_fingerprint = ?",
                (source_fingerprint,),
            ).fetchone()
        return row is not None

    def create_job(self, payload: JobCreate) -> JobRecord:
        now = utcnow()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO jobs (
                    source_type, source_key, source_fingerprint, torrent_hash, torrent_name,
                    source_path, category, tags_json, auto_upload, status, manual_repack,
                    manual_reupload, completed_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.source_type.value,
                    payload.source_key,
                    payload.source_fingerprint,
                    payload.torrent_hash,
                    payload.torrent_name,
                    payload.source_path,
                    payload.category,
                    json.dumps(payload.tags),
                    int(payload.auto_upload),
                    payload.status.value,
                    int(payload.manual_repack),
                    int(payload.manual_reupload),
                    payload.completed_at.isoformat() if payload.completed_at else None,
                    now,
                    now,
                ),
            )
            job_id = int(cursor.lastrowid)
        job = self.get_job(job_id)
        assert job is not None
        return job

    def update_job(self, job_id: int, payload: JobUpdate) -> JobRecord:
        values = payload.model_dump(exclude_unset=True)
        assignments: list[str] = []
        parameters: list[object] = []
        for key, value in values.items():
            assignments.append(f"{key} = ?")
            if isinstance(value, JobStatus):
                parameters.append(value.value)
            elif isinstance(value, datetime):
                parameters.append(value.isoformat())
            elif isinstance(value, bool):
                parameters.append(int(value))
            else:
                parameters.append(value)
        assignments.append("updated_at = ?")
        parameters.append(utcnow())
        parameters.append(job_id)
        with self.connect() as connection:
            connection.execute(f"UPDATE jobs SET {', '.join(assignments)} WHERE id = ?", parameters)
        job = self.get_job(job_id)
        assert job is not None
        return job

    def delete_job(self, job_id: int) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            return cursor.rowcount > 0

    def mark_processed_source(self, source_fingerprint: str, job_id: int, status: JobStatus) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO processed_sources (source_fingerprint, last_job_id, last_status, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source_fingerprint) DO UPDATE SET
                    last_job_id = excluded.last_job_id,
                    last_status = excluded.last_status,
                    updated_at = excluded.updated_at
                """,
                (source_fingerprint, job_id, status.value, utcnow()),
            )

    def add_event(self, message: str, level: str = "INFO", job_id: int | None = None) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO events (job_id, level, message, created_at) VALUES (?, ?, ?, ?)",
                (job_id, level, message, utcnow()),
            )

    def list_events(self, job_id: int | None = None, limit: int = 200) -> list[EventRecord]:
        with self.connect() as connection:
            if job_id is None:
                rows = connection.execute(
                    "SELECT * FROM events ORDER BY created_at DESC, id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM events WHERE job_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                    (job_id, limit),
                ).fetchall()
        return [
            EventRecord(
                id=row["id"],
                job_id=row["job_id"],
                level=row["level"],
                message=row["message"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def _job_from_row(self, row: sqlite3.Row) -> JobRecord:
        return JobRecord(
            id=row["id"],
            source_type=JobSourceType(row["source_type"]),
            source_key=row["source_key"],
            source_fingerprint=row["source_fingerprint"],
            torrent_hash=row["torrent_hash"],
            torrent_name=row["torrent_name"],
            source_path=row["source_path"],
            category=row["category"],
            tags=json.loads(row["tags_json"]),
            auto_upload=bool(row["auto_upload"]),
            status=JobStatus(row["status"]),
            iso_path=row["iso_path"],
            iso_size_bytes=row["iso_size_bytes"],
            upload_target_path=row["upload_target_path"],
            clouddrive_task_key=row["clouddrive_task_key"],
            upload_bytes=row["upload_bytes"],
            upload_total_bytes=row["upload_total_bytes"],
            pack_progress_percent=row["pack_progress_percent"],
            manual_repack=bool(row["manual_repack"]),
            manual_reupload=bool(row["manual_reupload"]),
            pack_log=row["pack_log"],
            error_message=row["error_message"],
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            pack_started_at=datetime.fromisoformat(row["pack_started_at"]) if row["pack_started_at"] else None,
            pack_finished_at=datetime.fromisoformat(row["pack_finished_at"]) if row["pack_finished_at"] else None,
            upload_started_at=datetime.fromisoformat(row["upload_started_at"]) if row["upload_started_at"] else None,
            upload_finished_at=datetime.fromisoformat(row["upload_finished_at"]) if row["upload_finished_at"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
