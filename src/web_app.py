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
from main import scrape_data, filter_latest_versions, download_data

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

app_state = AppState()

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
    """Main page of the 3GPP Downloader web UI"""
    with me.box(style=me.Style(padding=me.Padding.all(20))):
        me.text("3GPP Specification Downloader", style=me.Style(font_size=24, font_weight="bold"))

        # Status section
        with me.box(style=me.Style(margin=me.Margin.symmetric(vertical=20))):
            me.text("Status", style=me.Style(font_size=18, font_weight="bold"))

            # Scraping status
            with me.box(style=me.Style(display="flex", align_items="center", gap=10)):
                me.text("Scraping:")
                status_indicator(app_state.scraping_status)
                me.text(f"{app_state.scraping_progress:.1f}%")

            # Download status
            with me.box(style=me.Style(display="flex", align_items="center", gap=10)):
                me.text("Download:")
                status_indicator(app_state.download_status)
                me.text(f"{app_state.download_progress:.1f}%")

            # Current operation
            if app_state.current_operation:
                me.text(f"Current: {app_state.current_operation}", style=me.Style(font_style="italic"))

        # Control buttons
        with me.box(style=me.Style(margin=me.Margin.symmetric(vertical=20))):
            me.text("Actions", style=me.Style(font_size=18, font_weight="bold"))

            with me.box(style=me.Style(display="flex", gap=10)):
                me.button(
                    "Start Scraping",
                    on_click=start_scraping,
                    disabled=app_state.scraping_status == "running" or app_state.download_status == "running",
                    style=me.Style(background="#1976d2", color="white", padding=me.Padding.all(10))
                )

                me.button(
                    "Filter Latest Versions",
                    on_click=filter_versions,
                    disabled=app_state.scraping_status == "running" or app_state.download_status == "running",
                    style=me.Style(background="#388e3c", color="white", padding=me.Padding.all(10))
                )

                me.button(
                    "Start Download",
                    on_click=start_download,
                    disabled=app_state.scraping_status == "running" or app_state.download_status == "running" or not app_state.available_files,
                    style=me.Style(background="#f57c00", color="white", padding=me.Padding.all(10))
                )

        # Available files section
        if app_state.available_files:
            with me.box(style=me.Style(margin=me.Margin.symmetric(vertical=20))):
                me.text(f"Available Files ({len(app_state.available_files)})", style=me.Style(font_size=18, font_weight="bold"))

                # File list with checkboxes
                with me.box(style=me.Style(max_height=300, overflow_y="auto", border=me.Border.all(me.BorderSide(width=1, color="#ddd")))):
                    for file_info in app_state.available_files[:50]:  # Limit display
                        with me.box(style=me.Style(display="flex", align_items="center", padding=me.Padding.all(5), border=me.Border.all(me.BorderSide(width=1, color="#eee")))):
                            mel.checkbox(
                                label=f"{file_info.get('ts_number', 'Unknown')} - {file_info.get('version', 'Unknown')}",
                                key=f"file_{file_info.get('url', '')}",
                                on_change=on_file_selection_change
                            )

        # Log section
        with me.box(style=me.Style(margin=me.Margin.symmetric(vertical=20))):
            me.text("Activity Log", style=me.Style(font_size=18, font_weight="bold"))

            with me.box(style=me.Style(max_height=200, overflow_y="auto", background="#f5f5f5", padding=me.Padding.all(10), font_family="monospace", font_size=12)):
                max_messages = int(os.getenv('WEB_MAX_LOG_MESSAGES', '100'))
                for log_msg in app_state.log_messages[-max_messages:]:  # Show last N messages
                    me.text(log_msg)

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
    add_log_message("Starting scraping process...")

    # Run scraping in background thread
    def run_scraping():
        try:
            update_scraping_progress(10, "Initializing scraper...")
            success = scrape_data()
            if success:
                app_state.scraping_status = "completed"
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
    """Filter to latest versions"""
    if app_state.scraping_status == "running":
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
    """Start the download process"""
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
            success = download_data('selected.json')

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

def load_available_files():
    """Load available files from latest.json"""
    try:
        if Path('latest.json').exists():
            with open('latest.json', 'r') as f:
                app_state.available_files = json.load(f)
            add_log_message(f"Loaded {len(app_state.available_files)} available files")
        else:
            app_state.available_files = []
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

# Initialize available files on startup
load_available_files()