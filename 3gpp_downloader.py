#!/usr/bin/env python3
from typing import Any

import requests
from bs4 import BeautifulSoup
import os
import time
import argparse
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import signal
import sys
import logging
#import threading
import re
import humanize
from requests.adapters import HTTPAdapter
from urllib3 import HTTPSConnectionPool, PoolManager, Retry, Timeout
from urllib.parse import urljoin
from pathlib import Path
import scrapy
import json
from scrapy.crawler import CrawlerProcess
import atexit

# Global definitions
global executor
logging_file = 'downloader.log'
output_release = True
resume_file = 'links.json'
thread_count = 5
base_host = 'www.etsi.org'
base_url = 'https://www.etsi.org/deliver/etsi_ts/'
logger = logging.getLogger()
# Configure retry strategy
retry_strategy = Retry(
    total = 5,  # Total number of retries
    backoff_factor = 0.5,  # Factor for exponential backoff (e.g., 0s, 1s, 2s)
    status_forcelist = [429, 500, 502, 503, 504],  # Status codes to retry on
    #allowed_methods = ["GET"],  # HTTP methods to retry
)


# Class for a monitored HTTPS connection pool with cleanup
class MonitoredPoolManager:
    def __init__(self): #, url, timeout=30.0, maxsize=15, retries=retry_strategy):
        #self.pool = HTTPSConnectionPool(url, timeout=timeout, maxsize=maxsize, retries=retries)
        self.http = PoolManager(
            num_pools = 50,
            maxsize=100,
            block=False,
            retries=Retry(
                total=5,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504]
            ),
            timeout=Timeout(connect=10.0, read=60.0)
        )
        self.request_count = 0
        self.error_count = 0

    def request(self, method, url=base_url, **kwargs):
        self.request_count += 1
        try:
            response = self.http.request(method, url, **kwargs)
            logger.debug(f"{method} {url}: {response.status}")
            return response
        except Exception as e:
            self.error_count += 1
            logger.error(f"{method} {url}: failed {e}")
            raise

    def get_stats(self):
        return {
            'request_count': self.request_count,
            'error_count': self.error_count,
            'error_rate': self.request_count / max(self.error_count, 1)
        }

    def clear(self):
        logger.debug(f'Safe cleaning pools from class...')
        self.http.clear()
    #    self.pool.clear()


# Class for scrapy spider for recursively fetching the pdf links and saving them into the links.json file
class EtsiSpider(scrapy.Spider):
    name = 'etsi'
    start_urls = ['https://www.etsi.org/deliver/etsi_ts/']
    # For quick testing, uncomment the line below to limit to series 23 range (has Release 15+ PDFs), then run and check logs/links.json
    # start_urls = ['https://www.etsi.org/deliver/etsi_ts/123500_123599/']

    def parse(self, response):
        logger.info(f'Parsing root: {response.url}')
        # Adjusted regex to match the pattern after a specific path
        pattern = r'/\d{6}_\d{6}/$'
        for href in response.xpath('//a/@href').getall():
            logger.debug(f'href: {href}')
            if href.endswith('/') and re.search(pattern, href): #re.match(r'\d{6}_\d{6}/', href): #
                logger.debug(f'Found range dir: {href}')
                yield response.follow(href, callback=self.parse_range)
            else:
                continue

    def parse_range(self, response):
        logger.info(f'Parsing range from: {response.url}')
        # Adjusted regex to match the pattern after a specific path
        pattern = r'\d{6}/$'
        for href in response.xpath('//a/@href').getall():
            if href.endswith('/') and re.search(pattern, href): #re.match(r'\d{6}/', href):
                logger.debug(f'Found TS dir: {href}')
                yield response.follow(href, callback=self.parse_ts)

    def parse_ts(self, response):
        logger.info(f'Parsing 3GPP TS from: {response.url}')
        ts_dir = response.url.rstrip('/').split('/')[-1]  # e.g., '123501'
        if len(ts_dir) != 6 or not ts_dir.isdigit():
            return
        series = ts_dir[1:3]
        try:
            series_int = int(series)
            if not (21 <= series_int <= 39):  # Focus on 3GPP series 21-39
                return
        except ValueError:
            return
        ts_number = f'{series}.{ts_dir[3:]}'  # e.g., '23.501'
        self.logger.info(f'Processing TS: {ts_number} (series: {series})')
        # Adjusted regex to match the pattern after a specific path
        pattern = r'\d{1,2}\.\d{1,2}\.\d{1,2}_\d{2}/$'
        for href in response.xpath('//a/@href').getall():
            if href.endswith('/') and re.search(pattern, href): #re.match(r'\d{1,2}\.\d{1,2}\.\d{1,2}_\d{2}/', href):
                version_str = href[:-1]  # e.g., '18.10.00_60'
                logger.debug(f'Version string: {version_str}')
                if '_' in version_str:
                    v_part = version_str.split('/')[5][0:8] #version_str.split('_')[0]  # '18.10.00'
                    logger.debug(f'Version part: {v_part}')
                    parts = v_part.split('.')
                    if len(parts) == 3:
                        major, minor, editorial = map(int, parts)
                        if major >= 15:
                            meta = {
                                'series': series,
                                'release': major,
                                'version': f'{major}.{minor}.{editorial}',
                                'ts_number': ts_number
                            }
                            logger.debug(f'Found version dir: {href} (release: {major})')
                            yield response.follow(href, callback=self.parse_version, meta=meta)

    def parse_version(self, response):
        meta = response.meta
        logger.info(f'Parsing version from: {response.url}')
        for href in response.xpath('//a/@href').getall():
            if href.endswith('.pdf'):
                pdf_url = response.urljoin(href)
                logger.debug(f'Found PDF: {pdf_url}')
                item = {
                    'url': pdf_url,
                    'series': meta['series'],
                    'release': meta['release'],
                    'ts_number': meta['ts_number'],
                    'version': meta['version']
                }
                yield item

# Function to invoke the scrapy class and trigger the scraping
def run_scraper():
    """
    Function to invoke the scrapy class and trigger the scraping
    """
    logger.info(f"Starting scraper for the links...")
    process = CrawlerProcess(settings={
        'FEEDS': {
            'links.json': {'format': 'json', 'overwrite': True}
        },
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'ROBOTSTXT_OBEY': True,
        'CONCURRENT_REQUESTS': 32,  # Increased for speed; reduce if rate-limited
        'LOG_ENABLED': True,
        'LOG_FILE': 'scrapy.log',
        'LOG_LEVEL': 'DEBUG',
        'LOG_FORMAT': '%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
    })
    process.crawl(EtsiSpider)
    process.start()

def download_file(item, https, out_file = 'By-Releases', num_threads=4):
    """
    Function to download the pdf file in one go or as multithreaded chunked way if over 5MB
    """
    url = item['url']
    series = item['series']
    release = item['release']
    filename = url.split('/')[-1]
    logger.debug(f'Downloading file: {filename}')
    #dir_path = down_to
    if output_release:
        dir_path = os.path.join(f"{out_file}", f"Rel-{release}", f"Series-{series}")
        logger.debug(f'Saving to: {dir_path}')
    else:
        dir_path = os.path.join(f"{out_file}", f"Series-{series}")
        logger.debug(f'Saving to: {dir_path}')
    #dir_path = os.path.join(f'series-{series}', f'release-{release}')
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, filename)

    try:
        head = https.request("HEAD", url) #, allow_redirects=True, timeout=10)
        #head = https.request.head(allow_redirects = True, timeout = 10)
        #head.raise_for_status()
        size = int(head.headers['Content-length'])
        if size == 0:
            logger.info(f'Unknown size for {url}, skipping')
            return
        if os.path.exists(file_path):
            if os.path.getsize(file_path) == size:
                logger.debug(f'Skipping existing file: {file_path}')
                return
        disp_file_size = humanize.naturalsize(size)
        logger.debug(f"{url} size: {disp_file_size}")

        if size <= 5 * 1024 * 1024:
            start_time = time.time()
            r = https.request("GET", url) #, stream=True, timeout=30)
            #r.raise_for_status()
            with open(file_path, 'wb') as f:
                #for chunk in r.data: #read(8192): #r.iter_content(chunk_size=8192):
                #    f.write(chunk)
                f.write(r.data)
            end_time = time.time() - start_time
            logger.info(f'Downloaded (simple): {file_path} - {disp_file_size} in {end_time} seconds')
        else:
            if 'Accept-Ranges' not in head.headers: # or head.getheader('Accept-Ranges') != 'bytes':
                logger.warning(f'No range support for {url}, fallback download')
                start_time = time.time()
                r = request("GET", url) #, stream=True, timeout=30)
                #r.raise_for_status()
                with open(file_path, 'wb') as f:
                    #for chunk in r.data: #read(8192):
                    #    f.write(chunk)
                    f.write(r.data)
                end_time = time.time() - start_time
                logger.info(f'Downloaded (fallback): {file_path} = {disp_file_size} in {end_time} seconds')
                return
            chunk_size = size // num_threads
            ranges = []
            start = 0
            for i in range(num_threads):
                end = start + chunk_size - 1 if i < num_threads - 1 else size - 1
                ranges.append((start, end))
                start = end + 1


            def download_chunk(start, end, idx):
                headers = {'Range': f'bytes={start}-{end}'}
                r = https.request("GET", url, headers=headers) #, stream=True, timeout=30)
                #r.raise_for_status()
                return idx, r.data
            chunks = [None] * num_threads

            start_time = time.time()
            pbar = tqdm(total = size, unit = 'B', unit_scale = True, unit_divisor = chunk_size,
                        desc = os.path.basename(file_path))
            with ThreadPoolExecutor(max_workers=num_threads) as executor:
                futures = [executor.submit(download_chunk, s, e, i) for i, (s, e) in enumerate(ranges)]
                for future in as_completed(futures):
                    idx, content = future.result()
                    chunks[idx] = content
                    pbar.update(chunk_size)
            pbar.close()

            with open(file_path, 'wb') as f:
                for chunk in chunks:
                    f.write(chunk)

            end_time = time.time() - start_time
            logger.info(f'Downloaded (multi-threaded): {file_path} - {disp_file_size} in {end_time} seconds')
    except KeybooardInterrupt as e:
        logger.error(f"{e}: Shutting down threads...")
        executor.shutdown(wait=False)
    except requests.exceptions.RequestException as e:
        print(f'Network error for {url}: {e}')
    except Exception as e:
        print(f'Error for {url}: {e}')

def download_all(json_items, sessions, output = 'By-Releases', max_concurrent_downloads=5):
    #if not os.path.exists('links.json'):
    #    logger.info(f"links.json not found. Run scraper first.")
    #    return
    #with open('links.json', 'r') as f:
    #    items = json.load(f)
    logger.info(f"Starting download/update process...")
    if not json_items:
        logger.warning(f"No items in links.json! Check scrape logs for issues!")
        return

    with ThreadPoolExecutor(max_workers=max_concurrent_downloads) as executor:
        try:
            futures = [executor.submit(download_file, item, sessions, output, max_concurrent_downloads) for item in json_items]
            for future in as_completed(futures):
                future.result()
        except KeyBoardInterrupt:
            logger.error(f"Keyboard interrupt, shutting down threads...")
            executor.shutdown(wait=False)

def resume_download(links_items, sessions, output_path, num_connections):
    logger.info(f"Resuming downloads...")
    download_all(links_items, sessions, output_path, num_connections)

def cleanup(http_conns):
    http_conns.clear()
    logger.info(f"Cleaned up HTTPS connection pools at exit...")

def main(args):
    print(f"\n\n")


    # Setup logger
    logger.setLevel(logging.DEBUG)

    # File handler
    file_handler = logging.FileHandler(logging_file, mode='w')
    file_handler.setLevel(logging.DEBUG)  # Always log to file with maximum debug info, perhaps optimize to follow option switches?
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(threadName)s - %(levelname)s - [%(lineno)d] - %(message)s'))
    logger.addHandler(file_handler)

    # Console handler
    console_logging = logging.INFO
    if args.verbose:  # Deal with verbose console output
        console_logging = logging.DEBUG
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_logging)
    console_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(threadName)s - %(levelname)s - [%(lineno)d] - %(message)s'))
    logger.addHandler(console_handler)

    def signal_handler(sig, frame):
        #global executor
        logger.warning("\nInterrupted! Shutting thread down pool...please wait!")
        #executor.shutdown(wait=True, cancel_futures=True)
        logger.warning("\nInterrupted! Shutting down...")
        #if https_conns:
        #    https_conns.clear()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Check for output organisation
    if args.series:
        output_to: Any = "By-Series"
        output_release = False
    else:
        output_to = "By-Releases"
        output_release = True

    logger.info(f"Starting up...")
    logger.info(f"Organising 3GPP specs by {output_to}")
    thread_count = args.threads
    logger.info(f"Will use {thread_count} threads for processing downloads.\n")
    # Creating a HTTP connection pool 3 times the threads to be used for efficient reuse of connections
    http = MonitoredPoolManager() #base_url, maxsize = thread_count * 3 )
    atexit.register(cleanup, http)
    logger.info(f"Checking if scraped links resume file exists to resume downloads first...")
    # Check for existing links.json - indicates broken downloads.
    # Attempt to download from the links.json first and based on the resume option, continue or exit
    json_file = Path(resume_file)
    json_check = False
    if json_file.exists():
        output_overload = "By-Release"
        with json_file.open(mode='r') as f:
            json_items = json.load(f)
        if json_items:
            resume_download(json_items, http, output_overload, thread_count)
            json_file.unlink(missing_ok = True)  # File has been used, delete it
            json_check = True
        else:
            logger.info(f"No links found, nothing to resume...")
            json_file.unlink(missing_ok = True)  # File is useless, so delete it.
            json_check = True
    else:
        json_check = True

    if args.resume:
        logger.info(f"Resumed download processing finished, exiting. Try again for updates.")
        sys.exit(0)

    logger.info(f"\nDownloading/updating using Base URL: {base_url}")
    run_scraper()
    logger.info(f"Scraping complete...")

    if args.nodownload:
        logger.info(f"No download, exiting...")
        sys.exit(0); # test


    json_file = Path(resume_file)
    if not json_file.exists():
        logger.warning(f"No links found from scrape, please check debug logs! Exiting!")
        sys.exit(1)
    with json_file.open(mode='r') as f:
        json_items = json.load(f)

    download_all(json_items, https_conns, output_to, thread_count)
    http.clear();


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description='Download 3GPP specs PDFs for a specific release or all releases from Rel-15 onwards. \nDownloaded PDF is organised into directory named By-Releases (default) or By-Series. \n© Kumar Kadatoka\n',
        epilog='')
    #parser.add_argument('output_type', choices=['release', 'series'], nargs='?', default='release', help="The output structure type to save the downloaded PDFs, organized under release or series subdirectories.[default: release]")
    parser.add_argument("-S", "--series", action="store_true", help="Download into series ordered directories. (default: release ordered directories)")
    parser.add_argument("-R", "--release", type=int, default=None, help="The 3GPP release number (e.g., -R 15 for Rel-15). If not specified, downloads all releases from 15 onwards.")
    parser.add_argument("-T", "--threads", type=int, default=5, help="Number of threads for parallel downloads (default: 5, multi-threaded).")
    parser.add_argument("-v", "--verbose", action='store_true', help="Display verbose content for console (default: INFO).")
    parser.add_argument("-r", "--resume", action='store_true', help="Only use this switch to resume broken downloads and exit. New PDFs will not be downloaded.")
    parser.add_argument("-n", "--nodownload", action='store_true', help="Only create links.json and exit without downloads.")
    args = parser.parse_args()

    main(args)