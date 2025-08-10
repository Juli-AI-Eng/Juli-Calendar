"""Date parser for natural language date/time understanding."""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import re
from dateutil import parser as dateutil_parser
from dateutil.relativedelta import relativedelta
import pytz


class DateParser:
    """Parse natural language dates with timezone awareness."""
    
    def __init__(self):
        """Initialize the date parser."""
        # Relative day mappings
        self.relative_days = {
            "today": 0,
            "tomorrow": 1,
            "day after tomorrow": 2,
            "yesterday": -1
        }
        
        # Time of day mappings
        self.time_of_day = {
            "morning": 9,
            "afternoon": 14,
            "evening": 18,
            "night": 20,
            "end of day": 17,
            "eod": 17,
            "start of day": 9,
            "midnight": 0,
            "noon": 12
        }
        
        # Weekday names
        self.weekdays = [
            "monday", "tuesday", "wednesday", "thursday", 
            "friday", "saturday", "sunday"
        ]
    
    def parse_date(self, date_string: str, context: Dict[str, Any]) -> Optional[datetime]:
        """Parse a natural language date string into a datetime object."""
        if not date_string:
            return None
            
        date_string = date_string.lower().strip()
        current_dt = context.get("now", datetime.now())
        timezone_str = context.get("timezone", "UTC")
        
        try:
            tz = pytz.timezone(timezone_str)
            if not current_dt.tzinfo:
                current_dt = tz.localize(current_dt)
        except:
            tz = pytz.UTC
            current_dt = current_dt.replace(tzinfo=tz)
        
        # Check for specific time patterns like "tomorrow at 9 AM" first
        time_pattern = re.search(r'at (\d{1,2})\s*(am|pm|AM|PM)', date_string)
        if time_pattern:
            hour = int(time_pattern.group(1))
            meridiem = time_pattern.group(2).lower()
            
            if meridiem == 'pm' and hour != 12:
                hour += 12
            elif meridiem == 'am' and hour == 12:
                hour = 0
                
            # Check what day it refers to
            if "tomorrow" in date_string:
                result = current_dt + timedelta(days=1)
                result = result.replace(hour=hour, minute=0, second=0)
                return result
            elif "today" in date_string:
                result = current_dt.replace(hour=hour, minute=0, second=0)
                return result
        
        # Try relative days (check longest matches first)
        relative_days_sorted = sorted(self.relative_days.items(), key=lambda x: len(x[0]), reverse=True)
        for rel_day, days_offset in relative_days_sorted:
            if rel_day in date_string and " at " not in date_string:  # Skip if it has specific time
                result = current_dt + timedelta(days=days_offset)
                
                # Check for time of day modifier
                for tod, hour in self.time_of_day.items():
                    if tod in date_string:
                        result = result.replace(hour=hour, minute=0, second=0)
                        break
                else:
                    # Default to end of day for deadlines
                    if any(word in date_string for word in ["by", "deadline", "due"]):
                        result = result.replace(hour=17, minute=0, second=0)
                
                return result
        
        # Check for "next week"
        if "next week" in date_string:
            # Next Monday
            days_until_monday = (7 - current_dt.weekday()) % 7
            if days_until_monday == 0:
                days_until_monday = 7
            result = current_dt + timedelta(days=days_until_monday)
            result = result.replace(hour=9, minute=0, second=0)
            return result
        
        # Check for "this week"
        if "this week" in date_string:
            # End of this week (Friday)
            days_until_friday = (4 - current_dt.weekday()) % 7
            result = current_dt + timedelta(days=days_until_friday)
            result = result.replace(hour=17, minute=0, second=0)
            return result
        
        # Check for weekday references
        for i, weekday in enumerate(self.weekdays):
            if weekday in date_string:
                current_weekday = current_dt.weekday()
                days_ahead = (i - current_weekday) % 7
                
                # Handle "next" modifier
                if "next" in date_string:
                    if days_ahead == 0:
                        days_ahead = 7
                    else:
                        days_ahead += 7
                else:
                    # If the day has passed this week, assume next week
                    if days_ahead == 0:
                        days_ahead = 7
                
                result = current_dt + timedelta(days=days_ahead)
                
                # Check for time of day
                for tod, hour in self.time_of_day.items():
                    if tod in date_string:
                        result = result.replace(hour=hour, minute=0, second=0)
                        break
                else:
                    # Default to 9 AM for weekdays
                    result = result.replace(hour=9, minute=0, second=0)
                
                return result
        
        # Check for relative time periods (in X hours/minutes)
        in_hours_match = re.search(r'in (\d+) hour', date_string)
        if in_hours_match:
            hours = int(in_hours_match.group(1))
            return current_dt + timedelta(hours=hours)
        
        in_minutes_match = re.search(r'in (\d+) minute', date_string)
        if in_minutes_match:
            minutes = int(in_minutes_match.group(1))
            return current_dt + timedelta(minutes=minutes)
        
        # Check for time of day without specific date
        for tod, hour in self.time_of_day.items():
            if date_string == tod or date_string == f"at {tod}":
                result = current_dt.replace(hour=hour, minute=0, second=0)
                # If time has passed today, assume tomorrow
                if result <= current_dt:
                    result += timedelta(days=1)
                return result
        
        # Handle "soon" as end of today
        if date_string in ["soon", "later", "later today"]:
            return current_dt.replace(hour=17, minute=0, second=0)
        
        # Try dateutil parser as fallback
        try:
            # First try to parse with timezone
            parsed = dateutil_parser.parse(date_string, fuzzy=True)
            if not parsed.tzinfo:
                parsed = tz.localize(parsed)
            
            # If the parsed date is in the past, it might be a time today
            if parsed.date() < current_dt.date():
                # Check if it's just a time
                if not any(word in date_string for word in 
                          ["yesterday", "last", "ago", "previous"]):
                    # Assume it's today or tomorrow
                    parsed = parsed.replace(
                        year=current_dt.year,
                        month=current_dt.month,
                        day=current_dt.day
                    )
                    if parsed <= current_dt:
                        parsed += timedelta(days=1)
            
            return parsed
        except:
            pass
        
        # Return None if we can't parse
        return None
    
    def parse_duration(self, text: str) -> Optional[float]:
        """Parse duration from text (returns hours as float)."""
        # Look for patterns like "2 hours", "30 minutes", "1.5 hours"
        hours_match = re.search(r'(\d+(?:\.\d+)?)\s*hour', text)
        if hours_match:
            return float(hours_match.group(1))
        
        minutes_match = re.search(r'(\d+)\s*minute', text)
        if minutes_match:
            return float(minutes_match.group(1)) / 60.0
        
        # Look for "half hour"
        if "half hour" in text or "30 min" in text:
            return 0.5
        
        return None