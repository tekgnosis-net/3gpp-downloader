# Main script to run the 3GPP downloader
import atexit
from multiprocessing import pool
import os
import re
import sys
import argparse
import json
from pathlib import Path
from threading import Timer
import signal
from tools.etsi_spider import EtsiSpider
from scrapy.crawler import CrawlerProcess
from tools.monitored_pool import MonitoredPoolManager
import logging
from utils.logging_config import setup_logger
import time

#configure logger
logging_file = os.getenv('LOGGING_FILE', 'logs/downloader.log')
logger = setup_logger('downloader', log_file=logging_file)

def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}, exiting gracefully...")
    sys.exit(0)

def print_statistics(stats):
    """
    Print current download statistics
    """
    # Use a static variable to track if it's the initial call
    if not hasattr(print_statistics, "initial_call"):
        print_statistics.initial_call = True
    if print_statistics.initial_call:
        print_statistics.initial_call = False
        logger.info(f"Starting periodic statistics printing every 15 seconds...")
        return    
    # stats is a dictionary with keys: request_count, error_count, error_rate
    # Split the stats into individual variables for clarity
    request_count = stats.get('request_count', 0)
    error_count = stats.get('error_count', 0)
    error_rate = stats.get('error_rate', 0.0)
    logger.info(f"Current download stats: Requests: {request_count}, Errors: {error_count}, Error Rate: {error_rate:.2%}")
    # Log the complete stats dictionary for debugging
    logger.debug(f"Current download stats: {stats}")

def cleanup(pool):
    """
    Cleanup function to clear connection pools at exit
    """
    logger.info(f"Cleaning up HTTPS connection pools at exit...")
    pool.clear()
    logger.info(f"Cleaned up HTTPS connection pools at exit...")

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

    # Group by ts_number
    grouped = {}
    for item in data:
        ts = item['ts_number']
        if ts not in grouped:
            grouped[ts] = []
        grouped[ts].append(item)
    
    # For each group, find the item with the highest version
    filtered = []
    for ts, items in grouped.items():
        # Sort by version, assuming version is like '18.10.00'
        def version_key(item):
            v = item['version']
            return tuple(int(x) for x in v.split('.'))
        
        latest = max(items, key=version_key)
        filtered.append(latest)
    
    # Write to output file
    output_path = Path(output_file)
    with output_path.open('w') as f:
        json.dump(filtered, f, indent=0)
    
    end_time = time.time()
    elapsed = end_time - start_time
    logger.info(f"Filtered {len(data)} items to {len(filtered)} latest versions in {output_file} in {elapsed:.2f} seconds.")
    return True

# Function to invoke the scrapy class and trigger the scraping
def run_scraper(logging_lvl: int = logging.INFO, logfile: str = 'logs/scrapy.log'):
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

    process = CrawlerProcess(settings={
        'FEEDS': {
            'links.json': {'format': 'json', 'overwrite': True}
        },
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'ROBOTSTXT_OBEY': True,
        'CONCURRENT_REQUESTS': 32,  # Increased for speed; reduce if rate-limited
        'LOG_ENABLED': True,
        'LOG_FILE': logfile,
        'LOG_LEVEL': logging_lvl,
        'LOG_FORMAT': default_fmt,
        'LOG_DATEFORMAT': date_fmt,
    })
    # Start the crawling using the EtsiSpider
    process.crawl(EtsiSpider)
    # Measure the time taken for scraping
    start_time = time.time()
    logger.info("Scraping started...")
    process.start()
    end_time = time.time()
    elapsed = end_time - start_time
    logger.info(f"Scraping completed in {elapsed:.2f} seconds.")

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

    if args.verbose:
        logger.setLevel(logging.DEBUG)
    if args.nodownload:
        logger.info("No download mode activated.")
    # Add more logic here as needed to handle downloading based on args
    logger.info(f"Arguments received: {args}")
    # Initialize the monitored pool manager
    pool_manager = MonitoredPoolManager(logging_level=logging.DEBUG if args.verbose else logging.INFO, maxsize=args.threads)
    # Register cleanup function to be called at exit
    atexit.register(cleanup, pool_manager)
    # set up periodic statistics printing every 15 seconds
    stats_timer = Timer(15, print_statistics, args=(pool_manager.get_stats(),))
    stats_timer.start()
    # Ensure the timer is cancelled at exit
    atexit.register(stats_timer.cancel)
    # Log initial stats
    print_statistics(pool_manager.get_stats())
    # set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)



    try:
        run_scraper(logging_lvl=logging.DEBUG if args.verbose else logging.INFO)
    except Exception as e:
        logger.error(f"Error running scraper: {e}")
    
    # After scraping, filter to keep only the latest versions
    if not args.all:
        if filter_latest_versions(input_file='links.json', output_file='latest.json'):
            logger.info("Filtered to latest versions successfully.")
        else:
            logger.error("Failed to filter to latest versions.")
    else:
        logger.info("Downloading all versions as per --all flag; skipping filtering.")

    # After scraping, if nodownload is not set, proceed to download
    if not args.nodownload:
        logger.info("Starting download process...")
        # Placeholder for download logic
        # You would typically read links.json and start downloading PDFs here
        # For now, just log that the download would start
        logger.info("Download process completed.")

    stats_timer.cancel()

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