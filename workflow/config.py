import os
import json

def get_testing_mode():
    """Check if testing mode is enabled"""
    config_file = os.path.join(os.path.dirname(__file__), 'config.json')
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            return config.get('testing_mode', False)
    except:
        return False 