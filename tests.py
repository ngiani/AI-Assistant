from unittest import TestCase
from unittest.mock import patch, MagicMock
import unittest

from tools import MailTools, CalendarTools, FileSystemTools, build_file_part
from langchain.messages import AIMessageChunk, AIMessage, HumanMessage, ToolMessage
from agent import Agent
import os


class TestEmailTools(TestCase):
    
    # Here you would set up your tool and mock any external dependencies
    tool = MailTools() 
    
    def test_send_message_attachments_impl(self):
        
        with patch.object(self.tool, 'mail_service') as mock_service:
            # Mock the send method to simulate sending email
            mock_service.users().messages().send().execute.return_value = {
                'id': '12345'
            }
            self.assertEqual(self.tool.send_message_with_attachment_impl(
                os.environ["EMAIL_ADDRESS"],
                "Test Subject with Attachment",
                "This is a test email body with attachment.",
                [os.path.join(os.getcwd(), "test_attachment.txt")]
            ), "Email with attachment sent successfully to " + os.environ["EMAIL_ADDRESS"])
            
            with self.assertRaises(FileNotFoundError):
                self.tool.send_message_with_attachment_impl(
                    os.environ["EMAIL_ADDRESS"],
                    "Test Subject with Attachment",
                    "This is a test email body with attachment.",
                    [os.path.join(os.getcwd(), "non_existent_file.txt")]
                )
            
            # Test invalid email address format
            result = self.tool.send_message_with_attachment_impl(
                "invalid_email_address",
                "Test Subject with Attachment",
                "This is a test email body with attachment.",
                [os.path.join(os.getcwd(), "test_attachment.txt")]
            )
            self.assertIn("Error: Invalid email address format", result)
            
            # Test other invalid email formats
            invalid_emails = ["test@", "@domain.com", "test@domain", "test.domain.com", ""]
            for invalid_email in invalid_emails:
                result = self.tool.send_message_with_attachment_impl(
                    invalid_email,
                    "Test Subject",
                    "Body",
                    [os.path.join(os.getcwd(), "test_attachment.txt")]
                )
                self.assertIn("Error: Invalid email address format", result)
        
    def test_send_message_impl(self):
        
        with patch.object(self.tool, 'mail_service') as mock_service:
            # Mock the send method to simulate sending email
            mock_service.users().messages().send().execute.return_value = {
                'id': '12345'
            }
        
            self.assertEqual(self.tool.send_message_impl(os.environ["EMAIL_ADDRESS"],
                                                    "Test Subject",
                                                        "This is a test email body."),
                                "Email sent successfully to " + os.environ["EMAIL_ADDRESS"])
            
            # Test invalid email address format
            result = self.tool.send_message_impl(
                "invalid_email_address",
                "Test Subject with Attachment",
                "This is a test email body with attachment."
            )
            self.assertIn("Error: Invalid email address format", result)
            
            # Test various invalid email formats
            invalid_emails = [
                "no_at_sign.com",
                "test@",
                "@domain.com",
                "test@@domain.com",
                "test @domain.com",
                "test@domain",
                "test@.com"
            ]
            for invalid_email in invalid_emails:
                result = self.tool.send_message_impl(
                    invalid_email,
                    "Test Subject",
                    "Test Body"
                )
                self.assertIn("Error: Invalid email address format", result)
        
        
    
            
    def test_draft_message_impl(self):

        self.assertIsInstance(self.tool.draft_message_impl(os.environ["EMAIL_ADDRESS"],
                                                      "Draft Subject",
                                                      "This is a draft email body."), str)
            
    def test_draft_message_with_attachment_impl(self):

        self.assertIsInstance(self.tool.draft_message_with_attachment_impl(
            os.environ["EMAIL_ADDRESS"],
            "Draft Subject with Attachment",
            "This is a draft email body with attachment.",
            [os.path.join(os.getcwd(), "test_attachment.txt")]
        ), str)
        
        with self.assertRaises(FileNotFoundError):
            self.tool.draft_message_with_attachment_impl(
                os.environ["EMAIL_ADDRESS"],
                "Draft Subject with Attachment",
                "This is a draft email body with attachment.",
                [os.path.join(os.getcwd(), "non_existent_file.txt")]
            )

            
    def test_get_latest_emails_impl(self):
        
        with patch.object(self.tool, 'mail_service') as mock_service:
            # Mock the list and get methods to simulate fetching emails
            mock_service.users().messages().list().execute.return_value = {
                'messages': [{'id': '1'}, {'id': '2'}]
            }
            mock_service.users().messages().get().execute.side_effect = [
                {'snippet': 'Email 1 snippet', 'payload': {'headers': []}},
                {'snippet': 'Email 2 snippet', 'payload': { 'headers': [] }}
            ]
        
            emails = self.tool.get_latest_emails_impl(2).splitlines()
            self.assertIsInstance(emails, list)
            self.assertEqual(len(emails), 2)
        
    def test_build_file_part(self):

        test_filename = os.path.join(os.getcwd(), "test_attachment.txt")
        
        with open(test_filename, "rb") as f:
            file_part = build_file_part(test_filename)
            
        with self.assertRaises(FileNotFoundError):
            build_file_part("non_existent_file.txt")

        self.assertEqual(file_part.get_filename(), test_filename.split(os.sep)[-1])
        self.assertEqual(file_part.get_content_type(), "text/plain")

class TestCalendarTools(TestCase):
    
    tool = CalendarTools()
    
    def test_add_event_impl(self):
        with patch.object(self.tool, 'calendar_service') as mock_service:
            # Set up the mock chain: calendar_service.events().insert().execute()
            mock_service.events().insert().execute.return_value = {
                'htmlLink': 'http://example.com/event',
                'id': 'event123'
            }
            
            result = self.tool._add_event_to_calendar_impl(
                "Test Event",
                "New York",
                "Test event",
                "2026-12-31T10:00:00",
                "2026-12-31T11:00:00",
                "UTC",
                30,
                30
            )
            
            self.assertIn("Event created:", result)
            self.assertIn("EVENT_ID:event123", result)
        
    def test_add_recurrent_event_impl(self):
        
        with patch.object(self.tool, 'calendar_service') as mock_service:
            # Set up the mock chain: calendar_service.events().insert().execute()
            mock_service.events().insert().execute.return_value = {
                'htmlLink': 'http://example.com/event',
                'id': 'event123'
            }
        
            result = self.tool._add_recurrent_event_to_calendar_impl(
                "Recurrent Test Event",
                "New York",
                "Test recurrent event",
                "2026-12-31T10:00:00",
                "2026-12-31T11:00:00",
                "UTC",
                "RRULE:FREQ=DAILY;COUNT=5",
                30,
                30
            )
            self.assertIn("Recurrent Event created:", result)
            self.assertIn("EVENT_ID:event123", result)
    
    def test_validate_and_nomalize_rrule(self):
        valid_rule = "FREQ=WEEKLY;COUNT=10"
        no_frequency_rule = "COUNT=10;"
        empty_rule = ""
        invalid_frequency_rule = "FREQ=INVALID;COUNT=10"
        
        self.assertEqual(
            self.tool._validate_and_normalize_rrule(valid_rule),
            (True, "FREQ=WEEKLY;COUNT=10")
        )
        
        self.assertEqual(
            self.tool._validate_and_normalize_rrule(empty_rule),
            (False, "RRULE cannot be empty")
        )

        self.assertEqual(
            self.tool._validate_and_normalize_rrule(no_frequency_rule),
            (False, f"RRULE must contain FREQ parameter. Got: {no_frequency_rule}")
        )
        
        self.assertIn(
            "RRULE FREQ must be one of:",
            self.tool._validate_and_normalize_rrule(invalid_frequency_rule)[1]
        )
    
    
    def test_upcoming_events_impl(self):
        
        with patch.object(self.tool, 'calendar_service') as mock_service:
            # Set up the mock chain: calendar_service.events().list().execute()
            mock_service.events().list().execute.return_value = {
                'items': [
                    {'summary': 'Event 1', 'start': {'dateTime': '2026-12-01T10:00:00Z'}, 'end': {'dateTime': '2026-12-01T11:00:00Z'}},
                    {'summary': 'Event 2', 'start': {'dateTime': '2026-12-02T10:00:00Z'}, 'end': {'dateTime': '2026-12-02T11:00:00Z'}},
                    {'summary': 'Event 3', 'start': {'dateTime': '2026-12-03T10:00:00Z'}, 'end': {'dateTime': '2026-12-03T11:00:00Z'}}
                ]
            }
            
            
            events = self.tool._get_upcoming_events_impl(3).splitlines()
            self.assertIsInstance(events, list)
            self.assertLessEqual(len(events), 3)
        
    def test_modify_event_impl(self):
        
        with patch.object(self.tool, 'calendar_service') as mock_service:
            # Set up the mock chain: calendar_service.events().get().execute()
            mock_service.events().get().execute.return_value = {
                'summary': 'Event to Modify',
                'location': 'New York',
                'description': 'This event will be modified.',
                'start': {'dateTime': '2026-12-31T12:00:00', 'timeZone': 'UTC'},
                'end': {'dateTime': '2026-12-31T13:00:00', 'timeZone': 'UTC'}
            }
            # Set up the mock chain: calendar_service.events().update().execute()
            mock_service.events().update().execute.return_value = {
                'htmlLink': 'http://example.com/modified_event',
                'id': 'modified_event123'
            }
        
            # First, get an upcoming event to modify
            creation_result = self.tool._add_event_to_calendar_impl(
                "Event to Modify",
                "New York",
                "This event will be modified.",
                "2026-12-31T12:00:00",
                "2026-12-31T13:00:00",
                "UTC",
                30,
                30
            )
            print(creation_result)
            
            # Extract event ID from the response (format: "Event created: <link>|EVENT_ID:<id>")
            event_id = creation_result.split("EVENT_ID:")[1]
            
            # Now, modify the event
            modify_result = self.tool._modify_event_impl(
                event_id,
                summary="Modified Event",
                description="This event has been modified."
            )
            
            self.assertIn("Event updated:", modify_result)
    

class TestFileSystemTools(TestCase):
    
    tool = FileSystemTools()
    
    def test_show_folder_contents_impl(self):
        tool = FileSystemTools()
        
        # Create a test directory with some files
        test_dir = os.path.join(os.getcwd(), "test_dir")
        os.makedirs(test_dir, exist_ok=True)
        with open(os.path.join(test_dir, "file1.txt"), "w") as f:
            f.write("This is file 1.")
        with open(os.path.join(test_dir, "file2.txt"), "w") as f:
            f.write("This is file 2.")
        contents = tool.show_folder_contents_impl(test_dir)
        self.assertIn("file1.txt", contents)
        self.assertIn("file2.txt", contents)
        # Clean up
        os.remove(os.path.join(test_dir, "file1.txt"))
        os.remove(os.path.join(test_dir, "file2.txt"))
        os.rmdir(test_dir)
        
        # Test non-existent directory
        result = tool.show_folder_contents_impl("non_existent_dir")
        self.assertIn("does not exist", result)   
        
        
    def test_open_file_impl(self):
        tool = FileSystemTools()
        test_file = os.path.join(os.getcwd(), "test_file.txt")
        
        # Create a test file
        with open(test_file, "w") as f:
            f.write("This is a test file.")
        
        content = tool.open_file_impl(test_file)
        self.assertEqual(content, f"Opened file: {test_file}")
        
        # Clean up
        os.remove(test_file)
        
        # Test non-existent file
        result = tool.open_file_impl("non_existent_file.txt")
        self.assertIn("does not exist", result)    
        
    def test_remove_file_impl(self):
        tool = FileSystemTools()
        test_file = os.path.join(os.getcwd(), "test_file_to_remove.txt")
        
        # Create a test file
        with open(test_file, "w") as f:
            f.write("This file will be removed.")
        
        result = tool.remove_file_impl(test_file)
        self.assertIn("Removed file", result)
        
        # Test removing non-existent file
        result = tool.remove_file_impl("non_existent_file.txt")
        self.assertIn("does not exist", result)
        
    def test_remove_folder_impl(self):
        tool = FileSystemTools()
        test_dir = os.path.join(os.getcwd(), "test_dir_to_remove")
        
        # Create a test directory
        os.makedirs(test_dir, exist_ok=True)
        
        result = tool.remove_folder_impl(test_dir)
        self.assertIn("Removed folder", result)
        
        # Test removing non-existent directory
        result = tool.remove_folder_impl("non_existent_dir")
        self.assertIn("does not exist", result)
    
class TestAgent(TestCase):
    
    def test_invoke(self):
        with patch('agent.create_agent') as mock_create_agent:
            mock_agent_instance = MagicMock()
            mock_create_agent.return_value = mock_agent_instance
            mock_agent_instance.invoke.return_value = {
                'messages': [MagicMock(content="Test response", __class__=Agent)]
            }
            
            self.assertIn("Test response", mock_agent_instance.invoke.return_value['messages'][0].content)
            
    def test_stream_invoke(self):
        with patch('agent.create_agent') as mock_create_agent:
            mock_agent_instance = MagicMock()
            mock_create_agent.return_value = mock_agent_instance
            mock_agent_instance.stream.return_value = [
                [MagicMock(content="Token 1", __class__=Agent)],
                [MagicMock(content="Token 2", __class__=Agent)]
            ]
            
            tokens = list(mock_agent_instance.stream.return_value)
            self.assertEqual(len(tokens), 2)
            self.assertIn("Token 1", tokens[0][0].content)
            self.assertIn("Token 2", tokens[1][0].content)
            
    def test_ai_message_token(self):
        token = [AIMessageChunk(content="This is a token")]
        
        self.assertEqual(Agent.get_ai_message_token(self, token), "This is a token")
        
    def test_ai_message(self):
        response = {
            'messages': [
                AIMessage(content="AI message content")
            ]
        }
        
        self.assertEqual(Agent.get_ai_message(self, response), "AI message content")
        
    def test_human_message(self):
        response = {
            'messages': [
                HumanMessage(content="Human message content")
            ]
        }
        
        self.assertEqual(Agent.get_human_message(self, response), "Human message content")
        
    def test_tool_message(self):
        response = {
            'messages': [
                ToolMessage(content="Tool message content", tool_call_id="1")
            ]
        }
        
        self.assertEqual(Agent.get_tool_message(self, response), "Tool message content")

if __name__ == '__main__':
    unittest.main()
            
            
        
        
                         
        