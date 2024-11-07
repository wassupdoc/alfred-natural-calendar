#!/bin/bash

# setup.sh - Shell wrapper for Calendar NLP Workflow setup

# Ensure we're in the workflow directory
cd "$(dirname "$0")" || exit 1

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is required but not installed"
    echo "Please install Python 3 and try again"
    exit 1
fi

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ Error: pip3 is required but not installed"
    echo "Please install pip3 and try again"
    exit 1
fi

# Run setup script
echo "Running Calendar NLP Workflow setup..."
python3 setup.py

# Check if setup was successful
if [ $? -eq 0 ]; then
    echo "🎉 Setup completed successfully!"
else
    echo "❌ Setup failed. Please check the error messages above."
    exit 1
fi