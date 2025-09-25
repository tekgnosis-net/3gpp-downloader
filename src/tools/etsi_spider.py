# Class for scrapy spider for recursively fetching the pdf links and saving them into the links.json file
import scrapy
import re
import logging
from utils.logging_config import setup_logger
#configure logger
logging_file = 'logs/etsi_spider.log'
logger = setup_logger('etsi_spider', log_file=logging_file)

class EtsiSpider(scrapy.Spider):
    name = 'etsi'
    start_urls = ['https://www.etsi.org/deliver/etsi_ts/']
    # For quick testing, uncomment the line below to limit to series 23 range (has Release 15+ PDFs), then run and check logs/links.json
    # start_urls = ['https://www.etsi.org/deliver/etsi_ts/123500_123599/']


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
            if not (21 <= series_int <= 39):  # Focus on 3GPP series 21-39
                return
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
