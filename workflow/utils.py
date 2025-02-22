import os
import sys

def setup_imports():
    """Setup imports to work both as module and direct script"""
    workflow_dir = os.path.dirname(os.path.abspath(__file__))
    if workflow_dir not in sys.path:
        sys.path.insert(0, workflow_dir) 