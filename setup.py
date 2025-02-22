#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import shutil
from pathlib import Path

def install_dependencies():
    """Install required Python packages"""
    workflow_dir = os.path.dirname(os.path.abspath(__file__))
    lib_dir = os.path.join(workflow_dir, 'lib')
    
    # Create lib directory if it doesn't exist
    os.makedirs(lib_dir, exist_ok=True)
    
    # Install python-dateutil to lib directory
    try:
        subprocess.check_call([
            sys.executable, 
            '-m', 
            'pip', 
            'install',
            '--target=' + lib_dir,
            'python-dateutil'
        ])
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    install_dependencies()

if __name__ == "__main__":
    main()