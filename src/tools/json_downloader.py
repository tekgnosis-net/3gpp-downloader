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
from pathlib import Path
import json

import aiohttp          # HTTP client
import aiofiles         # async file I/O
from tqdm.asyncio import tqdm_asyncio   # progress bar that works inside an event loop
from utils.logging_config import setup_logger
#configure logger
logging_file = 'logs/json_downloader.log'
logger = setup_logger('json_downloader', log_file=logging_file)

__all__ = ["download_from_json"]

# ------------------------------------------------------------------
#  _fetch_and_write()
# ------------------------------------------------------------------
async def _fetch_and_write(
        url: str,
        dest_path: Path,
        *,
        overwrite_if_diff: bool = True,   # keep this flag for future extensions
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
    overwrite_if_diff : bool, default True
        If True, a download is performed only when either the file does not exist or its size differs from the remote one.

    Returns
    -------
    None – all side‑effects happen inside this coroutine.
    """
    # 1️⃣  Ask for the remote size (HEAD)
    async with aiohttp.ClientSession() as session:
        head_resp = await session.head(url)          # ← only headers are fetched
        remote_size = int(head_resp.headers['Content-Length'])

    # 2️⃣  Make sure the parent folder exists (creates any missing part)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # 3️⃣  Skip or overwrite depending on local size
    if dest_path.exists():
        local_size = dest_path.stat().st_size
        if local_size == remote_size:
            logger.info(f"[fetch_and_write] Skipping {dest_path} (size matches)")
            return

    logger.debug(f"[fetch_and_write] Downloading {url} to {dest_path} (remote size: {remote_size} bytes)")
    # 4️⃣  Perform the real GET and write to disk
    async with session.get(url) as resp:
        data = await resp.read()

    async with aiofiles.open(dest_path, "wb") as f:
        await f.write(data)

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
    # Create a semaphore that will allow *concurrency* tasks at once
    sem = asyncio.Semaphore(concurrency)

    with tqdm_asyncio(total=len(items), desc="Downloading") as pbar:
        for idx, item in enumerate(items):
            url   = item["url"]
            series = item.get("series", "0")
            release = item.get("release","0")

            # Build the destination path
            dest_path = (
                base_dir
                / f"rel-{release}"
                / f"series-{series}"
                / Path(url).name
            )
            # Start the download within the semaphore context
            if callback:
                callback(Path(url).name, "starting", 0)
            async with sem:
                await _fetch_and_write(url, dest_path)
                # Call the optional callback
                if callback:
                    callback(Path(url).name, "progress", int((idx + 1) / len(items) * 100))
                pbar.update(1)
            if callback:
                callback(Path(url).name, status="finished", percent=100)

# ------------------------------------------------------------------
#  download_from_json()
# ------------------------------------------------------------------
async def download_from_json(
        src_file: str | Path,
        dest_dir: str | Path = "./downloads/",
        url_key: str = "url",
        series_key: str = "series",
        release_key: str = "release",
        concurrency: int = 8,
        verbose: bool = True,
        progress_callback=None,
) -> None:
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
        Optional function that will receive (filename, status, percent_of_100)
        Example: lambda fn,pct: print(f"✓ {fn} finished at {pct}%")

    Returns
    -------
    None – all side‑effects happen inside this coroutine.
    """
    # 1️⃣  Load the JSON file
    src_path = Path(src_file)
    with src_path.open() as f:
        data: list[dict] = json.load(f)

    # 2️⃣  Kick off the async download loop
    if verbose:
        logger.info(f"[json_downloader] → downloading {len(data)} URLs to {dest_dir}")

    await _download_all(
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
            progress_callback=lambda fn,pct: print(f"✓ {fn} finished at {pct}%")
        )

    asyncio.run(main())