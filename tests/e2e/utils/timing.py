"""Timing utilities for E2E tests."""
import time
import functools
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional


class TestTimer:
    """Track timing for different parts of tests."""
    
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.timings: Dict[str, float] = {}
        self.start_times: Dict[str, float] = {}
        self.test_start = time.time()
        self.log_file = self._get_log_file()
        
    def _get_log_file(self) -> str:
        """Get the timing log file path."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        logs_dir = "logs/timing"
        os.makedirs(logs_dir, exist_ok=True)
        return f"{logs_dir}/{self.test_name}_{timestamp}_timing.json"
    
    def start(self, operation: str):
        """Start timing an operation."""
        self.start_times[operation] = time.time()
        
    def end(self, operation: str) -> float:
        """End timing an operation and return duration."""
        if operation not in self.start_times:
            return 0.0
            
        duration = time.time() - self.start_times[operation]
        self.timings[operation] = duration
        del self.start_times[operation]
        return duration
    
    def add_timing(self, operation: str, duration: float):
        """Add a timing directly."""
        self.timings[operation] = duration
        
    def save(self):
        """Save timings to log file."""
        total_duration = time.time() - self.test_start
        
        report = {
            "test_name": self.test_name,
            "total_duration": total_duration,
            "timestamp": datetime.now().isoformat(),
            "operations": self.timings,
            "summary": {
                "total_seconds": round(total_duration, 2),
                "slowest_operation": max(self.timings.items(), key=lambda x: x[1]) if self.timings else None,
                "operation_count": len(self.timings)
            }
        }
        
        with open(self.log_file, 'w') as f:
            json.dump(report, f, indent=2)
            
        # Also create a human-readable summary
        summary_file = self.log_file.replace('.json', '.txt')
        with open(summary_file, 'w') as f:
            f.write(f"Test Timing Report: {self.test_name}\n")
            f.write(f"{'=' * 60}\n")
            f.write(f"Total Duration: {total_duration:.2f} seconds\n\n")
            
            f.write("Operation Timings:\n")
            f.write("-" * 60 + "\n")
            
            # Sort by duration descending
            sorted_timings = sorted(self.timings.items(), key=lambda x: x[1], reverse=True)
            
            for operation, duration in sorted_timings:
                percentage = (duration / total_duration) * 100
                f.write(f"{operation:<40} {duration:>8.2f}s ({percentage:>5.1f}%)\n")
                
            f.write("-" * 60 + "\n")
            f.write(f"{'TOTAL':<40} {total_duration:>8.2f}s (100.0%)\n")


def time_operation(timer: TestTimer, operation: str):
    """Decorator to time a function call."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            timer.start(operation)
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = timer.end(operation)
                print(f"[TIMING] {operation}: {duration:.2f}s")
        return wrapper
    return decorator


class TimingContext:
    """Context manager for timing operations."""
    
    def __init__(self, timer: TestTimer, operation: str):
        self.timer = timer
        self.operation = operation
        
    def __enter__(self):
        self.timer.start(self.operation)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = self.timer.end(self.operation)
        print(f"[TIMING] {self.operation}: {duration:.2f}s")