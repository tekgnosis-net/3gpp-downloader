"""Shared state management for the FastAPI backend.

Provides a threadsafe manager that can be consumed by API endpoints and
background workers. It stores runtime telemetry (progress, statuses,
logs, file listings) as well as persisted user settings that mirror the
legacy experience.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel
from datetime import datetime, timezone

_SETTINGS_PATH = Path("web_settings.json")


class UserSettings(BaseModel):
    """Persisted configuration mirrored from the previous UI."""

    resume_downloads: bool = True
    no_download: bool = False
    download_all_versions: bool = False
    organize_by_series: bool = False
    specific_release: Optional[int] = None
    thread_count: int = 5
    verbose_logging: bool = False

    http_max_connections: int = 100
    http_max_connections_per_host: int = 10
    http_total_timeout: int = 300
    http_connect_timeout: int = 10
    http_read_timeout: int = 60

    retry_max_attempts: int = 5
    retry_base_delay: float = 1.0
    retry_max_delay: float = 60.0

    scrapy_download_delay: float = 0.1
    scrapy_concurrent_requests: int = 8
    etsi_min_release: int = 15

    web_max_log_messages: int = 100
    web_refresh_interval: int = 5

    class Config:
        extra = "allow"


@dataclass
class DownloadEvent:
    timestamp: str
    filename: str
    status: str
    description: str

    def as_dict(self) -> Dict[str, str]:
        return asdict(self)


class StateManager:
    """Thread-safe holder for runtime telemetry and settings."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.settings = UserSettings()
        self.scraping_status = "idle"
        self.download_status = "idle"
        self.scraping_progress = 0.0
        self.download_progress = 0.0
        self.current_operation = ""
        self.current_download_item: Optional[str] = None
        self.log_messages: List[str] = []
        self.available_files: List[Dict] = []
        self.current_file_type: str = "none"
        self.completed_downloads: List[str] = []
        self.failed_downloads: List[str] = []
        self.recent_download_events: List[DownloadEvent] = []
        self.last_update = time.time()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def load_settings(self) -> None:
        """Load settings from disk if available."""
        if _SETTINGS_PATH.exists():
            try:
                data = json.loads(_SETTINGS_PATH.read_text())
                self.settings = UserSettings(**data)
            except Exception:
                # fall back to defaults but keep file for troubleshooting
                self.settings = UserSettings()
        else:
            self.save_settings()

    def save_settings(self) -> None:
        """Persist the current settings to disk."""
        _SETTINGS_PATH.write_text(self.settings.model_dump_json(indent=2))

    # ------------------------------------------------------------------
    # Mutation helpers
    # ------------------------------------------------------------------
    def set_scraping_status(self, status: str, progress: float, message: Optional[str] = None) -> None:
        with self._lock:
            self.scraping_status = status
            self.scraping_progress = max(0.0, min(100.0, progress))
            if message:
                self.current_operation = message
                self.add_log(message)
            self._touch()

    def set_download_status(self, status: str, progress: float, message: Optional[str] = None) -> None:
        with self._lock:
            self.download_status = status
            self.download_progress = max(0.0, min(100.0, progress))
            if message:
                self.current_operation = message
                self.add_log(message)
            self._touch()

    def update_current_operation(self, message: str) -> None:
        with self._lock:
            self.current_operation = message
            self.add_log(message)
            self._touch()

    def add_log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        max_msgs = max(1, self.settings.web_max_log_messages)
        with self._lock:
            self.log_messages.append(entry)
            if len(self.log_messages) > max_msgs:
                self.log_messages = self.log_messages[-max_msgs:]
            self._touch()

    def clear_logs(self) -> None:
        with self._lock:
            self.log_messages = []
            self._touch()

    def set_available_files(self, files: List[Dict], file_type: str) -> None:
        with self._lock:
            self.available_files = files
            self.current_file_type = file_type
            count = len(files)
            self.add_log(f"Loaded {count} available file{'s' if count != 1 else ''} ({file_type})")
            self._touch()

    def clear_files(self) -> None:
        with self._lock:
            self.available_files = []
            self.current_file_type = "none"
            self._touch()

    def record_download_event(self, filename: str, status: str, description: str) -> None:
        event = DownloadEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            filename=filename,
            status=status,
            description=description,
        )
        with self._lock:
            self.recent_download_events.append(event)
            if len(self.recent_download_events) > 12:
                self.recent_download_events = self.recent_download_events[-12:]
            self._touch()

    def append_completed(self, filename: str) -> None:
        with self._lock:
            self.completed_downloads.append(filename)
            self.completed_downloads = self.completed_downloads[-32:]
            self._touch()

    def append_failed(self, filename: str) -> None:
        with self._lock:
            self.failed_downloads.append(filename)
            self.failed_downloads = self.failed_downloads[-32:]
            self._touch()

    def reset_download_tracking(self) -> None:
        with self._lock:
            self.download_status = "running"
            self.download_progress = 0.0
            self.current_download_item = None
            self.completed_downloads = []
            self.failed_downloads = []
            self.recent_download_events = []
            self._touch()

    def update_current_download_item(self, filename: Optional[str]) -> None:
        with self._lock:
            self.current_download_item = filename
            self._touch()

    def update_settings(self, updates: Dict) -> Dict:
        with self._lock:
            new_settings = self.settings.model_copy(update=updates)
            self.settings = new_settings
            self.save_settings()
            self._touch()
            return new_settings.model_dump()

    def set_verbose_logging(self, enabled: bool) -> None:
        with self._lock:
            self.settings = self.settings.model_copy(update={"verbose_logging": enabled})
            self.save_settings()
            self._touch()

    def _touch(self) -> None:
        self.last_update = time.time()

    # ------------------------------------------------------------------
    # Snapshot helpers
    # ------------------------------------------------------------------
    def snapshot(self) -> Dict:
        with self._lock:
            return {
                "scraping_status": self.scraping_status,
                "download_status": self.download_status,
                "scraping_progress": self.scraping_progress,
                "download_progress": self.download_progress,
                "current_operation": self.current_operation,
                "current_download_item": self.current_download_item,
                "log_messages": list(self.log_messages),
                "available_files": list(self.available_files),
                "current_file_type": self.current_file_type,
                "completed_downloads": list(self.completed_downloads),
                "failed_downloads": list(self.failed_downloads),
                "recent_download_events": [event.as_dict() for event in self.recent_download_events],
                "last_update": self.last_update,
                "settings": self.settings.model_dump(),
            }

    def get_settings(self) -> Dict:
        with self._lock:
            return self.settings.model_dump()

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def ensure_download_selection(self, urls: List[str]) -> Tuple[List[Dict], List[str]]:
        """Return matching file objects for the provided URLs."""
        with self._lock:
            matched = [f for f in self.available_files if f.get("url") in urls]
        found_urls = [f.get("url") for f in matched if f.get("url")]
        missing = [url for url in urls if url not in found_urls]
        return matched, missing


state_manager = StateManager()
state_manager.load_settings()