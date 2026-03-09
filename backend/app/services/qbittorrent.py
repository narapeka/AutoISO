from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import logging

import qbittorrentapi

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class CompletedTorrent:
    torrent_hash: str
    name: str
    source_path: str
    category: str | None
    tags: list[str]
    added_at: datetime
    completed_at: datetime


class QBittorrentService:
    MIN_THROTTLE_KIB = 100

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._saved_upload_limit_kib: int | None = None

    def _client(self) -> qbittorrentapi.Client:
        client = qbittorrentapi.Client(
            host=self.settings.qbittorrent_url,
            username=self.settings.qbittorrent_username,
            password=self.settings.qbittorrent_password,
            REQUESTS_ARGS={"timeout": 5},
            HTTPADAPTER_ARGS={"max_retries": 0},
        )
        client.auth_log_in()
        return client

    def test_connection(self) -> bool:
        try:
            client = self._client()
            client.app.version
            return True
        except Exception:
            return False

    def fetch_completed_torrents(self) -> list[CompletedTorrent]:
        return self._list_completed_torrents(apply_filters=True)

    def list_completed_torrents(self) -> list[CompletedTorrent]:
        return self._list_completed_torrents(apply_filters=False)

    def get_completed_torrent(self, torrent_hash: str) -> CompletedTorrent | None:
        for torrent in self.list_completed_torrents():
            if torrent.torrent_hash == torrent_hash:
                return torrent
        return None

    def get_upload_limit_kib(self) -> int:
        """Current global upload limit in KiB/s; 0 means unlimited."""
        try:
            client = self._client()
            limit_bps = client.transfer.upload_limit
            if limit_bps is None or limit_bps <= 0:
                return 0
            return limit_bps // 1024
        except Exception:
            return 0

    def set_upload_limit_kib(self, limit_kib: int) -> None:
        """Set global upload limit in KiB/s; 0 means unlimited."""
        try:
            client = self._client()
            client.transfer.set_upload_limit(limit_kib * 1024 if limit_kib > 0 else 0)
        except Exception:
            return

    def apply_throttle_for_clouddrive(self, bandwidth_kib: int) -> None:
        """When CD2 upload is active: save current qB limit, then set qB to (current - bandwidth_kib), min 100 KiB/s.
        If current is 0 (unlimited), we save 0 and set qB to 100 KiB/s; restore_upload_limit() will set 0 (unlimited) again.
        """
        if self._saved_upload_limit_kib is not None:
            return
        try:
            current_kib = self.get_upload_limit_kib()
            self._saved_upload_limit_kib = current_kib
            new_kib = current_kib - bandwidth_kib if current_kib > 0 else 0
            if new_kib < self.MIN_THROTTLE_KIB:
                new_kib = self.MIN_THROTTLE_KIB
            self.set_upload_limit_kib(new_kib)
        except Exception:
            return

    def restore_upload_limit(self) -> None:
        """Restore qB upload limit to the value saved when throttle was applied."""
        if self._saved_upload_limit_kib is None:
            return
        try:
            self.set_upload_limit_kib(self._saved_upload_limit_kib)
            self._saved_upload_limit_kib = None
        except Exception:
            return

    def _list_completed_torrents(self, apply_filters: bool) -> list[CompletedTorrent]:
        try:
            client = self._client()
            torrents = client.torrents.info()
        except Exception as exc:
            logger.warning("Failed to fetch qBittorrent torrents: %s", exc)
            return []

        items: list[CompletedTorrent] = []
        for torrent in torrents:
            file_list = []
            try:
                file_list = client.torrents.files(torrent_hash=getattr(torrent, "hash", ""))
            except Exception as exc:
                logger.debug("Failed to get files for torrent %s: %s", getattr(torrent, "hash", ""), exc)
            data = self._normalize_torrent(torrent, file_list=file_list, apply_filters=apply_filters)
            if data:
                items.append(data)
        items.sort(key=lambda item: item.added_at, reverse=True)
        return items

    def _normalize_torrent(
        self, torrent: Any, file_list: list[Any], apply_filters: bool
    ) -> CompletedTorrent | None:
        progress = getattr(torrent, "progress", 0)
        amount_left = getattr(torrent, "amount_left", 1)
        if progress < 1 or amount_left not in (0, None):
            return None

        category = getattr(torrent, "category", None) or None
        tags = self._parse_tags(getattr(torrent, "tags", ""))
        if apply_filters and self.settings.watched_categories and category not in self.settings.watched_categories:
            return None
        if apply_filters and self.settings.watched_tags and not set(tags).intersection(self.settings.watched_tags):
            return None

        if not self._has_bdmv_structure_in_file_list(file_list):
            return None

        content_path = getattr(torrent, "content_path", None)
        save_path = getattr(torrent, "save_path", None)
        name = getattr(torrent, "name", None)
        if content_path and str(content_path).strip():
            source_path = str(content_path).strip()
        elif save_path and name:
            source_path = str(Path(save_path) / str(name))
        else:
            logger.warning(
                "Skipping torrent %s: no source path (content_path=%s, save_path=%s, name=%s)",
                getattr(torrent, "hash", ""),
                content_path,
                save_path,
                name,
            )
            return None

        completion_on = getattr(torrent, "completion_on", 0) or 0
        if completion_on > 0:
            completed_at = datetime.fromtimestamp(completion_on, tz=timezone.utc)
        else:
            completed_at = datetime.now(timezone.utc)

        added_on = (
            getattr(torrent, "added_on", None)
            or getattr(torrent, "addition_date", None)
            or getattr(torrent, "added_time", None)
            or 0
        )
        if added_on > 0:
            added_at = datetime.fromtimestamp(added_on, tz=timezone.utc)
        else:
            added_at = completed_at

        return CompletedTorrent(
            torrent_hash=str(getattr(torrent, "hash", "")),
            name=str(name),
            source_path=source_path,
            category=category,
            tags=tags,
            added_at=added_at,
            completed_at=completed_at,
        )

    @staticmethod
    def _parse_tags(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @staticmethod
    def _has_bdmv_structure_in_file_list(file_list: list[Any]) -> bool:
        """Determine BDMV from qBittorrent file list (no filesystem access)."""
        names: list[str] = []
        for f in file_list or []:
            name = getattr(f, "name", None) or (f.get("name") if isinstance(f, dict) else None)
            if name:
                names.append(str(name).replace("\\", "/").casefold())
        has_stream = any("bdmv/stream/" in n for n in names)
        has_index = any("bdmv/index.bdmv" in n for n in names)
        return has_stream and has_index
