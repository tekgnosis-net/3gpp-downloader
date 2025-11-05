"""
3GPP Downloader Web UI
A web interface for the 3GPP specification downloader using Mesop framework.
"""

import mesop as me
import mesop.labs as mel
from pathlib import Path
import json
import asyncio
import threading
from typing import List, Dict, Optional
import time
import os
import logging
from utils.logging_config import setup_logger

# Configure logger for web app
logging_file = os.getenv('WEB_APP_LOG_FILE', 'logs/web_app.log')
logger_name = os.getenv('WEB_APP_LOGGER_NAME', 'web_app')
console_level = getattr(logging, os.getenv('WEB_APP_CONSOLE_LEVEL', 'INFO').upper(), logging.INFO)
file_level = getattr(logging, os.getenv('WEB_APP_FILE_LEVEL', 'INFO').upper(), logging.INFO)
max_bytes = int(os.getenv('WEB_APP_MAX_BYTES', '10485760'))
backup_count = int(os.getenv('WEB_APP_BACKUP_COUNT', '5'))

web_logger = setup_logger(logger_name, log_file=logging_file, console_level=console_level, logfile_level=file_level, max_bytes=max_bytes, backup_count=backup_count)
from main import scrape_data, filter_latest_versions, download_data, scrape_data_with_config, download_data_with_config

# Design System Constants
class Theme:
    """Modern design system with consistent colors, spacing, and typography"""

    # Color Palette
    PRIMARY = "#1976d2"
    PRIMARY_DARK = "#1565c0"
    PRIMARY_LIGHT = "#42a5f5"
    SECONDARY = "#dc004e"
    SECONDARY_DARK = "#9a0036"
    SECONDARY_LIGHT = "#ff5983"
    ACCENT = "#ff6f00"
    ACCENT_DARK = "#e65100"
    ACCENT_LIGHT = "#ff8f00"

    # Status Colors
    SUCCESS = "#4caf50"
    SUCCESS_LIGHT = "#81c784"
    ERROR = "#f44336"
    ERROR_LIGHT = "#ef5350"
    WARNING = "#ff9800"
    WARNING_LIGHT = "#ffb74d"
    INFO = "#2196f3"
    INFO_LIGHT = "#64b5f6"

    # Neutral Colors
    SURFACE = "#ffffff"
    SURFACE_VARIANT = "#f5f5f5"
    ON_SURFACE = "#1c1b1f"
    ON_SURFACE_VARIANT = "#49454f"
    OUTLINE = "#79747e"
    OUTLINE_VARIANT = "#c4c7c5"

    # Spacing (8px grid system)
    SPACE_1 = 8
    SPACE_2 = 16
    SPACE_3 = 24
    SPACE_4 = 32
    SPACE_5 = 40
    SPACE_6 = 48

    # Border Radius
    RADIUS_SM = 4
    RADIUS_MD = 8
    RADIUS_LG = 12
    RADIUS_XL = 16
    RADIUS_XXL = 24

    # Shadows
    SHADOW_SM = "0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24)"
    SHADOW_MD = "0 3px 6px rgba(0,0,0,0.15), 0 2px 4px rgba(0,0,0,0.12)"
    SHADOW_LG = "0 10px 20px rgba(0,0,0,0.15), 0 3px 6px rgba(0,0,0,0.10)"
    SHADOW_XL = "0 15px 25px rgba(0,0,0,0.15), 0 5px 10px rgba(0,0,0,0.05)"

    # Typography
    FONT_FAMILY = "'Roboto', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif"
    FONT_SIZE_H1 = 32
    FONT_SIZE_H2 = 24
    FONT_SIZE_H3 = 20
    FONT_SIZE_H4 = 18
    FONT_SIZE_H5 = 16
    FONT_SIZE_H6 = 14
    FONT_SIZE_BODY = 14
    FONT_SIZE_CAPTION = 12

    FONT_WEIGHT_LIGHT = 300
    FONT_WEIGHT_REGULAR = 400
    FONT_WEIGHT_MEDIUM = 500
    FONT_WEIGHT_BOLD = 700

    LINE_HEIGHT_TIGHT = 1.25
    LINE_HEIGHT_NORMAL = 1.5
    LINE_HEIGHT_RELAXED = 1.75

# Common Style Functions
def create_card_style(elevation: str = "md", padding: int = Theme.SPACE_4) -> me.Style:
    """Create a card style with consistent elevation and padding"""
    return me.Style(
        background=Theme.SURFACE,
        border_radius=Theme.RADIUS_LG,
        box_shadow=getattr(Theme, f"SHADOW_{elevation.upper()}"),
        padding=me.Padding.all(padding),
        border=me.Border.all(me.BorderSide(width=1, color=Theme.OUTLINE_VARIANT, style="solid")),
    )

def create_gradient_card_style(primary: str, secondary: str) -> me.Style:
    """Hero card style with gradient background for key insights"""
    return me.Style(
        background=f"linear-gradient(135deg, {primary}, {secondary})",
        border_radius=Theme.RADIUS_LG,
        padding=me.Padding.all(Theme.SPACE_4),
        color="white",
        box_shadow=Theme.SHADOW_LG,
        border=me.Border.all(me.BorderSide(width=0))
    )

def create_button_style(variant: str = "primary", size: str = "md") -> me.Style:
    """Create a button style with consistent theming"""
    base_style = me.Style(
        border_radius=Theme.RADIUS_MD,
        font_weight=Theme.FONT_WEIGHT_MEDIUM,
        border=me.Border.all(me.BorderSide(width=0)),
        cursor="pointer",
        transition="all 0.2s ease-in-out",
        text_transform="none",
        font_family=Theme.FONT_FAMILY,
    )

    # Size variants
    if size == "sm":
        base_style.padding = me.Padding.symmetric(horizontal=Theme.SPACE_3, vertical=Theme.SPACE_1)
        base_style.font_size = Theme.FONT_SIZE_CAPTION
    elif size == "lg":
        base_style.padding = me.Padding.symmetric(horizontal=Theme.SPACE_5, vertical=Theme.SPACE_3)
        base_style.font_size = Theme.FONT_SIZE_H5
    else:  # md
        base_style.padding = me.Padding.symmetric(horizontal=Theme.SPACE_4, vertical=Theme.SPACE_2)
        base_style.font_size = Theme.FONT_SIZE_BODY

    # Color variants
    if variant == "primary":
        base_style.background = Theme.PRIMARY
        base_style.color = "white"
    elif variant == "secondary":
        base_style.background = Theme.SECONDARY
        base_style.color = "white"
    elif variant == "accent":
        base_style.background = Theme.ACCENT
        base_style.color = "white"
    elif variant == "success":
        base_style.background = Theme.SUCCESS
        base_style.color = "white"
    elif variant == "error":
        base_style.background = Theme.ERROR
        base_style.color = "white"
    elif variant == "outline":
        base_style.background = "transparent"
        base_style.color = Theme.PRIMARY
        base_style.border = me.Border.all(me.BorderSide(width=1, color=Theme.PRIMARY))
    elif variant == "ghost":
        base_style.background = "transparent"
        base_style.color = Theme.ON_SURFACE

    return base_style

def create_status_chip(status: str, label: str) -> me.Style:
    """Create a status chip style based on status type"""
    base_style = me.Style(
        padding=me.Padding.symmetric(horizontal=Theme.SPACE_2, vertical=Theme.SPACE_1),
        border_radius=Theme.RADIUS_XL,
        font_size=Theme.FONT_SIZE_CAPTION,
        font_weight=Theme.FONT_WEIGHT_MEDIUM,
        display="inline-flex",
        align_items="center",
        gap=Theme.SPACE_1,
    )

    if status == "success" or status == "completed":
        base_style.background = Theme.SUCCESS_LIGHT
        base_style.color = Theme.SUCCESS
    elif status == "error" or status == "failed":
        base_style.background = Theme.ERROR_LIGHT
        base_style.color = Theme.ERROR
    elif status == "warning":
        base_style.background = Theme.WARNING_LIGHT
        base_style.color = Theme.WARNING
    elif status == "running" or status == "active":
        base_style.background = Theme.INFO_LIGHT
        base_style.color = Theme.INFO
    else:  # idle or default
        base_style.background = Theme.OUTLINE_VARIANT
        base_style.color = Theme.ON_SURFACE_VARIANT

    return base_style

# Global state for tracking operations
class AppState:
    def __init__(self):
        self.scraping_status = "idle"  # idle, running, completed, error
        self.download_status = "idle"   # idle, running, completed, error
        self.scraping_progress = 0
        self.download_progress = 0
        self.current_operation = ""
        self.log_messages: List[str] = []
        self.available_files: List[Dict] = []
        self.selected_files: List[str] = []
        self.current_file_type = "none"  # "none", "filtered", "all"
        self.current_page = 0
        self.show_download_confirmation = False
        self.last_update = 0  # timestamp for triggering re-renders
        self.completed_downloads: List[str] = []
        self.failed_downloads: List[str] = []
        self.recent_download_events: List[Dict[str, str]] = []
        self.current_download_item: Optional[str] = None

        # UI state
        self.show_advanced_settings = False
        self.current_tab = "dashboard"  # dashboard, settings, logs
        
        # File selection state
        self.search_query = ""
        self.series_filter = "All"
        self.release_filter = "All"
        
        # Notification state
        self.completion_message = ""
        self.show_completion_notification = False
        
        # Error state
        self.error_message = ""
        self.error_details = ""
        self.show_error_notification = False
        self.error_recovery_options = []

        # Configuration options (equivalent to main.py arguments)
        self.resume_downloads = True
        self.no_download = False
        self.download_all_versions = False
        self.organize_by_series = False
        self.specific_release: Optional[int] = None
        self.thread_count = 5
        self.verbose_logging = False
        
        # Environment-based configuration options
        # Logging settings
        self.main_console_level = "INFO"
        self.main_file_level = "DEBUG"
        self.web_console_level = "INFO"
        self.web_file_level = "INFO"
        
        # HTTP/Connection settings
        self.http_max_connections = 100
        self.http_max_connections_per_host = 10
        self.http_total_timeout = 300
        self.http_connect_timeout = 10
        self.http_read_timeout = 60
        
        # Retry settings
        self.retry_max_attempts = 5
        self.retry_base_delay = 1.0
        self.retry_max_delay = 60.0
        
        # Scrapy/Spider settings
        self.scrapy_download_delay = 0.1
        self.scrapy_concurrent_requests = 8
        self.etsi_min_release = 15

        # UI help hint visibility
        self.visible_hints: Dict[str, bool] = {}
        
        # Web UI settings
        self.web_max_log_messages = 100
        self.web_refresh_interval = 5

app_state = AppState()


def toggle_hint(key: str):
    """Toggle the visibility of a contextual settings hint"""
    app_state.visible_hints[key] = not app_state.visible_hints.get(key, False)
    app_state.last_update = time.time()


def settings_hint(key: str, message: str):
    """Render an interactive help icon with contextual guidance"""
    is_visible = app_state.visible_hints.get(key, False)
    with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_1)):
        with me.box(
            style=me.Style(
                cursor="pointer",
                display="flex",
                align_items="center",
                justify_content="center"
            ),
            on_click=lambda e, hint_key=key: toggle_hint(hint_key)
        ):
            me.icon("help" if is_visible else "help_outline", style=me.Style(
                color=Theme.PRIMARY if is_visible else Theme.ON_SURFACE_VARIANT,
                font_size=16
            ))

        if is_visible:
            me.text(message, style=me.Style(
                font_size=Theme.FONT_SIZE_CAPTION,
                color=Theme.ON_SURFACE_VARIANT,
                background=Theme.SURFACE_VARIANT,
                padding=me.Padding.symmetric(horizontal=Theme.SPACE_2, vertical=4),
                border_radius=Theme.RADIUS_MD,
                max_width="280px",
                line_height=1.4
            ))

def save_settings():
    """Save current settings to a JSON file"""
    settings_file = Path("web_settings.json")
    try:
        settings_data = {
            # Download options
            "resume_downloads": app_state.resume_downloads,
            "no_download": app_state.no_download,
            "download_all_versions": app_state.download_all_versions,
            "organize_by_series": app_state.organize_by_series,
            "specific_release": app_state.specific_release,
            "thread_count": app_state.thread_count,
            "verbose_logging": app_state.verbose_logging,
            
            # HTTP/Connection settings
            "http_max_connections": app_state.http_max_connections,
            "http_max_connections_per_host": app_state.http_max_connections_per_host,
            "http_total_timeout": app_state.http_total_timeout,
            "http_connect_timeout": app_state.http_connect_timeout,
            "http_read_timeout": app_state.http_read_timeout,
            
            # UI settings
            "show_advanced_settings": app_state.show_advanced_settings,
            "current_tab": app_state.current_tab,
            
            # File selection state
            "search_query": app_state.search_query,
            "series_filter": app_state.series_filter,
            "release_filter": app_state.release_filter
        }
        
        with open(settings_file, 'w') as f:
            json.dump(settings_data, f, indent=2)
        
        add_log_message(f"Settings saved to {settings_file}")
    except Exception as e:
        add_log_message(f"Error saving settings: {str(e)}")

def load_settings():
    """Load settings from JSON file"""
    settings_file = Path("web_settings.json")
    try:
        if settings_file.exists():
            with open(settings_file, 'r') as f:
                settings_data = json.load(f)
            
            # Load download options
            app_state.resume_downloads = settings_data.get("resume_downloads", True)
            app_state.no_download = settings_data.get("no_download", False)
            app_state.download_all_versions = settings_data.get("download_all_versions", False)
            app_state.organize_by_series = settings_data.get("organize_by_series", False)
            app_state.specific_release = settings_data.get("specific_release", None)
            app_state.thread_count = settings_data.get("thread_count", 5)
            app_state.verbose_logging = settings_data.get("verbose_logging", False)
            
            # Load HTTP/Connection settings
            app_state.http_max_connections = settings_data.get("http_max_connections", 100)
            app_state.http_max_connections_per_host = settings_data.get("http_max_connections_per_host", 10)
            app_state.http_total_timeout = settings_data.get("http_total_timeout", 300)
            app_state.http_connect_timeout = settings_data.get("http_connect_timeout", 10)
            app_state.http_read_timeout = settings_data.get("http_read_timeout", 60)
            
            # Load UI settings
            app_state.show_advanced_settings = settings_data.get("show_advanced_settings", False)
            app_state.current_tab = settings_data.get("current_tab", "dashboard")
            
            # Load file selection state
            app_state.search_query = settings_data.get("search_query", "")
            app_state.series_filter = str(settings_data.get("series_filter", "All"))
            app_state.release_filter = str(settings_data.get("release_filter", "All"))
            
            add_log_message(f"Settings loaded from {settings_file}")
        else:
            add_log_message("No settings file found, using defaults")
    except Exception as e:
        add_log_message(f"Error loading settings: {str(e)}")

def add_log_message(message: str):
    """Add a message to the log"""
    timestamp = time.strftime("%H:%M:%S")
    app_state.log_messages.append(f"[{timestamp}] {message}")
    max_entries = max(1, getattr(app_state, "web_max_log_messages", 100))
    if len(app_state.log_messages) > max_entries:
        app_state.log_messages = app_state.log_messages[-max_entries:]
    app_state.last_update = time.time()


class UILogHandler(logging.Handler):
    """Route Python logging output into the in-app activity log."""

    def __init__(self, level: int = logging.INFO):
        super().__init__(level)
        self.setFormatter(logging.Formatter("[%(name)s][%(levelname)s] %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
        except Exception:
            message = record.getMessage()

        for line in message.splitlines():
            try:
                add_log_message(line)
            except Exception:
                self.handleError(record)
                break


ui_log_handler = UILogHandler()

_TRACKED_LOGGER_NAMES = {
    logger_name,
    os.getenv('MAIN_LOGGER_NAME', 'downloader'),
    os.getenv('JSON_DOWNLOADER_LOGGER_NAME', 'json_downloader'),
    os.getenv('ETSI_SPIDER_LOGGER_NAME', 'etsi_spider'),
}


def _ensure_ui_handler(target_logger: logging.Logger) -> None:
    if target_logger and ui_log_handler not in target_logger.handlers:
        target_logger.addHandler(ui_log_handler)


def configure_logging_preferences() -> None:
    """Align Python logging output with the web UI visibility preferences."""
    level = logging.DEBUG if app_state.verbose_logging else logging.INFO
    ui_log_handler.setLevel(level)

    for name in _TRACKED_LOGGER_NAMES:
        if not name:
            continue
        target_logger = logging.getLogger(name)
        target_logger.setLevel(level)
        _ensure_ui_handler(target_logger)

    scrapy_logger = logging.getLogger("scrapy")
    scrapy_logger.setLevel(logging.INFO if app_state.verbose_logging else logging.WARNING)
    _ensure_ui_handler(scrapy_logger)

    web_logger.info("Verbose logging enabled" if app_state.verbose_logging else "Verbose logging disabled")

def record_download_event(filename: str, status: str, description: str):
    """Track noteworthy download events for dashboard insights"""
    timestamp = time.strftime("%H:%M:%S")
    app_state.recent_download_events.append({
        "timestamp": timestamp,
        "filename": filename,
        "status": status,
        "description": description
    })
    if len(app_state.recent_download_events) > 12:
        app_state.recent_download_events = app_state.recent_download_events[-12:]

def show_completion_notification(message: str):
    """Show a completion notification"""
    app_state.completion_message = message
    app_state.show_completion_notification = True

def dismiss_completion_notification(e: me.ClickEvent):
    """Dismiss the completion notification"""
    app_state.show_completion_notification = False
    app_state.completion_message = ""

def show_error_notification(message: str, details: str = "", recovery_options: List[str] = None):
    """Show an error notification with recovery options"""
    app_state.error_message = message
    app_state.error_details = details
    app_state.error_recovery_options = recovery_options or []
    app_state.show_error_notification = True

def dismiss_error_notification(e: me.ClickEvent):
    """Dismiss the error notification"""
    app_state.show_error_notification = False
    app_state.error_message = ""
    app_state.error_details = ""
    app_state.error_recovery_options = []

def retry_last_operation(e: me.ClickEvent):
    """Retry the last failed operation"""
    # For now, just dismiss the error - in a more sophisticated implementation,
    # this would track the last operation and retry it
    dismiss_error_notification(e)
    add_log_message("Retrying last operation...")

def update_scraping_progress(progress: float, message: str = ""):
    """Update scraping progress"""
    app_state.scraping_progress = progress
    app_state.last_update = time.time()  # Trigger UI re-render
    if message:
        app_state.current_operation = message
        add_log_message(message)
    
    # Show completion notification when scraping finishes
    if progress >= 100 and app_state.scraping_status == "running":
        app_state.scraping_status = "completed"
        show_completion_notification("Scraping completed successfully! Files have been discovered and saved.")

def update_download_progress(progress: float, message: str = ""):
    """Update download progress"""
    app_state.download_progress = progress
    app_state.last_update = time.time()  # Update timestamp to trigger re-render
    if message:
        app_state.current_operation = message
        add_log_message(message)
    
    # Show completion notification when download finishes
    if progress >= 100 and app_state.download_status == "running":
        app_state.download_status = "completed"

def download_progress_callback(filename: str, status: str, percent: float):
    """Handle download progress events emitted by the async downloader"""
    # Ensure tracking attributes exist once per batch
    if not getattr(download_progress_callback, "initialized", False):
        total = len(app_state.selected_files) or 1
        download_progress_callback.total_files = total
        download_progress_callback.completed_files = 0
        download_progress_callback.error_files = 0
        download_progress_callback.initialized = True

    if status == "starting":
        app_state.current_download_item = filename
        app_state.current_operation = f"Starting download: {filename}"
        app_state.last_update = time.time()
        record_download_event(filename, "Queued", "Preparing download")
    elif status == "file_progress":
        app_state.current_download_item = filename
        app_state.current_operation = f"Downloading {filename} ({percent:.0f}%)"
        app_state.last_update = time.time()
    elif status == "file_complete":
        download_progress_callback.completed_files += 1
        app_state.completed_downloads.append(filename)
        app_state.completed_downloads = app_state.completed_downloads[-15:]
        record_download_event(filename, "Completed", "Saved to downloads")
        add_log_message(f"Finished downloading {filename}")
    elif status == "error":
        download_progress_callback.error_files += 1
        app_state.failed_downloads.append(filename)
        app_state.failed_downloads = app_state.failed_downloads[-15:]
        record_download_event(filename, "Failed", "See logs for details")
        add_log_message(f"Error downloading {filename}")
        app_state.download_status = "error"
        app_state.current_operation = f"Error downloading {filename}"
        app_state.last_update = time.time()
    elif status == "overall_progress":
        # Map overall downloader percent (0-100) into reserved 80% window (10-90)
        download_window = max(0.0, min(100.0, percent))
        scaled_progress = 10 + (download_window * 0.8)
        completed = download_progress_callback.completed_files
        total = download_progress_callback.total_files
        errors = download_progress_callback.error_files
        status_message = f"Downloaded {completed}/{total} files"
        if errors:
            status_message += f" (errors: {errors})"
        update_download_progress(min(90, scaled_progress), status_message)
    elif status == "all_finished":
        if download_progress_callback.error_files:
            update_download_progress(90, f"Completed with {download_progress_callback.error_files} error(s)")
        else:
            update_download_progress(90, "Download processing complete")
        record_download_event("Batch", "All Files", "Download batch finished")
        app_state.current_download_item = None
    elif status == "errors":
        # Final error count communicated after completion
        error_count = int(percent)
        download_progress_callback.error_files = error_count
        if error_count:
            record_download_event("Batch", "Issues Detected", f"{error_count} file{'s' if error_count != 1 else ''} failed")
            show_error_notification(
                "Downloads completed with errors",
                f"{error_count} file{'s' if error_count != 1 else ''} failed to download.",
                [
                    "Check your network connection",
                    "Verify the source URLs are still valid",
                    "Review the logs tab for detailed error messages"
                ]
            )
        selected_count = len(app_state.selected_files)
        show_completion_notification(f"Download completed successfully! {selected_count} file{'s' if selected_count != 1 else ''} downloaded.")

@me.page(path="/", title=os.getenv('WEB_TITLE', '3GPP Downloader'))
def main_page():
    """Main page of the 3GPP Downloader web UI with modern design"""
    
    # Add CSS animations
    me.html("""
    <style>
    @keyframes progress-indeterminate {
        0% { left: -30%; }
        100% { left: 100%; }
    }
    .progress-indeterminate {
        animation: progress-indeterminate 1.5s ease-in-out infinite;
    }
    </style>
    """)

    # Completion notification
    if app_state.show_completion_notification:
        with me.box(
            style=me.Style(
                background="rgba(0, 0, 0, 0.6)" if app_state.show_completion_notification else "transparent",
                display="block" if app_state.show_completion_notification else "none",
                height="100%",
                overflow_x="auto",
                overflow_y="auto",
                position="fixed",
                width="100%",
                z_index=1001,
                top=0,
                left=0,
                backdrop_filter="blur(2px)",
            ),
            on_click=dismiss_completion_notification,
        ):
            with me.box(
                style=me.Style(
                    place_items="center",
                    display="grid",
                    height="100vh",
                )
            ):
                with me.box(
                    style=create_card_style("md", Theme.SPACE_4),
                    on_click=lambda e: None,
                ):
                    # Success header
                    with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2, margin=me.Margin(bottom=Theme.SPACE_3))):
                        me.icon("celebration", style=me.Style(color=Theme.SUCCESS, font_size=28))
                        me.text("Success!", style=me.Style(
                            font_size=Theme.FONT_SIZE_H4,
                            font_weight=Theme.FONT_WEIGHT_BOLD,
                            color=Theme.ON_SURFACE
                        ))

                    # Message
                    me.text(app_state.completion_message, style=me.Style(
                        font_size=Theme.FONT_SIZE_BODY,
                        color=Theme.ON_SURFACE_VARIANT,
                        margin=me.Margin(bottom=Theme.SPACE_4),
                        line_height=Theme.LINE_HEIGHT_NORMAL,
                        text_align="center"
                    ))

                    # Dismiss button
                    me.button(
                        "Continue",
                        on_click=dismiss_completion_notification,
                        style=create_button_style("primary", "md")
                    )

    # Error notification
    if app_state.show_error_notification:
        with me.box(
            style=me.Style(
                background="rgba(0, 0, 0, 0.6)" if app_state.show_error_notification else "transparent",
                display="block" if app_state.show_error_notification else "none",
                height="100%",
                overflow_x="auto",
                overflow_y="auto",
                position="fixed",
                width="100%",
                z_index=1002,
                top=0,
                left=0,
                backdrop_filter="blur(2px)",
            ),
            on_click=dismiss_error_notification,
        ):
            with me.box(
                style=me.Style(
                    place_items="center",
                    display="grid",
                    height="100vh",
                )
            ):
                with me.box(
                    style=create_card_style("xl", Theme.SPACE_5),
                    on_click=lambda e: None,
                ):
                    # Error header
                    with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2, margin=me.Margin(bottom=Theme.SPACE_3))):
                        me.icon("error", style=me.Style(color=Theme.ERROR, font_size=28))
                        me.text("Error Occurred", style=me.Style(
                            font_size=Theme.FONT_SIZE_H4,
                            font_weight=Theme.FONT_WEIGHT_BOLD,
                            color=Theme.ON_SURFACE
                        ))

                    # Error message
                    me.text(app_state.error_message, style=me.Style(
                        font_size=Theme.FONT_SIZE_BODY,
                        color=Theme.ON_SURFACE_VARIANT,
                        margin=me.Margin(bottom=Theme.SPACE_3),
                        line_height=Theme.LINE_HEIGHT_NORMAL,
                        text_align="center"
                    ))

                    # Error details (if available)
                    if app_state.error_details:
                        with me.box(style=me.Style(
                            background=Theme.ERROR + "10",
                            border=me.Border.all(me.BorderSide(width=1, color=Theme.ERROR + "40")),
                            border_radius=Theme.RADIUS_MD,
                            padding=me.Padding.all(Theme.SPACE_3),
                            margin=me.Margin(bottom=Theme.SPACE_4)
                        )):
                            me.text("Technical Details:", style=me.Style(
                                font_size=Theme.FONT_SIZE_CAPTION,
                                font_weight=Theme.FONT_WEIGHT_MEDIUM,
                                color=Theme.ERROR,
                                margin=me.Margin(bottom=Theme.SPACE_1)
                            ))
                            me.text(app_state.error_details, style=me.Style(
                                font_size=Theme.FONT_SIZE_CAPTION,
                                color=Theme.ON_SURFACE_VARIANT,
                                font_family="monospace",
                                word_wrap="break-word"
                            ))

                    # Recovery options
                    if app_state.error_recovery_options:
                        me.text("Suggested Actions:", style=me.Style(
                            font_size=Theme.FONT_SIZE_BODY,
                            font_weight=Theme.FONT_WEIGHT_MEDIUM,
                            color=Theme.ON_SURFACE,
                            margin=me.Margin(bottom=Theme.SPACE_2)
                        ))
                        for option in app_state.error_recovery_options:
                            with me.box(style=me.Style(margin=me.Margin(bottom=Theme.SPACE_2))):
                                me.text(f"• {option}", style=me.Style(
                                    font_size=Theme.FONT_SIZE_BODY,
                                    color=Theme.ON_SURFACE_VARIANT,
                                    line_height=Theme.LINE_HEIGHT_NORMAL
                                ))

                    # Action buttons
                    with me.box(style=me.Style(display="flex", gap=Theme.SPACE_3, justify_content="center")):
                        if app_state.error_recovery_options:
                            me.button(
                                "Try Again",
                                on_click=retry_last_operation,
                                style=create_button_style("primary", "md")
                            )
                        me.button(
                            "Dismiss",
                            on_click=dismiss_error_notification,
                            style=create_button_style("outline", "md")
                        )

    # Download confirmation dialog
    with me.box(
        style=me.Style(
            background="rgba(0, 0, 0, 0.6)" if app_state.show_download_confirmation else "transparent",
            display="block" if app_state.show_download_confirmation else "none",
            height="100%",
            overflow_x="auto",
            overflow_y="auto",
            position="fixed",
            width="100%",
            z_index=1000,
            top=0,
            left=0,
            backdrop_filter="blur(4px)",
        ),
        on_click=cancel_download_confirmation,
    ):
        with me.box(
            style=me.Style(
                place_items="center",
                display="grid",
                height="100vh",
            )
        ):
            with me.box(
                style=create_card_style("xl", Theme.SPACE_5),
                on_click=lambda e: None,
            ):
                # Dialog header
                with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2, margin=me.Margin(bottom=Theme.SPACE_4))):
                    me.icon("download", style=me.Style(color=Theme.PRIMARY, font_size=24))
                    me.text("Confirm Download", style=me.Style(
                        font_size=Theme.FONT_SIZE_H3,
                        font_weight=Theme.FONT_WEIGHT_BOLD,
                        color=Theme.ON_SURFACE
                    ))

                # Dialog content
                selected_count = len([f for f in app_state.available_files if f.get('url') in app_state.selected_files])
                me.text(
                    f"Are you sure you want to download {selected_count} selected file{'s' if selected_count != 1 else ''}?",
                    style=me.Style(
                        font_size=Theme.FONT_SIZE_BODY,
                        color=Theme.ON_SURFACE_VARIANT,
                        margin=me.Margin(bottom=Theme.SPACE_5),
                        line_height=Theme.LINE_HEIGHT_NORMAL
                    )
                )

                # Dialog actions
                with me.box(
                    style=me.Style(
                        display="flex",
                        justify_content="end",
                        gap=Theme.SPACE_2
                    )
                ):
                    me.button(
                        "Cancel",
                        on_click=cancel_download_confirmation,
                        style=create_button_style("ghost", "md")
                    )
                    me.button(
                        "Download",
                        on_click=confirm_download,
                        style=create_button_style("accent", "md")
                    )

    # Main application layout
    with me.box(
        style=me.Style(
            min_height="100vh",
            background=f"linear-gradient(135deg, {Theme.SURFACE_VARIANT} 0%, {Theme.SURFACE} 100%)",
            font_family=Theme.FONT_FAMILY
        )
    ):
        # Modern Header
        with me.box(
            style=me.Style(
                background=Theme.SURFACE,
                border=me.Border(bottom=me.BorderSide(width=1, color=Theme.OUTLINE_VARIANT)),
                box_shadow=Theme.SHADOW_SM,
                padding=me.Padding.symmetric(horizontal=Theme.SPACE_4, vertical=Theme.SPACE_3),
                position="sticky",
                top=0,
                z_index=100,
            )
        ):
            with me.box(
                style=me.Style(
                    max_width="1200px",
                    margin=me.Margin.symmetric(horizontal="auto"),
                    display="flex",
                    align_items="center",
                    justify_content="space-between"
                )
            ):
                # Logo and title
                with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_3)):
                    me.icon("description", style=me.Style(
                        color=Theme.PRIMARY,
                        font_size=32
                    ))
                    with me.box():
                        me.text("3GPP", style=me.Style(
                            font_size=Theme.FONT_SIZE_H4,
                            font_weight=Theme.FONT_WEIGHT_BOLD,
                            color=Theme.PRIMARY,
                            line_height=1.2
                        ))
                        me.text("Specification Downloader", style=me.Style(
                            font_size=Theme.FONT_SIZE_CAPTION,
                            color=Theme.ON_SURFACE_VARIANT,
                            line_height=1.2
                        ))

                # Navigation tabs
                with me.box(style=me.Style(display="flex", gap=Theme.SPACE_1)):
                    navigation_tabs()

        # Main content area
        with me.box(
            style=me.Style(
                max_width="1200px",
                margin=me.Margin.symmetric(horizontal="auto", vertical=Theme.SPACE_4),
                padding=me.Padding.symmetric(horizontal=Theme.SPACE_4)
            )
        ):
            # Tab content
            if app_state.current_tab == "dashboard":
                dashboard_content()
            elif app_state.current_tab == "settings":
                settings_content()
            elif app_state.current_tab == "logs":
                logs_content()

def switch_to_dashboard(e: me.ClickEvent):
    """Switch to dashboard tab"""
    app_state.current_tab = "dashboard"

def switch_to_settings(e: me.ClickEvent):
    """Switch to settings tab"""
    app_state.current_tab = "settings"

def switch_to_logs(e: me.ClickEvent):
    """Switch to logs tab"""
    app_state.current_tab = "logs"

def navigation_tabs():
    """Navigation tabs component"""
    tabs = [
        ("dashboard", "Dashboard", "dashboard", switch_to_dashboard),
        ("settings", "Settings", "settings", switch_to_settings),
        ("logs", "Logs", "article", switch_to_logs)
    ]

    for tab_id, label, icon, click_handler in tabs:
        is_active = app_state.current_tab == tab_id
        with me.box(
            style=me.Style(
                padding=me.Padding.symmetric(horizontal=Theme.SPACE_3, vertical=Theme.SPACE_2),
                border_radius=Theme.RADIUS_MD,
                cursor="pointer",
                background=Theme.PRIMARY_LIGHT if is_active else "transparent",
                color=Theme.SURFACE if is_active else Theme.ON_SURFACE,
                transition="all 0.2s ease-in-out",
                display="flex",
                align_items="center",
                gap=Theme.SPACE_2
            ),
            on_click=click_handler
        ):
            me.icon(icon, style=me.Style(font_size=18))
            me.text(label, style=me.Style(
                font_size=Theme.FONT_SIZE_BODY,
                font_weight=Theme.FONT_WEIGHT_MEDIUM
            ))

def switch_tab(tab_id: str):
    """Switch to a different tab"""
    app_state.current_tab = tab_id

def toggle_resume_downloads(e: me.CheckboxChangeEvent):
    """Toggle resume downloads setting"""
    app_state.resume_downloads = e.checked
    save_settings()

def toggle_download_all_versions(e: me.CheckboxChangeEvent):
    """Toggle download all versions setting"""
    app_state.download_all_versions = e.checked
    save_settings()

def toggle_organize_by_series(e: me.CheckboxChangeEvent):
    """Toggle organize by series setting"""
    app_state.organize_by_series = e.checked
    save_settings()

def toggle_verbose_logging(e: me.CheckboxChangeEvent):
    """Toggle verbose logging setting"""
    if app_state.verbose_logging == e.checked:
        return
    app_state.verbose_logging = e.checked
    configure_logging_preferences()
    save_settings()

def toggle_advanced_settings(e: me.CheckboxChangeEvent):
    """Toggle advanced settings visibility"""
    app_state.show_advanced_settings = e.checked
    save_settings()

def on_thread_count_change(e: me.InputBlurEvent):
    """Handle thread count input change"""
    try:
        app_state.thread_count = max(1, min(20, int(e.value)))
        save_settings()
    except ValueError:
        pass  # Keep current value if invalid

def on_max_connections_change(e: me.InputBlurEvent):
    """Handle max connections input change"""
    try:
        app_state.http_max_connections = max(1, min(1000, int(e.value)))
        save_settings()
    except ValueError:
        pass

def on_max_connections_per_host_change(e: me.InputBlurEvent):
    """Handle max connections per host input change"""
    try:
        app_state.http_max_connections_per_host = max(1, min(100, int(e.value)))
        save_settings()
    except ValueError:
        pass

def on_total_timeout_change(e: me.InputBlurEvent):
    """Handle total timeout input change"""
    try:
        app_state.http_total_timeout = max(10, min(3600, int(e.value)))
        save_settings()
    except ValueError:
        pass

def on_connect_timeout_change(e: me.InputBlurEvent):
    """Handle connect timeout input change"""
    try:
        app_state.http_connect_timeout = max(1, min(300, int(e.value)))
        save_settings()
    except ValueError:
        pass

def welcome_screen():
    """Welcome screen for first-time users or when no files are available"""
    with me.box(style=me.Style(
        display="flex",
        flex_direction="column",
        align_items="center",
        justify_content="center",
        min_height="60vh",
        text_align="center",
        padding=me.Padding.all(Theme.SPACE_4)
    )):
        # Welcome header
        me.icon("description", style=me.Style(
            font_size=64,
            color=Theme.PRIMARY,
            margin=me.Margin(bottom=Theme.SPACE_3)
        ))
        
        me.text("Welcome to 3GPP Downloader", style=me.Style(
            font_size=Theme.FONT_SIZE_H2,
            font_weight=Theme.FONT_WEIGHT_BOLD,
            color=Theme.ON_SURFACE,
            margin=me.Margin(bottom=Theme.SPACE_2)
        ))
        
        me.text("Download 3GPP technical specifications with ease", style=me.Style(
            font_size=Theme.FONT_SIZE_H5,
            color=Theme.ON_SURFACE_VARIANT,
            margin=me.Margin(bottom=Theme.SPACE_5)
        ))
        
        # Quick start guide
        with me.box(style=me.Style(
            background=Theme.SURFACE_VARIANT,
            padding=me.Padding.all(Theme.SPACE_4),
            border_radius=Theme.RADIUS_MD,
            margin=me.Margin(bottom=Theme.SPACE_4),
            max_width="600px"
        )):
            me.text("Get Started in 3 Simple Steps:", style=me.Style(
                font_size=Theme.FONT_SIZE_H5,
                font_weight=Theme.FONT_WEIGHT_MEDIUM,
                color=Theme.ON_SURFACE,
                margin=me.Margin(bottom=Theme.SPACE_3)
            ))
            
            # Step 1
            with me.box(style=me.Style(display="flex", align_items="flex-start", gap=Theme.SPACE_3, margin=me.Margin(bottom=Theme.SPACE_3))):
                with me.box(style=me.Style(
                    width=32, height=32, background=Theme.PRIMARY, border_radius="50%",
                    display="flex", align_items="center", justify_content="center", color="white",
                    font_weight=Theme.FONT_WEIGHT_BOLD, font_size=Theme.FONT_SIZE_H6, flex_shrink=0
                )):
                    me.text("1", style=me.Style(color="white"))
                with me.box(style=me.Style(text_align="left")):
                    me.text("Discover Specifications", style=me.Style(
                        font_size=Theme.FONT_SIZE_H6, font_weight=Theme.FONT_WEIGHT_MEDIUM,
                        color=Theme.ON_SURFACE, margin=me.Margin(bottom=Theme.SPACE_1)
                    ))
                    me.text("Click 'Start Scraping' to scan the 3GPP website and find all available technical specifications.", style=me.Style(
                        font_size=Theme.FONT_SIZE_BODY, color=Theme.ON_SURFACE_VARIANT, line_height=1.5
                    ))
            
            # Step 2
            with me.box(style=me.Style(display="flex", align_items="flex-start", gap=Theme.SPACE_3, margin=me.Margin(bottom=Theme.SPACE_3))):
                with me.box(style=me.Style(
                    width=32, height=32, background=Theme.SECONDARY, border_radius="50%",
                    display="flex", align_items="center", justify_content="center", color="white",
                    font_weight=Theme.FONT_WEIGHT_BOLD, font_size=Theme.FONT_SIZE_H6, flex_shrink=0
                )):
                    me.text("2", style=me.Style(color="white"))
                with me.box(style=me.Style(text_align="left")):
                    me.text("Choose What to Download", style=me.Style(
                        font_size=Theme.FONT_SIZE_H6, font_weight=Theme.FONT_WEIGHT_MEDIUM,
                        color=Theme.ON_SURFACE, margin=me.Margin(bottom=Theme.SPACE_1)
                    ))
                    me.text("Use filters to select specific series, releases, or get the latest versions only.", style=me.Style(
                        font_size=Theme.FONT_SIZE_BODY, color=Theme.ON_SURFACE_VARIANT, line_height=1.5
                    ))
            
            # Step 3
            with me.box(style=me.Style(display="flex", align_items="flex-start", gap=Theme.SPACE_3)):
                with me.box(style=me.Style(
                    width=32, height=32, background=Theme.ACCENT, border_radius="50%",
                    display="flex", align_items="center", justify_content="center", color="white",
                    font_weight=Theme.FONT_WEIGHT_BOLD, font_size=Theme.FONT_SIZE_H6, flex_shrink=0
                )):
                    me.text("3", style=me.Style(color="white"))
                with me.box(style=me.Style(text_align="left")):
                    me.text("Download Files", style=me.Style(
                        font_size=Theme.FONT_SIZE_H6, font_weight=Theme.FONT_WEIGHT_MEDIUM,
                        color=Theme.ON_SURFACE, margin=me.Margin(bottom=Theme.SPACE_1)
                    ))
                    me.text("Download selected specifications to your local machine with progress tracking.", style=me.Style(
                        font_size=Theme.FONT_SIZE_BODY, color=Theme.ON_SURFACE_VARIANT, line_height=1.5
                    ))
        
        # Action button
        start_button_style = create_button_style("primary", "lg")
        if app_state.scraping_status == "running" or app_state.download_status == "running":
            start_button_style.opacity = 0.6
            start_button_style.cursor = "not-allowed"

        me.button(
            "🚀 Start Scraping",
            on_click=start_scraping,
            disabled=int(app_state.scraping_status == "running" or app_state.download_status == "running"),
            style=start_button_style
        )

        # Show live status feedback even before files are discovered
        if app_state.scraping_status != "idle" or app_state.download_status != "idle":
            with me.box(style=me.Style(
                margin=me.Margin(top=Theme.SPACE_5),
                width="100%",
                max_width="640px",
                display="flex",
                flex_direction="column",
                gap=Theme.SPACE_3
            )):
                if app_state.scraping_status != "idle":
                    with me.box(style=create_card_style("md")):
                        status_card("Scraping", app_state.scraping_status, app_state.scraping_progress, "web")

                if app_state.download_status != "idle":
                    with me.box(style=create_card_style("md")):
                        status_card("Download", app_state.download_status, app_state.download_progress, "download", app_state.last_update)

def dashboard_content():
    """Dashboard tab content with modern design"""
    
    # Show welcome screen if no files are available
    if not app_state.available_files:
        return welcome_screen()
    
    # Status overview cards
    with me.box(
        style=me.Style(
            display="grid",
            grid_template_columns="repeat(auto-fit, minmax(300px, 1fr))",
            gap=Theme.SPACE_4,
            margin=me.Margin(bottom=Theme.SPACE_5)
        )
    ):
        # Scraping status card
        with me.box(style=create_card_style("md")):
            status_card("Scraping", app_state.scraping_status, app_state.scraping_progress, "web")

        # Download status card
        with me.box(style=create_card_style("md")):
            status_card("Download", app_state.download_status, app_state.download_progress, "download", app_state.last_update)

        # Files overview card
        with me.box(style=create_card_style("md")):
            files_overview_card()

    with me.box(style=me.Style(
        display="grid",
        grid_template_columns="repeat(auto-fit, minmax(320px, 1fr))",
        gap=Theme.SPACE_4,
        margin=me.Margin(bottom=Theme.SPACE_5)
    )):
        download_insights_card()
        recent_download_activity_card()

    # Help section
    with me.box(style=create_card_style("md", Theme.SPACE_4)):
        me.text("How to Use", style=me.Style(
            font_size=Theme.FONT_SIZE_H4,
            font_weight=Theme.FONT_WEIGHT_BOLD,
            margin=me.Margin(bottom=Theme.SPACE_3),
            color=Theme.ON_SURFACE
        ))

        with me.box(style=me.Style(display="flex", flex_direction="column", gap=Theme.SPACE_3)):
            # Step 1
            with me.box(style=me.Style(display="flex", align_items="flex-start", gap=Theme.SPACE_3)):
                with me.box(style=me.Style(
                    width=32, height=32, background=Theme.PRIMARY, border_radius="50%",
                    display="flex", align_items="center", justify_content="center", color="white",
                    font_weight=Theme.FONT_WEIGHT_BOLD, font_size=Theme.FONT_SIZE_H6
                )):
                    me.text("1", style=me.Style(color="white"))
                with me.box(style=me.Style(flex_grow=1)):
                    me.text("Start Scraping (Optional)", style=me.Style(
                        font_size=Theme.FONT_SIZE_H6, font_weight=Theme.FONT_WEIGHT_MEDIUM,
                        color=Theme.ON_SURFACE, margin=me.Margin(bottom=Theme.SPACE_1)
                    ))
                    me.text("Collect specification data from 3GPP website. Skip this step if you already have links.json or latest.json files from a previous run.", style=me.Style(
                        font_size=Theme.FONT_SIZE_BODY, color=Theme.ON_SURFACE_VARIANT, line_height=1.4
                    ))

            # Step 2
            with me.box(style=me.Style(display="flex", align_items="flex-start", gap=Theme.SPACE_3)):
                with me.box(style=me.Style(
                    width=32, height=32, background=Theme.SECONDARY, border_radius="50%",
                    display="flex", align_items="center", justify_content="center", color="white",
                    font_weight=Theme.FONT_WEIGHT_BOLD, font_size=Theme.FONT_SIZE_H6
                )):
                    me.text("2", style=me.Style(color="white"))
                with me.box(style=me.Style(flex_grow=1)):
                    me.text("Filter Versions (Optional)", style=me.Style(
                        font_size=Theme.FONT_SIZE_H6, font_weight=Theme.FONT_WEIGHT_MEDIUM,
                        color=Theme.ON_SURFACE, margin=me.Margin(bottom=Theme.SPACE_1)
                    ))
                    me.text("Reduce download size by keeping only the latest version of each specification. Requires links.json from scraping.", style=me.Style(
                        font_size=Theme.FONT_SIZE_BODY, color=Theme.ON_SURFACE_VARIANT, line_height=1.4
                    ))

            # Step 3
            with me.box(style=me.Style(display="flex", align_items="flex-start", gap=Theme.SPACE_3)):
                with me.box(style=me.Style(
                    width=32, height=32, background=Theme.ACCENT, border_radius="50%",
                    display="flex", align_items="center", justify_content="center", color="white",
                    font_weight=Theme.FONT_WEIGHT_BOLD, font_size=Theme.FONT_SIZE_H6
                )):
                    me.text("3", style=me.Style(color="white"))
                with me.box(style=me.Style(flex_grow=1)):
                    me.text("Select & Download", style=me.Style(
                        font_size=Theme.FONT_SIZE_H6, font_weight=Theme.FONT_WEIGHT_MEDIUM,
                        color=Theme.ON_SURFACE, margin=me.Margin(bottom=Theme.SPACE_1)
                    ))
                    me.text("Choose specifications from the list below, then download. Works with any available JSON file (latest.json preferred).", style=me.Style(
                        font_size=Theme.FONT_SIZE_BODY, color=Theme.ON_SURFACE_VARIANT, line_height=1.4
                    ))

    # Quick actions
    with me.box(style=create_card_style("md", Theme.SPACE_4)):
        me.text("Quick Actions", style=me.Style(
            font_size=Theme.FONT_SIZE_H4,
            font_weight=Theme.FONT_WEIGHT_BOLD,
            margin=me.Margin(bottom=Theme.SPACE_3),
            color=Theme.ON_SURFACE
        ))

        # Help text for color coding
        with me.box(style=me.Style(
            background=Theme.SURFACE_VARIANT,
            padding=me.Padding.all(Theme.SPACE_3),
            border_radius=Theme.RADIUS_MD,
            margin=me.Margin(bottom=Theme.SPACE_4),
            border=me.Border.all(me.BorderSide(width=1, color=Theme.OUTLINE_VARIANT))
        )):
            me.text("Workflow Status:", style=me.Style(
                font_size=Theme.FONT_SIZE_H6,
                font_weight=Theme.FONT_WEIGHT_BOLD,
                color=Theme.ON_SURFACE,
                margin=me.Margin(bottom=Theme.SPACE_2)
            ))
            
            # Show current file status
            files_status = []
            if Path('downloads/latest.json').exists():
                files_status.append("✅ Filtered versions available (latest.json)")
            if Path('downloads/links.json').exists():
                files_status.append("✅ All versions available (links.json)")
            
            if files_status:
                me.text("Files ready for download:", style=me.Style(
                    font_size=Theme.FONT_SIZE_CAPTION,
                    color=Theme.SUCCESS,
                    margin=me.Margin(bottom=Theme.SPACE_1)
                ))
                for status in files_status:
                    me.text(f"• {status}", style=me.Style(
                        font_size=Theme.FONT_SIZE_CAPTION,
                        color=Theme.ON_SURFACE_VARIANT
                    ))
                
                # Show which files are currently displayed
                current_display = {
                    "none": "No files loaded",
                    "filtered": "Filtered versions (latest.json)",
                    "all": "All versions (links.json)"
                }.get(app_state.current_file_type, "Unknown")
                
                me.text("", style=me.Style(margin=me.Margin(bottom=Theme.SPACE_1)))
                me.text(f"📋 Currently displaying: {current_display}", style=me.Style(
                    font_size=Theme.FONT_SIZE_CAPTION,
                    color=Theme.PRIMARY,
                    font_weight=Theme.FONT_WEIGHT_MEDIUM
                ))
            else:
                me.text("No files available - start scraping first", style=me.Style(
                    font_size=Theme.FONT_SIZE_CAPTION,
                    color=Theme.WARNING
                ))
            
            me.text("", style=me.Style(margin=me.Margin(bottom=Theme.SPACE_2)))
            
            me.text("Color Guide:", style=me.Style(
                font_size=Theme.FONT_SIZE_H6,
                font_weight=Theme.FONT_WEIGHT_BOLD,
                color=Theme.ON_SURFACE,
                margin=me.Margin(bottom=Theme.SPACE_2)
            ))
            with me.box(style=me.Style(display="flex", flex_direction="column", gap=Theme.SPACE_1)):
                with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2)):
                    me.box(style=me.Style(width=16, height=16, background=Theme.PRIMARY, border_radius=Theme.RADIUS_SM))
                    me.text("Blue: Data Collection (Start Scraping)", style=me.Style(font_size=Theme.FONT_SIZE_CAPTION, color=Theme.ON_SURFACE_VARIANT))
                with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2)):
                    me.box(style=me.Style(width=16, height=16, background=Theme.SECONDARY, border_radius=Theme.RADIUS_SM))
                    me.text("Red: Data Processing (Filter Versions)", style=me.Style(font_size=Theme.FONT_SIZE_CAPTION, color=Theme.ON_SURFACE_VARIANT))
                with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2)):
                    me.box(style=me.Style(width=16, height=16, background=Theme.ACCENT, border_radius=Theme.RADIUS_SM))
                    me.text("Orange: File Operations (Start Download)", style=me.Style(font_size=Theme.FONT_SIZE_CAPTION, color=Theme.ON_SURFACE_VARIANT))

        with me.box(style=me.Style(display="flex", gap=Theme.SPACE_3, flex_wrap="wrap")):
            # Workflow status indicator
            workflow_status()
            
            action_buttons()

    # File selection section
    if app_state.available_files:
        with me.box(style=create_card_style("md", Theme.SPACE_4)):
            me.text("Select Files to Download", style=me.Style(
                font_size=Theme.FONT_SIZE_H4,
                font_weight=Theme.FONT_WEIGHT_BOLD,
                margin=me.Margin(bottom=Theme.SPACE_3),
                color=Theme.ON_SURFACE
            ))

    # File selection section
    if app_state.available_files:
        with me.box(style=create_card_style("md", Theme.SPACE_4)):
            me.text("Select Files to Download", style=me.Style(
                font_size=Theme.FONT_SIZE_H4,
                font_weight=Theme.FONT_WEIGHT_BOLD,
                margin=me.Margin(bottom=Theme.SPACE_3),
                color=Theme.ON_SURFACE
            ))

            filtered_files = get_filtered_files()
            selected_count = len(app_state.selected_files)

            with me.box(style=me.Style(
                display="flex",
                justify_content="space-between",
                align_items="center",
                flex_wrap="wrap",
                gap=Theme.SPACE_3,
                margin=me.Margin(bottom=Theme.SPACE_3)
            )):
                me.text(
                    f"Selected {selected_count} of {len(filtered_files)} visible file{'s' if len(filtered_files) != 1 else ''}",
                    style=me.Style(font_size=Theme.FONT_SIZE_BODY, color=Theme.ON_SURFACE_VARIANT)
                )

                download_button_style = create_button_style("accent", "md")
                disable_download = app_state.download_status == "running" or selected_count == 0
                if disable_download:
                    download_button_style.opacity = 0.6
                    download_button_style.cursor = "not-allowed"

                me.button(
                    "⬇️ Start Download",
                    on_click=start_download,
                    disabled=int(disable_download),
                    style=download_button_style
                )
                if disable_download:
                    me.text(
                        "Select at least one specification to enable downloads.",
                        style=me.Style(font_size=Theme.FONT_SIZE_CAPTION, color=Theme.ON_SURFACE_VARIANT)
                    )

            # Smart selection controls
            with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_3, margin=me.Margin(bottom=Theme.SPACE_3), flex_wrap="wrap")):
                # Search box
                with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2)):
                    me.icon("search", style=me.Style(color=Theme.ON_SURFACE_VARIANT, font_size=20))
                    me.input(
                        label="Search files...",
                        value=app_state.search_query,
                        on_blur=on_search_change,
                        style=me.Style(width="200px")
                    )
                
                # Quick filters
                me.button(
                    "Select All",
                    on_click=select_all_files,
                    style=create_button_style("outline", "sm")
                )
                me.button(
                    "Select None", 
                    on_click=deselect_all_files,
                    style=create_button_style("outline", "sm")
                )
                
                # Series/Release filters
                with me.box(style=me.Style(display="flex", gap=Theme.SPACE_2)):
                    me.text("Filter:", style=me.Style(font_size=Theme.FONT_SIZE_CAPTION, color=Theme.ON_SURFACE_VARIANT))
                    me.select(
                        label="Series",
                        options=[{"label": opt, "value": opt} for opt in ["All"] + sorted(list(set(f.get('series', '') for f in app_state.available_files if f.get('series'))))],
                        value=app_state.series_filter,
                        on_selection_change=on_series_filter_change,
                        style=me.Style(width="120px")
                    )
                    me.select(
                        label="Release", 
                        options=[{"label": str(opt), "value": str(opt)} for opt in ["All"] + sorted(list(set(f.get('release', '') for f in app_state.available_files if f.get('release'))))],
                        value=app_state.release_filter,
                        on_selection_change=on_release_filter_change,
                        style=me.Style(width="120px")
                    )

            # Filtered results summary
            me.text(f"Showing {len(filtered_files)} of {len(app_state.available_files)} files", style=me.Style(
                font_size=Theme.FONT_SIZE_BODY,
                color=Theme.ON_SURFACE_VARIANT,
                margin=me.Margin(bottom=Theme.SPACE_2)
            ))

            # File list with smart display
            with me.box(style=me.Style(
                max_height="400px",
                overflow_y="auto",
                border=me.Border.all(me.BorderSide(width=1, color=Theme.OUTLINE_VARIANT)),
                border_radius=Theme.RADIUS_MD
            )):
                if not filtered_files:
                    with me.box(style=me.Style(
                        padding=me.Padding.all(Theme.SPACE_4),
                        text_align="center",
                        color=Theme.ON_SURFACE_VARIANT
                    )):
                        me.icon("search_off", style=me.Style(font_size=48, margin=me.Margin(bottom=Theme.SPACE_2)))
                        me.text("No files match your search criteria", style=me.Style(font_size=Theme.FONT_SIZE_H6))
                else:
                    for i, file_info in enumerate(filtered_files[:50]):  # Limit display to first 50 for performance
                        file_url = file_info.get('url', '')
                        file_name = file_info.get('name', file_url.split('/')[-1] if file_url else f'File {i+1}')
                        series = file_info.get('series', 'Unknown')
                        release = file_info.get('release', 'Unknown')
                        is_selected = file_url in app_state.selected_files
                        
                        with me.box(style=me.Style(
                            padding=me.Padding.all(Theme.SPACE_2),
                            border=me.Border(bottom=me.BorderSide(width=1, color=Theme.OUTLINE_VARIANT)) if i < len(filtered_files) - 1 and i < 49 else None,
                            background=Theme.SURFACE_VARIANT if i % 2 == 0 else Theme.SURFACE,
                            display="flex",
                            align_items="center",
                            gap=Theme.SPACE_2
                        )):
                            me.checkbox(
                                label="",
                                checked=int(is_selected),
                                on_change=on_file_selection_change,
                                key=f"file_{file_url}"
                            )
                            with me.box(style=me.Style(flex_grow=1, min_width=0)):
                                me.text(file_name, style=me.Style(
                                    font_size=Theme.FONT_SIZE_BODY,
                                    color=Theme.ON_SURFACE,
                                    font_weight=Theme.FONT_WEIGHT_MEDIUM if is_selected else Theme.FONT_WEIGHT_REGULAR,
                                    word_wrap="break-word"
                                ))
                                with me.box(style=me.Style(display="flex", gap=Theme.SPACE_3, margin=me.Margin(top=Theme.SPACE_1))):
                                    me.text(f"Series {series}", style=me.Style(
                                        font_size=Theme.FONT_SIZE_CAPTION,
                                        color=Theme.PRIMARY,
                                        background=Theme.PRIMARY_LIGHT,
                                        padding=me.Padding.symmetric(horizontal=Theme.SPACE_2, vertical=2),
                                        border_radius=Theme.RADIUS_SM
                                    ))
                                    me.text(f"Rel-{release}", style=me.Style(
                                        font_size=Theme.FONT_SIZE_CAPTION,
                                        color=Theme.SECONDARY,
                                        background=Theme.SECONDARY_LIGHT,
                                        padding=me.Padding.symmetric(horizontal=Theme.SPACE_2, vertical=2),
                                        border_radius=Theme.RADIUS_SM
                                    ))
                    
                    if len(filtered_files) > 50:
                        me.text(f"... and {len(filtered_files) - 50} more files", style=me.Style(
                            font_size=Theme.FONT_SIZE_CAPTION,
                            color=Theme.ON_SURFACE_VARIANT,
                            text_align="center",
                            padding=me.Padding.all(Theme.SPACE_2)
                        ))

    # Current operation
    if app_state.current_operation:
        with me.box(style=create_card_style("sm", Theme.SPACE_3)):
            with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2)):
                me.icon("info", style=me.Style(color=Theme.INFO, font_size=18))
                me.text(f"Current: {app_state.current_operation}", style=me.Style(
                    font_size=Theme.FONT_SIZE_BODY,
                    color=Theme.ON_SURFACE_VARIANT,
                    font_style="italic"
                ))

def status_card(title: str, status: str, progress: float, icon: str, update_timestamp: float = 0):
    """Modern status card component"""
    with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_3)):
        me.icon(icon, style=me.Style(
            color=get_status_color(status),
            font_size=24
        ))

        with me.box(style=me.Style(flex_grow=1)):
            me.text(title, style=me.Style(
                font_size=Theme.FONT_SIZE_H5,
                font_weight=Theme.FONT_WEIGHT_MEDIUM,
                color=Theme.ON_SURFACE,
                margin=me.Margin(bottom=Theme.SPACE_1)
            ))

            # Status chip
            with me.box(style=create_status_chip(status, get_status_label(status))):
                me.icon(get_status_icon(status), style=me.Style(font_size=14))
                me.text(get_status_label(status), style=me.Style(font_size=Theme.FONT_SIZE_CAPTION))

            # Enhanced progress display
            if status == "running":
                with me.box(style=me.Style(width="100%", margin=me.Margin(top=Theme.SPACE_2))):
                    # Show actual progress if available, otherwise indeterminate
                    if progress > 0:
                        # Determinate progress bar
                        with me.box(style=me.Style(
                            height=8,
                            background=Theme.SURFACE_VARIANT,
                            border_radius=Theme.RADIUS_MD,
                            overflow="hidden"
                        )):
                            me.box(style=me.Style(
                                height="100%",
                                width=f"{progress}%",
                                background=get_status_color(status),
                                border_radius=Theme.RADIUS_MD
                            ))
                    else:
                        # Indeterminate progress bar for running downloads
                        with me.box(style=me.Style(
                            height=8,
                            background=Theme.SURFACE_VARIANT,
                            border_radius=Theme.RADIUS_MD,
                            overflow="hidden",
                            position="relative"
                        )):
                            # Animated indeterminate progress
                            me.box(style=me.Style(
                                height="100%",
                                width="30%",
                                background=get_status_color(status),
                                position="absolute",
                                left="-30%"
                            ), classes="progress-indeterminate")
                    
                    # Progress details
                    with me.box(style=me.Style(
                        display="flex",
                        justify_content="space-between",
                        align_items="center",
                        margin=me.Margin(top=Theme.SPACE_1)
                    )):
                        primary_status_text = (
                            f"{progress:.0f}% complete" if progress > 0 else f"{title} in progress..."
                        )
                        me.text(primary_status_text, style=me.Style(
                            font_size=Theme.FONT_SIZE_CAPTION,
                            color=Theme.ON_SURFACE_VARIANT
                        ))
                        if app_state.current_operation:
                            me.text(app_state.current_operation, style=me.Style(
                                font_size=Theme.FONT_SIZE_CAPTION,
                                color=Theme.ON_SURFACE_VARIANT,
                                font_style="italic"
                            ))
            elif status == "completed":
                # Completion confirmation
                with me.box(style=me.Style(
                    display="flex",
                    align_items="center",
                    gap=Theme.SPACE_2,
                    margin=me.Margin(top=Theme.SPACE_2),
                    padding=me.Padding.all(Theme.SPACE_2),
                    background=Theme.SUCCESS + "10",
                    border_radius=Theme.RADIUS_MD,
                    border=me.Border.all(me.BorderSide(width=1, color=Theme.SUCCESS + "40"))
                )):
                    me.icon("check_circle", style=me.Style(color=Theme.SUCCESS, font_size=16))
                    me.text("Operation completed successfully", style=me.Style(
                        font_size=Theme.FONT_SIZE_CAPTION,
                        color=Theme.SUCCESS,
                        font_weight=Theme.FONT_WEIGHT_MEDIUM
                    ))
            elif status == "error":
                # Error display
                with me.box(style=me.Style(
                    display="flex",
                    align_items="center",
                    gap=Theme.SPACE_2,
                    margin=me.Margin(top=Theme.SPACE_2),
                    padding=me.Padding.all(Theme.SPACE_2),
                    background=Theme.ERROR + "10",
                    border_radius=Theme.RADIUS_MD,
                    border=me.Border.all(me.BorderSide(width=1, color=Theme.ERROR + "40"))
                )):
                    me.icon("error", style=me.Style(color=Theme.ERROR, font_size=16))
                    me.text("Operation failed - check logs for details", style=me.Style(
                        font_size=Theme.FONT_SIZE_CAPTION,
                        color=Theme.ERROR,
                        font_weight=Theme.FONT_WEIGHT_MEDIUM
                    ))

def files_overview_card():
    """Files overview card"""
    with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_3)):
        me.icon("folder", style=me.Style(
            color=Theme.SECONDARY,
            font_size=24
        ))

        with me.box(style=me.Style(flex_grow=1)):
            me.text("Available Files", style=me.Style(
                font_size=Theme.FONT_SIZE_H5,
                font_weight=Theme.FONT_WEIGHT_MEDIUM,
                color=Theme.ON_SURFACE,
                margin=me.Margin(bottom=Theme.SPACE_1)
            ))

            total_files = len(app_state.available_files)
            selected_files = len(app_state.selected_files)

            with me.box(style=me.Style(display="flex", gap=Theme.SPACE_3)):
                me.text(f"Total: {total_files}", style=me.Style(
                    font_size=Theme.FONT_SIZE_BODY,
                    color=Theme.ON_SURFACE_VARIANT
                ))
                me.text(f"Selected: {selected_files}", style=me.Style(
                    font_size=Theme.FONT_SIZE_BODY,
                    color=Theme.PRIMARY,
                    font_weight=Theme.FONT_WEIGHT_MEDIUM
                ))

def download_insights_card():
    """Show live download statistics with a modern hero card"""
    total_selected = len(app_state.selected_files)
    completed = len(app_state.completed_downloads)
    failed = len(app_state.failed_downloads)
    remaining = max(total_selected - completed - failed, 0)
    running = app_state.download_status == "running"

    with me.box(style=create_gradient_card_style(Theme.PRIMARY, Theme.PRIMARY_DARK)):
        me.text("Live Download Insights", style=me.Style(
            font_size=Theme.FONT_SIZE_H4,
            font_weight=Theme.FONT_WEIGHT_BOLD,
            color="white",
            margin=me.Margin(bottom=Theme.SPACE_3)
        ))

        with me.box(style=me.Style(
            display="grid",
            grid_template_columns="repeat(auto-fit, minmax(120px, 1fr))",
            gap=Theme.SPACE_3,
            margin=me.Margin(bottom=Theme.SPACE_3)
        )):
            metric_items = [
                ("Selected", total_selected, "playlist_add_check", "rgba(255,255,255,0.18)"),
                ("Completed", completed, "check_circle", "rgba(46,204,113,0.25)"),
                ("Errors", failed, "error", "rgba(231,76,60,0.25)"),
                ("Remaining", remaining if running else max(total_selected - completed, 0), "hourglass_empty", "rgba(255,255,255,0.18)")
            ]
            for label, value, icon_name, background in metric_items:
                with me.box(style=me.Style(
                    background=background,
                    border_radius=Theme.RADIUS_MD,
                    padding=me.Padding.all(Theme.SPACE_3),
                    display="flex",
                    flex_direction="column",
                    gap=Theme.SPACE_1
                )):
                    me.icon(icon_name, style=me.Style(color="white", font_size=20))
                    me.text(str(value), style=me.Style(
                        font_size=Theme.FONT_SIZE_H3,
                        font_weight=Theme.FONT_WEIGHT_BOLD,
                        color="white"
                    ))
                    me.text(label, style=me.Style(
                        font_size=Theme.FONT_SIZE_CAPTION,
                        text_transform="uppercase",
                        letter_spacing="0.08em",
                        color="rgba(255,255,255,0.85)"
                    ))

        detail_lines = []
        if running and app_state.current_download_item:
            detail_lines.append(f"Now downloading: {app_state.current_download_item}")
        if completed:
            detail_lines.append(f"Last completed: {app_state.completed_downloads[-1]}")
        if failed:
            detail_lines.append(f"Issues detected: {failed} file{'s' if failed != 1 else ''}")
        if not detail_lines:
            detail_lines.append("No downloads in progress yet")

        with me.box(style=me.Style(display="flex", flex_direction="column", gap=Theme.SPACE_1)):
            for line in detail_lines[:3]:
                me.text(line, style=me.Style(
                    font_size=Theme.FONT_SIZE_BODY,
                    color="rgba(255,255,255,0.85)"
                ))

def recent_download_activity_card():
    """Timeline of recent download activity"""
    events = list(app_state.recent_download_events)[-6:]
    events = list(reversed(events))

    status_styles = {
        "Queued": (Theme.INFO, "schedule"),
        "Completed": (Theme.SUCCESS, "check_circle"),
        "Failed": (Theme.ERROR, "error"),
        "All Files": (Theme.PRIMARY, "inventory"),
        "Issues Detected": (Theme.WARNING, "report_problem"),
    }

    with me.box(style=create_card_style("md", Theme.SPACE_4)):
        me.text("Recent Activity", style=me.Style(
            font_size=Theme.FONT_SIZE_H4,
            font_weight=Theme.FONT_WEIGHT_BOLD,
            color=Theme.ON_SURFACE,
            margin=me.Margin(bottom=Theme.SPACE_3)
        ))

        if not events:
            me.text("No download activity yet", style=me.Style(
                font_size=Theme.FONT_SIZE_BODY,
                color=Theme.ON_SURFACE_VARIANT,
                font_style="italic"
            ))
            return

        for event in events:
            status_color, status_icon = status_styles.get(event["status"], (Theme.PRIMARY, "info"))
            with me.box(style=me.Style(
                display="flex",
                align_items="flex-start",
                gap=Theme.SPACE_3,
                padding=me.Padding.symmetric(vertical=Theme.SPACE_2)
            )):
                with me.box(style=me.Style(
                    width=36,
                    height=36,
                    border_radius="50%",
                    background=status_color + "1A",
                    display="flex",
                    align_items="center",
                    justify_content="center"
                )):
                    me.icon(status_icon, style=me.Style(color=status_color, font_size=18))

                with me.box(style=me.Style(flex_grow=1)):
                    me.text(event["description"], style=me.Style(
                        font_size=Theme.FONT_SIZE_BODY,
                        color=Theme.ON_SURFACE,
                        font_weight=Theme.FONT_WEIGHT_MEDIUM
                    ))
                    me.text(event["filename"], style=me.Style(
                        font_size=Theme.FONT_SIZE_CAPTION,
                        color=Theme.ON_SURFACE_VARIANT
                    ))
                    me.text(event["timestamp"], style=me.Style(
                        font_size=Theme.FONT_SIZE_CAPTION,
                        color=Theme.OUTLINE
                    ))

def workflow_status():
    """Display current workflow status and next steps"""
    has_files = len(app_state.available_files) > 0
    has_selections = len(app_state.selected_files) > 0
    is_busy = app_state.scraping_status == "running" or app_state.download_status == "running"
    
    # Determine current step
    if is_busy:
        current_step = "Working..."
        next_step = "Please wait for current operation to complete"
        status_color = Theme.INFO
        status_icon = "sync"
    elif not has_files:
        current_step = "No files loaded"
        next_step = "Load existing files or start scraping"
        status_color = Theme.WARNING
        status_icon = "folder_open"
    elif app_state.current_file_type == "all" and not has_selections:
        current_step = "Files loaded (all versions)"
        next_step = "Filter to latest versions or select specific files"
        status_color = Theme.PRIMARY
        status_icon = "list"
    elif has_selections:
        current_step = f"{len(app_state.selected_files)} file{'s' if len(app_state.selected_files) != 1 else ''} selected"
        next_step = "Ready to download"
        status_color = Theme.SUCCESS
        status_icon = "check_circle"
    else:
        current_step = "Files available"
        next_step = "Select files to download"
        status_color = Theme.SECONDARY
        status_icon = "checklist"
    
    with me.box(style=me.Style(
        display="flex",
        align_items="center",
        gap=Theme.SPACE_2,
        padding=me.Padding.all(Theme.SPACE_3),
        background=Theme.SURFACE_VARIANT,
        border_radius=Theme.RADIUS_MD,
        border=me.Border.all(me.BorderSide(width=1, color=status_color + "40")),
        min_width="250px"
    )):
        me.icon(status_icon, style=me.Style(color=status_color, font_size=20))
        with me.box(style=me.Style(flex_grow=1)):
            me.text(current_step, style=me.Style(
                font_size=Theme.FONT_SIZE_BODY,
                font_weight=Theme.FONT_WEIGHT_MEDIUM,
                color=Theme.ON_SURFACE
            ))
            me.text(next_step, style=me.Style(
                font_size=Theme.FONT_SIZE_CAPTION,
                color=Theme.ON_SURFACE_VARIANT
            ))

def action_buttons():
    """Smart action buttons with workflow guidance"""
    # Determine current workflow state
    has_files = len(app_state.available_files) > 0
    has_filtered_files = len(get_filtered_files()) > 0
    has_selections = len(app_state.selected_files) > 0
    is_busy = app_state.scraping_status == "running" or app_state.download_status == "running"
    
    # Define actions based on current state
    actions = []
    
    if not has_files:
        # No files loaded - guide user to get files first
        actions = [
            ("Load Files", "folder_open", "primary", load_available_files, is_busy,
             "Load existing file lists (latest.json or links.json)"),
            ("Start Scraping", "web", "secondary", start_scraping, is_busy,
             "Scrape 3GPP website to discover available specifications"),
        ]
    elif app_state.current_file_type == "all" and not has_selections:
        # Has all files but nothing selected - guide to filtering
        actions = [
            ("Filter Latest", "filter_list", "primary", filter_versions, is_busy,
             "Show only latest versions (recommended for most users)"),
            ("Select Files", "checklist", "secondary", None, False,
             "Use search and filters above to select specific files"),
        ]
    elif has_filtered_files and not has_selections:
        # Has filtered files but nothing selected - guide to selection
        actions = [
            ("Select All", "check_box", "primary", select_all_files, is_busy,
             f"Select all {len(get_filtered_files())} displayed files"),
            ("Start Download", "download", "accent", start_download, is_busy or not has_selections,
             "Download selected files (select files first)"),
        ]
    elif has_selections:
        # Has selections - ready to download
        actions = [
            ("Start Download", "download", "primary", start_download, is_busy,
             f"Download {len(app_state.selected_files)} selected file{'s' if len(app_state.selected_files) != 1 else ''}"),
            ("Clear Selection", "clear_all", "outline", deselect_all_files, is_busy,
             "Deselect all files to start over"),
        ]
    else:
        # Fallback - general actions
        actions = [
            ("Load Files", "folder_open", "primary", load_available_files, is_busy,
             "Load existing file lists"),
            ("Start Scraping", "web", "secondary", start_scraping, is_busy,
             "Scrape for new specifications"),
        ]

    for label, icon, variant, callback, disabled, description in actions:
        with me.box(style=me.Style(display="flex", flex_direction="column", align_items="center", gap=Theme.SPACE_2, min_width="140px")):
            base_style = create_button_style(variant, "md")
            base_style.opacity = 0.6 if disabled else 1
            base_style.cursor = "not-allowed" if disabled else "pointer"
            
            # Special handling for buttons without callbacks (informational)
            if callback:
                me.button(
                    label,
                    on_click=callback,
                    disabled=int(disabled),
                    style=base_style
                )
            else:
                # Render as styled box for informational buttons
                info_style = create_button_style(variant, "md")
                info_style.opacity = base_style.opacity
                info_style.cursor = "default"
                info_style.display = "flex"
                info_style.align_items = "center"
                info_style.justify_content = "center"
                info_style.padding = me.Padding.symmetric(horizontal=Theme.SPACE_3, vertical=Theme.SPACE_2)
                info_style.border_radius = Theme.RADIUS_MD

                with me.box(style=info_style):
                    me.text(label, style=me.Style(
                        font_size=getattr(base_style, "font_size", Theme.FONT_SIZE_BODY),
                        font_weight=Theme.FONT_WEIGHT_MEDIUM,
                        color=Theme.ON_PRIMARY if variant == "primary" else Theme.ON_SURFACE
                    ))
            
            me.text(description, style=me.Style(
                font_size=Theme.FONT_SIZE_CAPTION,
                color=Theme.ON_SURFACE_VARIANT,
                text_align="center",
                line_height=1.3,
                max_width="140px"
            ))

def get_status_color(status: str) -> str:
    """Get color for status"""
    status_colors = {
        "idle": Theme.OUTLINE,
        "running": Theme.INFO,
        "completed": Theme.SUCCESS,
        "error": Theme.ERROR
    }
    return status_colors.get(status, Theme.OUTLINE)

def get_status_label(status: str) -> str:
    """Get human-readable status label"""
    status_labels = {
        "idle": "Idle",
        "running": "Running",
        "completed": "Completed",
        "error": "Error"
    }
    return status_labels.get(status, status.title())

def get_status_icon(status: str) -> str:
    """Get icon for status"""
    status_icons = {
        "idle": "radio_button_unchecked",
        "running": "sync",
        "completed": "check_circle",
        "error": "error"
    }
    return status_icons.get(status, "help")

def settings_content():
    """Settings tab content with organized configuration options"""
    with me.box(style=create_card_style("md")):
        me.text("Settings", style=me.Style(
            font_size=Theme.FONT_SIZE_H3,
            font_weight=Theme.FONT_WEIGHT_BOLD,
            margin=me.Margin(bottom=Theme.SPACE_4),
            color=Theme.ON_SURFACE
        ))

        # Basic Settings Section
        with me.box(style=create_card_style("sm", Theme.SPACE_3)):
            with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2, margin=me.Margin(bottom=Theme.SPACE_3))):
                me.icon("settings", style=me.Style(color=Theme.PRIMARY, font_size=20))
                me.text("Basic Settings", style=me.Style(
                    font_size=Theme.FONT_SIZE_H5,
                    font_weight=Theme.FONT_WEIGHT_MEDIUM,
                    color=Theme.ON_SURFACE
                ))

            me.text("Configure the most common download options and preferences.", style=me.Style(
                font_size=Theme.FONT_SIZE_BODY,
                color=Theme.ON_SURFACE_VARIANT,
                margin=me.Margin(bottom=Theme.SPACE_3)
            ))

            with me.box(style=me.Style(display="flex", flex_direction="column", gap=Theme.SPACE_3)):
                # Download behavior
                with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2)):
                    me.checkbox(
                        label="Resume interrupted downloads",
                        checked=int(app_state.resume_downloads),
                        on_change=toggle_resume_downloads,
                        style=me.Style(color=Theme.ON_SURFACE)
                    )
                    with me.box(style=me.Style(cursor="help")):
                        me.icon("help_outline", style=me.Style(
                            color=Theme.ON_SURFACE_VARIANT,
                            font_size=16
                        ))

                # Organization
                with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2)):
                    me.checkbox(
                        label="Organize files by series",
                        checked=int(app_state.organize_by_series),
                        on_change=toggle_organize_by_series,
                        style=me.Style(color=Theme.ON_SURFACE)
                    )
                    with me.box(style=me.Style(cursor="help")):
                        me.icon("help_outline", style=me.Style(
                            color=Theme.ON_SURFACE_VARIANT,
                            font_size=16
                        ))

                # Performance
                with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_3)):
                    me.text("Download threads:", style=me.Style(
                        font_size=Theme.FONT_SIZE_BODY,
                        color=Theme.ON_SURFACE,
                        min_width="140px"
                    ))
                    me.input(
                        label="",
                        value=str(app_state.thread_count),
                        on_blur=on_thread_count_change,
                        style=me.Style(width="80px")
                    )
                    with me.box(style=me.Style(cursor="help")):
                        me.icon("help_outline", style=me.Style(
                            color=Theme.ON_SURFACE_VARIANT,
                            font_size=16
                        ))

        # Advanced Settings Toggle
        with me.box(style=me.Style(
            margin=me.Margin(top=Theme.SPACE_4),
            padding=me.Padding.all(Theme.SPACE_3),
            background=Theme.SECONDARY + "08",
            border_radius=Theme.RADIUS_MD,
            border=me.Border.all(me.BorderSide(width=1, color=Theme.SECONDARY + "20"))
        )):
            with me.box(style=me.Style(display="flex", align_items="center", justify_content="space-between")):
                with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2)):
                    me.icon("expand_more" if app_state.show_advanced_settings else "expand_less", 
                           style=me.Style(color=Theme.SECONDARY, font_size=20))
                    me.text("Advanced Settings", style=me.Style(
                        font_size=Theme.FONT_SIZE_H5,
                        font_weight=Theme.FONT_WEIGHT_MEDIUM,
                        color=Theme.ON_SURFACE
                    ))
                me.checkbox(
                    label="",
                    checked=int(app_state.show_advanced_settings),
                    on_change=toggle_advanced_settings,
                    style=me.Style(color=Theme.SECONDARY)
                )

            me.text("Fine-tune connection settings, timeouts, and logging for advanced users.", style=me.Style(
                font_size=Theme.FONT_SIZE_BODY,
                color=Theme.ON_SURFACE_VARIANT,
                margin=me.Margin(top=Theme.SPACE_1)
            ))

        # Advanced Settings Panel
        if app_state.show_advanced_settings:
            with me.box(style=me.Style(
                margin=me.Margin(top=Theme.SPACE_3),
                padding=me.Padding.all(Theme.SPACE_3),
                background=Theme.SURFACE_VARIANT,
                border_radius=Theme.RADIUS_MD,
                border=me.Border.all(me.BorderSide(width=1, color=Theme.OUTLINE_VARIANT))
            )):
                # Download Options
                me.text("Download Behavior", style=me.Style(
                    font_size=Theme.FONT_SIZE_H6,
                    font_weight=Theme.FONT_WEIGHT_MEDIUM,
                    margin=me.Margin(bottom=Theme.SPACE_2),
                    color=Theme.ON_SURFACE
                ))

                with me.box(style=me.Style(display="flex", flex_direction="column", gap=Theme.SPACE_2, margin=me.Margin(bottom=Theme.SPACE_4))):
                    with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2)):
                        me.checkbox(
                            label="Download all versions of each specification",
                            checked=int(app_state.download_all_versions),
                            on_change=toggle_download_all_versions,
                            style=me.Style(color=Theme.ON_SURFACE)
                        )
                        me.icon("help_outline", style=me.Style(
                            color=Theme.ON_SURFACE_VARIANT,
                            font_size=16
                        ))

                # Connection Settings
                me.text("Connection Settings", style=me.Style(
                    font_size=Theme.FONT_SIZE_H6,
                    font_weight=Theme.FONT_WEIGHT_MEDIUM,
                    margin=me.Margin(bottom=Theme.SPACE_2),
                    color=Theme.ON_SURFACE
                ))

                with me.box(style=me.Style(display="grid", grid_template_columns="1fr 1fr", gap=Theme.SPACE_3, margin=me.Margin(bottom=Theme.SPACE_4))):
                    # Max Connections
                    with me.box(style=me.Style(display="flex", flex_direction="column", gap=Theme.SPACE_1)):
                        me.text("Max Connections:", style=me.Style(
                            font_size=Theme.FONT_SIZE_CAPTION,
                            color=Theme.ON_SURFACE_VARIANT
                        ))
                        me.input(
                            label="",
                            value=str(app_state.http_max_connections),
                            on_blur=on_max_connections_change,
                            style=me.Style(width="100%")
                        )

                    # Max Connections Per Host
                    with me.box(style=me.Style(display="flex", flex_direction="column", gap=Theme.SPACE_1)):
                        me.text("Max Per Host:", style=me.Style(
                            font_size=Theme.FONT_SIZE_CAPTION,
                            color=Theme.ON_SURFACE_VARIANT
                        ))
                        me.input(
                            label="",
                            value=str(app_state.http_max_connections_per_host),
                            on_blur=on_max_connections_per_host_change,
                            style=me.Style(width="100%")
                        )

                    # Total Timeout
                    with me.box(style=me.Style(display="flex", flex_direction="column", gap=Theme.SPACE_1)):
                        me.text("Total Timeout (sec):", style=me.Style(
                            font_size=Theme.FONT_SIZE_CAPTION,
                            color=Theme.ON_SURFACE_VARIANT
                        ))
                        me.input(
                            label="",
                            value=str(app_state.http_total_timeout),
                            on_blur=on_total_timeout_change,
                            style=me.Style(width="100%")
                        )

                    # Connect Timeout
                    with me.box(style=me.Style(display="flex", flex_direction="column", gap=Theme.SPACE_1)):
                        me.text("Connect Timeout (sec):", style=me.Style(
                            font_size=Theme.FONT_SIZE_CAPTION,
                            color=Theme.ON_SURFACE_VARIANT
                        ))
                        me.input(
                            label="",
                            value=str(app_state.http_connect_timeout),
                            on_blur=on_connect_timeout_change,
                            style=me.Style(width="100%")
                        )

                # Logging Settings
                me.text("Logging", style=me.Style(
                    font_size=Theme.FONT_SIZE_H6,
                    font_weight=Theme.FONT_WEIGHT_MEDIUM,
                    margin=me.Margin(bottom=Theme.SPACE_2),
                    color=Theme.ON_SURFACE
                ))

                with me.box(style=me.Style(display="flex", flex_direction="column", gap=Theme.SPACE_2)):
                    with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2)):
                        me.checkbox(
                            label="Verbose logging",
                            checked=int(app_state.verbose_logging),
                            on_change=toggle_verbose_logging,
                            style=me.Style(color=Theme.ON_SURFACE)
                        )
                        me.icon("help_outline", style=me.Style(
                            color=Theme.ON_SURFACE_VARIANT,
                            font_size=16
                        ))

def logs_content():
    """Logs tab content"""
    with me.box(style=create_card_style("md")):
        me.text("Activity Logs", style=me.Style(
            font_size=Theme.FONT_SIZE_H3,
            font_weight=Theme.FONT_WEIGHT_BOLD,
            margin=me.Margin(bottom=Theme.SPACE_4),
            color=Theme.ON_SURFACE
        ))

        if app_state.log_messages:
            for log in app_state.log_messages[-10:]:  # Show last 10 messages
                with me.box(style=me.Style(
                    padding=me.Padding.all(Theme.SPACE_2),
                    background=Theme.SURFACE_VARIANT,
                    border_radius=Theme.RADIUS_MD,
                    margin=me.Margin(bottom=Theme.SPACE_1)
                )):
                    me.text(log, style=me.Style(
                        font_size=Theme.FONT_SIZE_CAPTION,
                        color=Theme.ON_SURFACE_VARIANT,
                        font_family="'Courier New', monospace"
                    ))
        else:
            me.text("No activity logs yet", style=me.Style(
                font_size=Theme.FONT_SIZE_BODY,
                color=Theme.ON_SURFACE_VARIANT,
                font_style="italic"
            ))

def status_indicator(status: str):
    """Display a status indicator"""
    color = {
        "idle": "#757575",
        "running": "#1976d2",
        "completed": "#388e3c",
        "error": "#d32f2f"
    }.get(status, "#757575")

    me.box(style=me.Style(width=12, height=12, background=color, border_radius=6))

def start_scraping(e: me.ClickEvent):
    """Start the scraping process"""
    if app_state.scraping_status == "running":
        return

    app_state.scraping_status = "running"
    app_state.scraping_progress = 0
    app_state.last_update = time.time()
    
    if app_state.resume_downloads:
        update_scraping_progress(30, "Resume mode: preparing cached files...")
    else:
        update_scraping_progress(12, "Starting scraper – discovering ETSI specifications (this may take time)...")

    def scraping_progress_pulse():
        """Keep scraping progress responsive during long operations"""
        local_progress = max(app_state.scraping_progress, 12)
        while app_state.scraping_status == "running":
            time.sleep(2.0)
            if app_state.scraping_status != "running":
                break
            # Ease progress toward 85% while the spider runs
            local_progress = min(85.0, max(local_progress + 3.0, app_state.scraping_progress))
            update_scraping_progress(local_progress)

    threading.Thread(target=scraping_progress_pulse, daemon=True).start()

    # Run scraping in background thread
    def run_scraping():
        try:
            success = scrape_data_with_config(
                resume=app_state.resume_downloads,
                no_download=app_state.no_download,
                all_versions=app_state.download_all_versions,
                organize_by_series=app_state.organize_by_series,
                specific_release=app_state.specific_release,
                threads=app_state.thread_count,
                verbose=app_state.verbose_logging
            )
            if success:
                if app_state.resume_downloads:
                    update_scraping_progress(88, "Resume check complete – refreshing cached files...")
                else:
                    update_scraping_progress(88, "Processing scraped results...")

                load_available_files()

                discovered = len(app_state.available_files)
                summary_message = (
                    f"Scraping completed successfully ({discovered} file{'s' if discovered != 1 else ''} discovered)"
                    if discovered
                    else "Scraping completed but no files were discovered"
                )
                update_scraping_progress(100, summary_message)
            else:
                app_state.scraping_status = "error"
                update_scraping_progress(app_state.scraping_progress, "Scraping failed")
        except Exception as ex:
            app_state.scraping_status = "error"
            update_scraping_progress(app_state.scraping_progress, f"Scraping error: {str(ex)}")
            show_error_notification(
                "Scraping Failed",
                str(ex),
                [
                    "Check your internet connection",
                    "Try reducing thread count in settings",
                    "Check the logs tab for more details",
                    "Try scraping again in a few minutes"
                ]
            )

    threading.Thread(target=run_scraping, daemon=True).start()

def filter_versions(e: me.ClickEvent):
    """Filter to latest versions (or skip if downloading all versions)"""
    if app_state.scraping_status == "running":
        return

    if app_state.download_all_versions:
        add_log_message("All versions mode: skipping filtering, using all available files")
        load_available_files()
        return

    add_log_message("Filtering to latest versions...")

    source_path = None
    for candidate in [Path('downloads/links.json'), Path('links.json')]:
        if candidate.exists():
            source_path = candidate
            break

    if not source_path:
        message = "Cannot find links.json to filter. Run scraping first or place links.json in the downloads folder."
        add_log_message(message)
        show_error_notification(
            "Filtering Unavailable",
            message,
            [
                "Run Start Scraping to generate downloads/links.json",
                "Copy an existing links.json into the downloads folder",
                "Turn on 'Download all versions' if you prefer to skip filtering"
            ]
        )
        return

    output_path = Path('downloads/latest.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    app_state.current_operation = "Filtering to latest versions..."
    app_state.last_update = time.time()

    def run_filtering():
        try:
            success = filter_latest_versions(input_file=str(source_path), output_file=str(output_path))
            if success:
                app_state.current_operation = "Latest versions ready"
                add_log_message(f"Version filtering completed ({output_path})")
                load_available_files()
            else:
                add_log_message("Version filtering failed")
                show_error_notification(
                    "Filtering Failed",
                    "No valid specifications were produced. Check logs for details.",
                    [
                        "Confirm downloads/links.json contains valid specification entries",
                        "Try scraping again to regenerate the source data"
                    ]
                )
        except Exception as ex:
            add_log_message(f"Filtering error: {str(ex)}")
            show_error_notification(
                "Version Filtering Failed",
                str(ex),
                [
                    "Ensure links.json exists from a successful scrape",
                    "Check file permissions in the downloads folder",
                    "Try scraping again to regenerate links.json"
                ]
            )

    threading.Thread(target=run_filtering, daemon=True).start()

def start_download(e: me.ClickEvent):
    """Show download confirmation dialog"""
    if app_state.download_status == "running" or not app_state.available_files:
        return

    # Filter selected files
    selected_urls = []
    for file_info in app_state.available_files:
        if file_info.get('url') in app_state.selected_files:
            selected_urls.append(file_info)

    if not selected_urls:
        add_log_message("No files selected for download")
        return

    # Show confirmation dialog instead of starting download immediately
    app_state.show_download_confirmation = True

def confirm_download(e: me.ClickEvent):
    """Actually start the download after confirmation"""
    app_state.show_download_confirmation = False

    # Filter selected files
    selected_urls = []
    for file_info in app_state.available_files:
        if file_info.get('url') in app_state.selected_files:
            selected_urls.append(file_info)

    if not selected_urls:
        add_log_message("No files selected for download")
        return

    app_state.download_status = "running"
    app_state.download_progress = 0
    add_log_message(f"Starting download of {len(selected_urls)} files...")

    # Reset progress callback state
    if hasattr(download_progress_callback, 'total_files'):
        delattr(download_progress_callback, 'total_files')
    if hasattr(download_progress_callback, 'completed_files'):
        delattr(download_progress_callback, 'completed_files')
    if hasattr(download_progress_callback, 'error_files'):
        delattr(download_progress_callback, 'error_files')
    if hasattr(download_progress_callback, 'initialized'):
        delattr(download_progress_callback, 'initialized')

    app_state.completed_downloads.clear()
    app_state.failed_downloads.clear()
    app_state.recent_download_events.clear()
    app_state.current_download_item = None

    # Run download in background thread
    def run_download():
        try:
            update_download_progress(10, "Initializing downloader...")

            # Create filtered JSON for selected files
            filtered_data = selected_urls
            with open('selected.json', 'w') as f:
                json.dump(filtered_data, f, indent=2)

            update_download_progress(12, f"Queued {len(selected_urls)} files for download")
            
            success = download_data_with_config(
                input_file='selected.json',
                resume=app_state.resume_downloads,
                no_download=app_state.no_download,
                all_versions=app_state.download_all_versions,
                organize_by_series=app_state.organize_by_series,
                specific_release=app_state.specific_release,
                threads=app_state.thread_count,
                verbose=app_state.verbose_logging,
                progress_callback=download_progress_callback
            )
            
            if success:
                app_state.download_status = "completed"
                update_download_progress(100, "All downloads completed successfully")
            else:
                app_state.download_status = "error"
                update_download_progress(app_state.download_progress, "Download failed")

        except Exception as ex:
            app_state.download_status = "error"
            update_download_progress(app_state.download_progress, f"Download error: {str(ex)}")
            show_error_notification(
                "Download Failed",
                str(ex),
                [
                    "Check your internet connection",
                    "Verify selected files are still available",
                    "Try reducing thread count in settings",
                    "Check available disk space",
                    "Check the logs tab for more details"
                ]
            )

    threading.Thread(target=run_download, daemon=True).start()

def cancel_download_confirmation(e: me.ClickEvent):
    """Cancel the download confirmation"""
    app_state.show_download_confirmation = False

def toggle_advanced_settings(e: me.ClickEvent):
    """Toggle the visibility of advanced settings"""
    app_state.show_advanced_settings = not app_state.show_advanced_settings
    add_log_message(f"Advanced settings {'shown' if app_state.show_advanced_settings else 'hidden'}")

def on_setting_change(e: me.CheckboxChangeEvent):
    """Handle setting checkbox changes"""
    setting_name = e.key
    setattr(app_state, setting_name, e.checked)
    add_log_message(f"Setting '{setting_name}' changed to {e.checked}")

def on_thread_count_change(e: me.InputBlurEvent):
    """Handle thread count input changes"""
    try:
        thread_count = int(e.value)
        if thread_count < 1:
            thread_count = 1
        elif thread_count > 20:
            thread_count = 20
        app_state.thread_count = thread_count
        add_log_message(f"Thread count changed to {thread_count}")
    except ValueError:
        add_log_message("Invalid thread count, keeping current value")

def on_release_change(e: me.InputBlurEvent):
    """Handle specific release input changes"""
    try:
        if e.value.strip() == "":
            app_state.specific_release = None
            add_log_message("Specific release cleared")
        else:
            release = int(e.value)
            if release < 1:
                release = 1
            app_state.specific_release = release
            add_log_message(f"Specific release set to {release}")
    except ValueError:
        add_log_message("Invalid release number, keeping current value")

def on_select_change(e: me.SelectSelectionChangeEvent):
    """Handle select dropdown changes"""
    setting_name = e.key
    setattr(app_state, setting_name, e.value)
    add_log_message(f"Setting '{setting_name}' changed to {e.value}")

def on_numeric_input_change(e: me.InputBlurEvent):
    """Handle numeric input changes"""
    try:
        setting_name = e.key
        value = int(e.value)
        # Apply reasonable bounds based on the setting
        if "timeout" in setting_name or "delay" in setting_name:
            value = max(1, min(3600, value))  # 1 second to 1 hour
        elif "connections" in setting_name:
            value = max(1, min(1000, value))  # 1 to 1000 connections
        elif "attempts" in setting_name:
            value = max(1, min(20, value))  # 1 to 20 attempts
        elif "requests" in setting_name:
            value = max(1, min(50, value))  # 1 to 50 concurrent requests
        elif "release" in setting_name:
            value = max(1, min(50, value))  # Release 1 to 50
        elif "messages" in setting_name:
            value = max(10, min(1000, value))  # 10 to 1000 messages
        elif "interval" in setting_name:
            value = max(1, min(300, value))  # 1 second to 5 minutes
        
        setattr(app_state, setting_name, value)
        add_log_message(f"Setting '{setting_name}' changed to {value}")
    except ValueError:
        add_log_message(f"Invalid numeric value for '{e.key}', keeping current value")

def on_float_input_change(e: me.InputBlurEvent):
    """Handle float input changes"""
    try:
        setting_name = e.key
        value = float(e.value)
        # Apply reasonable bounds
        if "delay" in setting_name:
            value = max(0.01, min(10.0, value))  # 0.01 to 10 seconds
        
        setattr(app_state, setting_name, value)
        add_log_message(f"Setting '{setting_name}' changed to {value}")
    except ValueError:
        add_log_message(f"Invalid float value for '{e.key}', keeping current value")

def load_available_files():
    """Load available files from latest.json (check both root and downloads/ directory)"""
    try:
        # Check both root directory and downloads directory for latest.json
        latest_paths = [Path('latest.json'), Path('downloads/latest.json')]
        
        for latest_path in latest_paths:
            if latest_path.exists():
                with open(latest_path, 'r') as f:
                    app_state.available_files = json.load(f)
                add_log_message(f"Loaded {len(app_state.available_files)} available files from {latest_path}")
                app_state.current_file_type = "filtered"
                return
        
        # If no latest.json found, try links.json as fallback
        links_paths = [Path('links.json'), Path('downloads/links.json')]
        for links_path in links_paths:
            if links_path.exists():
                with open(links_path, 'r') as f:
                    app_state.available_files = json.load(f)
                add_log_message(f"Loaded {len(app_state.available_files)} available files from {links_path} (fallback)")
                app_state.current_file_type = "all"
                return
        
        app_state.available_files = []
        add_log_message("No available files found (neither latest.json nor links.json exist)")
        app_state.current_file_type = "none"
    except Exception as ex:
        add_log_message(f"Error loading available files: {str(ex)}")
        app_state.available_files = []
        app_state.current_file_type = "none"

def on_file_selection_change(e: me.CheckboxChangeEvent):
    """Handle file selection changes"""
    url = e.key.replace("file_", "")
    if e.checked:
        if url not in app_state.selected_files:
            app_state.selected_files.append(url)
    else:
        if url in app_state.selected_files:
            app_state.selected_files.remove(url)

def select_all_files(e: me.ClickEvent):
    """Select all filtered files"""
    filtered_files = get_filtered_files()
    for file_info in filtered_files:
        url = file_info.get('url', '')
        if url and url not in app_state.selected_files:
            app_state.selected_files.append(url)
    add_log_message(f"Selected all {len([f for f in filtered_files if f.get('url') in app_state.selected_files])} filtered files")

def deselect_all_files(e: me.ClickEvent):
    """Deselect all files"""
    app_state.selected_files = []
    add_log_message("Deselected all files")

def on_search_change(e: me.InputBlurEvent):
    """Handle search query changes"""
    app_state.search_query = e.value

def on_series_filter_change(e: me.SelectSelectionChangeEvent):
    """Handle series filter changes"""
    app_state.series_filter = str(e.value)

def on_release_filter_change(e: me.SelectSelectionChangeEvent):
    """Handle release filter changes"""
    app_state.release_filter = str(e.value)

def get_filtered_files() -> List[Dict]:
    """Get files filtered by search query and filters"""
    files = app_state.available_files
    
    # Apply search filter
    if app_state.search_query:
        query = app_state.search_query.lower()
        files = [f for f in files if query in f.get('name', '').lower() or query in f.get('url', '').lower()]
    
    # Apply series filter
    if app_state.series_filter != "All":
        files = [f for f in files if f.get('series', '') == app_state.series_filter]
    
    # Apply release filter
    if app_state.release_filter != "All":
        files = [f for f in files if str(f.get('release', '')) == app_state.release_filter]
    
    return files

def change_page(new_page: int):
    """Change the current page for file pagination"""
    files_per_page = 20
    total_pages = (len(app_state.available_files) + files_per_page - 1) // files_per_page
    if 0 <= new_page < total_pages:
        app_state.current_page = new_page

# Initialize available files and settings on startup
load_available_files()
load_settings()
configure_logging_preferences()