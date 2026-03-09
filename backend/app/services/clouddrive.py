from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import Settings
from app.models import JobRecord


@dataclass
class CloudDriveUploadTask:
    key: str
    file_name: str
    full_path: str
    size: int | None
    transferred_bytes: int | None
    status: str


class CloudDriveService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.degraded_mode = False

    def _client(self) -> Any:
        from clouddrive2_client import CloudDriveClient  # type: ignore

        client = CloudDriveClient(self.settings.clouddrive_url)
        if hasattr(client, "authenticate"):
            authenticated = client.authenticate(
                self.settings.clouddrive_username,
                self.settings.clouddrive_password,
            )
            if authenticated is False:
                self._close(client)
                raise RuntimeError("CloudDrive2 authentication failed")
        return client

    def test_connection(self) -> bool:
        try:
            client = self._client()
            if hasattr(client, "get_system_info"):
                client.get_system_info()
            self._close(client)
            return True
        except Exception:
            return False

    def list_upload_tasks(self) -> list[CloudDriveUploadTask]:
        try:
            client = self._client()
            all_tasks: list[CloudDriveUploadTask] = []
            page_size = 20
            if hasattr(client, "get_upload_file_list"):
                offset = 0
                while True:
                    result = client.get_upload_file_list(True, page_size, offset)
                    page = self._extract_tasks(result)
                    all_tasks.extend(page)
                    if len(page) < page_size:
                        break
                    offset += page_size
            self._close(client)
            self.degraded_mode = False
            return all_tasks
        except Exception:
            self.degraded_mode = True
            return []

    def match_task(self, job: JobRecord, tasks: list[CloudDriveUploadTask]) -> CloudDriveUploadTask | None:
        target_name = Path(job.upload_target_path or job.iso_path or "").name.lower()
        for task in tasks:
            if task.file_name.lower() == target_name:
                return task
            if target_name and target_name in task.full_path.lower():
                return task
        return None

    def _extract_tasks(self, result: Any) -> list[CloudDriveUploadTask]:
        items = []
        candidates = []
        if isinstance(result, list):
            candidates = result
        elif hasattr(result, "items"):
            candidates = list(getattr(result, "items"))
        elif hasattr(result, "uploadFiles"):
            candidates = list(getattr(result, "uploadFiles"))

        for item in candidates:
            items.append(
                CloudDriveUploadTask(
                    key=str(
                        getattr(item, "key", None)
                        or getattr(item, "taskKey", None)
                        or getattr(item, "fileKey", None)
                        or getattr(item, "id", "")
                    ),
                    file_name=str(getattr(item, "fileName", None) or getattr(item, "name", "")),
                    full_path=str(getattr(item, "fullPathName", None) or getattr(item, "path", "")),
                    size=getattr(item, "fileSize", None) or getattr(item, "size", None),
                    transferred_bytes=(
                        getattr(item, "transferedBytes", None)
                        or getattr(item, "transferredBytes", None)
                        or None
                    ),
                    status=str(getattr(item, "status", None) or getattr(item, "transferStatus", "unknown")),
                )
            )
        return items

    @staticmethod
    def _close(client: Any) -> None:
        if hasattr(client, "close"):
            client.close()
