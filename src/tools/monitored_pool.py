# Class for a monitored HTTPS connection pool with cleanup

from typing import Any
from urllib3 import PoolManager

from urllib3.util import Retry, Timeout
import logging
import os
from pathlib import Path
from utils.logging_config import setup_logger

#configure logger
logging_file = os.getenv('LOGGING_FILE', 'downloader.log')
logger = setup_logger('downloader', log_file=logging_file)

class MonitoredPoolManager:
    """
    A monitored HTTPS connection pool manager with cleanup capabilities.
    This class wraps around urllib3's PoolManager to provide monitoring of requests and errors,
    along with automatic retries and timeout handling.

    Args:
        base_url (str): The base URL for the connection pool. Default is 'https://www.etsi.org/deliver/etsi_ts/'.
    """

    def __init__(self, base_url: str = 'https://www.etsi.org/deliver/etsi_ts/', logging_level: int = logging.INFO, timeout: float = 30.0, maxsize: int = 15, retries: Retry = None):
        self.base_url = base_url # Base URL for requests
        self.timeout = timeout
        self.maxsize = maxsize
        self.retries = retries if retries else Retry(total=5, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
        self.logging_level = logging_level
        
        logger.setLevel(self.logging_level)

        logger.debug(f'Initializing MonitoredPoolManager with base_url: {self.base_url}, timeout: {self.timeout}, maxsize: {self.maxsize}, retries: {self.retries}')
        if not self.base_url.startswith('https') and not self.base_url.startswith('http'):
            logger.error(f"Invalid base_url: {self.base_url}")
            raise ValueError("Base URL must start with http or https")

        # Initialize the PoolManager with retries and timeout
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

    def request(self, method: str, url: str, **kwargs) -> Any:
        """
        Make a request using the connection pool and monitor requests and errors.
        Args:
            method (str): HTTP method (e.g., 'GET', 'POST').
            url (str): The URL to make the request to. If None, uses the base_url.
            **kwargs: Additional arguments to pass to the request method.
        Returns:
            The response object from the request.
        """
        self.request_count += 1
        if not url:
            url = self.base_url
        
        try:
            response = self.http.request(method, url, **kwargs)
            logger.debug(f"{method} {url}: {response.status}")
            return response
        except Exception as e:
            self.error_count += 1
            logger.error(f"{method} {url}: failed {e}")
            raise
        finally:
            logger.debug(f"Total requests: {self.request_count}, Total errors: {self.error_count}")

    def get_stats(self) -> dict:
        """
        Get statistics about the connection pool usage.
        Returns:
            dict: A dictionary containing request_count, error_count, and error_rate.
        """
        return {
            'request_count': self.request_count,
            'error_count': self.error_count,
            'error_rate': self.request_count / max(self.error_count, 1)
        }

    def clear(self):
        """
        Clear the connection pool and reset statistics.
        """
        logger.debug(f'Safe cleaning pools from class...')
        self.http.clear()
        self.request_count = 0
        self.error_count = 0
        logger.debug(f'Cleaned up connection pools from class...')