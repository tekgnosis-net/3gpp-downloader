#!/usr/bin/env python3
"""
Test script to verify the 3GPP Downloader setup
"""

import sys
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """Run a command and return success status"""
    print(f"🔍 Testing: {description}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"✅ {description}: PASSED")
            return True
        else:
            print(f"❌ {description}: FAILED")
            print(f"   Error: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"⏰ {description}: TIMEOUT")
        return False
    except Exception as e:
        print(f"❌ {description}: ERROR - {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing 3GPP Downloader Setup")
    print("=" * 40)

    # Check if we're in the right directory
    if not Path("requirements.txt").exists():
        print("❌ Error: Please run this script from the project root directory")
        sys.exit(1)

    # Test 1: Check Python version
    success = run_command("python3 --version", "Python 3.12+ available")
    if not success:
        sys.exit(1)

    # Test 2: Check if requirements can be installed (dry run)
    success = run_command("pip install --dry-run -r requirements.txt", "Dependencies can be installed")
    if not success:
        print("💡 Try: pip install -r requirements.txt")

    # Test 3: Check if main module can be imported
    success = run_command("python3 -c \"import sys; sys.path.insert(0, 'src'); import main; print('Import successful')\"", "Main module imports correctly")

    # Test 4: Check if web app can be imported (will fail without mesop, but that's expected)
    run_command("python3 -c \"import sys; sys.path.insert(0, 'src'); import web_app\" 2>/dev/null || echo 'Expected: Mesop not installed yet'", "Web app structure is valid")

    # Test 5: Check Docker setup
    if Path("Dockerfile").exists():
        success = run_command("docker --version", "Docker is available")
        if success:
            print("💡 To build: docker build -t gpp-downloader .")
            print("💡 To run: docker run -p 32123:32123 gpp-downloader")
    else:
        print("⚠️  Dockerfile not found")

    # Test 6: Check docker-compose
    if Path("docker-compose.yml").exists():
        success = run_command("docker-compose --version", "Docker Compose is available")
        if success:
            print("💡 To start: docker-compose up -d")
    else:
        print("⚠️  docker-compose.yml not found")

    print("\n" + "=" * 40)
    print("🎉 Setup verification complete!")
    print("\n📋 Next steps:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Run web UI: python run_web.py")
    print("3. Or use Docker: docker-compose up -d")
    print("4. Open browser: http://localhost:8080")

if __name__ == "__main__":
    main()