#!/usr/bin/env python3
"""Run E2E tests individually for manual verification"""

import subprocess
import sys
import os
import argparse
from pathlib import Path

# E2E test files and their descriptions
E2E_TESTS = [
    {
        "file": "test_manage_productivity_e2e.py",
        "class": "TestManageProductivityE2E",
        "tests": [
            ("test_create_reclaim_task", "Creates 'Review Q4 Budget' task in Reclaim - Look for it"),
            ("test_create_nylas_event", "Creates 'Team Standup' at 10am tomorrow - Check calendar"),
            ("test_update_task_complete", "Creates a new task, then marks it as complete - Watch status change"),
            ("test_reschedule_event", "Reschedules an event from 2pm to 4pm - Check new time"),
            ("test_natural_language_variations", "Creates 3 different items - Check all were created")
        ]
    },
    {
        "file": "test_duplicate_detection_e2e.py",
        "class": "TestDuplicateDetectionE2E",
        "tests": [
            ("test_duplicate_event_detection", "Creates event twice - Should warn about duplicate"),
            ("test_duplicate_event_approval_flow", "Creates duplicate event with approval - Check both exist"),
            ("test_duplicate_task_detection", "Creates task twice - Should detect duplicate"),
            ("test_fuzzy_title_matching", "Creates similar items - Should detect as duplicates")
        ]
    },
    {
        "file": "test_conflict_resolution_e2e.py",
        "class": "TestConflictResolutionE2E",
        "tests": [
            ("test_event_conflict_detection", "Creates conflicting event - Should suggest different time"),
            ("test_conflict_approval_flow", "Approves rescheduled time - Check new time in calendar"),
            ("test_buffer_time_conflict", "Creates back-to-back meetings - Should enforce 10min gap"),
            ("test_working_hours_scheduling", "Tries late night event - Should suggest work hours"),
            ("test_no_available_slot", "Tests fully booked calendar - Should handle gracefully")
        ]
    },
    {
        "file": "test_ai_routing.py",
        "class": "TestAIRouting",
        "tests": [
            ("test_task_query_routes_to_reclaim", "Creates task - Should use Reclaim.ai"),
            ("test_event_query_routes_to_nylas", "Creates meeting - Should use Nylas calendar")
        ]
    },
    {
        "file": "test_check_availability_e2e.py",
        "class": "TestCheckAvailabilityE2E",
        "tests": [
            ("test_check_specific_time_available", "Checks tomorrow 10am - Should show as available"),
            ("test_check_specific_time_busy", "Checks busy time slot - Should show conflict"),
            ("test_find_time_slots", "Finds 2hr slots this week - Lists available times"),
            ("test_check_various_durations", "Tests 15min, 1hr, 3hr slots - Shows availability"),
            ("test_natural_language_time_expressions", "Tests 'right now', 'this afternoon' etc - Parses correctly")
        ]
    },
    {
        "file": "test_find_and_analyze_e2e.py",
        "class": "TestFindAndAnalyzeE2E",
        "tests": [
            ("test_search_todays_items", "Shows today's tasks and events - Check your schedule"),
            ("test_search_by_keyword", "Searches for 'budget' items - Finds matching items"),
            ("test_search_overdue_tasks", "Lists overdue tasks - Shows past due items"),
            ("test_workload_analysis", "Analyzes week's workload - Shows busy periods"),
            ("test_time_range_searches", "Searches tomorrow, this week etc - Finds by time"),
            ("test_empty_search_results", "Searches for nonsense - Handles gracefully")
        ]
    },
    {
        "file": "test_approval_flow_e2e.py",
        "class": "TestApprovalFlowE2E", 
        "tests": [
            ("test_task_delete_no_approval_flow", "Deletes single task - No approval needed"),
            ("test_event_with_participants_approval_flow", "Creates meeting with others - Requires approval"),
            ("test_event_cancel_solo_no_approval_flow", "Cancels solo event - No approval needed"),
            ("test_bulk_operation_approval_flow", "Completes multiple tasks - May need approval")
        ]
    },
    {
        "file": "test_hybrid_workflows_e2e.py",
        "class": "TestHybridWorkflowsE2E",
        "tests": [
            ("test_check_availability_then_schedule", "Finds free time then books meeting - 2 step process"),
            ("test_find_tasks_and_complete", "Creates task, finds it, marks complete - 3 steps"),
            ("test_analyze_workload_then_optimize", "Checks workload then suggests improvements"),
            ("test_task_to_calendar_event_conversion", "Creates task then blocks calendar time"),
            ("test_full_productivity_workflow", "Complete 4-step workflow - Check, create, optimize")
        ]
    },
    {
        "file": "test_optimize_schedule_e2e.py",
        "class": "TestOptimizeScheduleE2E",
        "tests": [
            ("test_optimize_for_focus_time", "Finds 2hr focus blocks - Suggests best times"),
            ("test_balance_workload_optimization", "Spreads work evenly - Shows rebalanced schedule"),
            ("test_meeting_reduction_optimization", "Reduces meeting time - Suggests consolidation"),
            ("test_priority_based_optimization", "Prioritizes urgent work - Reorders by importance"),
            ("test_energy_based_optimization", "Matches work to energy - Morning for deep work"),
            ("test_natural_language_optimization_requests", "Various optimization requests - Smart suggestions")
        ]
    },
    {
        "file": "test_debug_ai_classification.py",
        "class": "TestDebugAIClassification",
        "tests": [
            ("test_task_classification", "Tests AI detects task queries - Debug output shown"),
            ("test_event_classification", "Tests AI detects event queries - Debug output shown")
        ]
    }
]

def print_header(text):
    print(f"\n{'='*60}")
    print(f"🧪 {text}")
    print(f"{'='*60}\n")

def print_success(text):
    print(f"✅ {text}")

def print_error(text):
    print(f"❌ {text}")

def print_info(text):
    print(f"ℹ️  {text}")

def run_single_test(test_file, class_name, test_name):
    """Run a single test"""
    cmd = [
        sys.executable, "-m", "pytest",
        f"tests/e2e/{test_file}::{class_name}::{test_name}",
        "-v", "-s", "--tb=short"
    ]
    
    print_info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    return result.returncode == 0

def main():
    parser = argparse.ArgumentParser(description="Run E2E tests with manual verification")
    parser.add_argument("--interactive", action="store_true", 
                       help="Pause between tests to inspect calendar")
    parser.add_argument("--demo", action="store_true",
                       help="Create useful calendar entries instead of test data")
    parser.add_argument("--keep-data", action="store_true",
                       help="Skip all cleanup operations")
    args = parser.parse_args()
    
    # Set environment variables based on flags
    if args.keep_data:
        os.environ["E2E_SKIP_CLEANUP"] = "true"
    
    if args.interactive:
        os.environ["E2E_INTERACTIVE"] = "true"
    
    # Always enable HTTP logging for E2E tests
    os.environ["E2E_LOGGING_ENABLED"] = "true"
    
    mode_text = "Interactive Mode" if args.interactive else "Manual Verification"
    if args.demo:
        mode_text += " (Demo Mode)"
    
    print_header(f"E2E Test Runner - {mode_text}")
    
    # Check if server is running
    import requests
    try:
        response = requests.get("http://localhost:5002/health", timeout=2)
        if response.status_code == 200:
            print_success("Server is running at http://localhost:5002")
        else:
            print_error("Server returned non-200 status")
    except:
        print_error("Server is not running! Please start it with: python scripts/run_server.py")
        print_info("In another terminal, run: python scripts/run_server.py")
        return
    
    # Check environment
    if not os.path.exists(".env.test"):
        print_error("No .env.test file found!")
        print_info("Copy .env.test.example to .env.test and add your credentials")
        return
    
    print_info("\nAvailable E2E Tests:")
    print_info("These tests will create real tasks/events in your calendar!")
    print()
    
    # List all tests
    test_num = 1
    all_tests = []
    for test_group in E2E_TESTS:
        print(f"\n📁 {test_group['file']}")
        for test_name, description in test_group['tests']:
            print(f"  {test_num:2d}. {test_name}")
            print(f"      {description}")
            all_tests.append((test_group['file'], test_group['class'], test_name, description))
            test_num += 1
    
    print("\n" + "-"*60)
    print("Options:")
    print("  - Enter a number to run a specific test")
    print("  - Enter 'all' to run all tests")
    print("  - Enter 'clean' to run cleanup scripts")
    print("  - Enter 'q' to quit")
    print("-"*60)
    
    while True:
        choice = input("\nYour choice: ").strip().lower()
        
        if choice == 'q':
            break
        elif choice == 'clean':
            print_info("\nRunning cleanup scripts...")
            subprocess.run([sys.executable, "scripts/clear_reclaim_tasks.py"])
            subprocess.run([sys.executable, "scripts/clear_nylas_events.py"])
        elif choice == 'all':
            print_info("\nRunning all tests...")
            for i, (test_file, class_name, test_name, description) in enumerate(all_tests):
                print_header(f"Running: {test_name} ({i+1}/{len(all_tests)})")
                print_info(description)
                if run_single_test(test_file, class_name, test_name):
                    print_success("Test passed!")
                else:
                    print_error("Test failed!")
                
                if args.interactive:
                    print("\n" + "="*60)
                    print("📅 Check your calendar to see the created event/task")
                    print("   The test data will remain in your calendar")
                    input("   Press Enter to continue to the next test...")
                    print("="*60)
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(all_tests):
                    test_file, class_name, test_name, description = all_tests[idx]
                    print_header(f"Running: {test_name}")
                    print_info(description)
                    if run_single_test(test_file, class_name, test_name):
                        print_success("\nTest passed!")
                        if args.interactive:
                            print("\n📅 Check your calendar to see the created event/task")
                            print("   The test data will remain in your calendar")
                    else:
                        print_error("\nTest failed!")
                else:
                    print_error("Invalid test number")
            except ValueError:
                print_error("Invalid input")

if __name__ == "__main__":
    main()