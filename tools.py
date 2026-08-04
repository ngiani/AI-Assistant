import base64
import mimetypes
import os
import os.path
import subprocess
import sys

from email.message import EmailMessage
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from email.message import EmailMessage
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.text import MIMEText


from langchain.tools import tool
from datetime import datetime, timedelta
from dateutil import tz

from dotenv import load_dotenv
from utils import get_file_path, resolve_relative_date, build_file_part

# Load environment variables from .env file
load_dotenv()

#Abstract tools class to define common behavior for all tool
class Tools:
    def get_tools(self):
        pass

class FileSystemTools(Tools):
    def show_folder_contents_impl(self, folder_path: str) -> str:
        """Implementation for showing folder contents."""
        if not os.path.exists(folder_path):
            return f"Error: The folder '{folder_path}' does not exist."
        if not os.path.isdir(folder_path):
            return f"Error: '{folder_path}' is not a directory."
        try:
            items = os.listdir(folder_path)
            if not items:
                return "The folder is empty."
            return "\n".join(items)
        except Exception as e:
            return f"An error occurred: {str(e)}"
        
    def show_folder_contents_tool(self):
            """Creates a tool wrapper for showing folder contents."""
            @tool
            def show_folder_contents(folder_path: str) -> str:
                """Shows the contents of the specified folder."""
                return self.show_folder_contents_impl(folder_path)
            return show_folder_contents
    
    def open_file_impl(self, file_path: str) -> str:
        """Implementation for opening a file with the default application."""
        # Check if file exists first
        if not os.path.exists(file_path):
            return f"Error: The file '{file_path}' does not exist."
        
        try:
            if os.name == 'nt':  # For Windows
                os.startfile(file_path)
            elif os.name == 'posix':  # For macOS and Linux
                subprocess.run(['open' if sys.platform == 'darwin' else 'xdg-open', file_path])
            return f"Opened file: {file_path}"
        except Exception as e:
            return f"An error occurred: {str(e)}"
    def open_file_tool(self):
            """Creates a tool wrapper for opening a file."""
            @tool
            def open_file(file_path: str) -> str:
                """Opens the specified file with the default application."""
                return self.open_file_impl(file_path)
            return open_file
        
    def remove_file_impl(self, file_path: str) -> str:
        """Implementation for removing a file."""
        try:
            os.remove(file_path)
            return f"Removed file: {file_path}"
        except FileNotFoundError:
            return f"Error: The file '{file_path}' does not exist."
        except Exception as e:
            return f"An error occurred: {str(e)}"
        
    def remove_file_tool(self):
            """Creates a tool wrapper for removing a file."""
            @tool
            def remove_file(file_path: str) -> str:
                """Removes the specified file."""
                return self.remove_file_impl(file_path)
            return remove_file
        
    def remove_folder_impl(self, folder_path: str) -> str:
        """Implementation for removing a folder."""
        try:
            os.rmdir(folder_path)
            return f"Removed folder: {folder_path}"
        except FileNotFoundError:
            return f"Error: The folder '{folder_path}' does not exist."
        except OSError as e:
            return f"Error: The folder '{folder_path}' is not empty or cannot be removed. {str(e)}"
        except Exception as e:
            return f"An error occurred: {str(e)}"
    def remove_folder_tool(self):
            """Creates a tool wrapper for removing a folder."""
            @tool
            def remove_folder(folder_path: str) -> str:
                """Removes the specified folder."""
                return self.remove_folder_impl(folder_path)
            return remove_folder
    def get_tools(self):
        """
        Returns a list of tool callables as standalone functions (not methods).
        """
        return [
            self.show_folder_contents_tool(),
            self.open_file_tool(),
            self.remove_file_tool(),
            self.remove_folder_tool()
        ]


class TimeTools(Tools):
    
    def get_current_time_impl(self) -> str:
        """Returns the current time as a string in Rome time (container clock may not be Rome-local)."""
        from_zone = tz.tzutc()
        to_zone = tz.gettz("Europe/Rome")
        
        # Get current UTC time as a datetime object with UTC timezone info
        utc_time = datetime.now(from_zone)
        
        # Convert to Rome timezone
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
            self._get_events_on_date_tool(),
            self._remove_event_tool()
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
        event_id = event.get('id')
        return f"Event created: {event.get('htmlLink')}|EVENT_ID:{event_id}"
    
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
            """Adds a one-time event to the calendar. ALWAYS call get_current_time first (including for 'today') and pass
            its result as current_date ('YYYY-MM-DD HH:MM:SS') - never assume today's date from memory. Dates must be
            ISO format with time, e.g. 'YYYY-MM-DDTHH:MM:SS'."""
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
        event_id = event.get('id')
        return f"Recurrent Event created: {event.get('htmlLink')}|EVENT_ID:{event_id}"
    
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
            """Adds a recurring event using recurrence_rule (e.g. 'FREQ=WEEKLY;BYDAY=TU'; no WKST). ALWAYS call
            get_current_time first (including for 'today') and pass its result as current_date ('YYYY-MM-DD HH:MM:SS') -
            never assume today's date from memory. Dates must be ISO format with time, e.g. 'YYYY-MM-DDTHH:MM:SS'."""
            
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
            event_list.append(f"{start} - {end} - {event['summary']} - ID: {event['id']}")
        
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
        
        try:
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
        except Exception as error:
            return f"An error occurred: {error}"
    
    def _get_events_on_date_tool(self):
        """Creates a tool wrapper for retrieving events on a specific date from the calendar."""
        @tool
        def get_events_on_date(date: str, current_date: str = None) -> str:
            """Retrieves events on a specific date from the calendar. date must be YYYY-MM-DD. ALWAYS call
            get_current_time first (including for 'today') and pass its result as current_date
            ('YYYY-MM-DD HH:MM:SS') so relative references like 'today'/'tomorrow' resolve correctly - never assume
            today's date from memory."""
            resolved_date = resolve_relative_date(date, current_date)
            return self._get_events_on_date_impl(resolved_date)
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
                tz = time_zone or event.get('start', {}).get('timeZone', 'Europe/Rome')
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
        except Exception as error:
            return f"An error occurred: {error}"
        
    def _modify_event_tool(self):
        """Creates a tool wrapper for modifying an event in the calendar."""
        @tool
        def modify_event(event_id: str, summary: str = None, description: str = None, location: str = None,
                        start_date: str = None, end_date: str = None, time_zone: str = None,
                        email_reminder: int = None, popup_reminder: int = None, current_date: str = None) -> str:
            """Modifies an event in the calendar; provide event_id and only the fields to update. If updating dates,
            ALWAYS call get_current_time first (including for 'today') and pass its result as current_date
            ('YYYY-MM-DD HH:MM:SS') - never assume today's date from memory. start_date/end_date must be ISO format
            with time; reminders are in minutes."""
            # Resolve relative dates using the provided current_date
            resolved_start = resolve_relative_date(start_date, current_date) if start_date else None
            resolved_end = resolve_relative_date(end_date, current_date) if end_date else None
            return self._modify_event_impl(event_id, summary, description, location,
                                            resolved_start, resolved_end, time_zone,
                                            email_reminder, popup_reminder)
        return modify_event

    def _remove_event_impl(self, event_id: str = None, summary: str = None, date: str = None) -> str:
        """Implementation for removing an event from the calendar, either directly by event_id, or by searching
        deterministically (in code, not via the LLM) for an event whose summary matches, optionally scoped to a
        specific date. This avoids relying on the model to visually match names in a list, which is unreliable."""
        if event_id:
            try:
                self.calendar_service.events().delete(calendarId='primary', eventId=event_id).execute()
                return f"Event {event_id} removed."
            except Exception as error:
                return f"An error occurred: {error}"

        if not summary:
            return "Error: provide either event_id, or summary (optionally with date) to identify the event to remove."

        try:
            if date:
                events_result = self.calendar_service.events().list(calendarId='primary',
                                                                    timeMin=f"{date}T00:00:00Z",
                                                                    timeMax=f"{date}T23:59:59Z",
                                                                    singleEvents=True,
                                                                    orderBy='startTime').execute()
            else:
                now = datetime.today().isoformat() + 'Z'  # 'Z' indicates UTC time
                events_result = self.calendar_service.events().list(calendarId='primary', timeMin=now,
                                                                    maxResults=50, singleEvents=True,
                                                                    orderBy='startTime').execute()
            events = events_result.get('items', [])
        except Exception as error:
            return f"An error occurred while searching for the event: {error}"

        scope = f" on {date}" if date else ""
        if not events:
            return f"No events found{scope}."

        summary_query = summary.strip().lower()
        exact_matches = [e for e in events if e.get('summary', '').strip().lower() == summary_query]
        partial_matches = [e for e in events if summary_query in e.get('summary', '').strip().lower()]
        matches = exact_matches or partial_matches

        if not matches:
            return f"No event found matching '{summary}'{scope}."

        if len(matches) > 1:
            listing = "\n".join(
                f"{e['start'].get('dateTime', e['start'].get('date'))} - {e['summary']} - ID: {e['id']}"
                for e in matches
            )
            return (f"Multiple events match '{summary}'{scope}. Ask the user which one, then call remove_event "
                    f"again with the exact event_id:\n{listing}")

        match = matches[0]
        try:
            self.calendar_service.events().delete(calendarId='primary', eventId=match['id']).execute()
            start = match['start'].get('dateTime', match['start'].get('date'))
            return f"Event '{match['summary']}' ({start}) removed."
        except Exception as error:
            return f"An error occurred: {error}"

    def _remove_event_tool(self):
        """Creates a tool wrapper for removing an event from the calendar."""
        @tool
        def remove_event(event_id: str = None, summary: str = None, date: str = None, current_date: str = None) -> str:
            """Removes an event from the calendar. Preferred: pass summary (the event's name/title as the user said
            it) and, if the user mentioned one, date (YYYY-MM-DD - resolve relative references like 'today' by
            calling get_current_time first and passing its result as current_date). The matching event is found
            deterministically and deleted automatically if there's exactly one match; if there are multiple matches
            you'll get a list of candidates with their event_id to ask the user about; if there's no match you'll be
            told so - never guess or delete an unrelated event. Alternatively, if you already know the exact
            event_id (e.g. the user gave it, or a previous tool call returned it), pass that instead."""
            resolved_date = resolve_relative_date(date, current_date) if date else None
            return self._remove_event_impl(event_id, summary, resolved_date)
        return remove_event
 
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
       
    def draft_message_impl(self, to: str, subject: str, body: str) -> dict:
        """Creates a draft email message. """
        from_ = os.getenv("EMAIL_ADDRESS")
        if not from_:
            raise ValueError("Email address environment variable is not set.")
        
        message = EmailMessage()
        message.set_content(body)
        message["To"] = to
        message["From"] = from_
        message["Subject"] = subject

        # encoded message
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        return encoded_message
    def draft_message_tool(self):
        """Creates a tool wrapper for drafting an email."""
        @tool
        def draft_message(to: str, subject: str, body: str) -> dict:
            """Creates a draft email message. The sender address is read from email_addres.txt."""
            return self.draft_message_impl(to, subject, body)
        return draft_message
     
    def send_message_impl(self, to: str, subject: str, body: str) -> str:
        """Sends an email using the Gmail API."""
        if self.mail_service is None:
            return "Error: Gmail service is not available. Please ensure credentials are properly configured."
        
        # Validate email address format
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, to):
            return f"Error: Invalid email address format: {to}"
        
        try:
            # Read from address from environment variable
            from_ = os.getenv("EMAIL_ADDRESS")
            if not from_:
                return "Error: Email address environment variable is not set."
            
            message = EmailMessage()
            message["To"] = to
            message["From"] = from_
            message["Subject"] = subject
            message.set_content(body)

            # encoded message
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

            create_message = {"raw": encoded_message}

            # send message to user identified by to
            self.mail_service.users().messages().send(userId="me", body=create_message).execute()
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"
        
        return "Email sent successfully to " + to
    
    def send_message_tool(self):
        """Creates a tool wrapper for sending an email."""
        @tool
        def send_message(to: str, subject: str, body: str) -> str:
            """Sends an email using the Gmail API. The sender address is read from .env file."""
            return self.send_message_impl(to, subject, body)
        return send_message
    
    def draft_message_with_attachment_impl(self, to: str, subject: str, body: str, file_paths: list[str]) -> dict:
        """Creates a message with attachments. If multiple files are provided, they will all be attached.

        Args:
            to: The recipient's email address.
            subject: The subject of the email.
            body: The body text of the email.
            file_paths: A list of file paths to attach.

        Returns:
            A dictionary representing the message.
        """
        from_ = os.getenv("EMAIL_ADDRESS")
        if not from_:
            raise ValueError("Email address environment variable is not set.")
        
        message = EmailMessage()
        message["To"] = to
        message["From"] = from_
        message["Subject"] = subject
        message.set_content(body)

        try :
            for file_path in file_paths:
                part = build_file_part(file_path)
                message.add_attachment(part.get_payload(decode=True), maintype=part.get_content_maintype(),
                                    subtype=part.get_content_subtype(), filename=part.get_filename())
        except FileNotFoundError:
            raise FileNotFoundError(f"Attachment file not found: {file_path}")

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return encoded_message
    
    def draft_message_with_attachment_tool(self):
        """Creates a tool wrapper for creating a message with attachments."""
        @tool
        def draft_message_with_attachment_tool(to: str, subject: str, body: str, file_paths: list[str]) -> dict:
            """Creates a message with attachments."""
            return self.draft_message_with_attachment_impl(to, subject, body, file_paths)
        return draft_message_with_attachment_tool
    
    def send_message_with_attachment_impl(self, to: str, subject: str, body: str, file_paths: list[str]) -> str:
        """Sends an email with attachments using the Gmail API."""
        if self.mail_service is None:
            return "Error: Gmail service is not available. Please ensure credentials are properly configured."
        
        # Validate email address format
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, to):
            return f"Error: Invalid email address format: {to}"
        
        # Read from address from environment variable
        from_ = os.getenv("EMAIL_ADDRESS")
        if not from_:
            return "Error: Email address environment variable is not set."
        
        message = EmailMessage()
        message.set_content(body)
        message["To"] = to
        message["From"] = from_
        message["Subject"] = subject
        message.set_content(body)

        try:
            for file_path in file_paths:
                
                part = build_file_part(file_path)
                message.add_attachment(part.get_payload(decode=True), maintype=part.get_content_maintype(),
                                    subtype=part.get_content_subtype(), filename=part.get_filename())
            
            # encoded message
            encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

            create_message = {"raw": encoded_message}
            # pylint: disable=E1101
            self.mail_service.users().messages().send(userId="me", body=create_message).execute()
 
        except FileNotFoundError:
            raise FileNotFoundError(f"Attachment file not found: {file_path}")
        except Exception as error:
            return f"An error occurred: {error}"
        
        return "Email with attachment sent successfully to " + to
    
    def send_message_with_attachment_tool(self):
        """Creates a tool wrapper for sending an email with attachments."""
        @tool
        def send_message_with_attachment(to: str, subject: str, body: str, file_paths: list[str]) -> str:
            """Sends an email with attachments using the Gmail API."""
            return self.send_message_with_attachment_impl(to, subject, body, file_paths)
        return send_message_with_attachment
    
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
            self.get_latest_emails_tool(), 
            self.send_message_tool(),
            self.draft_message_tool(),
            self.draft_message_with_attachment_tool(),
            self.send_message_with_attachment_tool()
        ]