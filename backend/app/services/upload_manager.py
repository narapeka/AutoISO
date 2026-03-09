import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.models import JobRecord

# 20–100 GB ISO 用较大块可减少回调与 DB 更新次数，同时进度仍足够平滑
COPY_CHUNK_SIZE = 128 * 1024 * 1024  # 128 MiB


@dataclass
class UploadStageResult:
    upload_target_path: Path


class UploadManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def stage_upload(
        self,
        job: JobRecord,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> UploadStageResult:
        if not job.iso_path:
            raise ValueError("Job has no ISO path to upload")

        source = Path(job.iso_path)
        if not source.exists():
            raise FileNotFoundError(f"ISO file does not exist: {source}")

        destination_root = Path(self.settings.clouddrive_target_path)
        destination_root.mkdir(parents=True, exist_ok=True)
        destination = destination_root / source.name
        total = source.stat().st_size
        copied = 0
        with open(source, "rb") as f_in, open(destination, "wb") as f_out:
            while True:
                chunk = f_in.read(COPY_CHUNK_SIZE)
                if not chunk:
                    break
                f_out.write(chunk)
                copied += len(chunk)
                if progress_callback is not None:
                    progress_callback(copied, total)
        shutil.copystat(str(source), str(destination))
        return UploadStageResult(upload_target_path=destination)

    def finalize_upload(self, job: JobRecord) -> Path:
        if not job.upload_target_path:
            raise ValueError("Job has no upload target path")

        target = Path(job.upload_target_path)
        packed_copy = Path(job.iso_path or "")
        if packed_copy.exists():
            packed_copy.unlink()
        return target
