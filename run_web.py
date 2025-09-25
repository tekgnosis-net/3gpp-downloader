#!/usr/bin/env python3
"""
Run the 3GPP Downloader Web UI
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def main():
    """Main entry point for the web application"""
    try:
        import mesop as me
        from web_app import main_page

        print("🚀 Starting 3GPP Downloader Web UI...")
        print("📱 Open your browser to: http://localhost:32123")
        print("❌ Press Ctrl+C to stop the server")

        # Start the Mesop web server
        me.run()

    except ImportError as e:
        print(f"❌ Error: {e}")
        print("💡 Please install dependencies: pip install -r requirements.txt")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Shutting down web server...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()