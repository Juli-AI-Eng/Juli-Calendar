#!/usr/bin/env python3
"""Debug semantic search issue."""
import asyncio
import logging
from src.ai.semantic_search import SemanticSearch

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_semantic_search():
    """Test semantic search functionality."""
    semantic_search = SemanticSearch()
    
    # Mock task data
    tasks = [
        {
            "id": 10576773,
            "title": "Quick task to complete in workflow test",
            "status": "NEW",
            "priority": "NORMAL",
            "due": None,
            "duration_hours": 0,
            "notes": "Will be found and completed",
            "provider": "reclaim",
            "type": "task"
        },
        {
            "id": 10576774,
            "title": "Another task for testing",
            "status": "NEW",
            "priority": "HIGH",
            "due": None,
            "duration_hours": 1,
            "notes": "Different task",
            "provider": "reclaim",
            "type": "task"
        }
    ]
    
    user_context = {
        "timezone": "America/New_York",
        "current_date": "2025-07-31",
        "current_time": "12:41:58"
    }
    
    # Test with the exact query from the failing test
    query = "Find tasks with 'workflow test' in the title"
    
    print(f"\nTesting semantic search with query: '{query}'")
    print(f"Tasks to search: {len(tasks)}")
    
    filtered_tasks, search_metadata = semantic_search.analyze_and_filter(
        query=query,
        items=tasks,
        item_type="task",
        user_context=user_context
    )
    
    print(f"\nSearch metadata: {search_metadata}")
    print(f"Filtered tasks: {len(filtered_tasks)}")
    for task in filtered_tasks:
        print(f"  - {task['title']} (ID: {task['id']})")

if __name__ == "__main__":
    asyncio.run(test_semantic_search())