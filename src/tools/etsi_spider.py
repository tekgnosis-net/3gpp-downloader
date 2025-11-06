# Class for scrapy spider for recursively fetching the pdf links and saving them into the links.json file
import scrapy
import re
import logging
import os
from utils.logging_config import setup_logger

try:
    from api.extensions.scrape_progress import EXTENSION_PATH as PROGRESS_EXTENSION
except Exception:  # pragma: no cover - defensive import guard
    PROGRESS_EXTENSION = None
#configure logger
logging_file = os.getenv('ETSI_SPIDER_LOG_FILE', 'logs/etsi_spider.log')
logger_name = os.getenv('ETSI_SPIDER_LOGGER_NAME', 'etsi_spider')
console_level = getattr(logging, os.getenv('ETSI_SPIDER_CONSOLE_LEVEL', 'INFO').upper(), logging.INFO)
file_level = getattr(logging, os.getenv('ETSI_SPIDER_FILE_LEVEL', 'DEBUG').upper(), logging.DEBUG)
max_bytes = int(os.getenv('ETSI_SPIDER_MAX_BYTES', '10485760'))
backup_count = int(os.getenv('ETSI_SPIDER_BACKUP_COUNT', '5'))

logger = setup_logger(logger_name, log_file=logging_file, console_level=console_level, logfile_level=file_level, max_bytes=max_bytes, backup_count=backup_count)

class EtsiSpider(scrapy.Spider):
    name = 'etsi'
    start_urls = os.getenv('ETSI_START_URLS', 'https://www.etsi.org/deliver/etsi_ts/').split(',')

    # Custom settings for the spider
    extension_settings = {
        'DOWNLOAD_DELAY': float(os.getenv('SCRAPY_DOWNLOAD_DELAY', '0.1')),
        'CONCURRENT_REQUESTS_PER_DOMAIN': int(os.getenv('SCRAPY_CONCURRENT_REQUESTS_PER_DOMAIN', '8')),
        'USER_AGENT': os.getenv('SCRAPY_USER_AGENT', '3gpp-downloader/1.0'),
    }
    if PROGRESS_EXTENSION:
        extension_settings.update(
            {
                'EXTENSIONS': {
                    PROGRESS_EXTENSION: 10,
                }
            }
        )

    custom_settings = extension_settings


    def parse(self, response):
        logger.debug(f'Parsing root: {response.url}')
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
        logger.debug(f'Parsing range from: {response.url}')
        # Adjusted regex to match the pattern after a specific path
        pattern = r'\d{6}/$'
        for href in response.xpath('//a/@href').getall():
            if href.endswith('/') and re.search(pattern, href): #re.match(r'\d{6}/', href):
                logger.debug(f'Found TS dir: {href}')
                yield response.follow(href, callback=self.parse_ts)

    def parse_ts(self, response):
        logger.debug(f'Parsing 3GPP TS from: {response.url}')
        ts_dir = response.url.rstrip('/').split('/')[-1]  # e.g., '123501'
        if len(ts_dir) != 6 or not ts_dir.isdigit():
            return
        series = ts_dir[1:3]
        try:
            series_int = int(series)
            focus_series = os.getenv('ETSI_FOCUS_SERIES', '21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39')
            if focus_series:
                allowed_series = [int(s.strip()) for s in focus_series.split(',')]
                if series_int not in allowed_series:
                    return
            else:
                # If no focus series specified, allow all
                pass
        except ValueError:
            logger.error(f'Invalid TS dir: {ts_dir}')
            return
        ts_number = f'{series}.{ts_dir[3:]}'  # e.g., '23.501'
        logger.debug(f'Processing TS: {ts_number} (series: {series})')
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
                        min_release = int(os.getenv('ETSI_MIN_RELEASE', '15'))
                        if major >= min_release:
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
        logger.debug(f'Parsing version from: {response.url}')
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
