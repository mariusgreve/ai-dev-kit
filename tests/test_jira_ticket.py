"""Exercise the bundled Jira reader against a loopback mock, never a real Jira."""

from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import threading
import unittest
from http.client import IncompleteRead
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit


SCRIPT = (Path(__file__).resolve().parents[1] / "skills/jira-implementation-analysis"
          / "scripts/fetch_jira_ticket.py")
SPEC = importlib.util.spec_from_file_location("fetch_jira_ticket", SCRIPT)
jira = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(jira)
TOKEN = "test-only-personal-access-token"


class MockJira(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.requests.append((self.command, self.path, self.headers["Authorization"]))
        status, headers, body = self.server.replies.pop(0)
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body if isinstance(body, bytes) else json.dumps(body).encode())

    def log_message(self, *args):
        pass


class JiraTicketTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MockJira)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}/jira"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.server.requests = []
        self.server.replies = []
        self.environment = {"JIRA_BASE_URL": self.base_url, "JIRA_TOKEN": TOKEN}
        self.issue = {
            "key": "PROJ-123",
            "names": {"customfield_10001": "Acceptance Criteria"},
            "fields": {
                "summary": "Fix search", "description": "Search returns duplicates",
                "status": {"name": "Open"}, "issuetype": {"name": "Bug"},
                "priority": {"name": "High"}, "labels": ["search"],
                "components": [{"name": "Backend"}],
                "customfield_10001": "No duplicate results",
                "comment": {"startAt": 0, "total": 1, "comments": [{"id": "1", "body": "Context"}]},
                "issuelinks": [{"type": {"name": "Blocks"}, "outwardIssue": {"key": "OTHER-1"}}],
                "subtasks": [{"key": "PROJ-124"}],
            },
        }

    def run_script(self, key="PROJ-123", environment=None):
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), key],
            env={**os.environ, "JIRA_BASE_URL": "", "JIRA_TOKEN": "",
                 "no_proxy": "*", "NO_PROXY": "*",
                 **(self.environment if environment is None else environment)},
            capture_output=True, text=True,
        )

    def assert_failure(self, result, message):
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn(message, result.stderr)
        self.assertNotIn(TOKEN, result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_fetches_all_fields_with_names_and_bearer_auth(self):
        self.server.replies = [(200, {}, self.issue)]
        result = self.run_script(environment={**self.environment, "JIRA_BASE_URL": self.base_url + "/"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), self.issue)
        method, target, authorization = self.server.requests[0]
        self.assertEqual(method, "GET")
        self.assertEqual(urlsplit(target).path, "/jira/rest/api/2/issue/PROJ-123")
        self.assertEqual(parse_qs(urlsplit(target).query), {"fields": ["*all"], "expand": ["names"]})
        self.assertEqual(authorization, "Bearer " + TOKEN)
        self.assertNotIn(TOKEN, result.stdout + result.stderr + target)
        self.assertEqual(len(self.server.requests), 1)

    def test_fetches_all_comment_pages_without_following_linked_tickets(self):
        self.issue["fields"]["comment"]["total"] = 3
        self.server.replies = [
            (200, {}, self.issue),
            (200, {}, {"startAt": 0, "total": 3, "comments": [{"id": "1"}, {"id": "2"}]}),
            (200, {}, {"startAt": 2, "total": 3, "comments": [{"id": "3"}]}),
        ]
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        comments = json.loads(result.stdout)["fields"]["comment"]
        self.assertEqual(comments["comments"], [{"id": "1"}, {"id": "2"}, {"id": "3"}])
        self.assertEqual(comments["startAt"], 0)
        for request, offset in zip(self.server.requests[1:], (0, 2)):
            self.assertEqual(request[0], "GET")
            self.assertEqual(urlsplit(request[1]).path, "/jira/rest/api/2/issue/PROJ-123/comment")
            self.assertEqual(parse_qs(urlsplit(request[1]).query)["startAt"], [str(offset)])
        self.assertEqual(len(self.server.requests), 3)

    def test_missing_comments_are_not_treated_as_an_empty_thread(self):
        del self.issue["fields"]["comment"]
        self.server.replies = [(200, {}, self.issue)]
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("comment", json.loads(result.stdout)["fields"])
        self.assertEqual(len(self.server.requests), 1)

    def test_rejects_stalled_or_changing_comment_pagination(self):
        for page in (
            {"startAt": 0, "total": 2, "comments": []},
            {"startAt": 1, "total": 2, "comments": [{"id": "2"}]},
            {"startAt": 0, "total": 3, "comments": [{"id": "1"}]},
        ):
            with self.subTest(page=page):
                self.issue["fields"]["comment"]["total"] = 2
                self.server.replies = [(200, {}, self.issue), (200, {}, page)]
                self.assert_failure(self.run_script(), "pagination")

    def test_rejects_malformed_initial_comment_pagination(self):
        for comment in (
            [], {"total": -1, "comments": []}, {"total": 0, "comments": [{"id": "1"}]},
            {"startAt": -1, "total": 0, "comments": []}, {"total": 1, "comments": None},
        ):
            with self.subTest(comment=comment):
                self.issue["fields"]["comment"] = comment
                self.server.replies = [(200, {}, self.issue)]
                self.assert_failure(self.run_script(), "Jira returned")

    def test_missing_environment_fails_without_a_request(self):
        for environment in ({}, {"JIRA_TOKEN": TOKEN}, {"JIRA_BASE_URL": self.base_url}):
            with self.subTest(environment=tuple(environment)):
                self.assert_failure(self.run_script(environment=environment), "JIRA_BASE_URL and JIRA_TOKEN")
        self.assertEqual(self.server.requests, [])

    def test_invalid_keys_fail_without_a_request(self):
        for key in ("../PROJ-123", "PROJ-123/comments", "PROJ-1?fields=*", "proj-123", "PROJ-0"):
            with self.subTest(key=key):
                self.assert_failure(self.run_script(key), "Invalid ticket key")
        self.assertEqual(self.server.requests, [])

    def test_rejects_unsafe_base_addresses_without_a_request(self):
        for address in (
            "http://jira.example.test", "ftp://jira.example.test",
            "https://user:password@jira.example.test", "https://jira.example.test?query=1",
            "https://jira.example.test/#fragment", "https://jira.example.test?",
            "https://jira.example.test#", "https://jira.example.test:invalid",
            "https://[broken", "https://jira.example.test\\other", "https://jira.example.test/\n",
        ):
            with self.subTest(address=address):
                environment = {**self.environment, "JIRA_BASE_URL": address}
                self.assert_failure(self.run_script(environment=environment), "JIRA_BASE_URL")
        self.assertEqual(self.server.requests, [])

    def test_rejects_token_header_injection_without_a_request(self):
        environment = {**self.environment, "JIRA_TOKEN": TOKEN + "\nInjected: value"}
        self.assert_failure(self.run_script(environment=environment), "JIRA_TOKEN")
        self.assertEqual(self.server.requests, [])

    def test_reports_status_errors_without_echoing_response_or_token(self):
        for status, message in ((401, "authentication"), (403, "denied access"),
                                (404, "not found"), (429, "429"), (500, "500")):
            with self.subTest(status=status):
                self.server.replies = [(status, {}, {"errorMessages": [TOKEN]})]
                self.assert_failure(self.run_script(), message)

    def test_refuses_redirects_and_does_not_forward_the_token(self):
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                self.server.requests = []
                self.server.replies = [(status, {"Location": self.base_url + "/other"}, {})]
                self.assert_failure(self.run_script(), "redirects are disabled")
                self.assertEqual(len(self.server.requests), 1)

    def test_invalid_json_and_unexpected_response_shapes(self):
        for body in (b"<html>Sign in</html>", b"\xff", [], {},
                     {"key": "OTHER-1", "fields": {}}):
            with self.subTest(body=body):
                self.server.replies = [(200, {}, body)]
                self.assert_failure(self.run_script(), "Jira returned")

    def test_does_not_print_a_token_reflected_in_successful_response(self):
        self.issue["fields"]["description"] = TOKEN
        self.server.replies = [(200, {}, self.issue)]
        self.assert_failure(self.run_script(), "refusing to print")

    def test_network_timeout_and_certificate_errors_are_sanitized(self):
        for reason, message in (
            (OSError(TOKEN), "Could not connect"),
            (TimeoutError(TOKEN), "timed out"),
            (ssl.SSLCertVerificationError(TOKEN), "certificate"),
        ):
            with self.subTest(reason=type(reason).__name__):
                out, err = io.StringIO(), io.StringIO()
                with (
                    patch.dict(os.environ, self.environment),
                    patch.object(sys, "argv", [str(SCRIPT), "PROJ-123"]),
                    patch.object(jira, "build_opener") as factory,
                    redirect_stdout(out), redirect_stderr(err),
                ):
                    factory.return_value.open.side_effect = URLError(reason)
                    code = jira.main()
                self.assertEqual(code, 1)
                self.assertEqual(out.getvalue(), "")
                self.assertIn(message, err.getvalue())
                self.assertNotIn(TOKEN, err.getvalue())

    def test_incomplete_response_is_a_clear_error(self):
        out, err = io.StringIO(), io.StringIO()
        with (
            patch.dict(os.environ, self.environment),
            patch.object(sys, "argv", [str(SCRIPT), "PROJ-123"]),
            patch.object(jira, "build_opener") as factory,
            redirect_stdout(out), redirect_stderr(err),
        ):
            factory.return_value.open.return_value.__enter__.return_value.read.side_effect = (
                IncompleteRead(TOKEN.encode())
            )
            self.assertEqual(jira.main(), 1)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("Could not connect", err.getvalue())
        self.assertNotIn(TOKEN, err.getvalue())


if __name__ == "__main__":
    unittest.main()
