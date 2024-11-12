#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import subprocess
import json

def ensure_dependencies():
    """Ensure all required dependencies are installed"""
    workflow_dir = os.path.dirname(os.path.abspath(__file__))
    lib_dir = os.path.join(workflow_dir, 'lib')
    
    if not os.path.exists(lib_dir) or not os.path.exists(os.path.join(lib_dir, 'dateutil')):
        setup_script = os.path.join(workflow_dir, 'setup.py')
        try:
            subprocess.run([sys.executable, setup_script], 
                         check=True,
                         stdout=subprocess.DEVNULL,  # Hide stdout
                         stderr=subprocess.DEVNULL)  # Hide stderr
            
            print(json.dumps({
                "alfredworkflow": {
                    "arg": "Setup complete. Please try again.",
                    "variables": {
                        "notificationTitle": "NLP Calendar setup"
                    }
                }
            }))
            sys.exit(0)
        except subprocess.CalledProcessError:
            print(json.dumps({
                "alfredworkflow": {
                    "arg": "Setup failed. Please check the workflow logs.",
                    "variables": {
                        "notificationTitle": "Error"
                    }
                }
            }))
            sys.exit(1)

# Run dependency check before any other imports
ensure_dependencies()

# Now it's safe to import other modules
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
from dateutil import parser, relativedelta
import re
from datetime import datetime, timedelta, date
import urllib.parse
from typing import Dict, Optional, List, Tuple

def get_workflow_data_dir():
    """Get Alfred workflow data directory"""
    data_dir = os.getenv('alfred_workflow_data')
    if not data_dir:
        data_dir = os.path.expanduser('~/Library/Application Support/Alfred/Workflow Data/com.ariestwn.calendar.nlp')
    
    # Create directory if it doesn't exist
    os.makedirs(data_dir, exist_ok=True)
    return data_dir

class CalendarNLPProcessor:
    def __init__(self):
        self.calendars = self.get_available_calendars()
        self.config = self.load_config()
        self.time_pattern = r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b'
        self.calendar_pattern = r'#(?:"([^"]+)"|\'([^\']+)\'|(\S+))'
        self.relative_time_pattern = r'in\s+(\d+)\s+(minutes?|hours?)'
        self.date_range_pattern = r'from\s+(\w+\s+\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s*(?:-|to)\s*(\w+\s+\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?)'
        self.duration_patterns = {
            'days': r'for\s+(\d+)\s+days?',
            'hours': r'for\s+(\d+)\s+hours?',
            'minutes': r'for\s+(\d+)\s+min(?:ute)?s?',
            'time_range': r'(\d{1,2})(?::(\d{2}))?\s*(?:am|pm)?(?:\s*-\s*(\d{1,2})(?::(\d{2}))?\s*(?:am|pm)?)'
        }
        self.location_patterns = [
            r'(?:^|\s)(?:at|in)\s+([^,\.\d][^,\.]*?)(?=\s+(?:on|at|from|tomorrow|today|next|every|\d{1,2}(?::\d{2})?(?:am|pm)|url:|notes?:|link:)|\s*$)'
        ]
        self.alert_patterns = {
            r'with\s+(\d+)\s*min(?:ute)?s?\s+(?:alert|reminder)': 'minutes',
            r'(\d+)\s*min(?:ute)?s?\s+(?:alert|reminder)': 'minutes',
            r'(\d+)\s*hour(?:s)?\s+(?:alert|reminder)': 'hours',
            r'(?:alert|remind)\s+(\d+)\s*min(?:ute)?s?\s+before': 'minutes',
            r'(?:alert|remind)\s+(\d+)\s*hour(?:s)?\s+before': 'hours'
        }
        self.url_patterns = [
            r'(?:url|link):\s*((?:https?://)[^\s]+)',
            r'\b((?:https?://)[^\s]+)(?=\s+(?:notes?:|$)|$)'
        ]
        self.notes_patterns = [
            r'notes?:\s*([^|]+?)(?=(?:\s+url:|\s+link:|\s*$))',
            r'description:\s*([^|]+?)(?=(?:\s+url:|\s+link:|\s*$))',
            r'details?:\s*([^|]+?)(?=(?:\s+url:|\s+link:|\s*$))'
        ]
        self.recurrence_patterns = {
            # Only match explicit recurring patterns
            r'every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)': lambda x: f'FREQ=WEEKLY;BYDAY={x.group(1)[:2].upper()}',
            r'every\s+(mon|tue|wed|thu|fri|sat|sun)': lambda x: f'FREQ=WEEKLY;BYDAY={x.group(1)[:2].upper()}',
            r'every\s+week(?:ly)?': 'FREQ=WEEKLY',
            r'every\s+day|daily': 'FREQ=DAILY',
            r'every\s+month|monthly': 'FREQ=MONTHLY',
            r'every\s+year|yearly|annually': 'FREQ=YEARLY',
            
            # Pattern for weekdays with end date
            r'every\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+until\s+(\d{1,2}/\d{1,2}(?:/\d{2,4})?)'
            : lambda x: f'FREQ=WEEKLY;BYDAY={x.group(1)[:2].upper()};UNTIL={parser.parse(x.group(2)).strftime("%Y%m%dT235959Z")}',
            
            # Multiple weekdays must be explicit with "every"
            r'every\s+(?:mon|tue|wed|thu|fri|sat|sun)(?:days?|\.)?(?:\s+and\s+(?:mon|tue|wed|thu|fri|sat|sun)(?:days?|\.)?)*': 
                lambda x: f'FREQ=WEEKLY;BYDAY={",".join(day[:2].upper() for day in re.findall(r"mon|tue|wed|thu|fri|sat|sun", x.group(0)))}'
        }
        self.calendar_keywords = {
            'work': ['work', 'office', 'business'],
            'personal': ['personal', 'private'],
            'family': ['family', 'home']
        }
        self.weekday_map = {
            'monday': 'MO', 'tuesday': 'TU', 'wednesday': 'WE', 'thursday': 'TH',
            'friday': 'FR', 'saturday': 'SA', 'sunday': 'SU',
            'mon': 'MO', 'tue': 'TU', 'wed': 'WE', 'thu': 'TH',
            'fri': 'FR', 'sat': 'SA', 'sun': 'SU'
        }

    def parse_date_range(self, text: str) -> Optional[Tuple[datetime, datetime]]:
        """Parse date range from text"""
        match = re.search(self.date_range_pattern, text, re.IGNORECASE)
        if match:
            start_str, end_str = match.groups()
            try:
                start_date = parser.parse(start_str)
                end_date = parser.parse(end_str)
                # If year not specified, use current year
                if start_date.year == datetime.now().year and end_date.year == datetime.now().year:
                    if end_date < start_date:
                        end_date = end_date.replace(year=end_date.year + 1)
                return start_date, end_date
            except:
                return None
        return None
    
    
    def load_config(self) -> Dict:
        """Load calendar configuration from the correct location"""
        data_dir = get_workflow_data_dir()
        config_file = os.path.join(data_dir, 'calendar_config.json')
        
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                # Verify that default calendar exists
                if config.get('default_calendar'):
                    # Find exact match ignoring case
                    matching_calendars = [cal for cal in self.calendars 
                                    if cal.lower() == config['default_calendar'].lower()]
                    if matching_calendars:
                        config['default_calendar'] = matching_calendars[0]
                    else:
                        config['default_calendar'] = "Calendar"
                else:
                    config['default_calendar'] = "Calendar"
                return config
        except Exception as e:
            print(f"Error loading config: {str(e)}", file=sys.stderr)
            return {"default_calendar": "Calendar"}

    def get_available_calendars(self) -> List[str]:
        """Get list of available and writable calendars"""
        script = '''
        tell application "Calendar"
            set calList to {}
            repeat with calItem in calendars
                try
                    if writable of calItem then
                        copy (name of calItem as string) to the end of calList
                    end if
                end try
            end repeat
            return calList
        end tell
        '''
        try:
            result = subprocess.run(['osascript', '-e', script],
                                  capture_output=True,
                                  text=True,
                                  check=True)
            calendars = [cal.strip() for cal in result.stdout.strip().split(',')]
            if not calendars:
                print("Warning: No writable calendars found", file=sys.stderr)
                return ["Calendar"]
            return calendars
        except subprocess.CalledProcessError as e:
            print(f"Error getting calendars: {e}", file=sys.stderr)
            return ["Calendar"]

    def parse_calendar_name(self, text: str) -> str:
        """Determine which calendar to use based on text"""
        # First check for explicit calendar selection with #
        calendar_match = re.search(r'#(\w+)', text)
        if calendar_match:
            calendar_name = calendar_match.group(1).capitalize()
            if calendar_name in self.calendars:
                return calendar_name
        
        # Then check for calendar keywords
        text_lower = text.lower()
        for cal_name, keywords in self.calendar_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                matching_cals = [c for c in self.calendars if cal_name.lower() in c.lower()]
                if matching_cals:
                    return matching_cals[0]
        
        # If no matches found, use default calendar from config
        return self.config.get('default_calendar')

    def parse_duration(self, text: str) -> int:
        """Extract duration in minutes from text"""
        # First check for time range (e.g., "5-6pm")
        range_match = re.search(self.duration_patterns['time_range'], text, re.IGNORECASE)
        if range_match:
            start_hour, start_min, end_hour, end_min = range_match.groups()
            start_hour = int(start_hour)
            start_min = int(start_min) if start_min else 0
            end_hour = int(end_hour)
            end_min = int(end_min) if end_min else 0
            
            # Convert to 24-hour format if needed
            if 'pm' in text.lower():
                if start_hour != 12:
                    start_hour += 12
                if end_hour != 12:
                    end_hour += 12
            
            duration_minutes = (end_hour * 60 + end_min) - (start_hour * 60 + start_min)
            if duration_minutes > 0:
                return duration_minutes
                
        # Check other duration patterns
        total_minutes = 60  # Default duration
        
        days_match = re.search(self.duration_patterns['days'], text, re.IGNORECASE)
        if days_match:
            return int(days_match.group(1)) * 24 * 60
        
        hours_match = re.search(self.duration_patterns['hours'], text, re.IGNORECASE)
        if hours_match:
            total_minutes = int(hours_match.group(1)) * 60
        
        minutes_match = re.search(self.duration_patterns['minutes'], text, re.IGNORECASE)
        if minutes_match:
            total_minutes = int(minutes_match.group(1))
        
        return total_minutes

    def clean_title(self, text: str) -> str:
        """Clean up the title"""
        # First clean recurrence and date/time info
        patterns_to_remove = [
            r'\bevery\b\s+\w+',  # Remove "every" patterns
            r'\b(?:tomorrow|today|next|on|at|from|to|daily|weekly|monthly)\b.*$',
            r'\bon\s+(?:mon|tue|wed|thu|fri|sat|sun)(?:day)?',  # Remove "on weekday"
            r'\b(?:mon|tue|wed|thu|fri|sat|sun)(?:day)?',  # Remove weekday mentions
            r'\d{1,2}(?::\d{2})?\s*(?:am|pm).*$',
            r'for\s+\d+\s+(?:day|hour|minute|min)s?.*$',
            r'(?:alert|remind).*$',
            r'with\s+\d+\s*(?:minute|min|hour)s?\s+(?:alert|reminder)',
            r'url\s+https?://\S+'
        ]
        
        title = text
        for pattern in patterns_to_remove:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)
        
        # Remove URLs and notes
        for pattern in self.url_patterns + self.notes_patterns:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)
        
        # Clean up remaining artifacts
        title = re.sub(r'\s+for\s*$', '', title)
        title = re.sub(r'\s+in\s*$', '', title)
        title = re.sub(r'\s+at\s*$', '', title)
        title = re.sub(r'\s+', ' ', title)
        
        return title.strip()

    def parse_location(self, text: str) -> Optional[str]:
        """Extract location from text"""
        for pattern in self.location_patterns:
            match = re.search(pattern, text)
            if match:
                location = match.group(1).strip()
                if not any(p in location.lower() for p in ['notes:', 'url:', 'link:', 'alert', 'remind']):
                    # Remove duration and time references
                    location = re.sub(r'for\s+\d+\s+(?:day|hour|minute|min)s?', '', location, flags=re.IGNORECASE)
                    location = re.sub(r'\d{1,2}(?::\d{2})?\s*(?:am|pm)', '', location, flags=re.IGNORECASE)
                    location = re.sub(r'(?:^|\s+)(?:at|in)\s+', '', location, flags=re.IGNORECASE)
                    return location.strip()
        return None
    
    def clean_location(self, text: str, time_str: str = '') -> Optional[str]:
        """Clean up location string"""
        if not text:
            return None

        cleaned = text.strip()
        
        # Remove specific words and patterns
        patterns_to_remove = [
            r'\bstarting\b',
            r'for\s+\d+\s+(?:day|hour|minute|min)s?',
            r'\d{1,2}(?::\d{2})?\s*(?:am|pm)',
            r'(?:^|\s+)(?:at|in)\s+',
            r'\s+for\s*$',
            r'url:.*$',
            r'notes:.*$',
            r'with\s+\d+\s*min(?:ute)?s?\s+alert',
            r'alert\s+\d+\s*min(?:ute)?s?'
        ]
        
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Clean up extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        return cleaned if cleaned else None

    def _extract_notes(self, text: str) -> Tuple[Optional[str], str]:
        for pattern in self.notes_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip(), text.replace(match.group(0), '')
        return None, text

    def _extract_zoom_url(self, text: str) -> Optional[str]:
        zoom_pattern = r'(?:url:\s*|link:\s*|)(https?://(?:[\w-]+\.)*zoom\.us/[^\s]+)'
        zoom_match = re.search(zoom_pattern, text, re.IGNORECASE)
        if zoom_match:
            return zoom_match.group(1).rstrip('.,;')
        return None

    def _extract_general_url(self, text: str) -> Optional[str]:
        general_pattern = r'(?:url:\s*|link:\s*|)(https?://[^\s]+)'
        url_match = re.search(general_pattern, text, re.IGNORECASE)
        if url_match:
            potential_url = url_match.group(1).rstrip('.,;')
            try:
                result = urllib.parse.urlparse(potential_url)
                if all([result.scheme, result.netloc]):
                    return potential_url
            except Exception:
                pass
        return None

    def parse_url_and_notes(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract URL and notes from text"""
        notes, working_text = self._extract_notes(text)
        
        if 'zoom.us' in working_text.lower():
            url = self._extract_zoom_url(working_text)
        else:
            url = self._extract_general_url(working_text)
        
        return url, notes

    def fix_relative_date(self, base_date: datetime, text: str) -> datetime:
        """Fix relative dates based on current date"""
        today = datetime.now()
        text_lower = text.lower()
        
        if 'tomorrow' in text_lower:
            tomorrow = today + timedelta(days=1)
            return base_date.replace(
                year=tomorrow.year,
                month=tomorrow.month,
                day=tomorrow.day
            )
        elif 'next' in text_lower:
            target_date = base_date
            if 'monday' in text_lower:
                # Calculate next Monday
                days_ahead = 0 - today.weekday() + 7  # Next week's Monday
                target_date = today + timedelta(days=days_ahead)
            elif 'week' in text_lower:
                target_date = today + timedelta(days=7)
            else:
                # For other cases, ensure date is in the future
                while target_date <= today:
                    target_date += timedelta(days=7)
            
            # Copy time from base_date to target_date
            return target_date.replace(
                hour=base_date.hour,
                minute=base_date.minute,
                second=0,
                microsecond=0
            )
        elif any(day in text_lower for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']):
            target_date = base_date
            while target_date <= today:
                target_date += timedelta(days=7)
            return target_date
        
        return base_date

    def parse_alerts(self, text: str) -> List[int]:
        alerts = set()  # Gunakan set untuk menghindari duplikat
        for pattern, unit in self.alert_patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                time_val = int(match.group(1))
                if unit == 'hours':
                    time_val *= 60  # Konversi jam ke menit
                alerts.add(time_val)
        return sorted(alerts) if alerts else [15]  # Default 15 menit jika tidak ada yang cocok

    def parse_recurrence(self, text: str) -> Optional[str]:
        """Extract recurrence pattern from text"""
        # Only process recurrence if "every" is present
        if not re.search(r'\bevery\b', text.lower()):
            return None
            
        text_lower = text.lower()
        
        # Handle "every year on MM/DD"
        birthday_match = re.search(r'every\s+year\s+on\s+(\d{1,2}/\d{1,2})', text_lower)
        if birthday_match:
            date_str = birthday_match.group(1)
            month, day = map(int, date_str.split('/'))
            return f'FREQ=YEARLY;BYMONTH={month};BYMONTHDAY={day}'
        
        # Check other recurrence patterns
        for pattern, format_str in self.recurrence_patterns.items():
            match = re.search(pattern, text_lower)
            if match:
                if callable(format_str):
                    return format_str(match)
                return format_str
                
        return None
    
    def parse_time(self, text: str, base_date: datetime) -> datetime:
        """Parse time from text with proper handling of different formats"""
        # Check for "now"
        if 'now' in text.lower():
            return datetime.now().replace(second=0, microsecond=0)
            
        # Check for "in X minutes/hours"
        relative_match = re.search(self.relative_time_pattern, text, re.IGNORECASE)
        if relative_match:
            amount = int(relative_match.group(1))
            unit = relative_match.group(2).lower()
            now = datetime.now()
            if 'hour' in unit:
                return now + timedelta(hours=amount)
            else:
                return now + timedelta(minutes=amount)
                
        # Regular time pattern
        match = re.search(self.time_pattern, text, re.IGNORECASE)
        if match:
            hour = int(match.group(1))
            minutes = int(match.group(2)) if match.group(2) else 0
            meridiem = match.group(3).lower() if match.group(3) else ''
            
            # Handle PM times
            if meridiem == 'pm' and hour != 12:
                hour += 12
            elif meridiem == 'am' and hour == 12:
                hour = 0
                
            return base_date.replace(hour=hour, minute=minutes, second=0, microsecond=0)
            
        return base_date

    def parse_event(self, text: str) -> dict:
        try:
            url, notes = self.parse_url_and_notes(text)
            clean_text = self._clean_text_for_parsing(text, url)
            
            # Get calendar based on text or default
            calendar_name = self.parse_calendar_name(clean_text)
            
            # Check for date range
            date_range = self.parse_date_range(clean_text)
            if date_range:
                start_date, end_date = date_range
                event_details = {
                    'title': self.clean_title(clean_text),
                    'calendar': calendar_name,
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'start_time': start_date.strftime('%H:%M:%S'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'end_time': end_date.strftime('%H:%M:%S'),
                    'alerts': self.parse_alerts(clean_text)
                }
            else:
                # Regular event parsing
                parsed_date = self.parse_time(clean_text, self._get_base_date(clean_text))
                duration = self.parse_duration(clean_text)
                end_date = parsed_date + timedelta(minutes=duration)
                
                event_details = {
                    'title': self.clean_title(clean_text),
                    'calendar': calendar_name,
                    'start_date': parsed_date.strftime('%Y-%m-%d'),
                    'start_time': parsed_date.strftime('%H:%M:%S'),
                    'end_date': end_date.strftime('%Y-%m-%d'),
                    'end_time': end_date.strftime('%H:%M:%S'),
                    'alerts': self.parse_alerts(clean_text)
                }
            
            # Add optional fields
            self._add_optional_fields(event_details, clean_text, url, notes)
            
            return event_details
        except Exception as e:
            return {'error': str(e)}
        
    def _clean_text_for_parsing(self, text: str, url: Optional[str]) -> str:
            """Clean text for parsing"""
            clean_text = text
            if url:
                clean_text = re.sub(r'(?:url|link):\s*' + re.escape(url), '', clean_text)
            clean_text = re.sub(r'(?:url|link):\s*https?://\S+', '', clean_text)
            clean_text = re.sub(r'https?://\S+', '', clean_text)
            return clean_text
    
    def _get_base_date(self, text: str) -> datetime:
        """Get base date from text"""
        today = datetime.now()
        text_lower = text.lower()
        
        if 'tomorrow' in text_lower:
            return today + timedelta(days=1)
        elif 'next week' in text_lower:
            return today + timedelta(days=7)
        
        # Handle specific weekdays
        for day in self.weekday_map:
            if day in text_lower:
                current_weekday = today.weekday()
                target_weekday = list(self.weekday_map.keys()).index(day) % 7
                days_ahead = (target_weekday - current_weekday) % 7
                if days_ahead == 0:  # If it's the same day, move to next week
                    days_ahead = 7
                return today + timedelta(days=days_ahead)
                
        return today
    
    def _add_optional_fields(self, event_details: dict, text: str, url: Optional[str], notes: Optional[str]):
        """Add optional fields to event details"""
        location = self.parse_location(text)
        if location:
            event_details['location'] = location
            
        if url:
            event_details['url'] = url
            
        if notes:
            event_details['notes'] = notes
            
        recurrence = self.parse_recurrence(text)
        if recurrence:
            event_details['recurrence'] = recurrence

def create_calendar_event(event_details: dict) -> str:
    """Create calendar event with proper AppleScript escaping"""
    start_date = datetime.strptime(f"{event_details['start_date']} {event_details['start_time']}", "%Y-%m-%d %H:%M:%S")
    
    # Properly escape calendar name for AppleScript
    calendar_name = event_details["calendar"].replace('"', '\\"')
    
    script_parts = [
        'tell application "Calendar"',
        f'    tell calendar "{calendar_name}"',  # Calendar name is now properly escaped
        '        set startDate to current date',
        f'        set year of startDate to {start_date.year}',
        f'        set month of startDate to {start_date.month}',
        f'        set day of startDate to {start_date.day}',
        f'        set hours of startDate to {start_date.hour}',
        f'        set minutes of startDate to {start_date.minute}',
        '        set seconds of startDate to 0',
        '',
        '        set endDate to current date',
        f'        set year of endDate to {int(event_details["end_date"][:4])}',
        f'        set month of endDate to {int(event_details["end_date"][5:7])}',
        f'        set day of endDate to {int(event_details["end_date"][8:10])}',
        f'        set hours of endDate to {int(event_details["end_time"].split(":")[0])}',
        f'        set minutes of endDate to {int(event_details["end_time"].split(":")[1])}',
        '        set seconds of endDate to 0',
        '',
        # Use quoted form for all property values
        f'        set newEvent to make new event with properties {{summary:"{event_details["title"]}", start date:startDate, end date:endDate}}'
    ]
    
    if 'location' in event_details:
        location = event_details['location'].replace('"', '\\"')
        script_parts.append(f'        set location of newEvent to "{location}"')
    
    if 'url' in event_details:
        url = event_details['url'].replace('"', '\\"')
        script_parts.append(f'        set url of newEvent to "{url}"')
    
    if 'notes' in event_details:
        notes = event_details['notes'].replace('"', '\\"')
        script_parts.append(f'        set description of newEvent to "{notes}"')
    
    if 'recurrence' in event_details:
        recurrence = event_details['recurrence'].replace('"', '\\"')
        script_parts.append(f'        set recurrence of newEvent to "{recurrence}"')
    
    for minutes in event_details['alerts']:
        alert_time = start_date - timedelta(minutes=minutes)
        script_parts.append(f'''
        set alertDate to current date
        set year of alertDate to {alert_time.year}
        set month of alertDate to {alert_time.month}
        set day of alertDate to {alert_time.day}
        set hours of alertDate to {alert_time.hour}
        set minutes of alertDate to {alert_time.minute}
        set seconds of alertDate to 0
        make new display alarm at newEvent with properties {{trigger date:alertDate}}
        ''')
    
    script_parts.extend([
        '    end tell',
        'end tell'
    ])
    
    applescript = '\n'.join(script_parts)
    
    try:
        result = subprocess.run(['osascript', '-e', applescript],
                              capture_output=True,
                              text=True,
                              check=True)
        
        if result.stderr:
            raise Exception(result.stderr)
        
        # Format date/time for notification
        start_date = datetime.strptime(f"{event_details['start_date']} {event_details['start_time']}", 
                                     "%Y-%m-%d %H:%M:%S")
        time_str = start_date.strftime("%-I:%M %p")
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        
        if start_date.date() == today.date():
            date_str = f"Today at {time_str}"
        elif start_date.date() == tomorrow.date():
            date_str = f"Tomorrow at {time_str}"
        else:
            date_str = start_date.strftime("%A, %B %-d at %I:%M %p")
        
        # Create notification details
        notification_details = f"📅 {event_details['calendar']} • {date_str}"
        if 'location' in event_details:
            notification_details += f"\n📍 {event_details['location']}"
        
        return json.dumps({
            "alfredworkflow": {
                "arg": notification_details,
                "variables": {
                    "notificationTitle": event_details['title']
                }
            }
        })
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        return json.dumps({
            "alfredworkflow": {
                "arg": f"Error: {error_msg}",
                "variables": {
                    "notificationTitle": "Error"
                }
            }
        })

def main():
    if len(sys.argv) < 2:
        print(json.dumps({
            "alfredworkflow": {
                "arg": "No input provided",
                "variables": {"error": "no_input"}
            }
        }))
        return

    user_input = " ".join(sys.argv[1:])
    processor = CalendarNLPProcessor()
    event_details = processor.parse_event(user_input)
    
    if 'error' not in event_details:
        result = create_calendar_event(event_details)
        print(result)
    else:
        print(json.dumps({
            "alfredworkflow": {
                "arg": f"Error parsing input: {event_details['error']}",
                "variables": event_details
            }
        }))

if __name__ == "__main__":
    main()