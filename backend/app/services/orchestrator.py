import asyncio
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.db.database import Database
from app.models import JobCreate, JobRecord, JobSourceType, JobStatus, JobUpdate, QBTaskSummary, SystemStatus
from app.services.clouddrive import CloudDriveService
from app.services.iso_builder import IsoBuilder
from app.services.qbittorrent import CompletedTorrent, QBittorrentService
from app.services.upload_manager import UploadManager

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _job_label(job: JobRecord, max_len: int = 56) -> str:
    """用于日志的任务显示名，便于多任务时区分。"""
    name = job.torrent_name or (Path(job.source_path).name if job.source_path else "")
    if not name:
        return f"任务 #{job.id}"
    return name if len(name) <= max_len else name[: max_len - 3] + "..."


@dataclass
class ServiceContainer:
    settings: Settings
    db: Database
    qbittorrent: QBittorrentService
    iso_builder: IsoBuilder
    upload_manager: UploadManager
    clouddrive: CloudDriveService


@dataclass
class Orchestrator:
    services: ServiceContainer
    _task: asyncio.Task[None] | None = None
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    _auto_polling_enabled: bool = False

    async def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.CancelledError, TimeoutError):
                logger.warning("Background orchestrator did not stop cleanly within 5 seconds.")
            finally:
                self._task = None

    def reload_settings(self, settings: Settings) -> None:
        self.services.settings = settings
        self.services.qbittorrent.settings = settings
        self.services.iso_builder.settings = settings
        self.services.upload_manager.settings = settings
        self.services.clouddrive.settings = settings

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._run_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Background cycle failed")
                self.services.db.add_event(f"［系统］后台调度周期失败：{exc}", level="ERROR")
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.services.settings.qbittorrent_poll_interval_seconds,
                )
            except TimeoutError:
                pass

    async def _run_cycle(self) -> None:
        if self._auto_polling_enabled and not self._stop_event.is_set():
            await asyncio.to_thread(self.discover_completed_torrents)
        if self._stop_event.is_set():
            return
        await asyncio.to_thread(self.process_pending_jobs)
        if self._stop_event.is_set():
            return
        await asyncio.to_thread(self.monitor_uploads)
        if self._stop_event.is_set():
            return
        await asyncio.to_thread(self.apply_qbittorrent_throttle)

    def run_cycle(self) -> None:
        if self._auto_polling_enabled:
            self.discover_completed_torrents()
        self.process_pending_jobs()
        self.monitor_uploads()
        self.apply_qbittorrent_throttle()

    def list_completed_qb_tasks(self) -> list[QBTaskSummary]:
        items: list[QBTaskSummary] = []
        for torrent in self.services.qbittorrent.list_completed_torrents():
            fingerprint = self._fingerprint_for_qb(torrent.torrent_hash)
            already_known = self.services.db.find_latest_job_by_fingerprint(fingerprint) is not None
            items.append(
                QBTaskSummary(
                    torrent_hash=torrent.torrent_hash,
                    name=torrent.name,
                    source_path=torrent.source_path,
                    category=torrent.category,
                    tags=torrent.tags,
                    completed_at=torrent.completed_at,
                    already_known=already_known,
                )
            )
        return items

    def create_manual_qb_job(self, torrent_hash: str, auto_upload: bool = True) -> JobRecord:
        torrent = self.services.qbittorrent.get_completed_torrent(torrent_hash)
        if not torrent:
            raise ValueError("Completed qBittorrent task not found")
        return self._create_job_from_torrent(torrent, JobSourceType.qb_manual, auto_upload=auto_upload)

    def create_manual_folder_job(
        self,
        source_path: str,
        name: str | None = None,
        auto_upload: bool = True,
    ) -> JobRecord:
        source = Path(source_path).expanduser()
        if not source.exists():
            raise ValueError("Source folder does not exist")
        fingerprint = self._fingerprint_for_folder(source)
        if self.services.db.find_active_job_by_fingerprint(fingerprint):
            raise ValueError("A job for this source folder is already active")
        if self.services.db.has_processed_source(fingerprint):
            raise ValueError("This source folder was already processed; use repack if needed")

        job = self.services.db.create_job(
            JobCreate(
                source_type=JobSourceType.folder_manual,
                source_key=str(source.resolve()),
                source_fingerprint=fingerprint,
                torrent_hash=None,
                torrent_name=name or source.name,
                source_path=str(source.resolve()),
                auto_upload=auto_upload,
                completed_at=utcnow(),
            )
        )
        self.services.db.add_event(f"已从本地文件夹创建任务「{_job_label(job)}」。", job_id=job.id)
        return job

    def set_auto_polling(self, enabled: bool) -> bool:
        self._auto_polling_enabled = enabled
        return self._auto_polling_enabled

    def discover_completed_torrents(self) -> None:
        mode = self.services.settings.auto_import_mode
        import_only = mode == "import_only"
        pack_and_upload = mode == "full_auto"
        for torrent in self.services.qbittorrent.fetch_completed_torrents():
            fingerprint = self._fingerprint_for_qb(torrent.torrent_hash)
            if self.services.db.has_processed_source(fingerprint):
                continue
            if self.services.db.find_active_job_by_fingerprint(fingerprint):
                continue
            initial_status = JobStatus.imported if import_only else JobStatus.pending
            auto_upload = pack_and_upload  # full_auto → True, pack_only → False
            self._create_job_from_torrent(
                torrent,
                JobSourceType.qb_auto,
                auto_upload=auto_upload,
                initial_status=initial_status,
            )

    def _create_job_from_torrent(
        self,
        torrent: CompletedTorrent,
        source_type: JobSourceType,
        auto_upload: bool,
        initial_status: JobStatus = JobStatus.pending,
    ) -> JobRecord:
        fingerprint = self._fingerprint_for_qb(torrent.torrent_hash)
        if self.services.db.find_active_job_by_fingerprint(fingerprint):
            raise ValueError("A job for this torrent is already active")
        job = self.services.db.create_job(
            JobCreate(
                source_type=source_type,
                source_key=torrent.torrent_hash,
                source_fingerprint=fingerprint,
                torrent_hash=torrent.torrent_hash,
                torrent_name=torrent.name,
                source_path=torrent.source_path,
                category=torrent.category,
                tags=torrent.tags,
                auto_upload=auto_upload,
                status=initial_status,
                completed_at=torrent.completed_at,
            )
        )
        _src = {"qb_auto": "qB 自动", "qb_manual": "qB 手动", "folder_manual": "本地文件夹"}.get(source_type.value, source_type.value)
        if initial_status == JobStatus.imported:
            msg = f"【{_job_label(job)}】已从 {_src} 导入，等待用户点击开始。"
        else:
            msg = f"【{_job_label(job)}】已从 {_src} 加入队列，将自动打包并上传。"
        self.services.db.add_event(msg, job_id=job.id)
        return job

    def process_pending_jobs(self) -> None:
        for job in self.services.db.list_jobs_by_status([JobStatus.pending]):
            self._process_single_job(job)

    def _process_single_job(self, job: JobRecord) -> None:
        self.services.db.update_job(
            job.id,
            JobUpdate(
                status=JobStatus.packing,
                pack_started_at=utcnow(),
                error_message=None,
                pack_progress_percent=0,
            ),
        )
        self.services.db.add_event(f"【{_job_label(job)}】已开始制作 ISO。", job_id=job.id)
        try:

            def on_pack_progress(pct: int) -> None:
                self.services.db.update_job(job.id, JobUpdate(pack_progress_percent=pct))

            result = self.services.iso_builder.build(job, progress_callback=on_pack_progress)
            built_job = self.services.db.update_job(
                job.id,
                JobUpdate(
                    status=JobStatus.packed,
                    iso_path=str(result.iso_path),
                    iso_size_bytes=result.iso_size_bytes,
                    pack_log=result.log,
                    pack_finished_at=utcnow(),
                    pack_progress_percent=100,
                ),
            )
            self.services.db.add_event(f"【{_job_label(job)}】ISO 制作完成。", job_id=job.id)
            if built_job.auto_upload:
                self._stage_upload(built_job)
        except Exception as exc:
            self.services.db.update_job(
                job.id,
                JobUpdate(
                    status=JobStatus.failed,
                    error_message=str(exc),
                    pack_finished_at=utcnow(),
                    pack_progress_percent=None,
                ),
            )
            self.services.db.add_event(f"【{_job_label(job)}】ISO 制作失败：{exc}", level="ERROR", job_id=job.id)

    def _stage_upload(self, job: JobRecord) -> JobRecord:
        total_bytes = job.iso_size_bytes or 0
        staged = self.services.db.update_job(
            job.id,
            JobUpdate(
                status=JobStatus.copying_to_mount,
                upload_started_at=utcnow(),
                upload_bytes=0,
                upload_total_bytes=total_bytes,
            ),
        )
        self.services.db.add_event(f"【{_job_label(job)}】正在将 ISO 复制到 CloudDrive 挂载目录。", job_id=job.id)
        try:

            def on_copy_progress(done: int, total: int) -> None:
                self.services.db.update_job(
                    job.id,
                    JobUpdate(upload_bytes=done, upload_total_bytes=total),
                )

            result = self.services.upload_manager.stage_upload(staged, progress_callback=on_copy_progress)
        except Exception as exc:
            failed = self.services.db.update_job(
                job.id,
                JobUpdate(status=JobStatus.failed, error_message=str(exc)),
            )
            self.services.db.add_event(f"【{_job_label(job)}】复制到挂载目录失败：{exc}", level="ERROR", job_id=job.id)
            return failed

        staged = self.services.db.update_job(
            job.id,
            JobUpdate(
                status=JobStatus.waiting_for_clouddrive_task,
                upload_target_path=str(result.upload_target_path),
            ),
        )
        self.services.db.add_event(
            f"【{_job_label(job)}】已复制到挂载路径，等待 CloudDrive2 上传：{result.upload_target_path}",
            job_id=job.id,
        )
        return staged

    def upload_packed_job(self, job_id: int) -> JobRecord:
        job = self.services.db.get_job(job_id)
        if not job:
            raise ValueError("Job not found")
        if job.status != JobStatus.packed:
            raise ValueError("Only packed jobs can be uploaded manually")
        return self._stage_upload(job)

    def monitor_uploads(self) -> None:
        jobs = self.services.db.list_jobs_by_status(
            [JobStatus.copying_to_mount, JobStatus.waiting_for_clouddrive_task, JobStatus.uploading]
        )
        tasks = self.services.clouddrive.list_upload_tasks()
        for job in jobs:
            matched_task = self.services.clouddrive.match_task(job, tasks)
            if matched_task:
                lowered = matched_task.status.lower()
                if any(token in lowered for token in ("error", "failed", "cancel")):
                    self.services.db.update_job(
                        job.id,
                        JobUpdate(status=JobStatus.failed, error_message=f"CloudDrive2 task failed: {matched_task.status}"),
                    )
                    self.services.db.add_event(
                        f"【{_job_label(job)}】CloudDrive2 上传失败，状态：{matched_task.status}",
                        level="ERROR",
                        job_id=job.id,
                    )
                    continue
                if any(token in lowered for token in ("finish", "complete", "done", "success")):
                    self._complete_upload(job, matched_task.key)
                    continue
                self.services.db.update_job(
                    job.id,
                    JobUpdate(
                        status=JobStatus.uploading,
                        clouddrive_task_key=matched_task.key,
                        upload_bytes=matched_task.transferred_bytes,
                        upload_total_bytes=matched_task.size,
                    ),
                )
                continue

    def _complete_upload(self, job: JobRecord, task_key: str | None) -> None:
        final_path = self.services.upload_manager.finalize_upload(job)
        self.services.db.update_job(
            job.id,
            JobUpdate(
                status=JobStatus.completed,
                upload_target_path=str(final_path),
                clouddrive_task_key=task_key,
                upload_finished_at=utcnow(),
                upload_bytes=job.iso_size_bytes,
                upload_total_bytes=job.iso_size_bytes,
            ),
        )
        self.services.db.mark_processed_source(job.source_fingerprint, job.id, JobStatus.completed)
        self.services.db.add_event(f"【{_job_label(job)}】上传完成，已删除本地打包副本。", job_id=job.id)

    def apply_qbittorrent_throttle(self) -> None:
        active = self.services.db.list_jobs_by_status(
            [JobStatus.copying_to_mount, JobStatus.waiting_for_clouddrive_task, JobStatus.uploading]
        )
        if active:
            self.services.qbittorrent.apply_throttle_for_clouddrive(
                self.services.settings.clouddrive_upload_bandwidth_mb * 1024
            )
        else:
            self.services.qbittorrent.restore_upload_limit()

    def retry_job(self, job_id: int) -> JobRecord:
        job = self.services.db.get_job(job_id)
        if not job:
            raise ValueError("Job not found")
        updated = self.services.db.update_job(
            job_id,
            JobUpdate(
                status=JobStatus.pending,
                error_message=None,
                manual_repack=True,
                manual_reupload=True,
                iso_path=None,
                iso_size_bytes=None,
                upload_target_path=None,
                clouddrive_task_key=None,
                upload_started_at=None,
                upload_finished_at=None,
                upload_bytes=None,
                upload_total_bytes=None,
            ),
        )
        self.services.db.add_event(f"【{_job_label(updated)}】用户点击重试，任务已重新加入队列。", job_id=job_id)
        return updated

    def reupload_job(self, job_id: int) -> JobRecord:
        job = self.services.db.get_job(job_id)
        if not job:
            raise ValueError("Job not found")
        if job.status == JobStatus.packed:
            return self.upload_packed_job(job_id)
        if not job.iso_path or not Path(job.iso_path).exists():
            raise ValueError("Packed ISO is unavailable; use repack instead")
        updated = self.services.db.update_job(job_id, JobUpdate(status=JobStatus.packed))
        return self._stage_upload(updated)

    def repack_job(self, job_id: int) -> JobRecord:
        updated = self.services.db.update_job(
            job_id,
            JobUpdate(
                status=JobStatus.pending,
                manual_repack=True,
                manual_reupload=False,
                error_message=None,
                iso_path=None,
                iso_size_bytes=None,
                upload_target_path=None,
                clouddrive_task_key=None,
                upload_started_at=None,
                upload_finished_at=None,
                upload_bytes=None,
                upload_total_bytes=None,
            ),
        )
        self.services.db.add_event(f"【{_job_label(job)}】用户请求重新打包，任务已加入队列。", job_id=job_id)
        return updated

    def start_job(self, job_id: int) -> JobRecord:
        job = self.services.db.get_job(job_id)
        if not job:
            raise ValueError("Job not found")
        if job.status != JobStatus.imported:
            raise ValueError("Only imported jobs can be started")
        updated = self.services.db.update_job(job_id, JobUpdate(status=JobStatus.pending))
        self.services.db.add_event(f"【{_job_label(job)}】用户点击开始，任务已加入队列。", job_id=job_id)
        return updated

    def start_jobs(self, job_ids: list[int]) -> list[JobRecord]:
        results: list[JobRecord] = []
        for job_id in job_ids:
            job = self.services.db.get_job(job_id)
            if not job or job.status != JobStatus.imported:
                continue
            updated = self.services.db.update_job(job_id, JobUpdate(status=JobStatus.pending))
            self.services.db.add_event(f"【{_job_label(job)}】用户批量开始，任务已加入队列。", job_id=job_id)
            results.append(updated)
        return results

    def cancel_jobs(self, job_ids: list[int]) -> list[JobRecord]:
        results: list[JobRecord] = []
        for job_id in job_ids:
            job = self.services.db.get_job(job_id)
            if not job or job.status in (JobStatus.completed, JobStatus.cancelled):
                continue
            updated = self.services.db.update_job(job_id, JobUpdate(status=JobStatus.cancelled))
            self.services.db.add_event(f"【{_job_label(job)}】用户批量取消任务。", level="WARNING", job_id=job_id)
            results.append(updated)
        return results

    def delete_job(self, job_id: int) -> None:
        job = self.services.db.get_job(job_id)
        if not job:
            raise ValueError("Job not found")
        if job.status not in (JobStatus.cancelled, JobStatus.imported):
            raise ValueError("Only cancelled or imported jobs can be deleted")
        self.services.db.delete_job(job_id)

    def cancel_job(self, job_id: int) -> JobRecord:
        job = self.services.db.get_job(job_id)
        updated = self.services.db.update_job(job_id, JobUpdate(status=JobStatus.cancelled))
        label = _job_label(job) if job else f"任务 #{job_id}"
        self.services.db.add_event(f"【{label}】用户取消任务。", level="WARNING", job_id=job_id)
        return updated

    def system_status(self) -> SystemStatus:
        queued = self.services.db.list_jobs_by_status(
            [
                JobStatus.imported,
                JobStatus.pending,
                JobStatus.packing,
                JobStatus.packed,
                JobStatus.copying_to_mount,
                JobStatus.waiting_for_clouddrive_task,
                JobStatus.uploading,
            ]
        )
        active_uploads = self.services.db.list_jobs_by_status(
            [JobStatus.copying_to_mount, JobStatus.waiting_for_clouddrive_task, JobStatus.uploading]
        )
        return SystemStatus(
            app_name="AutoISO",
            qbittorrent_connected=self.services.qbittorrent.test_connection(),
            clouddrive_connected=self.services.clouddrive.test_connection(),
            xorriso_available=shutil.which("xorriso") is not None,
            degraded_upload_monitoring=self.services.clouddrive.degraded_mode,
            active_uploads=len(active_uploads),
            queued_jobs=len(queued),
            auto_polling_enabled=self._auto_polling_enabled,
            auto_import_mode=self.services.settings.auto_import_mode,
        )

    @staticmethod
    def _fingerprint_for_qb(torrent_hash: str) -> str:
        return f"qb:{torrent_hash}"

    @staticmethod
    def _fingerprint_for_folder(source: Path) -> str:
        return f"folder:{source.resolve()}".lower()
