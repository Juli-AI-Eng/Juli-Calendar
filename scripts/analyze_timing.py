#!/usr/bin/env python3
"""Analyze timing logs from E2E tests to identify slow operations."""
import json
import os
from pathlib import Path
from collections import defaultdict
import statistics

def analyze_timing_logs():
    """Analyze all timing logs and generate a summary report."""
    timing_dir = Path("logs/timing")
    if not timing_dir.exists():
        print("No timing logs found.")
        return
    
    # Collect all timing data
    all_operations = defaultdict(list)
    test_totals = {}
    
    for json_file in timing_dir.glob("*_timing.json"):
        with open(json_file, 'r') as f:
            data = json.load(f)
            
        test_name = data["test_name"]
        test_totals[test_name] = data["total_duration"]
        
        for operation, duration in data["operations"].items():
            all_operations[operation].append(duration)
    
    # Print summary report
    print("E2E Test Timing Analysis")
    print("=" * 80)
    print()
    
    # Slowest tests
    print("Slowest Tests:")
    print("-" * 40)
    sorted_tests = sorted(test_totals.items(), key=lambda x: x[1], reverse=True)
    for test_name, duration in sorted_tests[:10]:
        print(f"{test_name:<50} {duration:>8.2f}s")
    
    print()
    print("Operation Statistics:")
    print("-" * 40)
    print(f"{'Operation':<40} {'Count':>6} {'Avg':>8} {'Max':>8} {'Total':>8}")
    print("-" * 80)
    
    # Sort by total time spent
    operation_stats = []
    for operation, durations in all_operations.items():
        stats = {
            'operation': operation,
            'count': len(durations),
            'avg': statistics.mean(durations),
            'max': max(durations),
            'total': sum(durations)
        }
        operation_stats.append(stats)
    
    operation_stats.sort(key=lambda x: x['total'], reverse=True)
    
    for stats in operation_stats:
        print(f"{stats['operation']:<40} {stats['count']:>6} {stats['avg']:>8.2f} {stats['max']:>8.2f} {stats['total']:>8.2f}")
    
    print()
    print("Key Findings:")
    print("-" * 40)
    
    # Identify bottlenecks
    http_operations = [op for op in all_operations.keys() if op.startswith("http_request_")]
    if http_operations:
        http_times = []
        for op in http_operations:
            http_times.extend(all_operations[op])
        avg_http = statistics.mean(http_times) if http_times else 0
        print(f"Average HTTP request time: {avg_http:.2f}s")
    
    # Server startup time
    test_total_times = all_operations.get("test_total", [])
    if test_total_times:
        avg_test_time = statistics.mean(test_total_times)
        print(f"Average test duration: {avg_test_time:.2f}s")
    
    # Calculate overhead
    for test_name, total_time in test_totals.items():
        # Find the JSON file for detailed timing
        json_file = next(timing_dir.glob(f"{test_name}_*_timing.json"), None)
        if json_file:
            with open(json_file, 'r') as f:
                data = json.load(f)
            
            # Sum up all operation times
            operation_sum = sum(data["operations"].values())
            overhead = total_time - operation_sum
            if overhead > 1.0:  # More than 1 second overhead
                print(f"High overhead in {test_name}: {overhead:.2f}s unaccounted")

if __name__ == "__main__":
    analyze_timing_logs()