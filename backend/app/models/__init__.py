from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JobSourceType(str, Enum):
    qb_auto = "qb_auto"
    qb_manual = "qb_manual"
    folder_manual = "folder_manual"


class JobStatus(str, Enum):
    imported = "imported"
    pending = "pending"
    packing = "packing"
    packed = "packed"
    copying_to_mount = "copying_to_mount"
    waiting_for_clouddrive_task = "waiting_for_clouddrive_task"
    uploading = "uploading"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class JobRecord(BaseModel):
    id: int
    source_type: JobSourceType
    source_key: str
    source_fingerprint: str
    torrent_hash: str | None = None
    torrent_name: str
    source_path: str
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    auto_upload: bool = True
    status: JobStatus
    iso_path: str | None = None
    iso_size_bytes: int | None = None
    upload_target_path: str | None = None
    clouddrive_task_key: str | None = None
    upload_bytes: int | None = None
    upload_total_bytes: int | None = None
    pack_progress_percent: int | None = None
    manual_repack: bool = False
    manual_reupload: bool = False
    pack_log: str | None = None
    error_message: str | None = None
    completed_at: datetime | None = None
    pack_started_at: datetime | None = None
    pack_finished_at: datetime | None = None
    upload_started_at: datetime | None = None
    upload_finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class JobCreate(BaseModel):
    source_type: JobSourceType
    source_key: str
    source_fingerprint: str
    torrent_hash: str | None = None
    torrent_name: str
    source_path: str
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    auto_upload: bool = True
    status: JobStatus = JobStatus.pending
    completed_at: datetime | None = None
    manual_repack: bool = False
    manual_reupload: bool = False


class JobUpdate(BaseModel):
    status: JobStatus | None = None
    iso_path: str | None = None
    iso_size_bytes: int | None = None
    upload_target_path: str | None = None
    clouddrive_task_key: str | None = None
    upload_bytes: int | None = None
    upload_total_bytes: int | None = None
    pack_progress_percent: int | None = None
    auto_upload: bool | None = None
    manual_repack: bool | None = None
    manual_reupload: bool | None = None
    pack_log: str | None = None
    error_message: str | None = None
    pack_started_at: datetime | None = None
    pack_finished_at: datetime | None = None
    upload_started_at: datetime | None = None
    upload_finished_at: datetime | None = None


class EventRecord(BaseModel):
    id: int
    job_id: int | None = None
    level: str
    message: str
    created_at: datetime


class ManualQBTaskRequest(BaseModel):
    torrent_hash: str
    auto_upload: bool = True


class ManualFolderTaskRequest(BaseModel):
    source_path: str
    name: str | None = None
    auto_upload: bool = True


class ManualUploadRequest(BaseModel):
    force: bool = False


class AutoPollingPayload(BaseModel):
    enabled: bool


class SettingsPayload(BaseModel):
    values: dict[str, str | int | bool]


class QBTaskSummary(BaseModel):
    torrent_hash: str
    name: str
    source_path: str
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    completed_at: datetime
    already_known: bool = False


class BatchJobIdsRequest(BaseModel):
    job_ids: list[int]


class SystemStatus(BaseModel):
    app_name: str
    qbittorrent_connected: bool
    clouddrive_connected: bool
    xorriso_available: bool
    degraded_upload_monitoring: bool
    active_uploads: int
    queued_jobs: int
    auto_polling_enabled: bool
    auto_import_mode: str
