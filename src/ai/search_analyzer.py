"""AI component for analyzing search queries."""
from typing import Dict, Any, Optional
import logging
from datetime import datetime
import os
import json
from openai import OpenAI

logger = logging.getLogger(__name__)


class SearchAnalyzer:
    """Analyzes search queries to understand intent and extract parameters."""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """Initialize the SearchAnalyzer with OpenAI client."""
        self.client = OpenAI(api_key=openai_api_key or os.getenv("OPENAI_API_KEY"))
    
    def analyze_search_query(self, query: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a search query using AI to determine intent and filters.
        """
        logger.info(f"Analyzing search query: {query}")
        
        try:
            # Try AI analysis first
            return self._ai_analysis(query, user_context)
        except Exception as e:
            logger.error(f"AI analysis failed: {e}, falling back to simple parsing")
            return self._fallback_analysis(query, user_context)
    
    def _ai_analysis(self, query: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Use OpenAI to intelligently analyze the search query."""
        
        # Define the function tool for search analysis
        analyze_search_tool = {
            "type": "function",
            "function": {
                "name": "analyze_search",
                "description": "Extract search parameters from user query",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "intent": {
                            "type": "string",
                            "enum": ["view_schedule", "find_specific", "workload_analysis", "find_overdue"],
                            "description": "The primary intent of the search"
                        },
                        "search_text": {
                            "type": ["string", "null"],
                            "description": "Keywords to search for in titles/descriptions"
                        },
                        "time_range": {
                            "type": ["string", "null"],
                            "description": "Natural language time period to search within (e.g., 'today', 'next Tuesday', 'past 3 days', etc.)"
                        },
                        "priority": {
                            "type": ["string", "null"],
                            "enum": ["high", "medium", "low"],
                            "description": "Priority level filter"
                        },
                        "status": {
                            "type": ["string", "null"],
                            "enum": ["pending", "completed", "cancelled"],
                            "description": "Status filter"
                        },
                        "participants": {
                            "type": ["array", "null"],
                            "items": {"type": "string"},
                            "description": "List of participant names to filter by"
                        },
                        "search_both": {
                            "type": "boolean",
                            "description": "Whether to search both tasks and events"
                        }
                    },
                    "required": ["intent", "search_both"]
                }
            }
        }
        
        system_message = f"""You are analyzing search queries for a productivity system.
Current date/time: {user_context.get('current_date')} {user_context.get('current_time')} {user_context.get('timezone', 'UTC')}

Extract search parameters from the user's query. Consider:
- Keywords they want to search for (extract the actual search terms)
- Time ranges (today, tomorrow, this week, etc.)
- Priority levels (urgent, high priority, etc.)
- Status filters (completed, pending, etc.)
- Participant names (meetings with specific people)
- Whether they're asking about workload/busyness

For queries like "Find tasks about X" or "Search for Y", extract X or Y as the search_text.
For nonsense or gibberish search terms, still extract them as search_text.
If the query contains no specific search terms and is just asking to view everything, set search_text to null."""

        try:
            from src.ai.openai_utils import call_function_tool
            result = call_function_tool(
                client=self.client,
                model="gpt-5",
                system_text=system_message,
                user_text=query,
                tool_def=analyze_search_tool,
                reasoning_effort="minimal",
                force_tool=True,
            )
            
            # Add any additional context
            if result.get("time_range"):
                result["filters"] = {"time_range": result["time_range"]}
            
            logger.info(f"AI search analysis result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"OpenAI call failed: {str(e)}")
            raise
    
    def _fallback_analysis(self, query: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback to simple pattern matching if AI fails."""
        query_lower = query.lower()
        
        # Detect workload analysis
        if any(word in query_lower for word in ["workload", "how many", "busy", "overloaded"]):
            return {
                "intent": "workload_analysis",
                "time_range": self._extract_time_range(query_lower, user_context),
                "analysis_type": "workload",
                "search_both": True
            }
        
        # Default to search
        result = {
            "intent": "view_schedule",
            "search_both": True
        }
        
        # Extract time range
        if "today" in query_lower:
            result["time_range"] = "today"
        elif "tomorrow" in query_lower:
            result["time_range"] = "tomorrow"
        elif "this week" in query_lower:
            result["time_range"] = "this_week"
        elif "overdue" in query_lower:
            result["time_range"] = "overdue"
            result["intent"] = "find_overdue"
        
        # Extract priority
        if "high priority" in query_lower or "urgent" in query_lower:
            result["priority"] = "high"
        
        return result
    
    def _extract_person_names(self, query: str, user_context: Dict[str, Any]) -> list:
        """
        Extract person names from search queries.
        
        Uses pattern matching to identify names after keywords like "with".
        In production, this would use NLP libraries or AI models for better accuracy.
        """
        import re
        
        names = []
        
        # Common patterns for extracting names after "with"
        patterns = [
            r'\bwith\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # "with John Smith"
            r'\bfrom\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # "from Sarah"
            r'\bby\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',    # "by Michael"
            r'\band\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',   # "and Jennifer"
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, query)
            names.extend(matches)
        
        # Clean up and filter names
        cleaned_names = []
        for name in names:
            # Remove common words that might be mistaken for names
            stop_words = {'Meeting', 'Call', 'Discussion', 'Review', 'Session', 'Conference', 'Team', 'All'}
            if name not in stop_words and len(name.strip()) > 1:
                cleaned_names.append(name.strip())
        
        # Remove duplicates while preserving order
        unique_names = []
        for name in cleaned_names:
            if name not in unique_names:
                unique_names.append(name)
        
        logger.debug(f"Extracted person names from '{query}': {unique_names}")
        
        return unique_names
    
    def _extract_time_range(self, query: str, user_context: Dict[str, Any]) -> str:
        """Extract time range from query."""
        if "today" in query:
            return "today"
        elif "tomorrow" in query:
            return "tomorrow"
        elif "this week" in query or "week" in query:
            return "this_week"
        elif "this month" in query or "month" in query:
            return "this_month"
        else:
            return "all"