"""Utility functions for AI Assistant."""

import base64
import mimetypes
import os
import os.path

from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.text import MIMEText

from datetime import datetime, timedelta
from dateutil import tz

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def get_file_path(filename):
    """Get absolute path to a file in the script directory."""
    return os.path.join(SCRIPT_DIR, filename)


def resolve_relative_date(date_str: str, current_date_str: str = None) -> str:
    """
    Converts relative date references like 'tomorrow', 'today', 'next week' to absolute dates.
    If the date is already in a specific format, returns it as-is (preserving time if present).
    Returns date in YYYY-MM-DD format (or YYYY-MM-DDTHH:MM:SS if time was in original).
    
    Args:
        date_str: The date string to resolve (can be relative like 'tomorrow' or absolute like '2024-01-15' or '2024-01-15T10:00:00')
        current_date_str: Optional current date string in format 'YYYY-MM-DD HH:MM:SS' (already in local time). If provided, used as reference point.
    """
    date_lower = date_str.lower().strip()
    
    # Check if date_str contains time information
    has_time = 'T' in date_str or ' ' in date_str
    time_part = ""
    if has_time and 'T' in date_str:
        time_part = date_str.split('T')[1]
    
    # Parse current_date_str if provided, otherwise use system time
    if current_date_str:
        try:
            today = datetime.strptime(current_date_str, "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            # If format doesn't match, try just the date part
            try:
                today = datetime.strptime(current_date_str, "%Y-%m-%d").date()
            except ValueError:
                today = datetime.now().date()
    else:
        today = datetime.now().date()
    
    # Helper to format date with optional time
    def format_with_time(date_obj, time_str=""):
        if time_str:
            return f"{date_obj.strftime('%Y-%m-%d')}T{time_str}"
        return date_obj.strftime("%Y-%m-%d")
    
    # Handle common relative date references
    if date_lower == 'today':
        return format_with_time(today, time_part)
    elif date_lower == 'tomorrow':
        return format_with_time(today + timedelta(days=1), time_part)
    elif date_lower == 'yesterday':
        return format_with_time(today - timedelta(days=1), time_part)
    elif date_lower == 'next week':
        return format_with_time(today + timedelta(weeks=1), time_part)
    elif date_lower == 'next month':
        return format_with_time(today + timedelta(days=30), time_part)
    elif 'tomorrow' in date_lower or 'today' in date_lower or 'yesterday' in date_lower:
        # Handle cases like "tomorrow at 3pm" or "today morning"
        # Try to extract relative date and return with time if it was present
        if 'tomorrow' in date_lower:
            return format_with_time(today + timedelta(days=1), time_part)
        elif 'today' in date_lower:
            return format_with_time(today, time_part)
        elif 'yesterday' in date_lower:
            return format_with_time(today - timedelta(days=1), time_part)
    
    # If it doesn't match relative dates, return as-is
    return date_str

def build_file_part(file):
    """Creates a MIME part for a file.

    Args:
        file: The path to the file to be attached.

    Returns:
        A MIME part that can be attached to a message.
    """
    try:
        content_type, encoding = mimetypes.guess_type(file)

        if content_type is None or encoding is not None:
            content_type = "application/octet-stream"
        main_type, sub_type = content_type.split("/", 1)
        
        if main_type == "text":
            with open(file, "rb") as f:
                msg = MIMEText(f.read().decode(), _subtype=sub_type)
        elif main_type == "image":
            with open(file, "rb") as f:
                msg = MIMEImage(f.read().decode(), _subtype=sub_type)
        elif main_type == "audio":
            with open(file, "rb") as f:
                msg = MIMEAudio(f.read().decode(), _subtype=sub_type)
        else:
            with open(file, "rb") as f:
                msg = MIMEBase(main_type, sub_type)
                msg.set_payload(f.read())
        filename = os.path.basename(file)
        msg.add_header("Content-Disposition", "attachment", filename=filename)
        return msg
    except FileNotFoundError:
        raise FileNotFoundError(f"Attachment file '{file}' not found.")
