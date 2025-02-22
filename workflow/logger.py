#!/usr/bin/env python3
import os
import logging
import json
from datetime import datetime

def setup_logger(name, testing=False):
    """Setup logger that can be toggled for testing"""
    logger = logging.getLogger(name)
    
    # Only setup handler if testing is enabled and none exists
    if testing and not logger.handlers:
        # Use common log file for all components
        data_dir = os.path.dirname(os.path.abspath(__file__))
        log_file = os.path.join(data_dir, 'workflow.log')
        
        # Create a handler if none exists for this log file
        if not any(isinstance(h, logging.FileHandler) and h.baseFilename == log_file 
                  for h in logging.root.handlers):
            handler = logging.FileHandler(log_file)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            
            # Add handler to root logger
            logging.root.addHandler(handler)
            logging.root.setLevel(logging.DEBUG)
            
            # Add startup marker to log
            logging.info('='*50)
            logging.info(f'Logging started at {datetime.now()}')
            logging.info('='*50)
    
    return logger 