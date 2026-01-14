import base64
import os
import os.path
import google.auth

from email.message import EmailMessage
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


from langchain.tools import tool
from datetime import datetime, timedelta
from dateutil import tz
import re

import inspect

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

def convert_utc_to_local(utc_str: str) -> str:
    """Converts a UTC date-time string to local time zone datetime object."""
    from_zone = tz.tzutc()
    to_zone = tz.tzlocal()
    
    # Handle ISO format strings (e.g., '2026-01-15T15:00:00' or '2026-01-15t15:00:00')
    utc_str_normalized = utc_str.replace('t', 'T').replace('Z', '').strip()
    
    # Try multiple date formats
    formats = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]
    utc = None
    for fmt in formats:
        try:
            utc = datetime.strptime(utc_str_normalized, fmt)
            break
        except ValueError:
            continue
    
    if utc is None:
        raise ValueError(f"Unable to parse date string: {utc_str}")
    
    #utc = utc.replace(tzinfo=from_zone)
    local_time = utc.astimezone(to_zone)
    
    return local_time.strftime("%Y-%m-%d %H:%M:%S")

#Abstract tools class to define common behavior for all tool
class Tools:
    def get_tools(self):
        pass

class TimeTools(Tools):
    
    def get_current_time_impl(self) -> str:
        """Returns the current system time as a string in local timezone."""
        from_zone = tz.tzutc()
        to_zone = tz.tzlocal()
        
        # Get current UTC time as a datetime object with UTC timezone info
        utc_time = datetime.now(from_zone)
        
        # Convert to local timezone
        local_time = utc_time.astimezone(to_zone)
        
        # Return as formatted string
        return local_time.strftime("%Y-%m-%d %H:%M:%S")

    def get_current_time_tool(self):
        """Creates a tool wrapper for getting the current system time."""
        @tool
        def get_current_time() -> str:
            """Returns the current system time as a string."""
            return self.get_current_time_impl()
        return get_current_time
    
    def get_tools(self):
        """
        Returns a list of tool callables as standalone functions (not methods).
        """
        return [
            self.get_current_time_tool()
        ]

class CalendarTools(Tools):
    
    def __init__(self):
        self.calendar_service = self.get_calendar_service()
    
    def get_calendar_service(self):
        SCOPES = ['https://www.googleapis.com/auth/calendar']
        creds = None
        calendar_token_path = get_file_path('calendar_token.json')
        if os.path.exists(calendar_token_path):
            creds = Credentials.from_authorized_user_file(calendar_token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    get_file_path('credentials.json'), SCOPES)
                creds = flow.run_local_server(port=0)
            with open(calendar_token_path, 'w') as token:
                token.write(creds.to_json())
        try:
            service = build('calendar', 'v3', credentials=creds)
            return service
        except HttpError as error:
            print(f'An error occurred: {error}')
            return None
        
    def get_tools(self):
        """
        Returns a list of tool callables as standalone functions (not methods).
        """
        return [
            self._add_event_to_calendar_tool(),
            self._add_recurrent_event_to_calendar_tool(),
            self._get_upcoming_events_tool(),
            self._modify_event_tool(),
            self._get_events_on_date_tool()
        ]

    def _add_event_to_calendar_impl(self, event_name: str, 
                            event_location:str, 
                            event_desc:str, 
                            event_start_date: str, 
                            event_end_date:str,
                            time_zone:str,
                            email_remainder:int,
                            popup_remainder:int) -> str:
        """Implementation for adding an event to the calendar."""
        event = {
            'summary': event_name,
            'location': event_location,
            'description': event_desc,
            'start': {
                'dateTime': event_start_date,
                'timeZone': time_zone,
            },
            'end': {
                'dateTime': event_end_date,
                'timeZone': time_zone,
            }
        }
        
        # Only add reminders if at least one is set
        reminders_overrides = []
        if email_remainder > 0:
            reminders_overrides.append({'method': 'email', 'minutes': email_remainder})
        if popup_remainder > 0:
            reminders_overrides.append({'method': 'popup', 'minutes': popup_remainder})
        
        if reminders_overrides:
            event['reminders'] = {
                'useDefault': False,
                'overrides': reminders_overrides,
            }
        else:
            event['reminders'] = {'useDefault': True}
        
        event = self.calendar_service.events().insert(calendarId='primary', body=event).execute()
        return f"Event created: {event.get('htmlLink')}"
    
    def _add_event_to_calendar_tool(self):
        """Creates a tool wrapper for adding an event to the calendar."""
        @tool
        def add_event_to_calendar(event_name: str, 
                                event_location:str, 
                                event_desc:str, 
                                event_start_date: str, 
                                event_end_date:str,
                                time_zone:str = "Europe/Rome",
                                email_remainder:int = 0,
                                popup_remainder:int = 0,
                                current_date: str = None) -> str:
            """Adds an event to the calendar. 
            IMPORTANT: If the user mentions relative dates like 'tomorrow', 'today', 'next week', 'next month', etc.,
            you MUST first call get_current_time tool to get the current date and time, then pass that result to 
            the current_date parameter of this function.
            current_date should be in format 'YYYY-MM-DD HH:MM:SS' (e.g., from get_current_time output).
            event_start_date and event_end_date should be in ISO format (e.g., '2024-01-15T10:00:00')."""
            # Resolve relative dates using the provided current_date
            resolved_start = resolve_relative_date(event_start_date, current_date)
            resolved_end = resolve_relative_date(event_end_date, current_date)
            
            return self._add_event_to_calendar_impl(event_name, event_location, event_desc, 
                                                   resolved_start, resolved_end, time_zone,
                                                   email_remainder, popup_remainder)
        return add_event_to_calendar

    def _add_recurrent_event_to_calendar_impl(self,
                                        event_name: str, 
                                        event_location:str, 
                                        event_desc:str, 
                                        event_start_date: str, 
                                        event_end_date:str,
                                        time_zone:str,
                                        recurrence_rule:str,
                                        email_remainder:int,
                                        popup_remainder:int) -> str:
        """Implementation for adding a recurrent event to the calendar."""
        event = {
            'summary': event_name,
            'location': event_location,
            'description': event_desc,
            'start': {
                'dateTime': event_start_date,
                'timeZone': time_zone,
            },
            'end': {
                'dateTime': event_end_date,
                'timeZone': time_zone,
            },
            'recurrence': [
                recurrence_rule
            ]
        }
        
        # Only add reminders if at least one is set
        reminders_overrides = []
        if email_remainder > 0:
            reminders_overrides.append({'method': 'email', 'minutes': email_remainder})
        if popup_remainder > 0:
            reminders_overrides.append({'method': 'popup', 'minutes': popup_remainder})
        
        if reminders_overrides:
            event['reminders'] = {
                'useDefault': False,
                'overrides': reminders_overrides,
            }
        else:
            event['reminders'] = {'useDefault': True}
        
        event = self.calendar_service.events().insert(calendarId='primary', body=event).execute()
        return f"Recurrent Event created: {event.get('htmlLink')}"
    
    def _validate_and_normalize_rrule(self, rrule: str) -> tuple[bool, str]:
        """Validates and normalizes an RRULE string for Google Calendar API.
        
        Args:
            rrule: The RRULE string to validate
            
        Returns:
            Tuple of (is_valid, normalized_rrule_or_error_message)
        """
        if not rrule:
            return False, "RRULE cannot be empty"
        
        rrule = rrule.strip()
        
        # Check for FREQ parameter
        if 'FREQ=' not in rrule:
            return False, f"RRULE must contain FREQ parameter. Got: {rrule}"
        
        # Valid FREQ values
        valid_freq = ['DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY']
        freq_found = False
        for freq in valid_freq:
            if f'FREQ={freq}' in rrule:
                freq_found = True
                break
        
        if not freq_found:
            return False, f"RRULE FREQ must be one of: {', '.join(valid_freq)}"
        
        # Remove problematic parameters for Google Calendar
        # WKST is often not needed and can cause issues
        normalized = rrule.replace(';WKST=MO', '').replace('WKST=MO;', '')
        
        # Ensure no trailing semicolons
        normalized = normalized.rstrip(';')
        
        return True, normalized
    
    def _build_recurrence_rule(self, frequency: str, day_of_week: str = None, 
                               interval: int = 1, count: int = None, until: str = None) -> str:
        """Builds an RRULE from natural language parameters.
        
        Args:
            frequency: 'DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY'
            day_of_week: 'MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU' (only for WEEKLY)
            interval: frequency interval (default 1)
            count: number of occurrences (optional)
            until: end date in YYYYMMDD format (optional)
        
        Returns:
            RRULE string
        """
        rule_parts = [f"FREQ={frequency}"]
        
        if interval != 1:
            rule_parts.append(f"INTERVAL={interval}")
        
        if day_of_week and frequency == "WEEKLY":
            rule_parts.append(f"BYDAY={day_of_week}")
        
        if count:
            rule_parts.append(f"COUNT={count}")
        elif until:
            rule_parts.append(f"UNTIL={until}")
        
        return ";".join(rule_parts)
    
    def _add_recurrent_event_to_calendar_tool(self):
        """Creates a tool wrapper for adding a recurrent event to the calendar."""
        @tool
        def add_recurrent_event_to_calendar(event_name: str, 
                                            event_start_date: str,
                                            event_end_date: str,
                                            recurrence_rule: str,
                                            event_location: str = "",
                                            event_desc: str = "",
                                            time_zone: str = "Europe/Rome",
                                            email_remainder: int = 0,
                                            popup_remainder: int = 0,
                                            current_date: str = None) -> str:
            """Adds a recurring event to the calendar with recurrence_rule parameter.
            
            *** PARAMETER NAMES ARE CRITICAL - USE EXACTLY AS SHOWN ***
            
            REQUIRED PARAMETERS:
            - event_name (string): Name/title of event (e.g. "Team Meeting")
            - event_start_date (string): ISO datetime like "2026-01-20T19:00:00"
            - event_end_date (string): ISO datetime like "2026-01-20T20:00:00"  
            - recurrence_rule (string): RRULE like "FREQ=WEEKLY;BYDAY=TU"
            
            OPTIONAL PARAMETERS:
            - event_location (string): Location of event
            - event_desc (string): Description
            - time_zone (string): Default is "UTC"
            - email_remainder (int): Minutes for email reminder (1440=1 day)
            - popup_remainder (int): Minutes for popup reminder (1440=1 day)
            
            RRULE EXAMPLES:
            - "FREQ=WEEKLY;BYDAY=TU" → Every Tuesday
            - "FREQ=DAILY" → Every day
            - "FREQ=WEEKLY;BYDAY=MO,WE,FR" → Mon, Wed, Fri each week
            - "FREQ=MONTHLY" → Monthly
            - "FREQ=WEEKLY;BYDAY=TU;COUNT=10" → 10 occurrences on Tuesdays
            
            PARAMETER NAME REMINDER: It is "recurrence_rule" not "recurrence" or "frequency"
            WKST RULE: Do NOT include WKST parameter - it causes API errors
            DATE FORMAT: Must be ISO format with time (YYYY-MM-DDTHH:MM:SS)"""
            
            # Validate and normalize recurrence rule
            is_valid, result = self._validate_and_normalize_rrule(recurrence_rule)
            if not is_valid:
                return f"Error in recurrence_rule: {result}. Use format like 'FREQ=WEEKLY;BYDAY=TU'"
            
            normalized_rrule = result
            
            # Resolve relative dates using the provided current_date
            resolved_start = resolve_relative_date(event_start_date, current_date) if event_start_date else event_start_date
            resolved_end = resolve_relative_date(event_end_date, current_date) if event_end_date else event_end_date
            
            # Ensure dates are in proper ISO format
            if not resolved_start or 'T' not in resolved_start:
                return "Error: event_start_date must be in ISO format with time (e.g., '2026-01-20T19:00:00')"
            if not resolved_end or 'T' not in resolved_end:
                return "Error: event_end_date must be in ISO format with time (e.g., '2026-01-20T20:00:00')"
            
            return self._add_recurrent_event_to_calendar_impl(event_name, event_location, event_desc,
                                                            resolved_start, resolved_end, time_zone,
                                                            normalized_rrule, email_remainder, popup_remainder)
        return add_recurrent_event_to_calendar

    def _get_upcoming_events_impl(self, max_results: int) -> str:
        """Implementation for retrieving upcoming events from the calendar."""
        now = datetime.today().isoformat() + 'Z'  # 'Z' indicates UTC time
        events_result = self.calendar_service.events().list(calendarId='primary', timeMin=now,
                                                    maxResults=max_results, singleEvents=True,
                                                    orderBy='startTime').execute()
        events = events_result.get('items', [])
        
        if not events:
            return 'No upcoming events found.'
        
        event_list = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            event_list.append(f"{start} - {end} - {event['summary']}")
        
        return "\n".join(event_list)
    
    def _get_upcoming_events_tool(self):
        """Creates a tool wrapper for retrieving upcoming events from the calendar."""
        @tool
        def get_upcoming_events(max_results: int) -> str:
            """Retrieves upcoming events from the calendar."""
            return self._get_upcoming_events_impl(max_results)
        return get_upcoming_events
    
    
    def _get_events_on_date_impl(self, date: str) -> str:
        """Implementation for retrieving events on a specific date from the calendar."""
        start_of_day = f"{date}T00:00:00Z"
        end_of_day = f"{date}T23:59:59Z"
        
        events_result = self.calendar_service.events().list(calendarId='primary', 
                                                            timeMin=start_of_day,
                                                            timeMax=end_of_day,
                                                            singleEvents=True,
                                                            orderBy='startTime').execute()
        events = events_result.get('items', [])
        
        if not events:
            return f'No events found on {date}.'
        
        event_list = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            event_list.append(f"{start} - {event['summary']} - ID: {event['id']}")
        
        return "\n".join(event_list)
    
    def _get_events_on_date_tool(self):
        """Creates a tool wrapper for retrieving events on a specific date from the calendar."""
        @tool
        def get_events_on_date(date: str) -> str:
            """Retrieves events on a specific date from the calendar."""
            return self._get_events_on_date_impl(date)
        return get_events_on_date
    
    def _modify_event_impl(self, event_id: str, summary: str = None, description: str = None, location: str = None, 
                           start_date: str = None, end_date: str = None, time_zone: str = None,
                           email_reminder: int = None, popup_reminder: int = None) -> str:
        """Implementation for modifying an event in the calendar."""
        if not any([summary, description, location, start_date, end_date, email_reminder, popup_reminder]):
            return "Error: At least one field must be provided to update."
        
        try:
            event = self.calendar_service.events().get(calendarId='primary', eventId=event_id).execute()
            
            # Update text fields
            if summary:
                event['summary'] = summary
            if description:
                event['description'] = description
            if location:
                event['location'] = location
            
            # Update date/time fields
            if start_date or end_date or time_zone:
                tz = time_zone or event.get('start', {}).get('timeZone', 'UTC')
                if start_date:
                    event['start'] = {
                        'dateTime': start_date,
                        'timeZone': tz,
                    }
                if end_date:
                    event['end'] = {
                        'dateTime': end_date,
                        'timeZone': tz,
                    }
            
            # Update reminders
            if email_reminder is not None or popup_reminder is not None:
                overrides = []
                if email_reminder is not None:
                    overrides.append({'method': 'email', 'minutes': email_reminder})
                if popup_reminder is not None:
                    overrides.append({'method': 'popup', 'minutes': popup_reminder})
                
                event['reminders'] = {
                    'useDefault': False,
                    'overrides': overrides if overrides else event.get('reminders', {}).get('overrides', [])
                }
            
            updated_event = self.calendar_service.events().update(calendarId='primary', eventId=event_id, body=event).execute()
            return f"Event updated: {updated_event.get('htmlLink')}"
        except HttpError as error:
            return f"An error occurred: {error}"
        
    def _modify_event_tool(self):
        """Creates a tool wrapper for modifying an event in the calendar."""
        @tool
        def modify_event(event_id: str, summary: str = None, description: str = None, location: str = None,
                        start_date: str = None, end_date: str = None, time_zone: str = None,
                        email_reminder: int = None, popup_reminder: int = None, current_date: str = None) -> str:
            """Modifies an event in the calendar. Provide the event ID and the fields you want to update.
            IMPORTANT: If the user mentions relative dates like 'tomorrow', 'today', 'next week', 'next month', etc.,
            you MUST first call get_current_time tool to get the current date and time, then pass that result to
            the current_date parameter of this function.
            current_date should be in format 'YYYY-MM-DD HH:MM:SS' (e.g., from get_current_time output).
            start_date and end_date should be in ISO format (e.g., '2024-01-15T10:00:00'). 
            email_reminder and popup_reminder should be in minutes."""
            # Resolve relative dates using the provided current_date
            resolved_start = resolve_relative_date(start_date, current_date) if start_date else None
            resolved_end = resolve_relative_date(end_date, current_date) if end_date else None
            return self._modify_event_impl(event_id, summary, description, location,
                                            resolved_start, resolved_end, time_zone,
                                            email_reminder, popup_reminder)
        return modify_event
            
            
            
class MailTools(Tools):
    def __init__(self):
        self.mail_service = self.get_mail_service()
    def get_mail_service(self):
        SCOPES = ['https://www.googleapis.com/auth/gmail.send', 'https://www.googleapis.com/auth/gmail.readonly']
        creds = None
        gmail_token_path = get_file_path('gmail_token.json')
        if os.path.exists(gmail_token_path):
            creds = Credentials.from_authorized_user_file(gmail_token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    # If refresh fails (e.g., scope mismatch), delete token and re-authenticate
                    print(f"Token refresh failed: {e}. Re-authenticating...")
                    if os.path.exists(gmail_token_path):
                        os.remove(gmail_token_path)
                    creds = None
            
            if not creds:
                flow = InstalledAppFlow.from_client_secrets_file(
                    get_file_path('credentials.json'), SCOPES)
                creds = flow.run_local_server(port=0)
            with open(gmail_token_path, 'w') as token:
                token.write(creds.to_json())
        try:
            service = build('gmail', 'v1', credentials=creds)
            return service
        except HttpError as error:
            print(f'An error occurred: {error}')
            return None
        
    def send_email_impl(self, to: str, subject: str, body: str) -> str:
        """Sends an email using the Gmail API."""
        if self.mail_service is None:
            return "Error: Gmail service is not available. Please ensure credentials are properly configured."
        
        try:
            # Read from address from email_addres.txt
            try:
                with open(get_file_path('email_addres.txt'), 'r') as file:
                    from_ = file.read().strip()
                if not from_:
                    return "Error: Email address file is empty."
            except FileNotFoundError:
                return "Error: email_addres.txt file not found. Please create it with your email address."
            
            message = EmailMessage()
            message.set_content(body)
            message["To"] = to
            message["From"] = from_
            message["Subject"] = subject

            # encoded message
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

            create_message = {"raw": encoded_message}
            # pylint: disable=E1101
            send_message = (
                self.mail_service.users()
                .messages()
                .send(userId="me", body=create_message)
                .execute()
            )
        except HttpError as error:
            return f"An error occurred: {error}"
        
        return "Email sent successfully to " + to
    
    def send_email_tool(self):
        """Creates a tool wrapper for sending an email."""
        @tool
        def send_email(to: str, subject: str, body: str) -> str:
            """Sends an email using the Gmail API. The sender address is read from email_addres.txt."""
            return self.send_email_impl(to, subject, body)
        return send_email
    
    def get_latest_emails_impl(self, count: int) -> str:
        """Implementation for retrieving the latest {count} emails from the inbox with."""
        
        try:
            results = (
                self.mail_service.users().messages().list(userId="me", labelIds=["INBOX"]).execute()
            )
            messages = results.get("messages", [])[:count]

            if not messages:
                return "No messages found."

            email_list = []
            for message in messages:
                msg = (
                    self.mail_service.users().messages().get(userId="me", id=message["id"]).execute()
                )
                headers = msg["payload"]["headers"]
                sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
                email_list.append(f'Message ID: {message["id"]}, From: {sender}, Subject: {msg["snippet"]}')
            
            return "\n".join(email_list)
        except HttpError as error:
            return f"An error occurred: {error}"
    
    def get_latest_emails_tool(self):
        """Creates a tool wrapper for retrieving the latest emails from the inbox."""
        @tool
        def get_latest_emails(count: int) -> str:
            """Retrieves the latest emails from the inbox."""
            return self.get_latest_emails_impl(count)
        return get_latest_emails
    
    def get_tools(self):
        """
        Returns a list of tool callables as standalone functions (not methods).
        """
        return [
            self.send_email_tool(),
            self.get_latest_emails_tool()
        ]