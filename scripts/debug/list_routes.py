#!/usr/bin/env python3
"""Test if routes are properly registered."""

import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import after loading env
from src.server import create_app

# Create app
app = create_app()

# List all routes
print("All registered routes:")
print("-" * 50)
for rule in app.url_map.iter_rules():
    methods = ', '.join(rule.methods - {'OPTIONS', 'HEAD'})
    print(f"{rule.rule:40} [{methods}]")

print("\n" + "-" * 50)
print("\nTesting OAuth routes:")

# Test with test client
with app.test_client() as client:
    # Test setup routes
    response = client.get('/setup/connect-url?provider=google')
    print(f"/setup/connect-url: {response.status_code} - {response.data[:100]}")