"""
json_downloader.py

A small, fully‑async helper that:
    * loads an array of JSON objects (each containing at least the keys url, series, release).
    * downloads every file concurrently.
    * writes each file into a nested tree: <root>/rel-<release>/series-<series>/<basename>.
    * uses HTTP HEAD to check remote size before downloading, so that already‑existing identical files are skipped.
    * creates missing parent directories automatically.
    * optionally reports progress via tqdm.asyncio and allows a callback after each download.

Author: KK (2025‑09‑25)
"""

# ────── Imports ──────
import asyncio
import logging
import os
from pathlib import Path
import json

import aiohttp          # HTTP client
import aiofiles         # async file I/O
from tqdm.asyncio import tqdm_asyncio   # progress bar that works inside an event loop
from utils.logging_config import setup_logger
#configure logger
logging_file = os.getenv('JSON_DOWNLOADER_LOG_FILE', 'logs/json_downloader.log')
logger_name = os.getenv('JSON_DOWNLOADER_LOGGER_NAME', 'json_downloader')
console_level = getattr(logging, os.getenv('JSON_DOWNLOADER_CONSOLE_LEVEL', 'INFO').upper(), logging.INFO)
file_level = getattr(logging, os.getenv('JSON_DOWNLOADER_FILE_LEVEL', 'DEBUG').upper(), logging.DEBUG)
max_bytes = int(os.getenv('JSON_DOWNLOADER_MAX_BYTES', '10485760'))
backup_count = int(os.getenv('JSON_DOWNLOADER_BACKUP_COUNT', '5'))

logger = setup_logger(logger_name, log_file=logging_file, console_level=console_level, logfile_level=file_level, max_bytes=max_bytes, backup_count=backup_count)

__all__ = ["download_from_json"]

# Global connector for connection pooling
_connector = None

def get_connector():
    global _connector
    if _connector is None:
        # Create connector with connection pooling
        _connector = aiohttp.TCPConnector(
            limit=int(os.getenv('HTTP_MAX_CONNECTIONS', '100')),  # Max connections
            limit_per_host=int(os.getenv('HTTP_MAX_CONNECTIONS_PER_HOST', '10')),  # Max connections per host
            ttl_dns_cache=int(os.getenv('HTTP_DNS_CACHE_TTL', '300')),  # DNS cache TTL
            use_dns_cache=os.getenv('HTTP_USE_DNS_CACHE', 'true').lower() == 'true',
            keepalive_timeout=int(os.getenv('HTTP_KEEPALIVE_TIMEOUT', '60')),
            enable_cleanup_closed=os.getenv('HTTP_ENABLE_CLEANUP_CLOSED', 'true').lower() == 'true',
        )
    return _connector

def get_session():
    return aiohttp.ClientSession(
        connector=get_connector(),
        timeout=aiohttp.ClientTimeout(
            total=float(os.getenv('HTTP_TOTAL_TIMEOUT', '300')),
            connect=float(os.getenv('HTTP_CONNECT_TIMEOUT', '10')),
            sock_read=float(os.getenv('HTTP_READ_TIMEOUT', '60'))
        )
    )

async def cleanup():
    """Cleanup the global connector"""
    global _connector
    if _connector:
        await _connector.close()
        _connector = None

# ------------------------------------------------------------------
#  Retry utilities
# ------------------------------------------------------------------
async def retry_with_backoff(func, *args, max_retries=None, base_delay=None, max_delay=None, **kwargs):
    """Retry a function with exponential backoff"""
    if max_retries is None:
        max_retries = int(os.getenv('RETRY_MAX_ATTEMPTS', '5'))
    if base_delay is None:
        base_delay = float(os.getenv('RETRY_BASE_DELAY', '1.0'))
    if max_delay is None:
        max_delay = float(os.getenv('RETRY_MAX_DELAY', '60.0'))

    delay = base_delay
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt == max_retries:
                raise e
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s...")
            await asyncio.sleep(delay)
            delay = min(delay * 2, max_delay)
        except Exception as e:
            # Don't retry for other exceptions
            raise e

# ------------------------------------------------------------------
#  _download_chunk()
# ------------------------------------------------------------------
async def _download_chunk(url, start, end, session):
    logger.debug(f"[download_chunk] Downloading bytes {start}-{end} from {url}")
    headers = {'Range': f'bytes={start}-{end}'}
    
    async def chunk_request():
        async with session.get(url, headers=headers) as resp:
            if resp.status != 206:  # Partial Content
                raise aiohttp.ClientError(f"Range request failed: {resp.status}")
            return await resp.read()
    
    return await retry_with_backoff(chunk_request)

async def _download_and_write_chunk(url, start, end, session, file_handle):
    """Download a chunk and write it directly to the file at the correct position."""
    logger.debug(f"[download_and_write_chunk] Downloading and writing bytes {start}-{end} from {url}")
    headers = {'Range': f'bytes={start}-{end}'}
    
    async def chunk_request():
        async with session.get(url, headers=headers) as resp:
            if resp.status != 206:  # Partial Content
                raise aiohttp.ClientError(f"Range request failed: {resp.status}")
            chunk_data = await resp.read()
            # Seek to the correct position and write
            await file_handle.seek(start)
            await file_handle.write(chunk_data)
            return len(chunk_data)
    
    return await retry_with_backoff(chunk_request)

# ------------------------------------------------------------------
#  _multipart_download()
# ------------------------------------------------------------------
async def _multipart_download(url, dest_path, remote_size, num_chunks=4, session=None, progress_callback=None):
    logger.info(f"[multipart_download] Using multi-part download for {dest_path} with {num_chunks} chunks")
    if session is None:
        session = get_session()
        close_session = True
    else:
        close_session = False
    
    try:
        # Calculate chunk ranges
        chunk_size = remote_size // num_chunks
        ranges = [(i * chunk_size, (i + 1) * chunk_size - 1 if i < num_chunks - 1 else remote_size - 1)
                  for i in range(num_chunks)]

        # Open file for writing
        async with aiofiles.open(dest_path, 'wb') as f:
            # Download and write chunks concurrently
            tasks = []
            downloaded = 0
            lock = asyncio.Lock()  # To synchronize progress updates
            
            async def download_and_write_with_progress(start, end):
                nonlocal downloaded
                chunk_size = await _download_and_write_chunk(url, start, end, session, f)
                async with lock:
                    downloaded += chunk_size
                    if progress_callback:
                        progress_callback(downloaded / remote_size * 100)
            
            for start, end in ranges:
                task = asyncio.create_task(download_and_write_with_progress(start, end))
                tasks.append(task)
            
            # Wait for all chunks to complete
            await asyncio.gather(*tasks)
    finally:
        if close_session:
            await session.close()

# ------------------------------------------------------------------
#  _fetch_and_write()
# ------------------------------------------------------------------
async def _fetch_and_write(
        url: str,
        dest_path: Path,
        *,
        num_chunks: int = 10,
        session=None,
        progress_callback=None,
) -> None:
    """
    Download *url* and store it at *dest_path*.  
    The function will:

      1. Send a HEAD request to get the remote size.
      2. If the file does not exist or its size differs from the remote one,
         perform a GET, otherwise skip.
      3. Create missing parent directories automatically.

    Parameters
    ----------
    url : str
        The absolute or relative URL to fetch.
    dest_path : pathlib.Path
        Full path (including the filename) where the downloaded bytes will be written.
    num_chunks : int, default 4
        Number of chunks to download the file in (for large files).
    session : aiohttp.ClientSession, optional
        Session to use for requests.

    Returns
    -------
    None – all side‑effects happen inside this coroutine.
    """
    if session is None:
        session = get_session()
        close_session = True
    else:
        close_session = False
    
    try:
        # 1️⃣  Ask for the remote size (HEAD) with retry
        async def head_request():
            async with session.head(url) as head_resp:
                if head_resp.status != 200:
                    raise aiohttp.ClientError(f"HEAD {url} returned {head_resp.status}")
                return head_resp
        
        head_resp = await retry_with_backoff(head_request)
        remote_size = int(head_resp.headers.get('Content-Length', 0))
        supports_ranges = head_resp.headers.get('Accept-Ranges', '').lower() == 'bytes'
        # 2️⃣  Make sure the parent folder exists (creates any missing part)
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # 3️⃣  Skip or overwrite depending on local size
        if dest_path.exists():
            local_size = dest_path.stat().st_size
            if local_size == remote_size:
                logger.info(f"[fetch_and_write] Skipping {dest_path} (size matches)")
                return True

        logger.debug(f"[fetch_and_write] Downloading {url} to {dest_path} (remote size: {remote_size} bytes)")
        # 4️⃣  Perform the download: use multipart if supported and file is large enough
        multipart_min_size = int(os.getenv('DOWNLOAD_MULTIPART_MIN_SIZE_MB', '1')) * 1024 * 1024
        if supports_ranges and remote_size > multipart_min_size:
            # Calculate optimal number of chunks based on file size and connection speed
            # Note: aiohttp connector limits concurrent requests per host to 10
            threshold_1 = int(os.getenv('DOWNLOAD_CHUNK_THRESHOLD_1_MB', '5')) * 1024 * 1024
            threshold_2 = int(os.getenv('DOWNLOAD_CHUNK_THRESHOLD_2_MB', '10')) * 1024 * 1024
            threshold_3 = int(os.getenv('DOWNLOAD_CHUNK_THRESHOLD_3_MB', '20')) * 1024 * 1024
            threshold_4 = int(os.getenv('DOWNLOAD_CHUNK_THRESHOLD_4_MB', '50')) * 1024 * 1024
            threshold_5 = int(os.getenv('DOWNLOAD_CHUNK_THRESHOLD_5_MB', '100')) * 1024 * 1024

            if remote_size > threshold_5:
                optimal_chunks = int(os.getenv('DOWNLOAD_CHUNK_COUNT_5', '10'))
            elif remote_size > threshold_4:
                optimal_chunks = int(os.getenv('DOWNLOAD_CHUNK_COUNT_4', '10'))
            elif remote_size > threshold_3:
                optimal_chunks = int(os.getenv('DOWNLOAD_CHUNK_COUNT_3', '8'))
            elif remote_size > threshold_2:
                optimal_chunks = int(os.getenv('DOWNLOAD_CHUNK_COUNT_2', '6'))
            else:
                optimal_chunks = int(os.getenv('DOWNLOAD_CHUNK_COUNT_1', '4'))

            await _multipart_download(url, dest_path, remote_size, optimal_chunks, session, progress_callback)
        else:
            # Fallback to single GET with retry
            async def get_request():
                async with session.get(url) as resp:
                    if resp.status != 200:
                        raise aiohttp.ClientError(f"GET {url} returned {resp.status}")
                    return await resp.read()
            
            data = await retry_with_backoff(get_request)
            async with aiofiles.open(dest_path, "wb") as f:
                await f.write(data)
        logger.info(f"[fetch_and_write] Downloaded {dest_path} ({remote_size} bytes)")
        return True
    except aiohttp.ClientError as e:
        logger.error(f"aiohttp error for {url}: {e}")
        return False
    except RuntimeError as e:
        logger.error(f"Runtime error (e.g., session closed) for {url}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error for {url}: {e}")
        return False
    finally:
        if close_session:
            await session.close()

    return True

# ------------------------------------------------------------------
#  _download_all()
# ------------------------------------------------------------------
async def _download_all(
        items: list[dict],
        base_dir: Path,
        concurrency: int = 4,
        callback=None,
) -> None:
    """
    Kick off all downloads concurrently, but update a tqdm bar after each file finishes.
    The *concurrency* argument limits how many coroutines run in parallel (uses an asyncio.Semaphore internally).
    If *callback* is provided it will be called with the filename and the current percent‑value.

    Parameters
    ----------
    items : list[dict]
        List of JSON objects that contain at least the keys url, series and release.
    base_dir : Path
        Root directory under which the nested tree will be created.
    concurrency : int, default 4
        How many downloads run at once.
    callback : callable | None
        Optional function that will be called after each file finishes.  
        It receives two arguments: (filename, percent_of_100).

    Returns
    -------
    None – side‑effects happen inside this coroutine.
    """
    total_items = len(items)
    if total_items == 0:
        return True

    completed = 0
    processed = 0
    errors = 0

    session = get_session()
    try:
        sem = asyncio.Semaphore(concurrency)
        lock = asyncio.Lock()
        pbar = None

        async def download_item(item):
            nonlocal completed, processed, errors

            url = item["url"]
            series = item.get("series", "0")
            release = item.get("release", "0")
            filename = Path(url).name

            dest_path = (
                base_dir
                / f"rel-{release}"
                / f"series-{series}"
                / filename
            )

            if callback:
                callback(filename, "starting", 0.0)

            try:
                async with sem:
                    def file_progress(pct: float):
                        if callback:
                            callback(filename, "file_progress", pct)

                    success = await _fetch_and_write(
                        url,
                        dest_path,
                        session=session,
                        progress_callback=file_progress,
                    )
            except Exception as exc:
                logger.error(f"Unexpected error downloading {url}: {exc}")
                success = False

            async with lock:
                processed += 1
                if success:
                    completed += 1
                    if callback:
                        callback(filename, "file_complete", 100.0)
                else:
                    errors += 1
                    if callback:
                        callback(filename, "error", 0.0)

                overall_pct = (processed / total_items) * 100 if total_items else 100.0
                if callback:
                    callback("__overall__", "overall_progress", overall_pct)

                if pbar is not None:
                    pbar.update(1)

        with tqdm_asyncio(total=total_items, desc="Downloading") as pbar:
            tasks = [asyncio.create_task(download_item(item)) for item in items]
            await asyncio.gather(*tasks)

        if callback:
            callback("__overall__", "all_finished", 100.0)
            if errors:
                callback("__overall__", "errors", errors)
    finally:
        await session.close()

    return errors == 0

# ------------------------------------------------------------------
#  download_from_json()
# ------------------------------------------------------------------
async def download_from_json(
        src_file: str | Path,
        dest_dir: str | Path = "./downloads/",
        url_key: str = "url",
        series_key: str = "series",
        release_key: str = "release",
        concurrency: int = 10,
        verbose: bool = True,
        progress_callback=None,
) -> bool:
    """
    High‑level helper that glues all the pieces together.

    Parameters
    ----------
    src_file : path to a JSON file (local or remote)
        The JSON must contain an array of objects, each having at least the keys defined by *url_key*, *series_key* and *release_key*.
    dest_dir : directory where every download will be written (root of the tree)
    url_key      : key that holds the URL in each object
    series_key   : key that holds the series number in each object
    release_key  : key that holds the release number in each object
    concurrency   : how many downloads run in parallel
    verbose       : if True, a tqdm progress bar is shown
    progress_callback : callable | None
        Optional function receiving (identifier, status, value).
        Status values:
            - "starting": file download about to begin
            - "file_progress": per-file percentage (value 0-100)
            - "file_complete": file finished successfully (value 100)
            - "error": file failed (value unused)
            - "overall_progress": aggregate percent of processed files
            - "all_finished": all downloads completed (value 100)
            - "errors": number of files that failed

    Returns
    -------
    bool
        True when all downloads succeed, False if any files fail.
    """
    # 1️⃣  Load the JSON file
    src_path = Path(src_file)
    with src_path.open() as f:
        data: list[dict] = json.load(f)

    # 2️⃣  Kick off the async download loop
    if verbose:
        logger.info(f"[json_downloader] → downloading {len(data)} URLs to {dest_dir}")

    return await _download_all(
        items=data,
        base_dir=Path(dest_dir),
        concurrency=concurrency,
        callback=progress_callback,
    )

# ------------------------------------------------------------------
#  Demo / entry point
# ------------------------------------------------------------------
if __name__ == "__main__":
    async def main() -> None:
        # Example usage: load a local JSON file that contains an array of objects
        await download_from_json(
            src_file="manifest.json",
            dest_dir="./downloads/By-Release",
            url_key="url",
            series_key="series",
            release_key="release",
            concurrency=8,
            verbose=True,
            progress_callback=lambda name, status, value: print(f"event={status} target={name} value={value}")
        )

    asyncio.run(main())