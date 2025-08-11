#!/usr/bin/env python3
"""Unified server runner for Reclaim MCP (prod or e2e)."""
import os
import sys
import logging
from pathlib import Path
import argparse

# Configure logging to show DEBUG messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add project root (parent of this scripts/ dir) to path so `src` is importable
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

def load_environment(mode: str):
    """Load environment variables from .env file if it exists."""
    try:
        from dotenv import load_dotenv
        env_file = project_root / (".env.test" if mode == "e2e" else ".env")
        if env_file.exists():
            load_dotenv(env_file)
            print(f"✅ Loaded environment from {env_file}")
        else:
            print(f"⚠️  No .env file found at {env_file}")
            print("   Copy .env.example to .env and configure your settings")
    except ImportError:
        print("⚠️  python-dotenv not installed. Install with: pip install python-dotenv")
        print("   Or set environment variables manually")

def validate_environment():
    """Validate required environment variables."""
    required_vars = {
        "OPENAI_API_KEY": "OpenAI API key for AI functionality"
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"  - {var}: {description}")
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(var)
        print("\nSet these variables in your .env file or environment")
        return False
    
    print("✅ All required environment variables are set")
    return True

def find_python_executable():
    """Find the available Python executable (python3 or python)."""
    import shutil
    
    # Try python3 first (preferred)
    if shutil.which("python3"):
        return "python3"
    
    # Fall back to python
    if shutil.which("python"):
        return "python"
    
    # If neither found, default to python3
    return "python3"

def main():
    """Run the server in prod-like or e2e mode."""
    parser = argparse.ArgumentParser(description="Run MCP server")
    parser.add_argument("--mode", choices=["prod", "e2e"], default="prod")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    python_cmd = find_python_executable()
    print(f"🚀 Starting Reclaim MCP Server using {python_cmd}...")

    # Load environment
    load_environment(args.mode)
    
    # Validate environment
    if not validate_environment():
        sys.exit(1)
    
    # Import after environment is loaded
    from src.server import create_app
    
    # Create app
    app = create_app()
    
    # Get configuration from environment / args
    if args.mode == "e2e":
        host = "127.0.0.1"
        port = args.port or 5002
        # IMPORTANT: Set debug to False for E2E mode to prevent Flask reloader issues.
        # The Flask reloader can cause race conditions and hanging tests during E2E runs.
        # For stable E2E testing, we disable debug mode to avoid unexpected restarts.
        debug = False
    else:
        host = os.getenv("HOST", "0.0.0.0")
        port = args.port or int(os.getenv("PORT", "5000"))
        debug = os.getenv("DEBUG", "false").lower() == "true"
    
    print(f"🌐 Server will run on http://{host}:{port}")
    print(f"🔧 Mode: {args.mode} | Debug: {'enabled' if debug else 'disabled'}")
    print("📡 Ready to receive MCP requests from Juli!")
    print("\nAvailable endpoints:")
    print("  GET  /health          - Health check")
    print("  GET  /mcp/tools       - List available tools")
    print("  POST /mcp/tools/{id}  - Execute a tool")
    print("  GET  /mcp/needs-setup - Check setup status")
    print("\n" + "="*50)
    
    try:
        # Run the server
        app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()