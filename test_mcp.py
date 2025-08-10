#!/usr/bin/env python3
import requests
import json

url = "https://a3ccf910f375.ngrok-free.app/mcp"
headers = {
    "Content-Type": "application/json",
    "ngrok-skip-browser-warning": "true"
}

# Test get_content
data = {
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
        "name": "get_content",
        "arguments": {
            "dataset_name": "making_unmaking_world_language"
        }
    }
}

response = requests.post(url, headers=headers, json=data)
result = response.json()

if result.get("result") and result["result"].get("content"):
    content_json = json.loads(result["result"]["content"][0]["text"])
    if content_json.get("success"):
        content = content_json.get("content", "")
        print(f"✅ Content retrieved successfully!")
        print(f"Content length: {len(content)} characters")
        print(f"First 300 characters:")
        print(content[:300] + "..." if len(content) > 300 else content)
    else:
        print(f"❌ Error: {content_json.get('error')}")
else:
    print(f"❌ Failed to get content: {result}")