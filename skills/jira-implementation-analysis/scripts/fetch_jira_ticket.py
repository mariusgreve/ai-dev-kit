#!/usr/bin/env python3
"""Read a Jira Data Center/Server ticket without modifying Jira or local files."""

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


def read_json(opener, base_url, token, path, **query):
    request = Request(
        base_url + path + "?" + urlencode(query),
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
    if not isinstance(result, dict):
        raise JiraReadError("Jira returned an unexpected response; expected a JSON object.")
    return result


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
            opener, base_url, token, issue_path + "/comment",
            startAt=len(comments), maxResults=100,
        )
        batch = page.get("comments")
        if (
            page.get("total") != total
            or page.get("startAt") != len(comments)
            or not isinstance(batch, list)
            or not batch
            or len(comments) + len(batch) > total
        ):
            raise JiraReadError(
                "Jira comment pagination is incomplete or changed during retrieval. Retry the read."
            )
        comments.extend(batch)
    fields["comment"] = {
        **comment, "startAt": 0, "maxResults": len(comments),
        "total": total, "comments": comments,
    }


def fetch_ticket(key, base_url, token):
    opener = build_opener(NoRedirects())
    issue_path = "/rest/api/2/issue/" + key
    issue = read_json(opener, base_url, token, issue_path, fields="*all", expand="names")
    if issue.get("key") != key or not isinstance(issue.get("fields"), dict):
        raise JiraReadError("Jira returned an unexpected ticket key or missing fields.")
    complete_comments(opener, base_url, token, issue_path, issue["fields"])
    return issue


def main():
    parser = argparse.ArgumentParser(
        description="Fetch a Jira Data Center/Server ticket as JSON using JIRA_BASE_URL and JIRA_TOKEN."
    )
    parser.add_argument("key", help="Jira ticket key, for example PROJ-123")
    args = parser.parse_args()
    try:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*-[1-9][0-9]*", args.key):
            raise JiraReadError("Invalid ticket key. Expected an uppercase key such as PROJ-123.")
        base_url, token = configuration()
        issue = fetch_ticket(args.key, base_url, token)
        output = json.dumps(issue, indent=2, ensure_ascii=False)
        if token in output:
            raise JiraReadError("Jira response contains the configured token; refusing to print it.")
    except JiraReadError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
