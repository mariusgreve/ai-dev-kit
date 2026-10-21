import subprocess
import unittest
SCRIPT = "./scripts/format-commit-message"

def format_message(message, *args):
   return subprocess.run(
       [SCRIPT, *args],
       input=message,
       text=True,
       capture_output=True,
   )

class FormatCommitMessageTest(unittest.TestCase):
   def test_wraps_prose(self):
       result = format_message(
           "Improve commit formatting\n\n"
           "This is a deliberately long paragraph that should be wrapped "
           "automatically without requiring the agent to decide where any "
           "of the line breaks should be placed."
       )
       self.assertEqual(result.returncode, 0)
       self.assertTrue(
           all(len(line) <= 72 for line in result.stdout.splitlines())
       )
   def test_reflows_existing_line_breaks(self):
       a = format_message(
           "Improve formatting\n\n"
           "This text was written on one line and should be formatted "
           "deterministically by the script."
       )
       b = format_message(
           "Improve formatting\n\n"
           "This text was written on one line\n"
           "and should be formatted deterministically\n"
           "by the script."
       )
       self.assertEqual(a.stdout, b.stdout)
   def test_wraps_bullets_with_hanging_indent(self):
       result = format_message(
           "Improve formatting\n\n"
           "- This is a deliberately long bullet item that should wrap "
           "onto another line while preserving the correct hanging indent."
       )
       lines = result.stdout.splitlines()
       continuation = lines[3]
       self.assertTrue(continuation.startswith("  "))
       self.assertTrue(all(len(line) <= 72 for line in lines))
   def test_rejects_long_subject(self):
       result = format_message("x" * 73)
       self.assertNotEqual(result.returncode, 0)
       self.assertIn("exceeds 72", result.stderr)
   def test_prefixes_subject_with_ticket(self):
       result = format_message("Fix the login flow", "--ticket", "TICKET-123")
       self.assertEqual(result.returncode, 0)
       self.assertEqual(result.stdout, "TICKET-123: Fix the login flow\n")
   def test_does_not_duplicate_ticket_prefix(self):
       result = format_message(
           "TICKET-123: Fix the login flow", "--ticket", "TICKET-123"
       )
       self.assertEqual(result.returncode, 0)
       self.assertEqual(result.stdout, "TICKET-123: Fix the login flow\n")
   def test_rejects_invalid_ticket(self):
       result = format_message("Fix the login flow", "--ticket", "ticket123")
       self.assertNotEqual(result.returncode, 0)
       self.assertIn("PROJECT-123", result.stderr)
   def test_ticket_prefix_counts_toward_subject_limit(self):
       result = format_message("x" * 62, "--ticket", "TICKET-123")
       self.assertNotEqual(result.returncode, 0)
       self.assertIn("exceeds 72", result.stderr)

if __name__ == "__main__":
   unittest.main()
