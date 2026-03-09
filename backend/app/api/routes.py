import os
import string
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from app.config import save_settings
from app.models import (
    AutoPollingPayload,
    BatchJobIdsRequest,
    EventRecord,
    JobRecord,
    ManualFolderTaskRequest,
    ManualQBTaskRequest,
    QBTaskSummary,
    SettingsPayload,
    SystemStatus,
)
from app.services.iso_builder import IsoBuilder
from app.services.orchestrator import Orchestrator

router = APIRouter(prefix="/api")


def get_orchestrator(request: Request) -> Orchestrator:
    return request.app.state.orchestrator  # type: ignore[no-any-return]


@router.get("/health", response_model=SystemStatus)
def health(request: Request) -> SystemStatus:
    return get_orchestrator(request).system_status()


@router.get("/jobs", response_model=list[JobRecord])
def list_jobs(request: Request) -> list[JobRecord]:
    return get_orchestrator(request).services.db.list_jobs()


@router.get("/jobs/{job_id}", response_model=JobRecord)
def get_job(request: Request, job_id: int) -> JobRecord:
    job = get_orchestrator(request).services.db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/events", response_model=list[EventRecord])
def list_events(request: Request, job_id: int | None = None, limit: int = 200) -> list[EventRecord]:
    return get_orchestrator(request).services.db.list_events(job_id=job_id, limit=limit)


@router.get("/settings", response_model=dict[str, str | int | bool])
def get_settings(request: Request) -> dict[str, str | int | bool]:
    return request.app.state.settings.operator_dict()  # type: ignore[no-any-return]


@router.put("/settings", response_model=dict[str, str | int | bool])
def put_settings(request: Request, payload: SettingsPayload) -> dict[str, str | int | bool]:
    settings = save_settings(payload.values)
    request.app.state.settings = settings
    get_orchestrator(request).reload_settings(settings)
    return settings.operator_dict()


@router.post("/dashboard/auto-polling", response_model=SystemStatus)
def set_auto_polling(request: Request, payload: AutoPollingPayload) -> SystemStatus:
    orchestrator = get_orchestrator(request)
    orchestrator.set_auto_polling(payload.enabled)
    return orchestrator.system_status()


def _list_drives() -> list[dict]:
    """Return list of drive letters on Windows (e.g. C:\, D:\)."""
    entries = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            entries.append({"name": f"{letter}:", "path": drive, "is_dir": True})
    return entries


@router.get("/browse")
def browse(path: str = "") -> dict:
    """List direct child directories. Empty or '/' = system root (on Windows: drive list)."""
    path_str = path.strip()
    if not path_str or path_str == "/":
        if os.name == "nt":
            return {"path": "", "entries": _list_drives()}
        resolved = Path("/")
        entries = []
        for child in sorted(resolved.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                entries.append({"name": child.name, "path": str(child), "is_dir": True})
        return {"path": str(resolved), "entries": entries}
    resolved = Path(path_str).expanduser().resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise HTTPException(status_code=404, detail="Path does not exist or is not a directory")
    entries = []
    for child in sorted(resolved.iterdir()):
        if child.is_dir() and not child.name.startswith("."):
            entries.append({"name": child.name, "path": str(child), "is_dir": True})
    return {"path": str(resolved), "entries": entries}


@router.get("/browse/check-bdmv")
def check_bdmv(path: str) -> dict:
    """Return whether the given path is a valid BDMV root (or BDMV folder)."""
    if not path or path.strip() == "/":
        return {"is_bdmv": False}
    resolved = Path(path.strip()).expanduser().resolve()
    if not resolved.exists() or not resolved.is_dir():
        return {"is_bdmv": False}
    root = IsoBuilder._resolve_bdmv_root(resolved)
    return {"is_bdmv": root is not None}


@router.get("/qbittorrent/completed", response_model=list[QBTaskSummary])
def list_completed_qb_tasks(request: Request) -> list[QBTaskSummary]:
    return get_orchestrator(request).list_completed_qb_tasks()


@router.post("/jobs/manual/qbittorrent", response_model=JobRecord)
def create_manual_qb_job(request: Request, payload: ManualQBTaskRequest) -> JobRecord:
    try:
        return get_orchestrator(request).create_manual_qb_job(
            payload.torrent_hash,
            auto_upload=payload.auto_upload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jobs/manual/folder", response_model=JobRecord)
def create_manual_folder_job(request: Request, payload: ManualFolderTaskRequest) -> JobRecord:
    try:
        return get_orchestrator(request).create_manual_folder_job(
            payload.source_path,
            name=payload.name,
            auto_upload=payload.auto_upload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/upload", response_model=JobRecord)
def upload_job(request: Request, job_id: int) -> JobRecord:
    try:
        return get_orchestrator(request).upload_packed_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/retry", response_model=JobRecord)
def retry_job(request: Request, job_id: int) -> JobRecord:
    try:
        return get_orchestrator(request).retry_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/reupload", response_model=JobRecord)
def reupload_job(request: Request, job_id: int) -> JobRecord:
    try:
        return get_orchestrator(request).reupload_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/repack", response_model=JobRecord)
def repack_job(request: Request, job_id: int) -> JobRecord:
    try:
        return get_orchestrator(request).repack_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/cancel", response_model=JobRecord)
def cancel_job(request: Request, job_id: int) -> JobRecord:
    try:
        return get_orchestrator(request).cancel_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/start", response_model=JobRecord)
def start_job(request: Request, job_id: int) -> JobRecord:
    try:
        return get_orchestrator(request).start_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jobs/batch/start", response_model=list[JobRecord])
def batch_start_jobs(request: Request, payload: BatchJobIdsRequest) -> list[JobRecord]:
    return get_orchestrator(request).start_jobs(payload.job_ids)


@router.post("/jobs/batch/cancel", response_model=list[JobRecord])
def batch_cancel_jobs(request: Request, payload: BatchJobIdsRequest) -> list[JobRecord]:
    return get_orchestrator(request).cancel_jobs(payload.job_ids)


@router.delete("/jobs/{job_id}")
def delete_job(request: Request, job_id: int) -> dict:
    try:
        get_orchestrator(request).delete_job(job_id)
        return {"ok": True}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
