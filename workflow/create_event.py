#!/usr/bin/env python3
import sys
import json
import subprocess
from typing import Dict
import logging
import os

# Setup imports
if __name__ == '__main__':
    from utils import setup_imports
    setup_imports()

# Now import workflow modules
from logger import setup_logger
from config import get_testing_mode

# Get logger
logger = setup_logger('create_event', testing=get_testing_mode())

def create_calendar_event(event: Dict) -> bool:
    """Create calendar event using AppleScript"""
    logger.debug(f"Creating event: {event}")
    
    # Parse dates into components
    start_year = event['start_date'][:4]
    start_month = int(event['start_date'][5:7])
    start_day = int(event['start_date'][8:10])
    start_hour = int(event['start_time'][:2])
    start_min = int(event['start_time'][3:5])
    
    end_year = event['end_date'][:4]
    end_month = int(event['end_date'][5:7])
    end_day = int(event['end_date'][8:10])
    end_hour = int(event['end_time'][:2])
    end_min = int(event['end_time'][3:5])
    
    # Build base properties
    properties = [
        f'summary:"{event["title"]}"',
        f'start date:startDate',
        f'end date:endDate'
    ]
    
    # Add optional properties
    if event.get('location'):
        properties.append(f'location:"{event["location"]}"')
    if event.get('url'):
        properties.append(f'url:"{event["url"]}"')
    if event.get('notes'):
        properties.append(f'description:"{event["notes"]}"')
    
    # Join properties with commas
    properties_str = ', '.join(properties)
    
    # Build AppleScript command - note the careful spacing and no trailing whitespace
    script = f'''tell application "Calendar"
    tell calendar "{event['calendar']}"
        set startDate to current date
        set year of startDate to {start_year}
        set month of startDate to {start_month}
        set day of startDate to {start_day}
        set hours of startDate to {start_hour}
        set minutes of startDate to {start_min}
        set seconds of startDate to 0
        
        set endDate to current date
        set year of endDate to {end_year}
        set month of endDate to {end_month}
        set day of endDate to {end_day}
        set hours of endDate to {end_hour}
        set minutes of endDate to {end_min}
        set seconds of endDate to 0
        
        make new event at end of events with properties {{{properties_str}}}
    end tell
end tell'''
    
    logger.debug(f"AppleScript: {script}")
    
    try:
        result = subprocess.run(['osascript', '-e', script], 
                              capture_output=True,
                              text=True,
                              check=True)
        logger.debug(f"Success: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error: {e.stderr}")
        print(f"Error creating event: {e}", file=sys.stderr)
        return False

def main():
    if len(sys.argv) < 2:
        logger.error("No event data provided")
        print("No event data provided")
        sys.exit(1)
        
    event_json = sys.argv[1]
    try:
        logger.debug(f"Received event JSON: {event_json}")
        event = json.loads(event_json)
        logger.debug(f"Parsed event: {event}")
        
        if create_calendar_event(event):
            result = json.dumps({
                "alfredworkflow": {
                    "arg": "Event created successfully",
                    "variables": {
                        "notificationTitle": "Calendar Event"
                    }
                }
            })
            logger.debug(f"Success response: {result}")
            print(result)
        else:
            result = json.dumps({
                "alfredworkflow": {
                    "arg": "Failed to create event",
                    "variables": {
                        "notificationTitle": "Error"
                    }
                }
            })
            logger.error(f"Failed to create event")
            print(result)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid event data format: {e}")
        print("Invalid event data format")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 