#!/usr/bin/env python3
"""Debug script to test search functionality"""

import asyncio
import json
import os
from datetime import datetime
import pytz
from src.tools.find_and_analyze import FindAndAnalyzeTool
from src.ai.search_analyzer import SearchAnalyzer

# Load credentials
from dotenv import load_dotenv
load_dotenv('.env.test')

async def test_search():
    """Test the search functionality"""
    
    # Setup
    tool = FindAndAnalyzeTool()
    analyzer = SearchAnalyzer()
    
    credentials = {
        "reclaim_api_key": os.getenv("RECLAIM_API_KEY"),
        "nylas_api_key": os.getenv("NYLAS_API_KEY"),
        "nylas_grant_id": os.getenv("NYLAS_GRANT_ID")
    }
    
    # User context
    eastern = pytz.timezone('America/New_York')
    now = datetime.now(eastern)
    
    user_context = {
        "timezone": "America/New_York",
        "current_date": now.strftime("%Y-%m-%d"),
        "current_time": now.strftime("%H:%M:%S"),
        "now": now
    }
    
    print(f"Current time: {now}")
    print(f"Current date: {now.strftime('%Y-%m-%d')}")
    
    # Test 1: Analyze the search query
    print("\n=== TESTING SEARCH ANALYZER ===")
    query = "What's on my calendar today?"
    search_intent = analyzer.analyze_search_query(query, user_context)
    print(f"Query: {query}")
    print(f"Search intent: {json.dumps(search_intent, indent=2)}")
    
    # Test 2: Execute the search
    print("\n=== TESTING FIND AND ANALYZE ===")
    data = {
        "query": query,
        "scope": "both",
        "user_timezone": "America/New_York",
        "current_date": now.strftime("%Y-%m-%d"),
        "current_time": now.strftime("%H:%M:%S")
    }
    
    result = await tool.execute(data, credentials)
    print(f"Search result: {json.dumps(result, indent=2)}")

if __name__ == "__main__":
    asyncio.run(test_search())