#!/bin/bash

# DataSite Connector - Public API Startup Script
# This script starts the HTTP API server for browser-based Claude access

echo "🚀 Starting DataSite Connector Public API..."

# Activate virtual environment
source venv/bin/activate

# Start the API server
echo "📡 Starting API server on http://localhost:8080"
echo "📖 API documentation will be available at: http://localhost:8080/docs"
echo ""
echo "🔒 Your content remains private and encrypted on your local system"
echo "🌐 The API provides secure access for browser-based Claude"
echo ""
echo "To make this accessible from browser Claude:"
echo "1. Keep this server running"
echo "2. Use ngrok or similar to create a public tunnel:"
echo "   ngrok http 8080"
echo "3. Use the ngrok URL in your Claude prompts"
echo ""
echo "Press Ctrl+C to stop the server"
echo "----------------------------------------"

# Start the server
python api_server.py