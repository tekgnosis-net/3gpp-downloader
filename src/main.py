# Main script to run the 3GPP downloader
import atexit
from multiprocessing import pool
import os
import re
import sys
import argparse
import json
from pathlib import Path
from threading import Timer, Event
import signal
from typing import Callable, Dict, Optional
from tools.etsi_spider import EtsiSpider
from scrapy.crawler import CrawlerProcess
from tools.monitored_pool import MonitoredPoolManager
import logging
from utils.logging_config import setup_logger
import time
from tools.json_downloader import download_from_json
from tools.filtering import filter_latest_records

try:
    from api.extensions.scrape_progress import EXTENSION_PATH as PROGRESS_EXTENSION
except Exception:  # pragma: no cover - optional extension
    PROGRESS_EXTENSION = None


#configure logger
logging_file = os.getenv('MAIN_LOG_FILE', os.getenv('LOGGING_FILE', 'logs/downloader.log'))
logger_name = os.getenv('MAIN_LOGGER_NAME', 'downloader')
console_level = getattr(logging, os.getenv('MAIN_CONSOLE_LEVEL', 'INFO').upper(), logging.INFO)
file_level = getattr(logging, os.getenv('MAIN_FILE_LEVEL', 'DEBUG').upper(), logging.DEBUG)
max_bytes = int(os.getenv('MAIN_MAX_BYTES', '10485760'))
backup_count = int(os.getenv('MAIN_BACKUP_COUNT', '5'))

logger = setup_logger(logger_name, log_file=logging_file, console_level=console_level, logfile_level=file_level, max_bytes=max_bytes, backup_count=backup_count)

def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}, exiting gracefully...")
    sys.exit(0)

def cleanup(pool):
    """
    Cleanup function to clear connection pools at exit
    """
    logger.info(f"Cleaning up HTTPS connection pools at exit...")
    pool.clear()
    logger.info(f"Cleaned up HTTPS connection pools at exit...")

def download_pdfs(
    input_file: str = 'latest.json',
    dest_dir: str = 'downloads/pdfs',
    concurrency: int = 5,
    callback=None,
    cancel_event: Optional[Event] = None,
) -> bool:
    """
    Downloads PDFs from the provided JSON file containing links.
    
    Args:
        input_file (str): Path to the input JSON file (default: 'latest.json')
        dest_dir (str): Directory to save the downloaded PDFs (default: 'downloads/pdfs')
        concurrency (int): Number of concurrent downloads (default: 5)
    callback (callable): Optional callback function to call after each download
    cancel_event (threading.Event | None): When set, stops further downloads gracefully

    Returns:
        bool: True if downloads were successful, False otherwise
    """
    # Create the destination directory if it doesn't exist
    dest_path = Path(dest_dir)
    dest_path.mkdir(parents=True, exist_ok=True)

    import asyncio

    try:
        result = asyncio.run(
            download_from_json(
                src_file=input_file,
                dest_dir=str(dest_path),
                concurrency=concurrency,
                progress_callback=callback,
                cancel_event=cancel_event,
            )
        )
    except asyncio.CancelledError:
        logger.info("Download cancelled by user")
        return False
    return bool(result)

def filter_latest_versions(input_file: str = 'links.json', output_file: str = 'latest.json') -> bool:
    """
    Reads the input JSON file, filters to keep only the latest version for each ts_number,
    and writes the filtered data to the output JSON file.
    
    Args:
        input_file (str): Path to the input JSON file (default: 'links.json')
        output_file (str): Path to the output JSON file (default: 'latest.json')
    """
    # Measure the time taken for filtering
    start_time = time.time()
    logger.info(f"Filtering latest versions from {input_file} to {output_file}...")
    input_path = Path(input_file)
    if not input_path.exists():
        logger.error(f"Input file {input_file} does not exist.")
        end_time = time.time()
        elapsed = end_time - start_time
        logger.info(f"Filtering failed in {elapsed:.2f} seconds.")
        return False
    
    with input_path.open('r') as f:
        data = json.load(f)
    
    if not data:
        logger.warning("No data in input file.")
        end_time = time.time()
        elapsed = end_time - start_time
        logger.info(f"Filtering failed in {elapsed:.2f} seconds.")
        return False

    filtered, skipped_items = filter_latest_records(data)

    if skipped_items:
        logger.warning(
            f"Skipped {skipped_items} entries missing ts_number/version while filtering {input_file}."
        )

    if not filtered:
        logger.error("No valid specifications found after filtering; aborting.")
        return False

    # Write to output file
    output_path = Path(output_file)
    with output_path.open('w') as f:
        json.dump(filtered, f, indent=2)
    
    end_time = time.time()
    elapsed = end_time - start_time
    logger.info(
        f"Filtered {len(data)} items to {len(filtered)} latest versions in {output_file} in {elapsed:.2f} seconds."
    )
    return True

# Function to invoke the scrapy class and trigger the scraping
def run_scraper(
    logging_lvl: int = logging.INFO,
    logfile: str = 'logs/scrapy.log',
    progress_callback: Optional[Callable[[float, Dict[str, int]], None]] = None,
) -> dict:
    """
    Function to invoke the scrapy class and trigger the scraping
    """
    logger.info(f"Starting scraper for the links...")
    # Define the format string with placeholders
    # - asctime: For date/time
    # - filename: Source file name
    # - lineno: Line number
    # - funcName: Function name
    # - threadName: Thread name
    # - levelname: Log level (e.g., DEBUG, INFO)
    # - message: The log message
    default_fmt = '%(asctime)s-%(filename)s:%(lineno)d-%(funcName)s()-%(threadName)s-%(levelname)s- %(message)s'

    # Australian date format: DD-MM-YYYY HH:MM:SS (no milliseconds for simplicity)
    # Example: 25-12-2023 14:30:59.123456
    date_fmt = '%d-%m-%Y %H:%M:%S.%f'

    settings = {
        'FEEDS': {
            'downloads/links.json': {'format': 'json', 'overwrite': True}
        },
        'USER_AGENT': os.getenv('SCRAPY_USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'),
        'ROBOTSTXT_OBEY': True,
        'CONCURRENT_REQUESTS': int(os.getenv('SCRAPY_CONCURRENT_REQUESTS_PER_DOMAIN', '32')),
        'DOWNLOAD_DELAY': float(os.getenv('SCRAPY_DOWNLOAD_DELAY', '0.1')),
        'LOG_ENABLED': True,
        'LOG_FILE': logfile,
        'LOG_LEVEL': logging_lvl,
        'LOG_FORMAT': default_fmt,
        'LOG_DATEFORMAT': date_fmt,
    }
    if PROGRESS_EXTENSION:
        settings.setdefault('EXTENSIONS', {})[PROGRESS_EXTENSION] = 5
        if progress_callback:
            settings['SCRAPE_PROGRESS_CALLBACK'] = progress_callback

    process = CrawlerProcess(settings=settings)
    # Start the crawling using the EtsiSpider
    process.crawl(EtsiSpider)
    # Measure the time taken for scraping
    start_time = time.time()
    logger.info("Scraping started...")
    process.start(install_signal_handlers=False)
    end_time = time.time()
    elapsed = end_time - start_time
    logger.info(f"Scraping completed in {elapsed:.2f} seconds.")

    # Safely attempt to collect scrapy stats. Some CrawlerProcess versions may not
    # expose a .stats attribute after start(); avoid raising an exception here so
    # the caller can still rely on the produced artifact (downloads/links.json)
    stats = {}
    try:
        if hasattr(process, "stats") and getattr(process.stats, "get_stats", None):
            stats = process.stats.get_stats() or {}
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning(f"Unable to collect scrapy stats from process: {exc}")
    links_path = Path('downloads/links.json')

    if stats:
        logger.info(f"Scrapy stats collected: {stats}")
    else:
        logger.warning("Scrapy stats collector returned empty results.")

    # Ensure we always report whether the output artifact exists
    stats['links_output_exists'] = links_path.exists() and links_path.stat().st_size > 0 if links_path.exists() else False

    # If item_scraped_count is missing but the file exists, approximate via file length
    if stats['links_output_exists'] and 'item_scraped_count' not in stats:
        try:
            with links_path.open('r') as handle:
                scraped_items = json.load(handle)
            stats['item_scraped_count'] = len(scraped_items)
            logger.info(f"Derived item count from links.json: {stats['item_scraped_count']}")
        except Exception as exc:
            logger.warning(f"Unable to derive item count from links.json: {exc}")

    # Treat scraping as successful when we actually produced items
    scraped_count = stats.get('item_scraped_count', 0)
    stats['scrape_success'] = scraped_count > 0

    if not stats['scrape_success'] and stats['links_output_exists']:
        try:
            with links_path.open('r') as handle:
                scraped_items = json.load(handle)
            scraped_count = len(scraped_items)
            stats['item_scraped_count'] = scraped_count
            stats['scrape_success'] = scraped_count > 0
            logger.info(
                "Verified scrape results from links.json: %s item(s) present", scraped_count
            )
        except Exception as exc:
            logger.warning("Unable to verify links.json contents: %s", exc)

    if not stats['scrape_success']:
        logger.error("Scraping completed without producing any items.")

    return stats

def scrape_data() -> bool:
    """
    Wrapper function for web app to run scraping
    Returns True if successful, False otherwise
    """
    try:
        logger.info("Starting scraping from web interface...")
        stats = run_scraper()
        if stats:
            logger.info("Scraping completed successfully")
            return True
        else:
            logger.error("Scraping failed")
            return False
    except Exception as e:
        logger.error(f"Scraping error: {e}")
        return False

def download_data(input_file: str = 'latest.json') -> bool:
    """
    Wrapper function for web app to run downloading
    Returns True if successful, False otherwise
    """
    try:
        logger.info(f"Starting download from {input_file}...")
        success = download_pdfs(input_file=input_file)
        if success:
            logger.info("Download completed successfully")
            return True
        else:
            logger.error("Download failed")
            return False
    except Exception as e:
        logger.error(f"Download error: {e}")
        return False

def scrape_data_with_config(
    resume: bool = False,
    no_download: bool = False,
    all_versions: bool = False,
    organize_by_series: bool = False,
    specific_release: int = None,
    threads: int = 5,
    verbose: bool = False,
    progress_callback: Optional[Callable[[float, Dict[str, int]], None]] = None,
) -> bool:
    """
    Enhanced scraping function with configuration options
    """
    try:
        if verbose:
            logger.setLevel(logging.DEBUG)
        
        logger.info("Starting scraping with configuration...")
        
        if resume:
            logger.info("Resume mode: checking for existing files...")
            # Resume logic - check for existing files and skip scraping if possible
            if Path('downloads/links.json').exists() or Path('downloads/latest.json').exists():
                logger.info("Found existing files, skipping scraping in resume mode")
                return True
            else:
                logger.info("No existing files found, proceeding with scraping")
        
        stats = run_scraper(
            logging_lvl=logging.DEBUG if verbose else logging.INFO,
            progress_callback=progress_callback,
        )
        if stats:
            logger.info("Scraping completed successfully")
            return True
        else:
            logger.error("Scraping failed")
            return False
    except Exception as e:
        logger.error(f"Scraping error: {e}")
        return False

def download_data_with_config(
    input_file: str = 'latest.json',
    resume: bool = False,
    no_download: bool = False,
    all_versions: bool = False,
    organize_by_series: bool = False,
    specific_release: int = None,
    threads: int = 5,
    verbose: bool = False,
    progress_callback=None,
    cancel_event: Optional[Event] = None,
) -> bool:
    """
    Enhanced download function with configuration options
    """
    try:
        if verbose:
            logger.setLevel(logging.DEBUG)
            
        if no_download:
            logger.info("No download mode: skipping download")
            return True
            
        logger.info(f"Starting download from {input_file} with configuration...")
        
        dest_dir = 'downloads/By-Series' if organize_by_series else 'downloads/By-Release'
        
        success = download_pdfs(
            input_file=input_file,
            dest_dir=dest_dir,
            concurrency=threads,
            callback=progress_callback,
            cancel_event=cancel_event,
        )
        if cancel_event and cancel_event.is_set():
            logger.info("Download cancelled before completion")
            return False
        if success:
            logger.info("Download completed successfully")
            return True
        else:
            logger.error("Download failed")
            return False
    except Exception as e:
        logger.error(f"Download error: {e}")
        return False

def main(args):
    """
    Main function to handle argument parsing and invoking the scraper and downloader
    Args:
        -S/--series: Download into series ordered directories
        -R/--release: The 3GPP release number (e.g., -R 15 for Rel-15). If not specified, downloads all releases from 15 onwards.
        -T/--threads: Number of threads for parallel downloads (default: 5, multi-threaded).
        -v/--verbose: Display verbose content for console (default: INFO).
        -r/--resume: Only use this switch to resume broken downloads and exit. New PDFs will not be downloaded.
        -n/--nodownload: Only create links.json and exit without downloads.
        -a/--all: Download all versions for the releases from Rel-15 to the latest available release (default: False).
        -h/--help: Show this help message and exit.
    Returns:
        None
    """

    # make sure downloads directory exists
    Path('downloads').mkdir(parents=True, exist_ok=True)
    # make sure logs directory exists
    Path('logs').mkdir(parents=True, exist_ok=True)

    if args.verbose:
        logger.setLevel(logging.DEBUG)
    if args.nodownload:
        logger.info("No download mode activated.")
    # Add more logic here as needed to handle downloading based on args
    logger.info(f"Arguments received: {args}")
    
    # set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if args.resume:
        logger.info("Resume mode activated. Exiting after downloading previously scraped links.")
        # In resume mode, skip scraping and just download from existing links.json or latest.json
        if Path('downloads/links.json').exists() or Path('downloads/latest.json').exists():
            if not args.all:
                if Path('downloads/links.json').exists():
                    if filter_latest_versions(input_file='downloads/links.json', output_file='downloads/latest.json'):
                        logger.info("Resume mode - Filtered to latest versions successfully.")
                        if download_pdfs(
                            input_file='downloads/latest.json', 
                            dest_dir='downloads/By-Release' if not args.series else 'downloads/By-Series', 
                            concurrency=args.threads, 
                            callback=lambda fn, status, pct: logger.info(f"✓ {fn} {status} at {pct}%")
                        ):
                            logger.info("Resume mode - Download completed successfully.")
                            # delete links and latest files
                            Path('downloads/links.json').unlink(missing_ok=True)
                            Path('downloads/latest.json').unlink(missing_ok=True)
                            sys.exit(0)
                        else:
                            logger.error("Resume mode - Download failed.")
                            sys.exit(1)
                    else:
                        logger.error("Resume mode - Failed to filter to latest versions.")
                        sys.exit(1)
                elif Path('downloads/latest.json').exists():
                    if download_pdfs(
                        input_file='downloads/latest.json', 
                        dest_dir='downloads/By-Release' if not args.series else 'downloads/By-Series', 
                        concurrency=args.threads, 
                        callback=lambda fn, status, pct: logger.info(f"✓ {fn} {status} at {pct}%")
                        ):
                        logger.info("Resume mode - Download completed successfully.")
                        # delete links and latest files
                        Path('downloads/links.json').unlink(missing_ok=True)
                        Path('downloads/latest.json').unlink(missing_ok=True)
                        sys.exit(0)
                    else:
                        logger.error("Resume mode - Download failed.")
                        # Lets continue with scraping

            else:
                logger.info("Resume mode - Downloading all versions as per --all flag; skipping filtering.")
                if not Path('downloads/links.json').exists():
                    logger.error("links.json does not exist for downloading all versions.")
                    try:
                        run_scraper(logging_lvl=logging.DEBUG if args.verbose else logging.INFO)
                    except Exception as e:
                        logger.error(f"Error running scraper: {e}") 
                        sys.exit(1)
                if not Path('downloads/links.json').exists():
                    logger.error("links.json does not exist after scraping.")
                    sys.exit(1)
                download_pdfs(
                    input_file='downloads/links.json', 
                    dest_dir='downloads/By-Release' if not args.series else 'downloads/By-Series', 
                    concurrency=args.threads, 
                    callback=lambda fn, status, pct: logger.info(f"✓ {fn} {status} at {pct}%")) 
            logger.info("Exiting as per resume mode.")
            sys.exit(0)

    try:
        run_scraper(logging_lvl=logging.DEBUG if args.verbose else logging.INFO)
    except Exception as e:
        logger.error(f"Error running scraper: {e}")
    
    # After scraping, filter to keep only the latest versions
    if not args.all:
        if filter_latest_versions(input_file='downloads/links.json', output_file='downloads/latest.json'):
            logger.info("Filtered to latest versions successfully.")
        else:
            logger.error("Failed to filter to latest versions.")
    else:
        logger.info("Downloading all versions as per --all flag; skipping filtering.")

    # After scraping, if nodownload is not set, proceed to download
    # if we have resume set and here, then we have issues with links.json or latest.json and failed to download
    # hopefully next run with resume will work since we have scraped fresh links.json
    if not args.nodownload and not args.resume: 
        logger.info("Starting download process...")
        if download_pdfs(
            input_file='downloads/latest.json' if not args.all else 'downloads/links.json', 
            dest_dir='downloads/By-Release' if not args.series else 'downloads/By-Series', 
            concurrency=args.threads, 
            callback=lambda fn, status, pct: logger.info(f"✓ {fn} {status} at {pct}%")):
            logger.info("Download process completed successfully.")
            # delete links and latest files
            Path('downloads/links.json').unlink(missing_ok=True)
            Path('downloads/latest.json').unlink(missing_ok=True)
            sys.exit(0)
        else:            
            logger.error("Download process encountered errors.")
            sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description='Download 3GPP specs PDFs for a specific release or all releases from Rel-15 onwards. \nDownloaded PDF is organised into directory named By-Releases (default) or By-Series. \n[IMPORTANT] Downloads only the last version of each TS.\n\n© Kumar Kadatoka\n',
        epilog='')
    #parser.add_argument('output_type', choices=['release', 'series'], nargs='?', default='release', help="The output structure type to save the downloaded PDFs, organized under release or series subdirectories.[default: release]")
    parser.add_argument("-S", "--series", action="store_true", help="Download into series ordered directories. (default: release ordered directories)")
    parser.add_argument("-R", "--release", type=int, default=None, help="The 3GPP release number (e.g., -R 15 for Rel-15). If not specified, downloads all releases from 15 onwards.")
    parser.add_argument("-T", "--threads", type=int, default=5, help="Number of threads for parallel downloads (default: 5, multi-threaded).")
    parser.add_argument("-v", "--verbose", action='store_true', help="Display verbose content for console (default: INFO).")
    parser.add_argument("-r", "--resume", action='store_true', help="Only use this switch to resume broken downloads and exit. New PDFs will not be downloaded.(default: False).")
    parser.add_argument("-n", "--nodownload", action='store_true', help="Only create links.json and exit without downloads.(default: False).")
    parser.add_argument("-a", "--all", action='store_true', help="Download all versions for the releases from Rel-15 to the latest available release (default: False).")
    args = parser.parse_args()

    main(args)