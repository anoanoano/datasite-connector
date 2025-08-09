#!/bin/bash

# SyftBox App Entry Point
# This script is called by SyftBox to run the datasite connector

echo "Starting DataSite Connector..."

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Install dependencies if needed
if [ ! -f ".deps_installed" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
    touch .deps_installed
fi

# Run the main application
python main.py

echo "DataSite Connector finished."