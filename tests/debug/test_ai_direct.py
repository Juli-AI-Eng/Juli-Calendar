#!/usr/bin/env python3
"""Direct test of AI classification without pytest."""
import os
import sys
from openai import OpenAI
from dotenv import load_dotenv

# Load environment
load_dotenv('.env.test')

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from ai.intent_router import IntentRouter

# Set up OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Create router
router = IntentRouter(client)

# Test queries
test_queries = [
    "Create a task to review the budget",
    "Task to delete without approval",
    "Schedule a meeting tomorrow at 2pm",
    "I need a new task for the project",
]

print("Testing AI Classification Directly:\n")

for query in test_queries:
    print(f"\nQuery: {query}")
    try:
        result = router.analyze_intent(query, {
            "timezone": "America/New_York",
            "current_date": "2025-07-29",
            "current_time": "11:00:00"
        })
        print(f"Provider: {result.get('provider')}")
        print(f"Intent Type: {result.get('intent_type')}")
        print(f"Reasoning: {result.get('reasoning')}")
        
        if "task" in query.lower() and result.get('provider') != 'reclaim':
            print("❌ ERROR: Task query was not routed to Reclaim!")
        elif "meeting" in query.lower() and result.get('provider') != 'nylas':
            print("❌ ERROR: Meeting query was not routed to Nylas!")
        else:
            print("✓ Correctly classified")
            
    except Exception as e:
        print(f"Error: {e}")