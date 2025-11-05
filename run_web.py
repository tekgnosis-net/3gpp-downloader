#!/usr/bin/env python3
"""Run the 3GPP Downloader Web UI backed by FastAPI and Chakra UI."""

import os
import sys
from pathlib import Path

import uvicorn

# Add src to path so `api.server` resolves when executed directly
sys.path.insert(0, str(Path(__file__).parent / "src"))


def main() -> None:
    """Launch the FastAPI server that serves both API and SPA assets."""
    host = os.getenv("WEB_HOST", "0.0.0.0")
    port = int(os.getenv("WEB_PORT", "32123"))

    # Import lazily so the insert above is definitely applied
    try:
        from api.server import app  # type: ignore
    except ImportError as exc:
        print(f"❌ Failed to import FastAPI application: {exc}")
        print("💡 Have you run `pip install -r requirements.txt`?")
        sys.exit(1)

    print("🚀 Starting 3GPP Downloader API + Chakra UI server...")
    print(f"📱 Open your browser to: http://localhost:{port}")
    print("❌ Press Ctrl+C to stop the server")

    try:
        uvicorn.run(app, host=host, port=port, log_level=os.getenv("UVICORN_LOG_LEVEL", "info"))
    except KeyboardInterrupt:
        print("\n👋 Shutting down web server...")
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"❌ Unexpected server error: {exc}")
        sys.exit(1)

if __name__ == "__main__":
    main()