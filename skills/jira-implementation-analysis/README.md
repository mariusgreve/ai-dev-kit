# Jira reader setup

The bundled script reads Jira Data Center/Server's Representational State Transfer
(REST) Application Programming Interface (API), version 2. It uses Python 3.10+
and its standard library only; no installation of extra packages is needed.

Configure the environment **before starting the agent session**:

- `JIRA_BASE_URL`: your Jira base address, including any context path, such as
  `https://jira.example.com/jira`. Use `https://` so the token is encrypted in
  transit. Unencrypted `http://` is accepted only for loopback testing.
- `JIRA_TOKEN`: a Personal Access Token (PAT) belonging to an account with read
  access to the ticket. Supply it through your shell or secret manager. Never
  put it in a prompt, committed file, command argument, or shell history.

For example, in Bash, read the token without echoing it or recording its value
in shell history:

```bash
export JIRA_BASE_URL='https://jira.example.com/jira'
read -r -s -p 'Jira personal access token: ' JIRA_TOKEN
printf '\n'
export JIRA_TOKEN
```

Start the agent from this environment, then invoke:

> Use jira-implementation-analysis. Ticket: PROJ-123.

To run the reader directly from this kit checkout:

```bash
python3 skills/jira-implementation-analysis/scripts/fetch_jira_ticket.py PROJ-123
```

For installed skills, locate the same script relative to the loaded skill
directory, not the repository being analyzed.

## Output and safety

The script sends only GET requests with `Authorization: Bearer <token>`. It
preserves custom base paths, validates ticket keys, verifies certificates,
uses a 30-second timeout per request and refuses redirects to avoid forwarding
the token. Use the final Jira base address, not a login or redirect address.

Standard output is a single JavaScript Object Notation (JSON) issue object from
`/rest/api/2/issue/<key>?fields=*all&expand=names`. The `fields` object includes
the summary, description, status, issue type, priority, labels, components,
custom fields, comments, issue links and subtasks that Jira makes available.
The `names` mapping identifies custom fields without hardcoded identifiers.
If comments are paginated, the script reads all pages from the issue's
`/comment` endpoint before printing the result. Linked tickets and subtasks
are included as embedded Jira references, not recursively fetched.

Output may contain sensitive ticket data. Read it directly; do not save it or
include it in unrelated logs. The script writes no files and does not print the
token or server error bodies. Errors go to standard error with a non-zero exit
code, without a partial issue on standard output. Missing configuration,
invalid keys, authentication failures (401), permission failures (403), missing
tickets/endpoints (404), redirects and network errors are reported explicitly.

This reader targets Jira Data Center/Server bearer-token authentication, not
Jira Cloud's email/token authentication. Field visibility depends on account
permissions and Jira configuration; a missing field does not prove the ticket
has no acceptance criteria or comments. It does not download attachments or
fetch linked pages. No real Jira service is used by the local mock tests.
