#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os

# Add lib directory to Python path before any other imports
workflow_dir = os.path.dirname(os.path.abspath(__file__))
lib_dir = os.path.join(workflow_dir, 'lib')
sys.path.insert(0, lib_dir)

# Now try importing dateutil
try:
    from dateutil import parser
except ImportError as e:
    import json
    print(json.dumps({
        "items": [{
            "title": "Setup Required",
            "subtitle": "Run setup.sh to install required dependencies",
            "valid": False,
            "icon": {
                "path": "icon.png"
            }
        }]
    }))
    sys.exit(1)

import json
import re
from datetime import datetime, timedelta
from typing import Optional, List

class EventPreview:
    def __init__(self):
        self.url_patterns = [
            r'(?:url|link):\s*((?:https?://)[^\s]+)',
            r'\b((?:https?://)[^\s]+)(?=\s+(?:notes?:|$)|$)'
        ]
        self.notes_patterns = [
            r'notes?:\s*([^|]+?)(?=(?:\s+url:|\s+link:|\s*$))',
            r'description:\s*([^|]+?)(?=(?:\s+url:|\s+link:|\s*$))',
            r'details?:\s*([^|]+?)(?=(?:\s+url:|\s+link:|\s*$))'
        ]
        self.location_patterns = [
            r'(?:^|\s)(?:at|in)\s+([^,\.\d][^,\.]*?)(?=\s+(?:on|at|from|tomorrow|today|next|every|\d{1,2}(?::\d{2})?(?:am|pm)|url:|notes?:|link:)|\s*$)'
        ]
        self.default_calendar = self.get_default_calendar()
        self.time_pattern = r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b'
        self.weekdays = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6,
            'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3,
            'fri': 4, 'sat': 5, 'sun': 6
        }

    def get_default_calendar(self):
        config_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'calendar_config.json')
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                return config.get('default_calendar', 'Calendar')
        except:
            return 'Calendar'

    def parse_time(self, text: str) -> Optional[datetime]:
        """Parse time from text with proper handling of hours without minutes"""
        match = re.search(self.time_pattern, text, re.IGNORECASE)
        if match:
            hour = int(match.group(1))
            minutes = int(match.group(2)) if match.group(2) else 0
            meridiem = match.group(3).lower() if match.group(3) else ''
            
            # Convert to 24-hour format if needed
            if meridiem == 'pm' and hour != 12:
                hour += 12
            elif meridiem == 'am' and hour == 12:
                hour = 0
            
            now = datetime.now()
            return now.replace(hour=hour, minute=minutes, second=0, microsecond=0)
        return None

    def get_next_weekday(self, weekday_name: str) -> datetime:
        """Get the next occurrence of a weekday"""
        weekday_name = weekday_name.lower()
        if weekday_name not in self.weekdays:
            return None
            
        today = datetime.now()
        target_weekday = self.weekdays[weekday_name]
        days_ahead = (target_weekday - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return today + timedelta(days=days_ahead)

    def is_recurring(self, text: str) -> bool:
        """Check if event is recurring"""
        recurring_patterns = [
            r'every\s+',
            r'daily',
            r'weekly',
            r'monthly',
            r'yearly',
            r'annually'
        ]
        text_lower = text.lower()
        return any(re.search(pattern, text_lower) for pattern in recurring_patterns)

    def parse_date(self, text: str) -> str:
        try:
            text_lower = text.lower()
            today = datetime.now()
            target_date = None
            target_time = None

            # Parse time first
            time_match = re.search(self.time_pattern, text_lower)
            if time_match:
                target_time = self.parse_time(text_lower)

            # Check recurring events
            if self.is_recurring(text_lower):
                for day in self.weekdays:
                    if day in text_lower:
                        if target_time:
                            return f"Every {day.capitalize()} at {target_time.strftime('%-I:%M %p')}"
                        return f"Every {day.capitalize()}"
            
            # Check for specific weekday
            for day in self.weekdays:
                if day in text_lower:
                    target_date = self.get_next_weekday(day)
                    break

            # Check for tomorrow
            if 'tomorrow' in text_lower:
                target_date = today + timedelta(days=1)
            # Check for next week
            elif 'next week' in text_lower:
                target_date = today + timedelta(days=7)
            # If no date specified, use today
            elif not target_date:
                target_date = today

            # Combine date and time
            if target_date:
                if target_time:
                    target_date = target_date.replace(
                        hour=target_time.hour,
                        minute=target_time.minute,
                        second=0,
                        microsecond=0
                    )

                # Format output
                if target_date.date() == today.date():
                    return f"Today at {target_date.strftime('%-I:%M %p')}"
                elif target_date.date() == (today + timedelta(days=1)).date():
                    return f"Tomorrow at {target_date.strftime('%-I:%M %p')}"
                else:
                    return target_date.strftime("%A, %B %-d at %-I:%M %p")

        except Exception as e:
            print(f"Error parsing date: {str(e)}", file=sys.stderr)
            return "Invalid date"

        return "Invalid date"

    def clean_title(self, text: str) -> str:
        # Remove calendar tags
        text = re.sub(r'#\w+\s*', '', text)
        
        # Remove URLs and notes
        for pattern in self.url_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        for pattern in self.notes_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Remove date/time patterns
        patterns_to_remove = [
            r'\b(?:tomorrow|today|next|on|at|from|to|every|daily|weekly|monthly)\b.*$',
            r'\d{1,2}(?::\d{2})?\s*(?:am|pm).*$',
            r'for\s+\d+\s+(?:day|hour|minute|min)s?.*$',
            r'(?:alert|remind).*$',
            r'with\s+\d+\s*(?:minute|min|hour)s?\s+(?:alert|reminder)',
            r'url\s+https?://\S+'
        ]
        
        title = text
        for pattern in patterns_to_remove:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)
        
        # Clean up remaining artifacts
        title = re.sub(r'\s+for\s*$', '', title)
        title = re.sub(r'\s+in\s*$', '', title)
        title = re.sub(r'\s+at\s*$', '', title)
        title = re.sub(r'\s+', ' ', title)
        
        return title.strip()

    def get_calendar(self, text: str) -> str:
        calendar_match = re.search(r'#(\w+)', text)
        if calendar_match:
            return calendar_match.group(1).capitalize()
        return self.default_calendar

    def parse_location(self, text: str) -> Optional[str]:
        for pattern in self.location_patterns:
            match = re.search(pattern, text)
            if match:
                location = match.group(1).strip()
                if not any(p in location.lower() for p in ['notes:', 'url:', 'link:', 'alert', 'remind']):
                    location = re.sub(r'for\s+\d+\s+(?:day|hour|minute|min)s?', '', location, flags=re.IGNORECASE)
                    location = re.sub(r'\d{1,2}(?::\d{2})?\s*(?:am|pm)', '', location, flags=re.IGNORECASE)
                    location = re.sub(r'(?:^|\s+)(?:at|in)\s+', '', location, flags=re.IGNORECASE)
                    return location.strip()
        return None

    def generate_items(self, text: str) -> List[dict]:
        title = self.clean_title(text)
        calendar = self.get_calendar(text)
        date = self.parse_date(text)
        location = self.parse_location(text)
        
        subtitle_parts = [f"📅 {calendar}"]
        if date:
            subtitle_parts.append(date)
        if location:
            subtitle_parts.append(f"📍 {location}")
        
        subtitle = " • ".join(subtitle_parts)
        
        items = [{
            "title": title or "Type event details...",
            "subtitle": subtitle,
            "arg": text,
            "valid": bool(title and date != "Invalid date"),
            "icon": {
                "path": "icon.png"
            }
        }]

        return items

def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "items": [{
                "title": "Type event details...",
                "subtitle": "Use natural language to describe your event",
                "valid": False,
                "icon": {
                    "path": "icon.png"
                }
            }]
        }))
        return

    query = " ".join(sys.argv[1:])
    preview = EventPreview()
    items = preview.generate_items(query)
    print(json.dumps({"items": items}))

if __name__ == "__main__":
    main()