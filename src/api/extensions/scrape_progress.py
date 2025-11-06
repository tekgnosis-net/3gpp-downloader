"""Scrapy extension to emit runtime progress updates to the state manager."""
from __future__ import annotations

import threading
from typing import Callable, Dict, Optional

from scrapy import signals
from scrapy.crawler import Crawler

from ..state_manager import state_manager


class ScrapeProgressExtension:
    """Tracks scrapy spider activity and updates the shared progress state."""

    def __init__(self, crawler: Crawler) -> None:
        self.crawler = crawler
        self.items_scraped = 0
        self.requests_scheduled = 0
        self.responses_received = 0
        self.lock = threading.Lock()
        callback = crawler.settings.get("SCRAPE_PROGRESS_CALLBACK")
        self.progress_callback: Optional[Callable[[float, Dict[str, int]], None]] = callback
        crawler.signals.connect(self.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(self.request_scheduled, signal=signals.request_scheduled)
        crawler.signals.connect(self.response_received, signal=signals.response_received)
        crawler.signals.connect(self.item_scraped, signal=signals.item_scraped)
        crawler.signals.connect(self.spider_closed, signal=signals.spider_closed)

    def _emit(self, progress: float) -> None:
        if self.progress_callback:
            snapshot: Dict[str, int] = {
                "items": self.items_scraped,
                "requests": self.requests_scheduled,
                "responses": self.responses_received,
            }
            try:
                self.progress_callback(float(progress), snapshot)
            except Exception:  # pragma: no cover - defensive callback guard
                pass

    def _update_progress(self, target: float, message: Optional[str] = None) -> None:
        current = float(state_manager.scraping_progress or 0.0)
        progress = max(current, target)
        state_manager.set_scraping_status("running", progress, message)
        self._emit(progress)

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> "ScrapeProgressExtension":
        return cls(crawler)

    def spider_opened(self, spider) -> None:  # pragma: no cover - requires runtime
        with self.lock:
            self.items_scraped = 0
            self.requests_scheduled = 0
            self.responses_received = 0
        self._update_progress(5.0, "Crawler initialised")

    def request_scheduled(self, request, spider) -> None:  # pragma: no cover - requires runtime
        with self.lock:
            self.requests_scheduled += 1
            queued = self.requests_scheduled
            # Estimate total work based on expected dataset (~13k docs)
            expected_total = 13000
            fraction = min(queued / expected_total, 1.0)
            progress = 5.0 + fraction * 30.0
        dynamic_message = None
        if queued % 500 == 0:
            dynamic_message = f"Scheduled {queued} requests"
        self._update_progress(progress, dynamic_message)

    def response_received(self, response, request, spider) -> None:  # pragma: no cover - requires runtime
        with self.lock:
            self.responses_received += 1
            expected_total = 13000
            fraction = min(self.responses_received / expected_total, 1.0)
            progress = 35.0 + fraction * 30.0
        dynamic_message = None
        if self.responses_received % 500 == 0:
            dynamic_message = f"Processed {self.responses_received} responses"
        self._update_progress(progress, dynamic_message)

    def item_scraped(self, item, spider) -> None:  # pragma: no cover - requires runtime
        with self.lock:
            self.items_scraped += 1
            baseline = 13000
            fraction = min(self.items_scraped / baseline, 1.0)
            progress = 65.0 + fraction * 25.0
        dynamic_message = None
        if self.items_scraped % 250 == 0:
            dynamic_message = f"Discovered {self.items_scraped} items"
        self._update_progress(progress, dynamic_message)

    def spider_closed(self, spider, reason) -> None:  # pragma: no cover - requires runtime
        # Leave final status adjustments to the caller once files are loaded.
        self._update_progress(85.0, "Crawler finished")


EXTENSION_PATH = "api.extensions.scrape_progress.ScrapeProgressExtension"
