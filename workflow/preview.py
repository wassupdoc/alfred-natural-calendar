#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json
import re
from datetime import datetime, timedelta
from typing import Optional, List

# Setup imports
if __name__ == '__main__':
    from utils import setup_imports
    setup_imports()

# Now import workflow modules
from __init__ import build_time_pattern, parse_time_match
from logger import setup_logger
from config import get_testing_mode

# Get logger
logger = setup_logger('preview', testing=get_testing_mode())

def get_workflow_data_dir():
    """Get Alfred workflow data directory"""
    data_dir = os.getenv('alfred_workflow_data')
    if not data_dir:
        data_dir = os.path.expanduser('~/Library/Application Support/Alfred/Workflow Data/com.ariestwn.calendar.nlp')
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

class EventPreview:
    def __init__(self):
        logger.debug("Initializing EventPreview")
        # Initialize patterns
        self.calendar_pattern = r'#(?:"([^"]+)"|\'([^\']+)\'|([^"\'\s]+))'
        self.time_pattern = build_time_pattern()
        self.location_pattern = r'(?:^|\s)(?:at|in)\s+([^,\.\d][^,\.]*?)(?=\s+(?:on|at|from|tomorrow|today|next|every|\d{1,2}(?::\d{2})?(?:am|pm)|url:|notes?:|link:)|\s*$)'
        
        # Load default calendar from config
        config_file = os.path.join(get_workflow_data_dir(), 'calendar_config.json')
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                self.default_calendar = config.get('default_calendar', 'Calendar')
        except:
            self.default_calendar = 'Calendar'
        
        # Weekday mapping for date parsing
        self.weekdays = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6,
            'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3,
            'fri': 4, 'sat': 5, 'sun': 6
        }

    def get_calendar(self, text: str) -> str:
        """Extract calendar name from text or use default"""
        calendar_match = re.search(self.calendar_pattern, text)
        if calendar_match:
            # Only get the first non-None group
            requested_calendar = next((g for g in calendar_match.groups() if g is not None), None)
            if requested_calendar:
                # Print for debugging
                print(f"Debug - Calendar found in preview: {requested_calendar}", file=sys.stderr)
                return requested_calendar.strip()
        return self.default_calendar

    def parse_time(self, text: str) -> Optional[datetime]:
        """Parse time from text"""
        match = re.search(self.time_pattern, text, re.IGNORECASE)
        if match:
            hour, minutes = parse_time_match(match)
            now = datetime.now()
            return now.replace(hour=hour, minute=minutes, second=0, microsecond=0)
        return None

    def get_next_weekday(self, weekday_name: str) -> datetime:
        """Get next occurrence of weekday"""
        weekday_name = weekday_name.lower()
        if weekday_name not in self.weekdays:
            return None
        
        today = datetime.now()
        target_weekday = self.weekdays[weekday_name]
        days_ahead = (target_weekday - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return today + timedelta(days=days_ahead)

    def parse_date(self, text: str) -> str:
        """Parse and format date from text"""
        text_lower = text.lower()
        today = datetime.now()
        target_date = None
        target_time = self.parse_time(text_lower)

        # Handle recurring events
        if 'every' in text_lower:
            for day in self.weekdays:
                if day in text_lower:
                    if target_time:
                        return f"Every {day.capitalize()} at {target_time.strftime('%-I:%M %p')}"
                    return f"Every {day.capitalize()}"

        # Handle weekdays
        for day in self.weekdays:
            if day in text_lower:
                target_date = self.get_next_weekday(day)
                break

        # Handle relative dates
        if 'tomorrow' in text_lower:
            target_date = today + timedelta(days=1)
        elif 'next week' in text_lower:
            target_date = today + timedelta(days=7)
        elif not target_date:
            target_date = today

        # Set time if specified
        if target_date and target_time:
            target_date = target_date.replace(
                hour=target_time.hour,
                minute=target_time.minute
            )

        # Format output
        if not target_date:
            return "Invalid date"
        
        if target_date.date() == today.date():
            return f"Today at {target_date.strftime('%-I:%M %p')}"
        elif target_date.date() == (today + timedelta(days=1)).date():
            return f"Tomorrow at {target_date.strftime('%-I:%M %p')}"
        return target_date.strftime("%A, %B %-d at %-I:%M %p")

    def clean_title(self, text: str) -> str:
        """Clean title from input text"""
        # Remove calendar tag
        text = re.sub(self.calendar_pattern, '', text)
        
        # Remove date/time patterns
        patterns_to_remove = [
            r'\b(?:tomorrow|today|next|on|at|from|to|every|daily|weekly|monthly)\b.*$',
            r'\d{1,2}(?::(\d{2}))?\s*(?:am|pm).*$',
            r'for\s+\d+\s+(?:day|hour|minute|min)s?.*$',
            r'(?:alert|remind).*$',
            r'with\s+\d+\s*(?:minute|min|hour)s?\s+(?:alert|reminder)',
            r'(?:^|\s)(?:at|in)\s+([^,\.\d][^,\.]*?)(?=\s+|$)'
        ]
        
        for pattern in patterns_to_remove:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return ' '.join(text.split())

    def parse_location(self, text: str) -> Optional[str]:
        """Extract location from text"""
        match = re.search(self.location_pattern, text)
        if match:
            location = match.group(1).strip()
            return location
        return None

    def generate_items(self, text: str) -> List[dict]:
        """Generate preview items"""
        logger.debug(f"Generating preview for: {text}")
        title = self.clean_title(text)
        calendar = self.get_calendar(text)
        date = self.parse_date(text)
        location = self.parse_location(text)
        
        # Instead of removing the calendar tag, preserve it
        subtitle_parts = [f"📅 {calendar}"]
        if date:
            subtitle_parts.append(date)
        if location:
            subtitle_parts.append(f"📍 {location}")
        
        subtitle = " • ".join(subtitle_parts)
        
        return [{
            "title": title or "Type event details...",
            "subtitle": subtitle,
            "arg": text,  # Pass the original text with calendar tag
            "valid": bool(title and date != "Invalid date"),
            "icon": {"path": "icon.png"}
        }]

def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "items": [{
                "title": "Type event details...",
                "subtitle": "Use natural language to describe your event",
                "valid": False,
                "icon": {"path": "icon.png"}
            }]
        }))
        return

    query = " ".join(sys.argv[1:])
    preview = EventPreview()
    items = preview.generate_items(query)
    print(json.dumps({"items": items}))

if __name__ == "__main__":
    main()