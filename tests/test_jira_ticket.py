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
        self.field_defs = [
            {"id": "customfield_10002", "name": "Internal Cost Notes"},
            {"id": "customfield_10001", "name": "Acceptance Criteria"},
        ]
        self.issue = {
            "key": "PROJ-123",
            "id": "1000",
            "fields": {
                "summary": "Fix search", "description": "Search returns duplicates",
                "status": {"name": "Open"}, "issuetype": {"name": "Bug"},
                "priority": {"name": "High"}, "labels": ["search"],
                "components": [{"name": "Backend"}],
                "customfield_10001": "No duplicate results",
                "customfield_10002": "This private field must not be requested or printed.",
                "attachment": [{"filename": "large-secret-design.pdf"}],
                "issuelinks": [{
                    "type": {"name": "Blocks", "outward": "blocks"},
                    "outwardIssue": {"key": "OTHER-1", "fields": {
                        "summary": "Related search", "status": {"name": "Open"},
                    }},
                }],
                "subtasks": [{"key": "PROJ-124", "fields": {
                    "summary": "Add search tests", "status": {"name": "In Progress"},
                }}],
            },
        }

    def standard_replies(self, issue=None, comments=None):
        if comments is None:
            comments = {
                "startAt": 0, "total": 1,
                "comments": [{
                    "author": {"displayName": "Reviewer"},
                    "created": "2026-10-20T12:00:00.000+0000",
                    "body": "Keep search results unique.",
                }],
            }
        issue = json.loads(json.dumps(self.issue if issue is None else issue))
        issue["fields"]["comment"] = comments
        return [(200, {}, self.field_defs), (200, {}, issue)]

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

    def test_fetches_only_relevant_fields_and_emits_compact_shape(self):
        self.server.replies = self.standard_replies()
        result = self.run_script(environment={**self.environment, "JIRA_BASE_URL": self.base_url + "/"})
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(
            list(payload),
            ["key", "fields"],
        )
        self.assertEqual(payload["key"], "PROJ-123")
        fields = payload["fields"]
        self.assertEqual(fields["acceptance_criteria"], {"Acceptance Criteria": "No duplicate results"})
        self.assertEqual(fields["comment"]["total"], 1)
        self.assertEqual(fields["comment"]["comments"][0]["body"], "Keep search results unique.")
        self.assertEqual(fields["issuelinks"][0]["outwardIssue"]["key"], "OTHER-1")
        self.assertEqual(fields["subtasks"][0]["key"], "PROJ-124")
        self.assertNotIn("Internal Cost Notes", result.stdout)
        self.assertNotIn("private field", result.stdout)
        self.assertNotIn("large-secret-design.pdf", result.stdout)
        self.assertEqual(len(self.server.requests), 2)
        method, target, authorization = self.server.requests[0]
        self.assertEqual(method, "GET")
        self.assertEqual(urlsplit(target).path, "/jira/rest/api/2/field")
        self.assertEqual(authorization, "Bearer " + TOKEN)
        method, target, authorization = self.server.requests[1]
        self.assertEqual(method, "GET")
        self.assertEqual(urlsplit(target).path, "/jira/rest/api/2/issue/PROJ-123")
        params = parse_qs(urlsplit(target).query)
        self.assertEqual(params["fields"], [",".join((*jira.ISSUE_FIELDS, "customfield_10001"))])
        self.assertNotIn("expand", params)
        self.assertNotIn("customfield_10002", params["fields"][0])
        self.assertEqual(authorization, "Bearer " + TOKEN)
        self.assertNotIn(TOKEN, result.stdout + result.stderr)

    def test_keeps_all_comment_bodies_when_paged(self):
        comment_list = [{
            "author": {"displayName": "R" * 500},
            "created": f"2026-10-{index + 1:02d}",
            "body": f"comment-{index} " + ("x" * 2_000),
        } for index in range(105)]
        replies = self.standard_replies(comments={
            "startAt": 0, "maxResults": 20, "total": 105, "comments": comment_list[:20],
        })
        replies.append((200, {}, {
            "startAt": 0, "total": 105, "comments": comment_list[:100],
        }))
        replies.append((200, {}, {
            "startAt": 100, "total": 105, "comments": comment_list[100:],
        }))
        self.server.replies = replies
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        comments = payload["fields"]["comment"]
        self.assertEqual(comments["total"], 105)
        self.assertEqual(len(comments["comments"]), 105)
        self.assertEqual(comments["comments"][0]["body"], comment_list[0]["body"])
        self.assertEqual(comments["comments"][0]["author"]["displayName"], "R" * 500)
        self.assertEqual(comments["comments"][-1]["body"], comment_list[-1]["body"])
        self.assertEqual(len(self.server.requests), 4)
        for request, offset in zip(self.server.requests[2:], (0, 100)):
            self.assertEqual(request[0], "GET")
            self.assertEqual(
                urlsplit(request[1]).path,
                "/jira/rest/api/2/issue/PROJ-123/comment",
            )
            params = parse_qs(urlsplit(request[1]).query)
            self.assertEqual(params["startAt"], [str(offset)])
            self.assertEqual(params["maxResults"], [str(jira.COMMENT_PAGE_SIZE)])

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
                self.server.replies = [
                    (200, {}, self.field_defs),
                    (status, {}, {"errorMessages": [TOKEN]}),
                ]
                self.assert_failure(self.run_script(), message)

    def test_refuses_redirects_and_does_not_forward_the_token(self):
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                self.server.requests = []
                self.server.replies = [
                    (200, {}, self.field_defs),
                    (status, {"Location": self.base_url + "/other"}, {}),
                ]
                self.assert_failure(self.run_script(), "redirects are disabled")
                self.assertEqual(len(self.server.requests), 2)

    def test_invalid_json_and_unexpected_response_shapes(self):
        for body in (b"<html>Sign in</html>", b"\xff", {}, "unexpected"):
            with self.subTest(body=body):
                self.server.replies = [(200, {}, body)]
                self.assert_failure(self.run_script(), "Jira returned")

    def test_does_not_print_a_token_reflected_in_successful_response(self):
        self.issue["fields"]["description"] = TOKEN
        self.server.replies = self.standard_replies()
        self.assert_failure(self.run_script(), "refusing to print")

    def test_preserves_long_values_in_selected_fields(self):
        description = "é" * 9_000
        acceptance_criteria = "Acceptance criteria " * 500
        self.issue["fields"]["description"] = description
        self.issue["fields"]["customfield_10001"] = acceptance_criteria
        replies = self.standard_replies(comments={
            "startAt": 0, "total": 1,
            "comments": [{"body": "Comment " * 1_000}],
        })
        self.server.replies = replies
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        fields = json.loads(result.stdout)["fields"]
        self.assertEqual(fields["description"], description)
        self.assertEqual(
            fields["acceptance_criteria"]["Acceptance Criteria"],
            acceptance_criteria,
        )
        self.assertEqual(fields["comment"]["comments"][0]["body"], "Comment " * 1_000)

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
