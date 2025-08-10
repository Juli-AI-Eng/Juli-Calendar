#!/usr/bin/env python3
"""Simple test to reproduce the intent_result error"""

import asyncio
import json
import os
from src.tools.manage_productivity import ManageProductivityTool
from datetime import datetime
import pytz

# Load credentials
from dotenv import load_dotenv
load_dotenv('.env.test')

async def test_simple():
    """Test the problematic query directly"""
    
    tool = ManageProductivityTool()
    
    credentials = {
        "reclaim_api_key": os.getenv("RECLAIM_API_KEY"),
        "nylas_api_key": os.getenv("NYLAS_API_KEY"),
        "nylas_grant_id": os.getenv("NYLAS_GRANT_ID")
    }
    
    # The query that caused the error
    data = {
        "query": "Schedule 'Quarterly Budget Review' tomorrow at 4pm",
        "context": "Fuzzy matching test",
        "user_timezone": "America/New_York",
        "current_date": "2025-07-31",
        "current_time": "14:18:03"
    }
    
    print(f"Testing query: {data['query']}")
    
    try:
        result = await tool.execute(data, credentials)
        print(f"Result: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_simple())