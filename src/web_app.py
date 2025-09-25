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
        
        # Configuration options (equivalent to main.py arguments)
        self.resume_downloads = False
        self.no_download = False
        self.download_all_versions = False
        self.organize_by_series = False
        self.specific_release: Optional[int] = None
        self.thread_count = 5
        self.verbose_logging = False

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
    
    # Download confirmation dialog
    with me.box(
        style=me.Style(
            background="rgba(0, 0, 0, 0.4)" if app_state.show_download_confirmation else "transparent",
            display="block" if app_state.show_download_confirmation else "none",
            height="100%",
            overflow_x="auto",
            overflow_y="auto",
            position="fixed",
            width="100%",
            z_index=1000,
            top=0,
            left=0,
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
                style=me.Style(
                    background=me.theme_var("surface-container-lowest"),
                    border_radius=20,
                    box_sizing="content-box",
                    box_shadow=(
                        "0 3px 1px -2px #0003, 0 2px 2px #00000024, 0 1px 5px #0000001f"
                    ),
                    margin=me.Margin.symmetric(vertical="0", horizontal="auto"),
                    padding=me.Padding.all(20),
                    max_width=400,
                ),
                on_click=lambda e: e.stop_propagation(),  # Prevent closing when clicking inside dialog
            ):
                me.text("Confirm Download", style=me.Style(font_size=20, font_weight="bold", margin=me.Margin(bottom=15)))
                
                # Count selected files
                selected_count = len([f for f in app_state.available_files if f.get('url') in app_state.selected_files])
                
                me.text(f"Are you sure you want to download {selected_count} selected file{'s' if selected_count != 1 else ''}?", 
                       style=me.Style(margin=me.Margin(bottom=20)))
                
                with me.box(
                    style=me.Style(
                        display="flex", 
                        justify_content="end", 
                        gap=10, 
                        margin=me.Margin(top=20)
                    )
                ):
                    me.button("Cancel", on_click=cancel_download_confirmation, style=me.Style(padding=me.Padding.symmetric(horizontal=15, vertical=8)))
                    me.button(
                        "Download", 
                        on_click=confirm_download, 
                        style=me.Style(
                            background="#f57c00", 
                            color="white", 
                            padding=me.Padding.symmetric(horizontal=15, vertical=8)
                        )
                    )
    
    with me.box(style=me.Style(padding=me.Padding.all(20))):
        me.text("3GPP Specification Downloader", style=me.Style(font_size=24, font_weight="bold"))

        # Status section
        with me.box(style=me.Style(margin=me.Margin.symmetric(vertical=20))):
            me.text("Status", style=me.Style(font_size=18, font_weight="bold"))

            # Scraping status
            with me.box(style=me.Style(display="flex", align_items="center", gap=10)):
                me.text("Scraping:")
                status_indicator(app_state.scraping_status)
                if app_state.scraping_status == "running":
                    me.progress_spinner(diameter=20, stroke_width=2)
                me.text(f"{app_state.scraping_progress:.1f}%")
            
            # Scraping progress bar
            if app_state.scraping_status in ["running", "completed"]:
                with me.box(style=me.Style(width="100%", margin=me.Margin.symmetric(vertical=5))):
                    me.progress_bar(
                        value=app_state.scraping_progress,
                        mode="determinate" if app_state.scraping_progress > 0 else "indeterminate",
                        color="primary"
                    )

            # Download status
            with me.box(style=me.Style(display="flex", align_items="center", gap=10)):
                me.text("Download:")
                status_indicator(app_state.download_status)
                if app_state.download_status == "running":
                    me.progress_spinner(diameter=20, stroke_width=2)
                me.text(f"{app_state.download_progress:.1f}%")
            
            # Download progress bar
            if app_state.download_status in ["running", "completed"]:
                with me.box(style=me.Style(width="100%", margin=me.Margin.symmetric(vertical=5))):
                    me.progress_bar(
                        value=app_state.download_progress,
                        mode="determinate" if app_state.download_progress > 0 else "indeterminate",
                        color="accent"
                    )

            # Current operation
            if app_state.current_operation:
                me.text(f"Current: {app_state.current_operation}", style=me.Style(font_style="italic"))

        # Error display section
        if app_state.scraping_status == "error" or app_state.download_status == "error":
            with me.box(style=me.Style(
                margin=me.Margin.symmetric(vertical=10),
                padding=me.Padding.all(15),
                background="#ffebee",
                border=me.Border.all(me.BorderSide(width=1, color="#f44336")),
                border_radius=4
            )):
                me.text("❌ Error Occurred", style=me.Style(
                    font_size=16, 
                    font_weight="bold", 
                    color="#d32f2f"
                ))
                if app_state.scraping_status == "error":
                    me.text("Scraping operation failed. Check the activity log for details.", style=me.Style(color="#d32f2f"))
                if app_state.download_status == "error":
                    me.text("Download operation failed. Check the activity log for details.", style=me.Style(color="#d32f2f"))

        # Settings section
        with me.box(style=me.Style(margin=me.Margin.symmetric(vertical=20))):
            me.text("Settings", style=me.Style(font_size=18, font_weight="bold"))

            with me.box(style=me.Style(display="grid", grid_template_columns="repeat(auto-fit, minmax(300px, 1fr))", gap=20)):
                # Download options
                with me.box(style=me.Style(padding=me.Padding.all(15), border=me.Border.all(me.BorderSide(width=1, color="#ddd")), border_radius=8)):
                    me.text("Download Options", style=me.Style(font_size=16, font_weight="bold", margin=me.Margin(bottom=10)))
                    
                    me.checkbox(
                        label="Resume broken downloads (only resume, don't scrape new)",
                        key="resume_downloads",
                        checked=app_state.resume_downloads,
                        on_change=on_setting_change
                    )
                    
                    me.checkbox(
                        label="Download all versions (not just latest)",
                        key="download_all_versions",
                        checked=app_state.download_all_versions,
                        on_change=on_setting_change
                    )
                    
                    me.checkbox(
                        label="No download (only create links.json)",
                        key="no_download",
                        checked=app_state.no_download,
                        on_change=on_setting_change
                    )

                # Organization options
                with me.box(style=me.Style(padding=me.Padding.all(15), border=me.Border.all(me.BorderSide(width=1, color="#ddd")), border_radius=8)):
                    me.text("Organization Options", style=me.Style(font_size=16, font_weight="bold", margin=me.Margin(bottom=10)))
                    
                    me.checkbox(
                        label="Organize by series (default: by release)",
                        key="organize_by_series",
                        checked=app_state.organize_by_series,
                        on_change=on_setting_change
                    )

                # Performance options
                with me.box(style=me.Style(padding=me.Padding.all(15), border=me.Border.all(me.BorderSide(width=1, color="#ddd")), border_radius=8)):
                    me.text("Performance Options", style=me.Style(font_size=16, font_weight="bold", margin=me.Margin(bottom=10)))
                    
                    with me.box(style=me.Style(display="flex", align_items="center", gap=10, margin=me.Margin(bottom=10))):
                        me.text("Thread count:")
                        me.input(
                            key="thread_count",
                            value=str(app_state.thread_count),
                            on_blur=on_thread_count_change,
                            style=me.Style(width=80)
                        )
                    
                    me.checkbox(
                        label="Verbose logging",
                        key="verbose_logging",
                        checked=app_state.verbose_logging,
                        on_change=on_setting_change
                    )

                # Release options
                with me.box(style=me.Style(padding=me.Padding.all(15), border=me.Border.all(me.BorderSide(width=1, color="#ddd")), border_radius=8)):
                    me.text("Release Options", style=me.Style(font_size=16, font_weight="bold", margin=me.Margin(bottom=10)))
                    
                    with me.box(style=me.Style(display="flex", align_items="center", gap=10)):
                        me.text("Specific release (leave empty for all):")
                        me.input(
                            key="specific_release",
                            value=str(app_state.specific_release) if app_state.specific_release else "",
                            on_blur=on_release_change,
                            placeholder="e.g., 15",
                            style=me.Style(width=100)
                        )

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
                    "Filter to Latest Versions" if not app_state.download_all_versions else "Load All Versions",
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
                me.text(f"Available Files ({len(app_state.available_files)} total)", style=me.Style(font_size=18, font_weight="bold"))
                
                # File selection controls
                with me.box(style=me.Style(display="flex", gap=10, align_items="center", margin=me.Margin(bottom=10))):
                    me.button(
                        "Select All",
                        on_click=lambda e: select_all_files(),
                        style=me.Style(background="#2196f3", color="white", padding=me.Padding.symmetric(horizontal=15, vertical=8))
                    )
                    me.button(
                        "Deselect All", 
                        on_click=lambda e: deselect_all_files(),
                        style=me.Style(background="#757575", color="white", padding=me.Padding.symmetric(horizontal=15, vertical=8))
                    )
                    me.text(f"Selected: {len(app_state.selected_files)}", style=me.Style(font_weight="bold"))

                # File list with pagination
                files_per_page = 20
                total_pages = (len(app_state.available_files) + files_per_page - 1) // files_per_page
                current_page = getattr(app_state, 'current_page', 0)
                
                # Pagination controls
                if total_pages > 1:
                    with me.box(style=me.Style(display="flex", gap=5, align_items="center", margin=me.Margin(bottom=10))):
                        me.button(
                            "◀",
                            on_click=lambda e: change_page(current_page - 1),
                            disabled=current_page == 0,
                            style=me.Style(padding=me.Padding.symmetric(horizontal=10, vertical=5))
                        )
                        me.text(f"Page {current_page + 1} of {total_pages}", style=me.Style(font_weight="bold"))
                        me.button(
                            "▶",
                            on_click=lambda e: change_page(current_page + 1),
                            disabled=current_page >= total_pages - 1,
                            style=me.Style(padding=me.Padding.symmetric(horizontal=10, vertical=5))
                        )

                # File list
                start_idx = current_page * files_per_page
                end_idx = min(start_idx + files_per_page, len(app_state.available_files))
                displayed_files = app_state.available_files[start_idx:end_idx]
                
                with me.box(style=me.Style(max_height=400, overflow_y="auto", border=me.Border.all(me.BorderSide(width=1, color="#ddd")))):
                    for file_info in displayed_files:
                        file_url = file_info.get('url', '')
                        is_selected = file_url in app_state.selected_files
                        
                        with me.box(style=me.Style(
                            display="flex", 
                            align_items="center", 
                            padding=me.Padding.all(8), 
                            border=me.Border.all(me.BorderSide(width=1, color="#eee")),
                            background="#f9f9f9" if is_selected else "white"
                        )):
                            me.checkbox(
                                label=f"{file_info.get('ts_number', 'Unknown')} - {file_info.get('version', 'Unknown')} ({file_info.get('release', 'Unknown')})",
                                key=f"file_{file_url}",
                                checked=is_selected,
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

# Initialize available files on startup
load_available_files()