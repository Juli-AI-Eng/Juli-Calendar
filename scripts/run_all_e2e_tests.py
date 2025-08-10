#!/usr/bin/env python3
"""Run all E2E tests with proper logging and reporting."""

import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

def main():
    # Create logs directory
    log_dir = Path("logs/e2e")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create a timestamp for this test run
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Main log file for this test run
    main_log = log_dir / f"test_run_{timestamp}.log"
    
    print(f"🧪 Running E2E Tests")
    print(f"📝 Logs will be saved to: {main_log}")
    print("=" * 60)
    
    # Set environment variables
    env = os.environ.copy()
    env["E2E_LOGGING_ENABLED"] = "true"
    
    # Command to run all E2E tests
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/e2e",
        "-v",  # verbose
        "-s",  # no capture (show print statements)
        "--tb=short",  # short traceback
        "--color=yes",  # colored output
        f"--junit-xml=logs/e2e/junit_{timestamp}.xml",  # JUnit XML report
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    print("=" * 60)
    
    # Run tests and capture output
    with open(main_log, "w") as log_file:
        # Write header
        log_file.write(f"E2E Test Run - {datetime.now().isoformat()}\n")
        log_file.write("=" * 80 + "\n")
        log_file.write(f"Command: {' '.join(cmd)}\n")
        log_file.write("=" * 80 + "\n\n")
        
        # Run the tests
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Stream output to both console and log file
        for line in process.stdout:
            print(line, end="")
            log_file.write(line)
            log_file.flush()
        
        # Wait for process to complete
        return_code = process.wait()
        
        # Write footer
        log_file.write("\n" + "=" * 80 + "\n")
        log_file.write(f"Test run completed at {datetime.now().isoformat()}\n")
        log_file.write(f"Exit code: {return_code}\n")
    
    print("\n" + "=" * 60)
    print(f"✅ Test run complete! Exit code: {return_code}")
    print(f"📝 Full log saved to: {main_log}")
    print(f"🤖 AI grading logs saved to: logs/e2e/ai_grading/")
    print(f"📊 Test reports available in: logs/e2e/")
    
    return return_code

if __name__ == "__main__":
    sys.exit(main())