#!/usr/bin/env python3
"""Run server for E2E tests without any mocking."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# DO NOT import tests or conftest - avoid all mocking
if __name__ == "__main__":
    # Ensure project root on sys.path for `src` imports
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))

    # Load environment variables
    load_dotenv(".env.test")
    
    # Set up environment
    os.environ["FLASK_APP"] = "src.server:create_app"
    
    # Import Flask and run
    from flask import Flask
    from src.server import create_app
    
    app = create_app()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    app.run(port=port, debug=False)