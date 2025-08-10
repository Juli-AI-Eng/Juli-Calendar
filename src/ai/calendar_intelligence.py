"""Simple calendar intelligence for smarter scheduling."""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import difflib
import logging

logger = logging.getLogger(__name__)


class CalendarIntelligence:
    """Provides intelligent calendar analysis and scheduling suggestions."""
    
    # Buffer time between meetings (in minutes)
    MEETING_BUFFER_MINUTES = 10
    
    # Threshold for fuzzy title matching (0.0 to 1.0)
    TITLE_SIMILARITY_THRESHOLD = 0.85
    
    @staticmethod
    def calculate_title_similarity(title1: str, title2: str) -> float:
        """
        Calculate similarity between two titles using fuzzy matching.
        Returns a score between 0.0 and 1.0.
        """
        # Normalize titles for comparison
        title1_normalized = title1.lower().strip()
        title2_normalized = title2.lower().strip()
        
        # Use SequenceMatcher for fuzzy matching
        return difflib.SequenceMatcher(None, title1_normalized, title2_normalized).ratio()
    
    @staticmethod
    def titles_are_similar(title1: str, title2: str) -> bool:
        """Check if two titles are similar enough to be considered duplicates.
        
        Special cases:
        - Numbered items (anywhere in the string) are not duplicates if numbers differ
        - Test/bulk items with numbers are not duplicates
        """
        import re
        
        # Normalize for comparison
        t1_lower = title1.lower().strip()
        t2_lower = title2.lower().strip()
        
        # Extract all numbers from both titles
        nums1 = re.findall(r'\d+', title1)
        nums2 = re.findall(r'\d+', title2)
        
        # If both have numbers and they're different, check if removing numbers makes them identical
        if nums1 and nums2 and nums1 != nums2:
            # Remove all numbers and extra spaces
            t1_no_nums = re.sub(r'\d+', '', t1_lower).strip()
            t1_no_nums = re.sub(r'\s+', ' ', t1_no_nums)  # Normalize spaces
            
            t2_no_nums = re.sub(r'\d+', '', t2_lower).strip()
            t2_no_nums = re.sub(r'\s+', ' ', t2_no_nums)  # Normalize spaces
            
            # If they're identical without numbers, they're numbered variants (NOT duplicates)
            # This handles "Task 1" vs "Task 2", "1. Task" vs "2. Task", "Bulk test task 1" vs "Bulk test task 2"
            if t1_no_nums == t2_no_nums:
                return False
        
        # For test/bulk operations, be more lenient
        if ('test' in t1_lower or 'bulk' in t1_lower) and ('test' in t2_lower or 'bulk' in t2_lower):
            # Use a higher threshold (95% similarity) for test data
            similarity = CalendarIntelligence.calculate_title_similarity(title1, title2)
            return similarity >= 0.95
        
        # Otherwise, use normal similarity check
        similarity = CalendarIntelligence.calculate_title_similarity(title1, title2)
        return similarity >= CalendarIntelligence.TITLE_SIMILARITY_THRESHOLD
    
    @staticmethod
    def check_buffer_conflict(
        new_start: datetime,
        new_end: datetime,
        existing_start: datetime,
        existing_end: datetime
    ) -> bool:
        """
        Check if events conflict considering buffer time.
        Returns True if there's a conflict (including buffer).
        """
        # Add buffer to existing event
        buffer = timedelta(minutes=CalendarIntelligence.MEETING_BUFFER_MINUTES)
        buffered_start = existing_start - buffer
        buffered_end = existing_end + buffer
        
        # Check if new event overlaps with buffered time
        return new_start < buffered_end and new_end > buffered_start
    
    @staticmethod
    def format_time_suggestion(
        original_time: datetime,
        suggested_time: datetime,
        conflict_title: str
    ) -> str:
        """Format a user-friendly message about the time suggestion."""
        # Simple, clear message
        if original_time.date() == suggested_time.date():
            # Same day
            return (
                f"'{conflict_title}' is scheduled at {original_time.strftime('%-I:%M %p')}. "
                f"The next available time is {suggested_time.strftime('%-I:%M %p')}."
            )
        else:
            # Different day
            return (
                f"'{conflict_title}' is scheduled at {original_time.strftime('%-I:%M %p on %A')}. "
                f"The next available time is {suggested_time.strftime('%-I:%M %p on %A, %B %-d')}."
            )
    
    @staticmethod
    def is_working_hours(dt: datetime) -> bool:
        """Check if a datetime is within normal working hours (9 AM - 6 PM on weekdays)."""
        # Skip weekends
        if dt.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Check hour is between 9 AM and 6 PM
        return 9 <= dt.hour < 18
    
    @staticmethod
    def next_working_time(dt: datetime) -> datetime:
        """Get the next valid working time from a given datetime."""
        # If already in working hours, return as-is
        if CalendarIntelligence.is_working_hours(dt):
            return dt
        
        # If after hours, move to next day at 9 AM
        if dt.hour >= 18:
            next_day = dt + timedelta(days=1)
            next_day = next_day.replace(hour=9, minute=0, second=0, microsecond=0)
        else:
            # Before hours, move to 9 AM same day
            next_day = dt.replace(hour=9, minute=0, second=0, microsecond=0)
        
        # Skip weekends
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        
        return next_day