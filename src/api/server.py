"""FastAPI application exposing the 3GPP downloader workflows.

This service wraps the existing scraping and download pipeline with a
modern JSON API so a Chakra UI front-end (or any REST client) can
orchestrate jobs and monitor progress.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal, Tuple

from fastapi import BackgroundTasks, Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from main import (
    download_data_with_config,
    filter_latest_versions,
    scrape_data_with_config,
)
from .state_manager import state_manager

logger = logging.getLogger(__name__)

app = FastAPI(title="3GPP Downloader API", version="1.0.0")

ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", ROOT_DIR / "frontend" / "dist")).resolve()

# Allow local dev front-ends by default; production deployments should
# override with env vars.
allowed_origins = os.getenv("API_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------
# Pydantic request/response models
# ---------------------------------------------------------------------


class SettingsUpdate(BaseModel):
    resume_downloads: Optional[bool] = None
    no_download: Optional[bool] = None
    download_all_versions: Optional[bool] = None
    organize_by_series: Optional[bool] = None
    specific_release: Optional[int] = Field(default=None, ge=1)
    thread_count: Optional[int] = Field(default=None, ge=1, le=50)
    verbose_logging: Optional[bool] = None


class DownloadRequest(BaseModel):
    urls: List[str]

    def ensure_valid(self) -> None:
        if not self.urls:
            raise HTTPException(status_code=400, detail="At least one URL must be supplied")


class ScrapeRequest(BaseModel):
    force: bool = False


class FilterRequest(BaseModel):
    clear: bool = False


class FilesQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)
    order_by: Optional[str] = None
    direction: Literal["asc", "desc"] = "asc"
    query: Optional[str] = None
    series: Optional[str] = None
    release: Optional[int] = Field(default=None, ge=0)

    def normalized_direction(self) -> str:
        return self.direction


# ---------------------------------------------------------------------
# Logging bridge so python logging streams into runtime state
# ---------------------------------------------------------------------


class UILogHandler(logging.Handler):
    """Redirect log output into the shared state manager."""

    def __init__(self, level: int = logging.INFO) -> None:
        super().__init__(level=level)
        self.setFormatter(logging.Formatter("[%(name)s][%(levelname)s] %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:  # pragma: no cover - defensive
            message = record.getMessage()
        for line in message.splitlines():
            state_manager.add_log(line)


ui_log_handler = UILogHandler()
_TRACKED_LOGGERS = {
    os.getenv("MAIN_LOGGER_NAME", "downloader"),
    os.getenv("JSON_DOWNLOADER_LOGGER_NAME", "json_downloader"),
    os.getenv("ETSI_SPIDER_LOGGER_NAME", "etsi_spider"),
}


def configure_logging_bridge(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    ui_log_handler.setLevel(level)

    for name in _TRACKED_LOGGERS:
        if not name:
            continue
        target = logging.getLogger(name)
        target.setLevel(level)
        if ui_log_handler not in target.handlers:
            target.addHandler(ui_log_handler)

    # Ensure this module follows the same verbosity
    logging.getLogger(__name__).setLevel(level)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _ensure_directories() -> None:
    Path("downloads").mkdir(parents=True, exist_ok=True)
    Path("logs").mkdir(parents=True, exist_ok=True)


def _coerce_release(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _load_available_files(prefer: Optional[str] = None) -> None:
    def load_from_candidates(candidates: List[Path], file_type: str) -> bool:
        for candidate in candidates:
            if candidate.exists():
                try:
                    files = candidate.read_text()
                    payload: List[Dict[str, Any]] = []
                    if files:
                        payload = json.loads(files)
                    state_manager.set_available_files(payload, file_type)
                    return True
                except Exception as exc:  # pragma: no cover - defensive
                    state_manager.add_log(f"Error reading {candidate}: {exc}")
        return False

    latest_candidates = [Path("downloads/latest.json"), Path("latest.json")]
    links_candidates = [Path("downloads/links.json"), Path("links.json")]

    priority: List[Tuple[str, List[Path]]] = []
    if prefer == "all":
        priority.extend([("all", links_candidates), ("filtered", latest_candidates)])
    elif prefer == "filtered":
        priority.extend([("filtered", latest_candidates), ("all", links_candidates)])
    else:
        priority.extend([("filtered", latest_candidates), ("all", links_candidates)])

    for file_type, candidates in priority:
        if load_from_candidates(candidates, file_type):
            return

    state_manager.clear_files()


# JSON is needed in helper
import json  # noqa: E402 - imported after helper definition so lint stays happy


_scrape_lock = threading.Lock()
_filter_lock = threading.Lock()
_download_lock = threading.Lock()
_download_cancel_event = threading.Event()


def _run_scrape_job(force: bool = False, resume_override: Optional[bool] = None) -> None:
    if not _scrape_lock.acquire(blocking=False):
        return
    try:
        _ensure_directories()
        state_manager.set_scraping_status("running", 5.0, "Starting scraper...")
        if force:
            cleared = False
            for candidate in [Path("downloads/links.json"), Path("links.json"), Path("downloads/latest.json")]:
                if candidate.exists():
                    try:
                        candidate.unlink()
                        cleared = True
                    except Exception as exc:  # pragma: no cover - defensive
                        state_manager.add_log(f"Failed to remove {candidate}: {exc}")
            if cleared:
                state_manager.add_log("Force scrape requested: cleared cached manifests")
        settings = state_manager.get_settings()
        resume_mode = settings.get("resume_downloads", True)
        if resume_override is not None:
            if resume_override != resume_mode:
                state_manager.add_log(
                    f"Resume mode overridden to {'on' if resume_override else 'off'} for this scrape run"
                )
            resume_mode = resume_override
        success = scrape_data_with_config(
                resume=resume_mode,
                no_download=settings.get("no_download", False),
                all_versions=settings.get("download_all_versions", False),
                organize_by_series=settings.get("organize_by_series", False),
                specific_release=settings.get("specific_release"),
                threads=settings.get("thread_count", 5),
                verbose=settings.get("verbose_logging", False),
            )

        if success:
            state_manager.set_scraping_status("running", 85.0, "Scrape completed, loading files...")
            _load_available_files()
            discovered = len(state_manager.available_files)
            state_manager.set_scraping_status(
                "completed",
                100.0,
                (f"Scraping finished. {discovered} file{'s' if discovered != 1 else ''} discovered."),
            )
        else:
            state_manager.set_scraping_status("error", state_manager.scraping_progress, "Scraping failed")
    except Exception as exc:  # pragma: no cover - defensive
        state_manager.set_scraping_status("error", state_manager.scraping_progress, f"Scraping error: {exc}")
    finally:
        _scrape_lock.release()


def _run_filter_job() -> None:
    if not _filter_lock.acquire(blocking=False):
        return
    try:
        _ensure_directories()
        state_manager.update_current_operation("Filtering to latest versions...")

        source_path: Optional[Path] = None
        for candidate in [Path("downloads/links.json"), Path("links.json")]:
            if candidate.exists():
                source_path = candidate
                break

        if not source_path:
            state_manager.add_log("Cannot locate links.json for filtering")
            state_manager.set_scraping_status("error", state_manager.scraping_progress, "Filtering failed")
            return

        output_path = Path("downloads/latest.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        success = filter_latest_versions(input_file=str(source_path), output_file=str(output_path))
        if success:
            state_manager.update_current_operation("Latest versions ready")
            _load_available_files(prefer="filtered")
        else:
            state_manager.add_log("Filtering command returned no data")
    except Exception as exc:  # pragma: no cover - defensive
        state_manager.add_log(f"Filtering error: {exc}")
    finally:
        _filter_lock.release()


class DownloadProgressTracker:
    def __init__(self, total_items: int) -> None:
        self.total_items = max(1, total_items)
        self.completed = 0
        self.errors = 0
        self.lock = threading.Lock()

    def __call__(self, identifier: str, status: str, value: float) -> None:
        with self.lock:
            if identifier != "__overall__":
                filename = identifier
            else:
                filename = None

            if status == "starting" and filename:
                state_manager.update_current_download_item(filename)
                state_manager.record_download_event(filename, "Queued", "Preparing download")
                state_manager.set_download_status("running", state_manager.download_progress, f"Starting download: {filename}")
            elif status == "file_progress" and filename:
                state_manager.update_current_download_item(filename)
                state_manager.set_download_status("running", state_manager.download_progress, f"Downloading {filename} ({int(value)}%)")
            elif status == "file_complete" and filename:
                self.completed += 1
                state_manager.append_completed(filename)
                state_manager.record_download_event(filename, "Completed", "Saved to downloads")
                message = f"Downloaded {self.completed}/{self.total_items} files"
                if self.errors:
                    message += f" (errors: {self.errors})"
                state_manager.set_download_status("running", state_manager.download_progress, message)
            elif status == "error" and filename:
                self.errors += 1
                state_manager.append_failed(filename)
                state_manager.record_download_event(filename, "Failed", "See logs for details")
                state_manager.set_download_status("error", state_manager.download_progress, f"Error downloading {filename}")
            elif status == "overall_progress":
                progress = 10.0 + (max(0.0, min(100.0, value)) * 0.8)
                message = f"Downloaded {self.completed}/{self.total_items} files"
                if self.errors:
                    message += f" (errors: {self.errors})"
                state_manager.set_download_status("running", min(progress, 95.0), message)
            elif status == "all_finished":
                if self.errors:
                    state_manager.set_download_status("error", 100.0, f"Completed with {self.errors} error(s)")
                else:
                    state_manager.set_download_status("completed", 100.0, "All downloads completed successfully")
                state_manager.update_current_download_item(None)
            elif status == "errors":
                self.errors = int(value)
                if self.errors:
                    state_manager.set_download_status("error", state_manager.download_progress, f"Encountered {self.errors} download error(s)")


def _run_download_job(urls: List[str]) -> None:
    if not _download_lock.acquire(blocking=False):
        return
    try:
        _ensure_directories()
        _download_cancel_event.clear()
        matched, missing = state_manager.ensure_download_selection(urls)
        if missing:
            state_manager.add_log(f"Ignoring {len(missing)} unknown selection(s)")
        if not matched:
            state_manager.set_download_status("idle", state_manager.download_progress, "No matching files to download")
            return

        Path("selected.json").write_text(json.dumps(matched, indent=2))

        tracker = DownloadProgressTracker(total_items=len(matched))
        state_manager.reset_download_tracking()
        state_manager.set_download_status("running", 10.0, f"Queued {len(matched)} files for download")

        settings = state_manager.get_settings()
        success = download_data_with_config(
            input_file="selected.json",
            resume=settings.get("resume_downloads", True),
            no_download=settings.get("no_download", False),
            all_versions=settings.get("download_all_versions", False),
            organize_by_series=settings.get("organize_by_series", False),
            specific_release=settings.get("specific_release"),
            threads=settings.get("thread_count", 5),
            verbose=settings.get("verbose_logging", False),
            progress_callback=tracker,
            cancel_event=_download_cancel_event,
        )

        if _download_cancel_event.is_set():
            state_manager.set_download_status("error", state_manager.download_progress, "Download cancelled by user")
            state_manager.update_current_download_item(None)
        elif success and not tracker.errors:
            state_manager.set_download_status("completed", 100.0, "All downloads completed successfully")
        elif success:
            state_manager.set_download_status("error", 100.0, f"Completed with {tracker.errors} error(s)")
        else:
            state_manager.set_download_status("error", state_manager.download_progress, "Download failed")
    except Exception as exc:  # pragma: no cover - defensive
        state_manager.set_download_status("error", state_manager.download_progress, f"Download error: {exc}")
    finally:
        _download_cancel_event.clear()
        _download_lock.release()


# ---------------------------------------------------------------------
# FastAPI endpoints
# ---------------------------------------------------------------------


@app.on_event("startup")
def on_startup() -> None:
    state_manager.load_settings()
    configure_logging_bridge(state_manager.settings.verbose_logging)
    _ensure_directories()
    _load_available_files()
    state_manager.add_log("API server initialised")


@app.get("/api/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok", "timestamp": time.time()}


@app.get("/api/state")
def get_state() -> Dict:
    return state_manager.snapshot()


@app.get("/api/settings")
def get_settings() -> Dict:
    return state_manager.get_settings()


@app.patch("/api/settings")
def update_settings(payload: SettingsUpdate) -> Dict:
    updated = state_manager.update_settings({k: v for k, v in payload.model_dump(exclude_none=True).items()})
    if payload.verbose_logging is not None:
        configure_logging_bridge(payload.verbose_logging)
    return updated


@app.post("/api/scrape", status_code=202)
def start_scrape(background_tasks: BackgroundTasks, payload: Optional[ScrapeRequest] = Body(default=None)) -> Dict[str, Any]:
    request = payload or ScrapeRequest()
    if state_manager.scraping_status == "running":
        raise HTTPException(status_code=409, detail="Scraping already in progress")
    background_tasks.add_task(_run_scrape_job, request.force, False)
    message = "Force scraping started" if request.force else "Scraping started"
    return {"message": message, "force": request.force, "resume_override": False}


@app.post("/api/filter", status_code=202)
def start_filter(background_tasks: BackgroundTasks, payload: Optional[FilterRequest] = Body(default=None)) -> Dict[str, str]:
    request = payload or FilterRequest()
    if request.clear:
        state_manager.update_current_operation("Showing all available versions")
        _load_available_files(prefer="all")
        return {"message": "Filter cleared"}

    background_tasks.add_task(_run_filter_job)
    return {"message": "Filtering started"}


@app.post("/api/download", status_code=202)
def start_download(request: DownloadRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    request.ensure_valid()
    if state_manager.download_status == "running":
        raise HTTPException(status_code=409, detail="Download already in progress")
    background_tasks.add_task(_run_download_job, request.urls)
    return {"message": "Download started", "selected": len(request.urls)}


@app.post("/api/download/stop", status_code=202)
def stop_download() -> Dict[str, str]:
    if state_manager.download_status != "running":
        raise HTTPException(status_code=409, detail="No active download to stop")
    state_manager.add_log("Download cancellation requested")
    state_manager.set_download_status("running", state_manager.download_progress, "Cancelling downloads...")
    _download_cancel_event.set()
    return {"message": "Cancellation requested"}


@app.post("/api/files")
def list_files(payload: Optional[FilesQuery] = Body(default=None)) -> Dict[str, Any]:
    query = payload or FilesQuery()
    snapshot = state_manager.snapshot()
    items: List[Dict[str, Any]] = snapshot.get("available_files", [])

    filtered = list(items)

    if query.query:
        needle = query.query.strip().lower()
        if needle:
            search_fields = ["ts_number", "series", "name", "version", "url", "release"]

            def matches_query(item: Dict[str, Any]) -> bool:
                for field in search_fields:
                    value = item.get(field)
                    if isinstance(value, str) and needle in value.lower():
                        return True
                    if isinstance(value, (int, float)) and needle in str(value).lower():
                        return True
                return False

            filtered = [item for item in filtered if matches_query(item)]

    if query.series:
        series = query.series.strip().lower()
        if series:
            filtered = [
                item
                for item in filtered
                if isinstance(item.get("series"), str) and item["series"].strip().lower() == series
            ]

    if query.release is not None:
        target_release = query.release
        filtered = [
            item
            for item in filtered
            if _coerce_release(item.get("release")) == target_release
        ]

    order_field = query.order_by or "ts_number"
    allowed_fields = {"ts_number", "series", "release", "version", "name"}
    if order_field not in allowed_fields:
        order_field = "ts_number"

    reverse = query.normalized_direction() == "desc"

    def sort_key(item: Dict[str, Any]) -> Any:
        value = item.get(order_field)
        if isinstance(value, str):
            return value.lower()
        return value if value is not None else ""

    try:
        filtered.sort(key=sort_key, reverse=reverse)
    except TypeError:
        filtered.sort(
            key=lambda item: str(item.get(order_field, "")),
            reverse=reverse,
        )

    total = len(filtered)
    page = query.page
    page_size = query.page_size
    start = (page - 1) * page_size
    end = start + page_size
    paged_items = filtered[start:end]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "file_type": snapshot.get("current_file_type", "none"),
        "items": paged_items,
    }


@app.post("/api/files/reload")
def reload_files() -> Dict[str, str]:
    _load_available_files()
    return {"message": "File catalogue refreshed"}


@app.post("/api/logs/clear")
def clear_logs() -> Dict[str, str]:
    state_manager.log_messages = []
    state_manager.add_log("Logs cleared")
    return {"message": "Logs cleared"}


if FRONTEND_DIST.exists():
    index_path = FRONTEND_DIST / "index.html"
    if not index_path.exists():
        logger.warning("Frontend dist directory %s is missing index.html", FRONTEND_DIST)
    else:
        logger.info("Serving frontend assets from %s", FRONTEND_DIST)

    @app.get("/", include_in_schema=False)
    async def serve_index() -> FileResponse:  # type: ignore[return-value]
        return FileResponse(index_path)

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:  # type: ignore[return-value]
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index_path)

    app.mount(
        "/assets",
        StaticFiles(directory=FRONTEND_DIST / "assets" if (FRONTEND_DIST / "assets").exists() else FRONTEND_DIST),
        name="assets",
    )
else:
    logger.warning("Frontend dist directory %s not found; API will run without static assets", FRONTEND_DIST)
