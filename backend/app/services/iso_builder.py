import re
import subprocess
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings
from app.models import JobRecord

# xorriso stderr line e.g. "xorriso : UPDATE :  14.43% done" or "xorriso : UPDATE :  13.64% done"
XORRISO_PERCENT_RE = re.compile(r"(\d+\.?\d*)\s*%\s*done", re.IGNORECASE)


@dataclass
class IsoBuildResult:
    iso_path: Path
    iso_size_bytes: int
    log: str


class IsoBuilder:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def validate_source(self, source_path: Path) -> Path:
        if not source_path.exists():
            raise FileNotFoundError(f"Source path does not exist: {source_path}")

        normalized_root = self._resolve_bdmv_root(source_path)
        if normalized_root is None:
            raise ValueError(f"Source path is not a BDMV-compatible directory: {source_path}")
        return normalized_root

    def build(
        self,
        job: JobRecord,
        progress_callback: Callable[[int], None] | None = None,
    ) -> IsoBuildResult:
        source_path = self.validate_source(Path(job.source_path))
        self.settings.packed_path.mkdir(parents=True, exist_ok=True)

        safe_name = self._safe_name(job.torrent_name)
        filename = f"{safe_name}.iso"
        iso_path = self.settings.packed_path / filename
        volume_id = self._volume_id(job.torrent_name)

        command = [
            "xorriso",
            "-as",
            "mkisofs",
            "-iso-level",
            "3",
            "-udf",
            "-allow-limited-size",
            "-V",
            volume_id,
            "-o",
            str(iso_path),
            str(source_path),
        ]
        stderr_lines: list[str] = []
        last_reported: list[int] = [0]  # mutable so closure can update

        def read_stderr(pipe: subprocess.PIPE) -> None:
            assert pipe is not None
            for line in iter(pipe.readline, ""):
                stderr_lines.append(line)
                if progress_callback is None:
                    continue
                m = XORRISO_PERCENT_RE.search(line)
                if m:
                    try:
                        pct = min(100, max(0, round(float(m.group(1)))))
                        if pct > last_reported[0]:
                            last_reported[0] = pct
                            progress_callback(pct)
                    except (ValueError, TypeError):
                        pass

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout_parts: list[str] = []
        if process.stdout:
            stdout_parts.append(process.stdout.read())
        if process.stderr is not None:
            if progress_callback is not None:
                t = threading.Thread(target=read_stderr, args=(process.stderr,))
                t.daemon = True
                t.start()
                t.join(timeout=86400)
            else:
                stderr_lines.append(process.stderr.read())
        process.wait()
        log = "\n".join(part for part in (("".join(stdout_parts)), "\n".join(stderr_lines)) if part).strip()
        if process.returncode != 0:
            raise RuntimeError(log or f"xorriso failed with exit code {process.returncode}")
        if not iso_path.exists():
            raise RuntimeError("xorriso reported success but no ISO file was created")
        if progress_callback is not None:
            progress_callback(100)
        return IsoBuildResult(
            iso_path=iso_path,
            iso_size_bytes=iso_path.stat().st_size,
            log=log or "ISO build completed successfully.",
        )

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9._ -]+", "_", value).strip() or "movie"

    def _volume_id(self, torrent_name: str) -> str:
        base = self._safe_name(torrent_name).upper().replace(" ", "_")
        volume = f"AUTOISO_{base}"
        return volume[:32]

    @classmethod
    def _resolve_bdmv_root(cls, source_path: Path) -> Path | None:
        if cls._is_bdmv_root(source_path):
            return source_path
        if source_path.name.casefold() == "bdmv" and cls._is_bdmv_directory(source_path):
            return source_path.parent
        return None

    @classmethod
    def _is_bdmv_root(cls, source_path: Path) -> bool:
        bdmv_dir = cls._find_child_casefold(source_path, "BDMV")
        if bdmv_dir is None:
            return False
        return cls._is_bdmv_directory(bdmv_dir)

    @classmethod
    def _is_bdmv_directory(cls, bdmv_dir: Path) -> bool:
        stream_dir = cls._find_child_casefold(bdmv_dir, "STREAM")
        index_file = cls._find_child_casefold(bdmv_dir, "index.bdmv")
        return (
            bdmv_dir.is_dir()
            and stream_dir is not None
            and stream_dir.is_dir()
            and index_file is not None
            and index_file.exists()
        )

    @staticmethod
    def _find_child_casefold(parent: Path, name: str) -> Path | None:
        if not parent.is_dir():
            return None
        target = name.casefold()
        for child in parent.iterdir():
            if child.name.casefold() == target:
                return child
        return None
