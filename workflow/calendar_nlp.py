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
        
        # Define weekday_map first
        self.weekday_map = {
            'monday': 'MO', 'tuesday': 'TU', 'wednesday': 'WE', 'thursday': 'TH',
            'friday': 'FR', 'saturday': 'SA', 'sunday': 'SU',
            'mon': 'MO', 'tue': 'TU', 'wed': 'WE', 'thu': 'TH',
            'fri': 'FR', 'sat': 'SA', 'sun': 'SU'
        }
        
        # Create weekdays pattern
        self.weekdays = '|'.join(self.weekday_map.keys())
        
        # Calendar pattern
        self.calendar_pattern = r'#(?:"([^"]+)"|\'([^\']+)\'|([^"\'\s]+))'
        
        # Basic time patterns
        self.time_pattern = r'\b(\d{1,2})(?::(\d{2}))?\s*([ap]m?)\b'
        self._base_time = r'\d{1,2}(?::\d{2})?\s*(?:am?|pm?)'
        self.relative_time_pattern = r'in\s+(\d+)\s+(?:min(?:ute)?s?|hours?)'
        
        # Date range pattern
        self.date_range_pattern = r'from\s+(\w+\s+\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s*(?:-|to)\s*(\w+\s+\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?)'
        
        # Location patterns
        self.location_patterns = [
            # Basic location with @ marker
            r'''(?:^|\s)@\s*
                (
                    (?:[A-Za-z0-9][A-Za-z0-9\s&\.'+-]*?)
                    (?:\s*@\s*[A-Za-z0-9][A-Za-z0-9\s&\.'+-]*?)*?
                )
                (?=
                    \s+(?:\d{1,2}(?::\d{2})?\s*(?:am?|pm?)|
                    (?:[01]\d|2[0-3]):[0-5]\d|
                    tomorrow|today|next|every)|
                    \s*$
                )
            ''',
            r'(?:online|virtual)\s*meeting'
        ]
        
        # Location pattern - handles all location cases
        self.location_pattern = r'@\s*([A-Za-z0-9][A-Za-z0-9\s&\.\'+\-]*?)(?=\s+(?:at\s+\d{1,2}(?::\d{2})?\s*(?:am?|pm?)|tomorrow|today|next|every)|$)'
        
        # Ordinal number patterns
        self.ordinal_patterns = [
            (r'(\d+)\s*(?:st)\b', r'\1st'),
            (r'(\d+)\s*(?:nd)\b', r'\1nd'),
            (r'(\d+)\s*(?:rd)\b', r'\1rd'),
            (r'(\d+)\s*(?:th)\b', r'\1th'),
        ]
        
        # Update patterns to better handle numbers and "at"
        self.number_patterns = [
            # Handle numbers after keywords with optional "at"
            (r'((?:Floor|Level|Room|St\.?|Street|Ave\.?|Avenue)\s*(?:at\s*)?)(\d+)(st|nd|rd|th)?(?=\s|$)', r'\1\2\3'),
            
            # Handle ordinal numbers before keywords
            (r'(\d+)(st|nd|rd|th)\s+(Floor|Level|Room)', r'\1\2 \3'),
            
            # Handle plain numbers with keywords
            (r'(\d+)(st|nd|rd|th)?\s+(Floor|Level|Room)', r'\1\2 \3'),
            
            # Handle street addresses
            (r'(\d+)(st|nd|rd|th)?\s+(St\.?|Street|Ave\.?|Avenue)', r'\1\2 \3'),
            
            # Handle building numbers
            (r'(Building|Room)\s+(\d+)', r'\1 \2')
        ]
        
        # Location keywords that should keep "at"
        self.location_keywords = ['floor', 'level', 'room', 'street', 'st', 'ave', 'avenue']
        
        # Update alert patterns to handle all cases
        self.alert_patterns = {
            # Basic minutes/hours
            r'(\d+)\s*min(?:ute)?s?\s*(?:alert|reminder)': 'minutes',
            r'(\d+)\s*hour(?:s)?\s*(?:alert|reminder)': 'hours',
            # Before cases
            r'(?:alert|remind)\s+(\d+)\s*min(?:ute)?s?\s*before': 'minutes',
            r'(?:alert|remind)\s+(\d+)\s*hour(?:s)?\s*before': 'hours',
            # With cases
            r'with\s+(\d+)\s*min(?:ute)?s?\s*(?:alert|reminder)': 'minutes',
            r'with\s+(\d+)\s*hour(?:s)?\s*(?:alert|reminder)': 'hours',
            # Natural language
            r'(?:with\s+)?(?:an?\s+hour)\s*(?:alert|reminder|before)': 'natural_hour',
            r'(?:with\s+)?(?:half\s*(?:an?\s*)?hour)\s*(?:alert|reminder|before)': 'natural_half'
        }
        
        # Duration patterns
        self.duration_patterns = {
            'time_range': r'(\d{1,2})(?::(\d{2}))?\s*([ap]m?)?\s*(?:-|to)\s*(\d{1,2})(?::(\d{2}))?\s*([ap]m?)?'
        }
        
        # URL and notes prefixes
        self._url_prefixes = r'(?:url|link|meet(?:ing)?(?:\s+link)?|zoom|teams)'
        self._note_prefixes = r'(?:notes?|description|details?)'
        
        # URL patterns - updated for better matching
        self.url_patterns = [
            rf'{self._url_prefixes}:\s*((?:https?://)[^\s]+)',
            r'((?:https?://)?(?:[\w-]+\.)*zoom\.us/[^\s]+)',
            r'((?:https?://)?(?:[\w-]+\.)*teams\.microsoft\.com/[^\s]+)',
            r'((?:https?://)?(?:[\w-]+\.)*meet\.google\.com/[^\s]+)'
        ]
        
        # Notes patterns
        self.notes_patterns = [
            rf'{self._note_prefixes}:\s*([^|]+?)(?=\s+(?:{self._url_prefixes}):|\s*$)'
        ]

        # Add pattern to remove locations from title
        self.patterns_to_remove = [
            r'\bevery\b\s+\w+',
            r'\b(?:tomorrow|today|next|on|at|from|to|daily|weekly|monthly)\b.*$',
            r'\bon\s+(?:mon|tue|wed|thu|fri|sat|sun)(?:day)?',
            r'\b(?:mon|tue|wed|thu|fri|sat|sun)(?:day)?',
            rf'{self._base_time}.*$',
            r'for\s+\d+\s+(?:day|hour|minute|min)s?.*$',
            r'(?:alert|remind).*$',
            r'with\s+\d+\s*(?:minute|min|hour)s?\s+(?:alert|reminder)',
            r'url\s+https?://\S+',
            r'@\s*[^@\s][^@]*(?=\s+(?:at|tomorrow|next|\d|\$|$))'  # Remove location markers
        ]

        # Section patterns
        self.section_patterns = {
            'event_type': r'^(meeting|lunch|dinner|coffee|call|zoom|standup|training|class)',
            'location': r'@\s*([^@](?:.*?@[^@]+)*?.*?)(?=\s+(?:at\s+\d|tomorrow|next|every|$))',  # Handle multiple @ parts
            'time': r'(?:at\s+)?(\d{1,2}(?::\d{2})?\s*(?:am?|pm?))',
            'date': r'(tomorrow|today|next\s+\w+|\d{1,2}/\d{1,2}(?:/\d{2,4})?)',
            'recurrence': r'(every\s+(?:day|week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|mon|tue|wed|thu|fri|sat|sun))',
        }

        # Recurrence patterns - order matters!
        self.recurrence_patterns = {
            # Multiple days pattern (must come before single day)
            rf'every\s+({self.weekdays})(?:\s+and\s+({self.weekdays}))+': 
                lambda x: f'FREQ=WEEKLY;BYDAY={",".join(self.weekday_map[day.lower()] for day in re.findall(rf"{self.weekdays}", x.group(0)))}',
            
            # Until date pattern (must come before single day)
            rf'every\s+({self.weekdays})\s+until\s+(\d{{1,2}}/\d{{1,2}}(?:/\d{{2,4}})?)\b':
                lambda x: f'FREQ=WEEKLY;BYDAY={self.weekday_map[x.group(1).lower()]};UNTIL={self._parse_until_date(x.group(2))}',
            
            # Single day pattern
            rf'every\s+({self.weekdays})\b': 
                lambda x: f'FREQ=WEEKLY;BYDAY={self.weekday_map[x.group(1).lower()]}',
            
            # Simple frequencies
            r'every\s+week(?:ly)?\b': 'FREQ=WEEKLY',
            r'every\s+day|daily\b': 'FREQ=DAILY',
            r'every\s+month|monthly\b': 'FREQ=MONTHLY',
            r'every\s+year|yearly|annually\b': 'FREQ=YEARLY',
        }

    def _parse_until_date(self, date_str: str) -> str:
        """Parse until date and return formatted string"""
        today = datetime.now()
        parts = date_str.split('/')
        if len(parts) == 2:
            month, date = parts
            # Use current year, but if date has passed, use next year
            target_date = datetime(today.year, int(month), int(date))
            if target_date < today:
                year = today.year + 1
            else:
                year = today.year
        else:
            month, date, year = parts
            if len(year) == 2:
                year = '20' + year
        return f"{year}{int(month):02d}{int(date):02d}T235959Z"

    def parse_date_range(self, text: str) -> Optional[Tuple[datetime, datetime]]:
        """Parse date range from text with better date handling"""
        match = re.search(self.date_range_pattern, text, re.IGNORECASE)
        if match:
            start_str, end_str = match.groups()
            try:
                today = datetime.now()
                
                # Parse dates with default year handling
                start_date = parser.parse(start_str, default=today)
                end_date = parser.parse(end_str, default=today)
                
                # If end date is before start date, try next month/year
                if end_date < start_date:
                    if start_date.month == end_date.month:
                        # Same month, assume next year
                        end_date = end_date.replace(year=end_date.year + 1)
                    else:
                        # Different month, might be next month
                        end_date = end_date + relativedelta(months=1)
                        if end_date < start_date:
                            end_date = end_date.replace(year=end_date.year + 1)
                
                return start_date, end_date
            except (ValueError, TypeError):
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
        print(f"Debug - Input text: {text}", file=sys.stderr)
        
        # First check for explicit calendar selection with #
        calendar_match = re.search(self.calendar_pattern, text)
        if calendar_match:
            # Get the first non-None group (only one should match)
            requested_calendar = next((g for g in calendar_match.groups() if g is not None), None)
            if requested_calendar:
                # Print for debugging
                print(f"Debug - Found calendar: {requested_calendar}", file=sys.stderr)
                # Verify calendar exists in available calendars
                matching_calendars = [cal for cal in self.calendars 
                                if cal.lower() == requested_calendar.lower()]
                if matching_calendars:
                    print(f"Debug - Matched calendar: {matching_calendars[0]}", file=sys.stderr)
                    return matching_calendars[0]
        
        # Use default calendar from config
        default_cal = self.config.get('default_calendar')
        if default_cal and any(cal.lower() == default_cal.lower() for cal in self.calendars):
            matching_cals = [cal for cal in self.calendars 
                        if cal.lower() == default_cal.lower()]
            return matching_cals[0]
        
        return "Calendar"

    def parse_duration(self, text: str) -> int:
        """Parse duration from text, returns minutes"""
        # Default duration of 60 minutes
        default_duration = 60
        
        # Try to match time range pattern
        match = re.search(self.duration_patterns['time_range'], text, re.IGNORECASE)
        if match:
            start_hour, start_min, start_meridiem, end_hour, end_min, end_meridiem = match.groups()
            
            # Convert to 24-hour format
            start_hour = int(start_hour)
            end_hour = int(end_hour)
            start_min = int(start_min) if start_min else 0
            end_min = int(end_min) if end_min else 0
            
            # Handle meridiem (AM/PM)
            start_meridiem = start_meridiem.lower() if start_meridiem else end_meridiem.lower()
            end_meridiem = end_meridiem.lower() if end_meridiem else start_meridiem.lower()
            
            # Adjust hours for PM
            if start_meridiem and 'p' in start_meridiem and start_hour != 12:
                start_hour += 12
            if end_meridiem and 'p' in end_meridiem and end_hour != 12:
                end_hour += 12
            
            # Handle 12 AM/PM special cases
            if start_hour == 12:
                if start_meridiem and 'a' in start_meridiem:
                    start_hour = 0
            if end_hour == 12:
                if end_meridiem and 'a' in end_meridiem:
                    end_hour = 0
            
            # Calculate duration in minutes
            start_minutes = start_hour * 60 + start_min
            end_minutes = end_hour * 60 + end_min
            
            # Handle crossing midnight
            if end_minutes < start_minutes:
                end_minutes += 24 * 60
            
            duration = end_minutes - start_minutes
            return duration if duration > 0 else default_duration
            
        return default_duration

    def clean_title(self, text: str) -> str:
        """Clean up the title"""
        title = text
        for pattern in self.patterns_to_remove:
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

    def verify_location(self, location: str) -> Tuple[bool, Optional[str]]:
        """Verify location using macOS Contacts and Maps
        Returns: (is_valid, formatted_location)
        """
        # First check Contacts with more detail
        contacts_script = '''
            tell application "Contacts"
                set matchingContacts to {}
                repeat with theContact in every person
                    set contactMatches to {}
                    repeat with theAddress in every address of theContact
                        set addressText to formatted address of theAddress as string
                        if addressText contains "%s" then
                            -- Get contact details
                            set contactName to name of theContact
                            set addressLabel to label of theAddress
                            if addressLabel is missing value then
                                set addressLabel to "address"
                            end if
                            -- Format as JSON-like string
                            set contactInfo to contactName & "|" & addressLabel & "|" & addressText
                            copy contactInfo to the end of contactMatches
                        end if
                    end repeat
                    if length of contactMatches > 0 then
                        copy contactMatches to the end of matchingContacts
                    end if
                end repeat
                return matchingContacts
            end tell
        ''' % location.replace('"', '\\"')
        
        try:
            result = subprocess.run(['osascript', '-e', contacts_script],
                                  capture_output=True,
                                  text=True,
                                  check=True)
            if result.stdout.strip():
                # Process multiple matches
                matches = result.stdout.strip().split(', ')
                if len(matches) > 1:
                    # Multiple matches found - format them for selection
                    formatted_matches = []
                    for match in matches:
                        name, label, address = match.split('|')
                        formatted_matches.append(f"{name} ({label}): {address}")
                    # Return the most relevant match (first one for now)
                    # Could be enhanced to use fuzzy matching or other relevance criteria
                    return True, formatted_matches[0]
                else:
                    # Single match
                    name, label, address = matches[0].split('|')
                    return True, f"{name} ({label}): {address}"
        except subprocess.CalledProcessError:
            pass

        # Then check Maps
        maps_script = '''
            tell application "Maps"
                try
                    set searchResults to search for "%s"
                    set matchingLocations to {}
                    repeat with i from 1 to count of searchResults
                        if i > 3 then exit repeat -- Limit to top 3 results
                        set theResult to item i of searchResults
                        copy (name of theResult & "|" & address of theResult) to the end of matchingLocations
                    end repeat
                    return matchingLocations
                on error
                    return ""
                end try
            end tell
        ''' % location.replace('"', '\\"')
        
        try:
            result = subprocess.run(['osascript', '-e', maps_script],
                                  capture_output=True,
                                  text=True,
                                  check=True)
            if result.stdout.strip():
                # Process multiple matches from Maps
                matches = result.stdout.strip().split(', ')
                if len(matches) > 1:
                    # Multiple matches - format them for selection
                    formatted_matches = []
                    for match in matches:
                        name, address = match.split('|')
                        formatted_matches.append(f"{name} ({address})")
                    # Return most relevant (first) match
                    return True, formatted_matches[0]
                else:
                    # Single match
                    name, address = matches[0].split('|')
                    return True, f"{name} ({address})"
        except subprocess.CalledProcessError:
            pass
            
        # If not found, return original location
        return False, location

    def split_into_sections(self, text: str) -> dict:
        """Split text into sections based on markers"""
        sections = {
            'event_type': None,
            'location': None,
            'time': None,
            'date': None,
            'recurrence': None,
            'remaining': text
        }
        
        # Extract each section
        for section_type, pattern in self.section_patterns.items():
            match = re.search(pattern, sections['remaining'], re.IGNORECASE)
            if match:
                sections[section_type] = match.group(1)
                sections['remaining'] = re.sub(pattern, '', sections['remaining'], count=1)
        
        return sections

    def parse_location(self, text: str) -> Optional[str]:
        """Extract location from text with verification"""
        # Pre-process text to handle no spaces around @
        text = re.sub(r'(?<=[A-Za-z0-9])@(?=[A-Za-z0-9])', ' @ ', text)
        
        # Find location after @
        match = re.search(self.location_pattern, text, re.IGNORECASE)
        if not match:
            return None
            
        location = match.group(1).strip()
        
        # Skip if contains special keywords
        if any(p in location.lower() for p in ['notes:', 'url:', 'link:', 'alert', 'remind']):
            return None
        
        # Handle ordinal numbers
        for pattern, repl in self.ordinal_patterns:
            location = re.sub(pattern, repl, location)
        
        # Add space between text and numbers
        location = re.sub(r'([A-Za-z])(\d)', r'\1 \2', location)
        
        # Clean up extra spaces
        location = re.sub(r'\s+', ' ', location).strip()
        
        # Remove trailing words
        location = re.sub(r'\s+(?:tomorrow|today|next|every)\s*$', '', location, flags=re.IGNORECASE)
        
        # Verify and format
        is_valid, formatted_location = self.verify_location(location)
        if is_valid:
            return formatted_location
        return location
    
    def clean_location(self, text: str, time_str: str = '') -> Optional[str]:
        """Clean up location string"""
        if not text:
            return None

        cleaned = text.strip()
        
        # Remove specific words and patterns
        for pattern in self.clean_patterns:
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
        url = None
        notes = None
        
        # Try URL patterns first
        for pattern in self.url_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                url = match.group(1).strip()
                break
        
        # Then try notes patterns
        for pattern in self.notes_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                notes = match.group(1).strip()
                break
        
        return url, notes

    def parse_recurrence(self, text: str) -> Optional[str]:
        """Extract recurrence pattern from text"""
        if not re.search(r'\bevery\b', text.lower()):
            return None
            
        text_lower = text.lower()
        
        # Try each pattern
        for pattern, format_str in self.recurrence_patterns.items():
            match = re.search(pattern, text_lower)
            if match:
                if callable(format_str):
                    return format_str(match)
                return format_str
        
        return None

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
        """Extract alert times from text"""
        alerts = set()
        
        # Process each alert pattern
        for pattern, unit in self.alert_patterns.items():
            matches = re.finditer(pattern, text, re.IGNORECASE | re.VERBOSE)
            for match in matches:
                if unit == 'natural_hour':
                    alerts.add(60)  # 1 hour in minutes
                elif unit == 'natural_half':
                    alerts.add(30)  # 30 minutes
                else:
                    time_val = int(match.group(1))
                    if unit == 'hours':
                        time_val *= 60
                    alerts.add(time_val)
        
        return sorted(alerts) if alerts else [15]

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
            
            # Handle am/pm more explicitly
            if meridiem:
                if meridiem in ('p', 'pm') and hour != 12:
                    hour += 12
                elif meridiem in ('a', 'am') and hour == 12:
                    hour = 0
            
            return base_date.replace(hour=hour, minute=minutes, second=0, microsecond=0)
            
        return base_date

    def parse_event(self, text: str) -> dict:
        """Parse event details from text"""
        # Initialize basic event structure
        event_details = {
            'title': '',
            'calendar': 'Calendar',
            'start_date': '',
            'start_time': '',
            'end_date': '',
            'end_time': '',
            'alerts': [15]  # Default 15-min alert
        }
        
        try:
            # Parse components
            url, notes = self.parse_url_and_notes(text)
            clean_text = self._clean_text_for_parsing(text, url)
            
            # Set title first
            event_details['title'] = self.clean_title(clean_text)
            
            # Get calendar
            calendar_name = self.parse_calendar_name(clean_text)
            if calendar_name:
                event_details['calendar'] = calendar_name
            
            # Parse date/time
            date_range = self.parse_date_range(clean_text)
            if date_range:
                start_date, end_date = date_range
            else:
                base_date = self._get_base_date(clean_text)
                start_date = self.parse_time(clean_text, base_date)
                duration = self.parse_duration(clean_text)
                end_date = start_date + timedelta(minutes=duration)
            
            # Update date/time fields
            event_details.update({
                'start_date': start_date.strftime('%Y-%m-%d'),
                'start_time': start_date.strftime('%H:%M:%S'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'end_time': end_date.strftime('%H:%M:%S'),
            })
            
            # Parse alerts
            alerts = self.parse_alerts(clean_text)
            if alerts:
                event_details['alerts'] = alerts
            
            # Add optional fields
            location = self.parse_location(clean_text)
            if location:
                event_details['location'] = location
            
            if url:
                event_details['url'] = url
            
            if notes:
                event_details['notes'] = notes
            
            recurrence = self.parse_recurrence(clean_text)
            if recurrence:
                event_details['recurrence'] = recurrence
            
        except Exception as e:
            print(f"Error parsing event: {str(e)}", file=sys.stderr)
            event_details['error'] = str(e)
        
        return event_details
        
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
    """Create calendar event with proper date handling"""
    start_date = datetime.strptime(f"{event_details['start_date']} {event_details['start_time']}", "%Y-%m-%d %H:%M:%S")
    end_date = datetime.strptime(f"{event_details['end_date']} {event_details['end_time']}", "%Y-%m-%d %H:%M:%S")
    
    # Properly escape the strings for AppleScript
    calendar_name = event_details["calendar"].replace('"', '\\"')
    title = event_details["title"].replace('"', '\\"')
    
    script = f'''
        tell application "Calendar"
            tell calendar "{calendar_name}"
                -- Set up start date
                set eventStartDate to current date
                set year of eventStartDate to {start_date.year}
                set month of eventStartDate to {start_date.month}
                set day of eventStartDate to {start_date.day}
                set hours of eventStartDate to {start_date.hour}
                set minutes of eventStartDate to {start_date.minute}
                set seconds of eventStartDate to 0
                
                -- Set up end date
                set eventEndDate to current date
                set year of eventEndDate to {end_date.year}
                set month of eventEndDate to {end_date.month}
                set day of eventEndDate to {end_date.day}
                set hours of eventEndDate to {end_date.hour}
                set minutes of eventEndDate to {end_date.minute}
                set seconds of eventEndDate to 0
                
                -- Create event with all required properties
                make new event with properties {{summary:"{title}", start date:eventStartDate, end date:eventEndDate}}
                set newEvent to result
    '''
    
    # Add optional properties
    if 'location' in event_details:
        location = event_details['location'].replace('"', '\\"')
        script += f'\n                set location of newEvent to "{location}"'
    
    if 'url' in event_details:
        url = event_details['url'].replace('"', '\\"')
        script += f'\n                set url of newEvent to "{url}"'
    
    if 'notes' in event_details:
        notes = event_details['notes'].replace('"', '\\"')
        script += f'\n                set description of newEvent to "{notes}"'
    
    if 'recurrence' in event_details:
        recurrence = event_details['recurrence'].replace('"', '\\"')
        script += f'\n                set recurrence of newEvent to "{recurrence}"'
    
    # Add alerts
    for minutes in event_details['alerts']:
        alert_time = start_date - timedelta(minutes=minutes)
        script += f'''
                set alertDate to current date
                set year of alertDate to {alert_time.year}
                set month of alertDate to {alert_time.month}
                set day of alertDate to {alert_time.day}
                set hours of alertDate to {alert_time.hour}
                set minutes of alertDate to {alert_time.minute}
                set seconds of alertDate to 0
                make new display alarm at newEvent with properties {{trigger date:alertDate}}
        '''
    
    script += '''
                return newEvent
            end tell
        end tell
    '''
    
    try:
        result = subprocess.run(['osascript', '-e', script],
                              capture_output=True,
                              text=True,
                              check=True)
        
        if result.stderr:
            raise Exception(result.stderr)
        
        # Format notification...
        time_str = start_date.strftime("%-I:%M %p")
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        
        if start_date.date() == today.date():
            date_str = f"Today at {time_str}"
        elif start_date.date() == tomorrow.date():
            date_str = f"Tomorrow at {time_str}"
        else:
            date_str = start_date.strftime("%A, %B %-d at %I:%M %p")
        
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