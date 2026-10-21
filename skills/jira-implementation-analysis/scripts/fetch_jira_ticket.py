#!/usr/bin/env python3
"""Fetch a compact, read-only Jira Data Center/Server ticket summary."""

import argparse
from http.client import HTTPException
import json
import os
import re
import ssl
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


COMMENT_PAGE_SIZE = 100
ISSUE_FIELDS = (
    "summary", "description", "status", "issuetype", "priority",
    "labels", "components", "issuelinks", "subtasks", "comment",
)
AC_FIELD_PATTERN = re.compile(r"\bacceptance criteri(?:a|on)\b", re.IGNORECASE)


class JiraReadError(Exception):
    pass


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the bearer token to a redirected endpoint.
        return None


def configuration():
    base_url = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
    token = os.environ.get("JIRA_TOKEN", "")
    if not base_url or not token:
        raise JiraReadError("Set JIRA_BASE_URL and JIRA_TOKEN before fetching a ticket.")
    try:
        address = urlsplit(base_url)
        port = address.port
    except ValueError:
        raise JiraReadError("JIRA_BASE_URL must be a valid Jira base address.") from None
    if (
        not address.hostname
        or address.username is not None
        or address.password is not None
        or "?" in base_url
        or "#" in base_url
        or re.search(r"[\s\\]", base_url)
        or port == 0
    ):
        raise JiraReadError(
            "JIRA_BASE_URL must be a Jira base address without credentials, query or fragment."
        )
    if address.scheme != "https" and not (
        address.scheme == "http" and address.hostname in {"127.0.0.1", "::1", "localhost"}
    ):
        raise JiraReadError(
            "JIRA_BASE_URL must use https:// (http:// is allowed only for loopback testing)."
        )
    if not re.fullmatch(r"[!-~]+", token):
        raise JiraReadError("JIRA_TOKEN must contain only visible ASCII characters without spaces.")
    return base_url, token


def read_json(opener, base_url, token, path, expected_type, **query):
    url = base_url + path
    if query:
        url += "?" + urlencode(query)
    request = Request(
        url,
        headers={"Accept": "application/json", "Authorization": "Bearer " + token},
        method="GET",
    )
    try:
        with opener.open(request, timeout=30) as response:
            data = response.read()
    except HTTPError as exc:
        messages = {
            401: "Jira rejected authentication (401). Check JIRA_TOKEN.",
            403: "Jira denied access (403). Check the token's permissions.",
            404: "Jira ticket or endpoint not found (404). Check the key, base address and access.",
        }
        if 300 <= exc.code < 400:
            message = "Jira redirected the request; redirects are disabled. Check JIRA_BASE_URL."
        else:
            message = messages.get(exc.code, f"Jira request failed with HTTP status {exc.code}.")
        exc.close()
        raise JiraReadError(message) from None
    except (URLError, OSError, HTTPException) as exc:
        reason = exc.reason if isinstance(exc, URLError) else exc
        if isinstance(reason, TimeoutError):
            message = "Jira request timed out."
        elif isinstance(reason, ssl.SSLError):
            message = "Jira certificate verification or secure connection failed. Check the trusted certificates."
        else:
            message = "Could not connect to Jira. Check the base address and network access."
        raise JiraReadError(message) from None
    try:
        result = json.loads(data)
    except (ValueError, UnicodeError):
        raise JiraReadError("Jira returned invalid JSON instead of a ticket response.") from None
    if not isinstance(result, expected_type):
        expected = "array" if expected_type is list else "object"
        raise JiraReadError(f"Jira returned an unexpected response; expected a JSON {expected}.")
    return result


def discover_acceptance_fields(opener, base_url, token):
    fields = read_json(opener, base_url, token, "/rest/api/2/field", list)
    matches = []
    for item in fields:
        if not isinstance(item, dict):
            continue
        field_id, name = item.get("id"), item.get("name")
        if (
            isinstance(field_id, str)
            and re.fullmatch(r"customfield_[0-9]+", field_id)
            and isinstance(name, str)
            and AC_FIELD_PATTERN.search(name)
        ):
            matches.append((field_id, name))
    matches.sort(key=lambda pair: pair[0])
    return matches


def complete_comments(opener, base_url, token, issue_path, fields):
    comment = fields.get("comment")
    if comment is None:
        return
    if not isinstance(comment, dict):
        raise JiraReadError("Jira returned an invalid comments field.")
    total = comment.get("total")
    comments = comment.get("comments")
    start = comment.get("startAt", 0)
    if (
        type(total) is not int or total < 0
        or type(start) is not int or start < 0
        or not isinstance(comments, list)
        or start + len(comments) > total
    ):
        raise JiraReadError("Jira returned invalid comment pagination.")
    if start == 0 and len(comments) == total:
        return

    comments = []
    while len(comments) < total:
        page = read_json(
            opener, base_url, token, issue_path + "/comment", dict,
            startAt=len(comments), maxResults=COMMENT_PAGE_SIZE,
        )
        if (
            page.get("total") != total
            or page.get("startAt") != len(comments)
            or not isinstance(page.get("comments"), list)
            or not page["comments"]
            or len(comments) + len(page["comments"]) > total
            or any(not isinstance(item, dict) for item in page["comments"])
        ):
            raise JiraReadError(
                "Jira comment pagination is incomplete or changed during retrieval. Retry the read."
            )
        comments.extend(page["comments"])
    fields["comment"] = {
        **comment, "startAt": 0, "maxResults": len(comments),
        "total": total, "comments": comments,
    }


def fetch_ticket(key, base_url, token):
    opener = build_opener(NoRedirects())
    acceptance_fields = discover_acceptance_fields(opener, base_url, token)
    requested_fields = list(ISSUE_FIELDS)
    requested_fields.extend(field_id for field_id, _ in acceptance_fields)
    issue_path = "/rest/api/2/issue/" + key
    issue = read_json(
        opener, base_url, token, issue_path, dict,
        fields=",".join(requested_fields),
    )
    if issue.get("key") != key or not isinstance(issue.get("fields"), dict):
        raise JiraReadError("Jira returned an unexpected ticket key or missing fields.")
    complete_comments(opener, base_url, token, issue_path, issue["fields"])
    selected_fields = {
        name: value
        for name, value in issue["fields"].items()
        if name in requested_fields
    }
    if acceptance_fields:
        selected_fields["acceptance_criteria"] = {
            name: selected_fields.pop(field_id)
            for field_id, name in acceptance_fields
            if field_id in selected_fields
        }
    return json.dumps(
        {"key": key, "fields": selected_fields},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Fetch a compact Jira Data Center/Server ticket summary as JSON."
    )
    parser.add_argument("key", help="Jira ticket key, for example PROJ-123")
    args = parser.parse_args()
    try:
        if (
            len(args.key) > 100
            or not re.fullmatch(r"[A-Z][A-Z0-9_]*-[1-9][0-9]*", args.key)
        ):
            raise JiraReadError("Invalid ticket key. Expected an uppercase key such as PROJ-123.")
        base_url, token = configuration()
        output = fetch_ticket(args.key, base_url, token)
        if token in output:
            raise JiraReadError("Jira response contains the configured token; refusing to print it.")
    except JiraReadError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
