"""AI-powered semantic search for tasks and events."""
from typing import Dict, Any, List, Optional, Tuple
import logging
from datetime import datetime, timedelta
import os
import json
from openai import OpenAI

logger = logging.getLogger(__name__)


class SemanticSearch:
    """Performs intelligent semantic search using AI for both time extraction and content matching."""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        """Initialize the SemanticSearch with OpenAI client."""
        self.client = OpenAI(api_key=openai_api_key or os.getenv("OPENAI_API_KEY"))
    
    def analyze_and_filter(
        self, 
        query: str, 
        items: List[Dict[str, Any]], 
        item_type: str,  # "task" or "event"
        user_context: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Analyze query and filter items using semantic understanding.
        
        Returns:
            Tuple of (filtered_items, search_metadata)
        """
        if not items:
            return [], {"reason": "No items to search"}
        
        # First, extract time range and search intent
        search_intent = self._extract_search_intent(query, user_context)
        
        # Pre-filter by time if a specific range is detected
        time_filtered_items = self._apply_time_filter(items, search_intent, user_context)
        
        # If no time filter was applied or we still have many items, use semantic matching
        if len(time_filtered_items) > 20 or search_intent.get("needs_semantic_match", True):
            final_items = self._semantic_filter(query, time_filtered_items, item_type, user_context)
        else:
            final_items = time_filtered_items
        
        return final_items, search_intent
    
    def _extract_search_intent(self, query: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract time range and search intent from query."""
        logger.info(f"[SemanticSearch] Extracting intent from query: '{query}'")
        
        extract_intent_tool = {
            "type": "function",
            "function": {
                "name": "extract_search_intent",
                "description": "Extract time range and search criteria from user query",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "time_range": {
                            "type": ["object", "null"],
                            "additionalProperties": False,
                            "properties": {
                                "start": {
                                    "type": "string",
                                    "description": "Start date/time in ISO format"
                                },
                                "end": {
                                    "type": "string",
                                    "description": "End date/time in ISO format"
                                },
                                "description": {
                                    "type": "string",
                                    "description": "Human-readable time range (e.g., 'today', 'this week')"
                                }
                            },
                            "required": ["start", "end", "description"]
                        },
                        "search_criteria": {
                            "type": "object",
                            "properties": {
                                "keywords": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Important keywords or topics to search for"
                                },
                                "priority": {
                                    "type": ["string", "null"],
                                    "enum": ["high", "medium", "low", None]
                                },
                                "status": {
                                    "type": ["string", "null"],
                                    "enum": ["pending", "complete", "overdue", None]
                                },
                                "participants": {
                                    "type": ["array", "null"],
                                    "items": {"type": "string"},
                                    "description": "Names of people mentioned"
                                }
                            },
                            "required": ["keywords", "priority", "status", "participants"]
                        },
                        "needs_semantic_match": {
                            "type": "boolean",
                            "description": "Whether semantic matching is needed beyond simple filters"
                        },
                        "intent": {
                            "type": "string",
                            "enum": ["find_specific", "view_schedule", "check_workload", "find_overdue"],
                            "description": "The primary intent of the search"
                        }
                    },
                    "required": ["time_range", "search_criteria", "needs_semantic_match", "intent"]
                },
                "strict": True
            }
        }
        
        system_message = f"""Extract search parameters from the user's query.
Current date/time: {user_context.get('current_date')} {user_context.get('current_time')} {user_context.get('timezone', 'UTC')}

Time range extraction:
- "today" → from start of today to end of today
- "tomorrow" → from start of tomorrow to end of tomorrow  
- "this week" → from Monday to Sunday of current week
- "next week" → from Monday to Sunday of next week
- "overdue" → anything before now
- If no time mentioned → null (search all time)

Search criteria:
- Extract meaningful keywords (not common words like "find", "show", "get")
- Identify priority levels, status filters, and participant names
- Set needs_semantic_match=true if the query is complex or conceptual"""
        
        try:
            from src.ai.openai_utils import call_function_tool
            result = call_function_tool(
                client=self.client,
                model="gpt-5",
                system_text=system_message,
                user_text=query,
                tool_def=extract_intent_tool,
                reasoning_effort="minimal",
                force_tool=True,
            )
            
            logger.info(f"Extracted search intent: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to extract search intent: {e}")
            return {
                "time_range": None,
                "search_criteria": {"keywords": query.split()},
                "needs_semantic_match": True,
                "intent": "find_specific"
            }
    
    def _apply_time_filter(
        self, 
        items: List[Dict[str, Any]], 
        search_intent: Dict[str, Any],
        user_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply time-based filtering to items."""
        time_range = search_intent.get("time_range")
        if not time_range:
            return items
        
        filtered = []
        now = user_context["now"]
        
        for item in items:
            # Get item time (due date for tasks, start time for events)
            item_time = None
            if item.get("type") == "task" and item.get("due"):
                item_time = datetime.fromisoformat(item["due"])
            elif item.get("type") == "event" and item.get("start"):
                item_time = datetime.fromisoformat(item["start"])
            
            if not item_time:
                continue
            
            # Check if item falls within time range
            if "start" in time_range and "end" in time_range:
                start = datetime.fromisoformat(time_range["start"])
                end = datetime.fromisoformat(time_range["end"])
                if start <= item_time <= end:
                    filtered.append(item)
            elif search_intent.get("intent") == "find_overdue":
                if item_time < now:
                    filtered.append(item)
        
        return filtered
    
    def _semantic_filter(
        self, 
        query: str,
        items: List[Dict[str, Any]], 
        item_type: str,
        user_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Use AI for semantic matching of items."""
        logger.info(f"[SemanticSearch] Semantic filtering {len(items)} {item_type}s with query: '{query}'")
        
        semantic_match_tool = {
            "type": "function",
            "function": {
                "name": "semantic_match",
                "description": f"Find {item_type}s that semantically match the user's query",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "matching_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": f"IDs of {item_type}s that match the query semantically"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Explanation of why these items match"
                        },
                        "confidence_scores": {
                            "type": "object",
                            "additionalProperties": {"type": "number"},
                            "description": "Confidence score (0-1) for each matching ID"
                        }
                    },
                    "required": ["matching_ids", "reasoning", "confidence_scores"]
                },
                "strict": True
            }
        }
        
        # Prepare item summaries for AI
        item_summaries = []
        for item in items:
            summary = {
                "id": str(item.get("id")),
                "title": item.get("title"),
                "content": item.get("notes") or item.get("description", ""),
                "time": item.get("due") or item.get("start"),
                "priority": item.get("priority"),
                "participants": item.get("participants", [])
            }
            item_summaries.append(summary)
        
        system_message = f"""You are performing semantic search on {item_type}s.
Match items based on conceptual similarity, not just keyword matching.

Examples of semantic matching:
- "budget review" matches "Q4 financial analysis"
- "team meeting" matches "weekly standup"
- "urgent tasks" matches items with high priority
- "meetings with John" matches events where John is a participant

Consider:
- Synonyms and related concepts
- Context and intent
- Partial matches and abbreviations
- Priority and urgency indicators"""
        
        try:
            from src.ai.openai_utils import call_function_tool
            result = call_function_tool(
                client=self.client,
                model="gpt-5",
                system_text=system_message,
                user_text=f"Query: {query}\n\nItems: {json.dumps(item_summaries)}",
                tool_def=semantic_match_tool,
                reasoning_effort="minimal",
                force_tool=True,
            )
            
            # Filter items by matching IDs with confidence threshold
            matching_ids = set(result.get("matching_ids", []))
            confidence_scores = result.get("confidence_scores", {})
            
            filtered = []
            for item in items:
                item_id = str(item.get("id"))
                if item_id in matching_ids and confidence_scores.get(item_id, 0) > 0.7:
                    filtered.append(item)
            
            logger.info(f"Semantic search matched {len(filtered)} items: {result.get('reasoning')}")
            return filtered
            
        except Exception as e:
            logger.error(f"Semantic matching failed: {e}")
            # Fallback to keyword matching
            return self._fallback_keyword_filter(query, items)
    
    def _fallback_keyword_filter(self, query: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Simple keyword-based fallback filter."""
        query_lower = query.lower()
        keywords = query_lower.split()
        
        filtered = []
        for item in items:
            title = (item.get("title") or "").lower()
            content = (item.get("notes") or item.get("description") or "").lower()
            
            # Check if any keyword matches
            if any(keyword in title or keyword in content for keyword in keywords):
                filtered.append(item)
        
        return filtered