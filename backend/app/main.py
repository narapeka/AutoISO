import logging
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from logging import Handler, LogRecord
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import ensure_config_file, get_settings
from app.db.database import Database
from app.services.clouddrive import CloudDriveService
from app.services.iso_builder import IsoBuilder
from app.services.orchestrator import Orchestrator, ServiceContainer
from app.services.qbittorrent import QBittorrentService
from app.services.upload_manager import UploadManager


class DailyFileHandler(Handler):
    def __init__(self, log_dir: Path, keep_days: int = 10) -> None:
        super().__init__()
        self.log_dir = log_dir
        self.keep_days = keep_days
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._current_date: str | None = None
        self._stream = None

    def emit(self, record: LogRecord) -> None:
        log_date = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d")
        if self._current_date != log_date or self._stream is None:
            self._rotate(log_date)
        assert self._stream is not None
        message = self.format(record)
        self._stream.write(message + "\n")
        self._stream.flush()

    def close(self) -> None:
        if self._stream:
            self._stream.close()
            self._stream = None
        super().close()

    def _rotate(self, log_date: str) -> None:
        if self._stream:
            self._stream.close()
        self._current_date = log_date
        file_path = self.log_dir / f"{log_date}.log"
        self._stream = file_path.open("a", encoding="utf-8")
        self._cleanup()

    def _cleanup(self) -> None:
        cutoff = datetime.now() - timedelta(days=self.keep_days)
        for file_path in self.log_dir.glob("*.log"):
            try:
                file_date = datetime.strptime(file_path.stem, "%Y-%m-%d")
            except ValueError:
                continue
            if file_date < cutoff:
                file_path.unlink(missing_ok=True)


def configure_logging(level: str, log_dir: Path) -> None:
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    file_handler = DailyFileHandler(log_dir=log_dir, keep_days=10)
    file_handler.setFormatter(formatter)

    root.addHandler(stream)
    root.addHandler(file_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_config_file()
    settings = get_settings()

    for path in (settings.data_root, settings.logs_path, settings.packed_path):
        path.mkdir(parents=True, exist_ok=True)

    configure_logging(settings.log_level, settings.logs_path)

    database = Database(settings.database_path)
    database.initialize()

    services = ServiceContainer(
        settings=settings,
        db=database,
        qbittorrent=QBittorrentService(settings),
        iso_builder=IsoBuilder(settings),
        upload_manager=UploadManager(settings),
        clouddrive=CloudDriveService(settings),
    )
    orchestrator = Orchestrator(services)
    app.state.settings = settings
    app.state.orchestrator = orchestrator
    await orchestrator.start()
    try:
        yield
    finally:
        await orchestrator.stop()


app = FastAPI(title="AutoISO", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

# 生产环境：挂载前端构建产物（Docker 中复制到 backend 根目录的 static）
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="frontend")
else:

    @app.get("/")
    def root() -> dict[str, str]:
        return {"name": "AutoISO", "status": "ok"}
