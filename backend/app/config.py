from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

# 支持通过环境变量 AUTOISO_DATA_DIR 指定数据目录（Docker 中可设为 /app/data）
_default_data = Path(__file__).resolve().parent / "data"
APP_DATA_DIR = Path(os.environ.get("AUTOISO_DATA_DIR", _default_data))
CONFIG_PATH = APP_DATA_DIR / "config.yaml"
DATABASE_PATH = APP_DATA_DIR / "autoiso.db"
LOGS_PATH = APP_DATA_DIR / "logs"
PACKED_PATH = APP_DATA_DIR / "packed"


class Settings(BaseModel):
    log_level: str = "INFO"

    qbittorrent_url: str = "http://localhost:8080"
    qbittorrent_username: str = "admin"
    qbittorrent_password: str = "adminadmin"
    qbittorrent_poll_interval_seconds: int = 60
    qbittorrent_category_filter: str = ""
    qbittorrent_tag_filter: str = ""

    clouddrive_url: str = "localhost:19798"
    clouddrive_upload_bandwidth_mb: int = 5
    clouddrive_username: str = "admin"
    clouddrive_password: str = "password"
    clouddrive_target_path: str = "/CloudDrive/115open/我的上传"

    auto_import_mode: str = "full_auto"  # "import_only" | "pack_only" | "full_auto"

    @property
    def data_root(self) -> Path:
        return APP_DATA_DIR

    @property
    def config_path(self) -> Path:
        return CONFIG_PATH

    @property
    def database_path(self) -> Path:
        return DATABASE_PATH

    @property
    def logs_path(self) -> Path:
        return LOGS_PATH

    @property
    def packed_path(self) -> Path:
        return PACKED_PATH

    @property
    def watched_categories(self) -> list[str]:
        return [item.strip() for item in self.qbittorrent_category_filter.split(",") if item.strip()]

    @property
    def watched_tags(self) -> list[str]:
        return [item.strip() for item in self.qbittorrent_tag_filter.split(",") if item.strip()]

    def operator_dict(self) -> dict[str, Any]:
        data = self.model_dump(mode="json")
        return data


def _default_settings() -> dict[str, Any]:
    return Settings().operator_dict()


def _write_config(path: Path, values: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(values, handle, sort_keys=False, allow_unicode=True)


def ensure_config_file() -> Path:
    if not CONFIG_PATH.exists():
        _write_config(CONFIG_PATH, _default_settings())
    return CONFIG_PATH


def _load_yaml_settings() -> Settings:
    ensure_config_file()
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        loaded = {}
    merged = {**_default_settings(), **loaded}
    return Settings.model_validate(merged)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return _load_yaml_settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


def save_settings(values: dict[str, Any]) -> Settings:
    current = get_settings().operator_dict()
    merged = {**current, **values}
    validated = Settings.model_validate(merged)
    _write_config(CONFIG_PATH, validated.operator_dict())
    return reload_settings()
