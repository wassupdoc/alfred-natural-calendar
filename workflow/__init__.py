# Empty file to make the directory a Python package 

# Time pattern components
TIME_COMPONENTS = {
    'hours': r'(\d{1,2})',                  # 1-12
    'minutes': r'(?::(\d{2}))?',            # :00-:59
    'meridiem': r'([ap])(?:\s*m)?',         # a/p/am/pm
    'spaces': r'\s*',                       # Optional spaces
    'at': r'(?:at\s+)?'                     # Optional "at"
}

# Build time patterns
def build_time_pattern():
    """Build time pattern from components"""
    return (f"{TIME_COMPONENTS['at']}"
            f"{TIME_COMPONENTS['hours']}"
            f"{TIME_COMPONENTS['minutes']}"
            f"{TIME_COMPONENTS['spaces']}"
            f"{TIME_COMPONENTS['meridiem']}"
            r"\b")

def build_base_time_pattern():
    """Build base time pattern from components"""
    return (f"{TIME_COMPONENTS['at']}"
            r"\d{1,2}"
            r"(?::\d{2})?"
            f"{TIME_COMPONENTS['spaces']}"
            r"[ap](?:\s*m)?\b")

# Shared time parsing function
def parse_time_match(match):
    """Parse time from regex match"""
    hour = int(match.group(1))
    minutes = int(match.group(2)) if match.group(2) else 0
    meridiem = match.group(3).lower()  # Will be 'a' or 'p'
    
    if meridiem == 'p' and hour != 12:
        hour += 12
    elif meridiem == 'a' and hour == 12:
        hour = 0
        
    return hour, minutes 