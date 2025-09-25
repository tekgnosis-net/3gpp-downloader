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
        # Execute the web app module to register pages
        print("📦 Executing web_app module...")
        import runpy
        runpy.run_module('web_app', run_name='__main__')
        print("✅ Web app module executed successfully")

        print("🚀 Starting 3GPP Downloader Web UI...")
        print("📱 Open your browser to: http://localhost:32123")
        print("💡 When running with Docker, use: http://localhost:8081")
        print("❌ Press Ctrl+C to stop the server")

        # Use the proper Mesop server setup with static file serving
        from mesop.server.server import configure_flask_app
        from mesop.server.static_file_serving import configure_static_file_serving
        from mesop.server.constants import PROD_PACKAGE_PATH

        print("🚀 Starting 3GPP Downloader Web UI...")
        print("📱 Open your browser to: http://localhost:32123")
        print("💡 When running with Docker, use: http://localhost:8081")
        print("❌ Press Ctrl+C to stop the server")

        # Create the Flask app with proper configuration
        flask_app = configure_flask_app(prod_mode=False)

        # Configure static file serving for the Mesop web assets
        configure_static_file_serving(
            flask_app,
            static_file_runfiles_base=PROD_PACKAGE_PATH,
            disable_gzip_cache=False,
        )

        # Run the app
        flask_app.run(host="0.0.0.0", port=32123, use_reloader=False)

    except ImportError as e:
        print(f"❌ Error: {e}")
        print("💡 Please install dependencies: pip install -r requirements.txt")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Shutting down web server...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print("💡 Available mesop methods:")
        try:
            import mesop as me
            print(f"   {[attr for attr in dir(me) if not attr.startswith('_')]}")
        except:
            print("   Unable to inspect mesop module")
        sys.exit(1)

if __name__ == "__main__":
    main()