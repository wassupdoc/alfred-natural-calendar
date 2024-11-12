#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import shutil
from pathlib import Path

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
    
    # Install python-dateutil quietly
    try:
        subprocess.run([
            sys.executable,
            '-m', 'pip',
            'install',
            '--target', lib_dir,
            '--quiet',  # Make pip quiet
            '--no-cache-dir',
            'python-dateutil'
        ], check=True,
        stdout=subprocess.DEVNULL,  # Hide stdout
        stderr=subprocess.DEVNULL)  # Hide stderr
        
        # Verify installation
        sys.path.insert(0, lib_dir)
        try:
            from dateutil import parser
            return True
        except ImportError:
            return False
            
    except subprocess.CalledProcessError:
        return False

def main():
    if setup_workflow():
        sys.exit(0)
    sys.exit(1)

if __name__ == "__main__":
    main()