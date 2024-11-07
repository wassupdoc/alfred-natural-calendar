#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
setup.py - Automatic dependency installer for Calendar NLP Workflow
This script runs automatically when the workflow is first used or when dependencies are missing.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
import json

def setup_workflow():
    """Install required dependencies for the workflow"""
    workflow_dir = os.path.dirname(os.path.abspath(__file__))
    lib_dir = os.path.join(workflow_dir, 'lib')
    
    # Clear existing lib directory if it exists
    if os.path.exists(lib_dir):
        shutil.rmtree(lib_dir)
    
    # Create fresh lib directory
    os.makedirs(lib_dir, exist_ok=True)
    
    # Create __init__.py
    Path(os.path.join(lib_dir, '__init__.py')).touch()
    
    # Install python-dateutil
    try:
        subprocess.run([
            sys.executable,
            '-m', 'pip',
            'install',
            '--target', lib_dir,
            '--upgrade',
            '--no-cache-dir',
            'python-dateutil'
        ], check=True)
        
        # Verify installation
        sys.path.insert(0, lib_dir)
        try:
            from dateutil import parser
            print("Dependencies installed successfully!")
            return True
        except ImportError:
            print("Failed to verify installation.")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        return False

def main():
    try:
        if setup_workflow():
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"Setup failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()