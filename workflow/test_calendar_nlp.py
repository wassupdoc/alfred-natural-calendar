import unittest
from datetime import datetime, timedelta
from typing import Tuple, Optional
import os
import sys

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflow.calendar_nlp import CalendarNLPProcessor

class TestCalendarNLP(unittest.TestCase):
    def setUp(self):
        """Set up test environment"""
        self.processor = CalendarNLPProcessor()
        self.now = datetime.now()
        self.tomorrow = self.now + timedelta(days=1)
        
        # Mock methods to avoid external dependencies
        self.original_verify = self.processor.verify_location
        self.processor.verify_location = self.mock_verify_location
        
        # Mock calendar methods
        self.original_get_calendars = self.processor.get_available_calendars
        self.processor.get_available_calendars = lambda: ["Calendar", "Work", "Personal"]
        
        # Mock config
        self.original_load_config = self.processor.load_config
        self.processor.load_config = lambda: {"default_calendar": "Calendar"}

    def tearDown(self):
        """Restore original methods"""
        self.processor.verify_location = self.original_verify
        self.processor.get_available_calendars = self.original_get_calendars
        self.processor.load_config = self.original_load_config

    def mock_verify_location(self, location: str) -> Tuple[bool, str]:
        """Mock location verification"""
        # Return the location unchanged for most cases
        if "John's house" in location:
            return True, "John Smith (home): 123 Main St"
        elif "Apple Park" in location:
            return True, "Apple Park (One Apple Park Way, Cupertino, CA)"
        elif "Starbucks" in location:
            return False, location
        elif any(x in location.lower() for x in ['floor', 'level', 'room', 'street', 'st.', 'ave']):
            # Return unchanged for locations with floor/level/room numbers
            return False, location
        elif any(x in location for x in ['3rd', '5th', '12th']):
            # Return unchanged for ordinal numbers
            return False, location
        elif "Cafe" in location and not any(x in location for x in ["101", "at"]):
            # Only format simple cafe names
            return True, "Local Cafe (456 Food St)"
        
        # For all other cases, return the original location
        return False, location

    def test_time_parsing(self):
        """Test various time formats"""
        test_cases = [
            ("dinner at 7p", "7:00 PM"),
            ("meeting at 2pm", "2:00 PM"),
            ("lunch at 12p", "12:00 PM"),
            ("coffee at 9a", "9:00 AM"),
            ("meeting at 3:30pm", "3:30 PM"),
            ("call at 11:45a", "11:45 AM"),
        ]
        
        for input_text, expected_time in test_cases:
            with self.subTest(input_text=input_text):
                print(f"Debug - Input text: {input_text}")
                result = self.processor.parse_event(input_text)
                parsed_time = datetime.strptime(result['start_time'], '%H:%M:%S').strftime('%-I:%M %p')
                print(f"Debug - Parsed time: {parsed_time}")
                self.assertEqual(parsed_time, expected_time)

    def test_location_parsing(self):
        """Test location extraction"""
        test_cases = [
            ("lunch @ Starbucks tomorrow", "Starbucks"),
            ("meeting @ Conference Room A", "Conference Room A"),
            ("dinner @ The Coffee Bean & Tea Leaf", "The Coffee Bean & Tea Leaf")
        ]
        
        for input_text, expected_location in test_cases:
            with self.subTest(input_text=input_text):
                print(f"Debug - Input text: {input_text}")
                result = self.processor.parse_event(input_text)
                parsed_location = result.get('location', '')
                print(f"Debug - Parsed location: {parsed_location}")
                self.assertEqual(parsed_location, expected_location)

    def test_time_range_parsing(self):
        """Test time range parsing"""
        test_cases = [
            ("meeting 2-3pm", 60),
            ("training 9:30am-11:30am", 120),
            ("class 1p-2:30p", 90),
        ]
        
        for input_text, expected_duration in test_cases:
            with self.subTest(input_text=input_text):
                print(f"Debug - Input text: {input_text}")
                result = self.processor.parse_duration(input_text)
                print(f"Debug - Parsed duration: {result} minutes")
                self.assertEqual(result, expected_duration)

    def test_alerts(self):
        """Test alert/reminder parsing"""
        test_cases = [
            ("meeting tomorrow at 2pm with 30min alert", [30]),
            ("lunch @ Starbucks at 1pm with 15min reminder", [15]),
            ("meeting @ Room 101 at 3pm alert 1 hour before", [60]),
            ("meeting @ Conference Room at 2pm with 1 hour alert with 15min alert", [15, 60]),
        ]
        
        for input_text, expected_alerts in test_cases:
            with self.subTest(input_text=input_text):
                result = self.processor.parse_event(input_text)
                self.assertEqual(sorted(result['alerts']), sorted(expected_alerts))

    def test_recurrence(self):
        """Test recurrence pattern parsing"""
        test_cases = [
            ("team sync every monday at 10am", "FREQ=WEEKLY;BYDAY=MO"),
            ("meeting every friday at 2pm", "FREQ=WEEKLY;BYDAY=FR"),
            ("standup every day at 9am", "FREQ=DAILY"),
        ]
        
        for input_text, expected_recurrence in test_cases:
            with self.subTest(input_text=input_text):
                result = self.processor.parse_event(input_text)
                self.assertEqual(result.get('recurrence'), expected_recurrence)

    def test_title_cleaning(self):
        """Test title extraction and cleaning"""
        test_cases = [
            ("meeting tomorrow at 2pm", "meeting"),
            ("lunch @ Starbucks tomorrow at 1pm", "lunch"),
            ("zoom call tomorrow at 3pm url: https://zoom.us/j/123", "zoom call"),
            ("meeting @ Room 101 tomorrow at 2pm with 30min alert", "meeting"),
        ]
        
        for input_text, expected_title in test_cases:
            with self.subTest(input_text=input_text):
                result = self.processor.parse_event(input_text)
                self.assertEqual(result['title'], expected_title)

    def test_url_parsing(self):
        """Test URL extraction"""
        test_cases = [
            ("zoom call tomorrow 3pm url: https://zoom.us/j/123", "https://zoom.us/j/123"),
            ("meeting 2pm url: https://meet.google.com/abc", "https://meet.google.com/abc"),
        ]
        
        for input_text, expected_url in test_cases:
            with self.subTest(input_text=input_text):
                result = self.processor.parse_event(input_text)
                self.assertEqual(result.get('url'), expected_url)

    def test_time_edge_cases(self):
        """Test edge cases for time parsing"""
        test_cases = [
            # Midnight/Noon cases
            ("meeting at 12pm", "12:00 PM"),  # Noon
            ("meeting at 12am", "12:00 AM"),  # Midnight
            ("lunch at 12p", "12:00 PM"),
            ("call at 12a", "12:00 AM"),
            
            # Extra spaces
            ("meeting at  2 pm", "2:00 PM"),
            ("call at 3  p", "3:00 PM"),
            
            # Case sensitivity
            ("meeting at 2PM", "2:00 PM"),
            ("call at 3A", "3:00 AM"),
            ("lunch at 12P", "12:00 PM"),
            
            # Space variations
            ("dinner at 6 p", "6:00 PM"),
            ("dinner at 6 pm", "6:00 PM"),
            ("dinner at 6p", "6:00 PM"),
            ("dinner at 6pm", "6:00 PM"),
            ("meeting at 9 a", "9:00 AM"),
            ("meeting at 9 am", "9:00 AM"),
            ("meeting at 9a", "9:00 AM"),
            ("meeting at 9am", "9:00 AM"),
        ]
        
        for input_text, expected_time in test_cases:
            with self.subTest(input_text=input_text):
                result = self.processor.parse_event(input_text)
                parsed_time = datetime.strptime(result['start_time'], '%H:%M:%S').strftime('%-I:%M %p')
                self.assertEqual(parsed_time, expected_time)

    def test_location_edge_cases(self):
        """Test edge cases for location parsing"""
        test_cases = [
            ('meeting @ Room 101', 'Room 101'),
            ('lunch @ 5th Floor Cafe', '5th Floor Cafe'),
            ('meeting @ Building 2 Floor 3', 'Building 2 Floor 3'),
            ('lunch @ Ben & Jerry\'s', 'Ben & Jerry\'s'),
            ('meeting @ C++ User Group', 'C++ User Group'),
            ('dinner @ P.F. Chang\'s', 'P.F. Chang\'s'),
            ('meeting @ 12th Floor Conference Room', '12th Floor Conference Room'),
            ('lunch @ The 3rd Cafe', 'The 3rd Cafe')
        ]
        
        for input_text, expected_location in test_cases:
            with self.subTest(input_text=input_text):
                print(f"Debug - Input text: {input_text}", file=sys.stderr)
                parsed_location = self.processor.parse_location(input_text)
                self.assertEqual(parsed_location, expected_location)

    def test_duration_edge_cases(self):
        """Test edge cases for duration parsing"""
        test_cases = [
            # Crossing midnight
            ("meeting 11pm-1am", 120),
            ("event 11:30pm-12:30am", 60),
            
            # Different formats
            ("meeting 2p-3:30pm", 90),
            ("call 9am-11:00a", 120),
            
            # With spaces
            ("meeting 2pm - 4pm", 120),
            ("call 9am -10am", 60),
        ]
        
        for input_text, expected_duration in test_cases:
            with self.subTest(input_text=input_text):
                result = self.processor.parse_duration(input_text)
                self.assertEqual(result, expected_duration)

    def test_alert_edge_cases(self):
        """Test edge cases for alert parsing"""
        test_cases = [
            # Multiple same alerts
            ("meeting 2pm with 30min alert with 30 minute alert", [30]),
            
            # Mixed formats
            ("meeting 2pm alert 1 hour before with 30min reminder", [30, 60]),
            
            # Natural language
            ("meeting 2pm with half hour alert", [30]),
            ("meeting 2pm with an hour alert", [60]),
            
            # Multiple alerts with different formats
            ("meeting 2pm alert 2 hours before with 90min reminder with 30 minute alert", [30, 90, 120]),
        ]
        
        for input_text, expected_alerts in test_cases:
            with self.subTest(input_text=input_text):
                result = self.processor.parse_event(input_text)
                self.assertEqual(sorted(result['alerts']), sorted(expected_alerts))

    def test_recurrence_edge_cases(self):
        """Test edge cases for recurrence parsing"""
        # Get current year for test
        current_year = datetime.now().year
        
        test_cases = [
            ('meeting every monday and wednesday at 2pm', 'FREQ=WEEKLY;BYDAY=MO,WE'),
            ('meeting every MONDAY at 2pm', 'FREQ=WEEKLY;BYDAY=MO'),
            ('meeting every mon and wed at 2pm', 'FREQ=WEEKLY;BYDAY=MO,WE'),
            # Update test to use dynamic year
            ('meeting every monday until 12/31', f'FREQ=WEEKLY;BYDAY=MO;UNTIL={current_year}1231T235959Z'),
        ]
        
        for input_text, expected_recurrence in test_cases:
            with self.subTest(input_text=input_text):
                result = self.processor.parse_event(input_text)
                self.assertEqual(result.get('recurrence'), expected_recurrence)

    def test_invalid_inputs(self):
        """Test handling of invalid inputs"""
        test_cases = [
            # Invalid times
            "meeting at 13pm",
            "call at 25:00",
            
            # Invalid ranges
            "meeting 5pm-3pm",
            
            # Missing required parts
            "meeting at",
            "lunch tomorrow",
            
            # Invalid alerts
            "meeting 2pm with 0min alert",
            
            # Invalid URLs
            "meeting url: not-a-url",
        ]
        
        for input_text in test_cases:
            with self.subTest(input_text=input_text):
                result = self.processor.parse_event(input_text)
                # Should either return error dict or handle gracefully
                self.assertTrue('error' in result or result.get('title'))

    def test_location_verification(self):
        """Test location verification with mocked responses"""
        test_cases = [
            # Known locations (mocked responses)
            ("meeting @ Apple Park", "Apple Park"),
            ("lunch @ Starbucks", "Starbucks"),
            ("meeting @ John's house", "John Smith"),
            ("meeting @ Cafe", "Local Cafe"),
            # Simple locations
            ("meeting @ Tech Hub", "Tech Hub"),
            ("lunch @ WeWork", "WeWork"),
            # Locations that don't exist
            ("meeting @ Random Place 123", "Random Place 123"),
        ]
        
        for input_text, expected_location_part in test_cases:
            with self.subTest(input_text=input_text):
                result = self.processor.parse_event(input_text)
                location = result.get('location', '').split('(')[0].strip()
                self.assertTrue(
                    expected_location_part in location,
                    f"Expected '{expected_location_part}' to be in '{location}'"
                )

    def test_location_with_time_like_numbers(self):
        """Test locations containing time-like numbers"""
        test_cases = [
            ("meeting @ Room 230", "Room 230"),
            ("lunch @ Cafe 101", "Cafe 101"),
            ("meeting @ Floor 12", "Floor 12"),
            ("meeting @ The 2nd Floor", "The 2nd Floor"),
            ("lunch @ 3rd Street Cafe", "3rd Street Cafe"),
        ]
        
        for input_text, expected_location in test_cases:
            with self.subTest(input_text=input_text):
                print(f"Debug - Input text: {input_text}", file=sys.stderr)
                parsed_location = self.processor.parse_location(input_text)
                self.assertEqual(parsed_location, expected_location)

    def test_location_with_no_spaces(self):
        """Test locations with no spaces around @ marker"""
        test_cases = [
            ('meeting @Room 101', 'Room 101'),
            ('lunch@ Cafe 101', 'Cafe 101'),
            ('meeting @ Floor12', 'Floor 12'),
            ('lunch@The 3rd Cafe', 'The 3rd Cafe')
        ]
        
        for input_text, expected_location in test_cases:
            with self.subTest(input_text=input_text):
                print(f"Debug - Input text: {input_text}", file=sys.stderr)
                parsed_location = self.processor.parse_location(input_text)
                self.assertEqual(parsed_location, expected_location)

    def test_time_variations(self):
        """Test various time input formats"""
        test_cases = [
            # Basic p/pm variations
            ("dinner at 6p", "6:00 PM"),
            ("dinner at 6 p", "6:00 PM"),
            ("dinner at 6pm", "6:00 PM"),
            ("dinner at 6 pm", "6:00 PM"),
            
            # Basic a/am variations
            ("breakfast at 8a", "8:00 AM"),
            ("breakfast at 8 a", "8:00 AM"),
            ("breakfast at 8am", "8:00 AM"),
            ("breakfast at 8 am", "8:00 AM"),
            
            # Without 'at'
            ("dinner 6p", "6:00 PM"),
            ("dinner 6 p", "6:00 PM"),
            ("dinner 6pm", "6:00 PM"),
            ("dinner 6 pm", "6:00 PM"),
            
            # With minutes
            ("meeting at 6:30p", "6:30 PM"),
            ("meeting at 6:30 p", "6:30 PM"),
            ("meeting at 6:30pm", "6:30 PM"),
            ("meeting at 6:30 pm", "6:30 PM"),
        ]
        
        for input_text, expected_time in test_cases:
            with self.subTest(input_text=input_text):
                print(f"Debug - Input text: {input_text}")
                result = self.processor.parse_event(input_text)
                parsed_time = datetime.strptime(result['start_time'], '%H:%M:%S').strftime('%-I:%M %p')
                print(f"Debug - Parsed time: {parsed_time}")
                self.assertEqual(parsed_time, expected_time)

if __name__ == '__main__':
    unittest.main() 