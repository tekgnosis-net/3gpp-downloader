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
        self.current_page = 0
        self.show_download_confirmation = False

        # UI state
        self.show_advanced_settings = False
        self.current_tab = "dashboard"  # dashboard, settings, logs

        # Configuration options (equivalent to main.py arguments)
        self.resume_downloads = False
        self.no_download = False
        self.download_all_versions = False
        self.organize_by_series = False
        
        # Configuration options (equivalent to main.py arguments)
        self.resume_downloads = False
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
        
        # Web UI settings
        self.web_max_log_messages = 100
        self.web_refresh_interval = 5

app_state = AppState()

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
            "current_tab": app_state.current_tab
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
            app_state.resume_downloads = settings_data.get("resume_downloads", False)
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
            
            add_log_message(f"Settings loaded from {settings_file}")
        else:
            add_log_message("No settings file found, using defaults")
    except Exception as e:
        add_log_message(f"Error loading settings: {str(e)}")

def add_log_message(message: str):
    """Add a message to the log"""
    timestamp = time.strftime("%H:%M:%S")
    app_state.log_messages.append(f"[{timestamp}] {message}")
    # Keep only last 100 messages
    if len(app_state.log_messages) > 100:
        app_state.log_messages = app_state.log_messages[-100:]

def update_scraping_progress(progress: float, message: str = ""):
    """Update scraping progress"""
    app_state.scraping_progress = progress
    if message:
        app_state.current_operation = message
        add_log_message(message)

def update_download_progress(progress: float, message: str = ""):
    """Update download progress"""
    app_state.download_progress = progress
    if message:
        app_state.current_operation = message
        add_log_message(message)

@me.page(path="/", title=os.getenv('WEB_TITLE', '3GPP Downloader'))
def main_page():
    """Main page of the 3GPP Downloader web UI with modern design"""

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
                on_click=lambda e: e.stop_propagation(),
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
    app_state.verbose_logging = e.checked
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

def dashboard_content():
    """Dashboard tab content with modern design"""
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
            status_card("Download", app_state.download_status, app_state.download_progress, "download")

        # Files overview card
        with me.box(style=create_card_style("md")):
            files_overview_card()

    # Quick actions
    with me.box(style=create_card_style("md", Theme.SPACE_4)):
        me.text("Quick Actions", style=me.Style(
            font_size=Theme.FONT_SIZE_H4,
            font_weight=Theme.FONT_WEIGHT_BOLD,
            margin=me.Margin(bottom=Theme.SPACE_4),
            color=Theme.ON_SURFACE
        ))

        with me.box(style=me.Style(display="flex", gap=Theme.SPACE_3, flex_wrap="wrap")):
            action_buttons()

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

def status_card(title: str, status: str, progress: float, icon: str):
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

            # Progress bar for running operations
            if status == "running" and progress > 0:
                with me.box(style=me.Style(width="100%", margin=me.Margin(top=Theme.SPACE_2))):
                    with me.box(style=me.Style(height=6, border_radius=Theme.RADIUS_SM)):
                        me.progress_bar(
                            value=progress,
                            mode="determinate",
                            color="primary"
                        )
                    me.text(f"{progress:.1f}%", style=me.Style(
                        font_size=Theme.FONT_SIZE_CAPTION,
                        color=Theme.ON_SURFACE_VARIANT,
                        text_align="right",
                        margin=me.Margin(top=Theme.SPACE_1)
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

def action_buttons():
    """Quick action buttons"""
    actions = [
        ("Start Scraping", "web", "primary", start_scraping, app_state.scraping_status == "running" or app_state.download_status == "running"),
        ("Filter Versions", "filter_list", "secondary", filter_versions, app_state.scraping_status == "running" or app_state.download_status == "running"),
        ("Start Download", "download", "accent", start_download, app_state.scraping_status == "running" or app_state.download_status == "running" or not app_state.available_files),
    ]

    for label, icon, variant, callback, disabled in actions:
        base_style = create_button_style(variant, "md")
        base_style.opacity = 0.6 if disabled else 1
        base_style.cursor = "not-allowed" if disabled else "pointer"
        me.button(
            label,
            on_click=callback,
            disabled=int(disabled),
            style=base_style
        )

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
    """Settings tab content with configuration options"""
    with me.box(style=create_card_style("md")):
        me.text("Settings", style=me.Style(
            font_size=Theme.FONT_SIZE_H3,
            font_weight=Theme.FONT_WEIGHT_BOLD,
            margin=me.Margin(bottom=Theme.SPACE_4),
            color=Theme.ON_SURFACE
        ))

        # Download Options
        me.text("Download Options", style=me.Style(
            font_size=Theme.FONT_SIZE_H4,
            font_weight=Theme.FONT_WEIGHT_MEDIUM,
            margin=me.Margin(bottom=Theme.SPACE_3),
            color=Theme.ON_SURFACE
        ))

        with me.box(style=me.Style(display="flex", flex_direction="column", gap=Theme.SPACE_3)):
            # Resume Downloads
            with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2)):
                me.checkbox(
                    label="Resume Downloads",
                    checked=int(app_state.resume_downloads),
                    on_change=toggle_resume_downloads,
                    style=me.Style(color=Theme.ON_SURFACE)
                )

            # Download All Versions
            with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2)):
                me.checkbox(
                    label="Download All Versions",
                    checked=int(app_state.download_all_versions),
                    on_change=toggle_download_all_versions,
                    style=me.Style(color=Theme.ON_SURFACE)
                )

            # Organize by Series
            with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2)):
                me.checkbox(
                    label="Organize by Series",
                    checked=int(app_state.organize_by_series),
                    on_change=toggle_organize_by_series,
                    style=me.Style(color=Theme.ON_SURFACE)
                )

        # Thread Count
        me.text("Performance Settings", style=me.Style(
            font_size=Theme.FONT_SIZE_H4,
            font_weight=Theme.FONT_WEIGHT_MEDIUM,
            margin=me.Margin(top=Theme.SPACE_4, bottom=Theme.SPACE_3),
            color=Theme.ON_SURFACE
        ))

        with me.box(style=me.Style(display="flex", flex_direction="column", gap=Theme.SPACE_3)):
            with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_3)):
                me.text("Thread Count:", style=me.Style(
                    font_size=Theme.FONT_SIZE_BODY,
                    color=Theme.ON_SURFACE,
                    min_width="120px"
                ))
                me.input(
                    label="",
                    value=str(app_state.thread_count),
                    on_blur=on_thread_count_change,
                    style=me.Style(width="80px")
                )

        # Logging Settings
        me.text("Logging Settings", style=me.Style(
            font_size=Theme.FONT_SIZE_H4,
            font_weight=Theme.FONT_WEIGHT_MEDIUM,
            margin=me.Margin(top=Theme.SPACE_4, bottom=Theme.SPACE_3),
            color=Theme.ON_SURFACE
        ))

        with me.box(style=me.Style(display="flex", flex_direction="column", gap=Theme.SPACE_3)):
            with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2)):
                me.checkbox(
                    label="Verbose Logging",
                    checked=int(app_state.verbose_logging),
                    on_change=toggle_verbose_logging,
                    style=me.Style(color=Theme.ON_SURFACE)
                )

        # Advanced Settings Toggle
        me.text("Advanced Settings", style=me.Style(
            font_size=Theme.FONT_SIZE_H4,
            font_weight=Theme.FONT_WEIGHT_MEDIUM,
            margin=me.Margin(top=Theme.SPACE_4, bottom=Theme.SPACE_3),
            color=Theme.ON_SURFACE
        ))

        with me.box(style=me.Style(display="flex", align_items="center", gap=Theme.SPACE_2)):
            me.checkbox(
                label="Show Advanced Settings",
                checked=int(app_state.show_advanced_settings),
                on_change=toggle_advanced_settings,
                style=me.Style(color=Theme.ON_SURFACE)
            )

        # Advanced Settings Panel
        if app_state.show_advanced_settings:
            with me.box(style=me.Style(
                margin=me.Margin(top=Theme.SPACE_3),
                padding=me.Padding.all(Theme.SPACE_3),
                background=Theme.SURFACE_VARIANT,
                border_radius=Theme.RADIUS_MD,
                border=me.Border.all(me.BorderSide(width=1, color=Theme.OUTLINE_VARIANT))
            )):
                me.text("HTTP/Connection Settings", style=me.Style(
                    font_size=Theme.FONT_SIZE_H5,
                    font_weight=Theme.FONT_WEIGHT_MEDIUM,
                    margin=me.Margin(bottom=Theme.SPACE_3),
                    color=Theme.ON_SURFACE
                ))

                with me.box(style=me.Style(display="grid", grid_template_columns="1fr 1fr", gap=Theme.SPACE_3)):
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
                        me.text("Max Connections Per Host:", style=me.Style(
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
                        me.text("Total Timeout (seconds):", style=me.Style(
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
                        me.text("Connect Timeout (seconds):", style=me.Style(
                            font_size=Theme.FONT_SIZE_CAPTION,
                            color=Theme.ON_SURFACE_VARIANT
                        ))
                        me.input(
                            label="",
                            value=str(app_state.http_connect_timeout),
                            on_blur=on_connect_timeout_change,
                            style=me.Style(width="100%")
                        )

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
    
    if app_state.resume_downloads:
        add_log_message("Resume mode: checking for existing files...")
    else:
        add_log_message("Starting scraping process...")

    # Run scraping in background thread
    def run_scraping():
        try:
            if app_state.resume_downloads:
                update_scraping_progress(50, "Checking for existing files...")
            else:
                update_scraping_progress(10, "Initializing scraper...")
                
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
                app_state.scraping_status = "completed"
                if app_state.resume_downloads:
                    update_scraping_progress(100, "Resume check completed - files loaded")
                else:
                    update_scraping_progress(100, "Scraping completed successfully")
                load_available_files()
            else:
                app_state.scraping_status = "error"
                update_scraping_progress(0, "Scraping failed")
        except Exception as ex:
            app_state.scraping_status = "error"
            update_scraping_progress(0, f"Scraping error: {str(ex)}")

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

    def run_filtering():
        try:
            success = filter_latest_versions()
            if success:
                add_log_message("Version filtering completed")
                load_available_files()
            else:
                add_log_message("Version filtering failed")
        except Exception as ex:
            add_log_message(f"Filtering error: {str(ex)}")

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

    # Run download in background thread
    def run_download():
        try:
            update_download_progress(10, "Initializing downloader...")

            # Create filtered JSON for selected files
            filtered_data = selected_urls
            with open('selected.json', 'w') as f:
                json.dump(filtered_data, f, indent=2)

            update_download_progress(20, "Starting downloads...")
            success = download_data_with_config(
                input_file='selected.json',
                resume=app_state.resume_downloads,
                no_download=app_state.no_download,
                all_versions=app_state.download_all_versions,
                organize_by_series=app_state.organize_by_series,
                specific_release=app_state.specific_release,
                threads=app_state.thread_count,
                verbose=app_state.verbose_logging
            )

            if success:
                app_state.download_status = "completed"
                update_download_progress(100, "All downloads completed successfully")
            else:
                app_state.download_status = "error"
                update_download_progress(0, "Download failed")

        except Exception as ex:
            app_state.download_status = "error"
            update_download_progress(0, f"Download error: {str(ex)}")

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
                return
        
        # If no latest.json found, try links.json as fallback
        links_paths = [Path('links.json'), Path('downloads/links.json')]
        for links_path in links_paths:
            if links_path.exists():
                with open(links_path, 'r') as f:
                    app_state.available_files = json.load(f)
                add_log_message(f"Loaded {len(app_state.available_files)} available files from {links_path} (fallback)")
                return
        
        app_state.available_files = []
        add_log_message("No available files found (neither latest.json nor links.json exist)")
    except Exception as ex:
        add_log_message(f"Error loading available files: {str(ex)}")
        app_state.available_files = []

def on_file_selection_change(e: me.CheckboxChangeEvent):
    """Handle file selection changes"""
    url = e.key.replace("file_", "")
    if e.checked:
        if url not in app_state.selected_files:
            app_state.selected_files.append(url)
    else:
        if url in app_state.selected_files:
            app_state.selected_files.remove(url)

def select_all_files():
    """Select all available files"""
    app_state.selected_files = [file_info.get('url', '') for file_info in app_state.available_files if file_info.get('url')]
    add_log_message(f"Selected all {len(app_state.selected_files)} files")

def deselect_all_files():
    """Deselect all files"""
    app_state.selected_files = []
    add_log_message("Deselected all files")

def change_page(new_page: int):
    """Change the current page for file pagination"""
    files_per_page = 20
    total_pages = (len(app_state.available_files) + files_per_page - 1) // files_per_page
    if 0 <= new_page < total_pages:
        app_state.current_page = new_page

# Initialize available files and settings on startup
load_available_files()
load_settings()
load_settings()