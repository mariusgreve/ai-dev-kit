---
name: git-commit
description: Analyze staged, unstaged, and untracked Git changes, split them into logical commits when needed, write repository-appropriate messages, and create the commits. Use when asked to commit changes, make commits, or organize a working tree into commits.
---

# Git Commit

Turn the current working tree into one or more focused, reviewable commits.
Do not stop after proposing messages: create the commits unless the user asks
only for a plan or message review.

An optional Jira ticket can be passed as the skill's first argument, for
example `$git-commit TICKET-123`. When no argument is passed, detect the ticket
from the current branch name (see "Resolve the Jira ticket"). Pass the resolved
ticket to the formatter for every commit.

## Resolve the Jira ticket

1. If a ticket argument was passed, use it. It takes precedence over the branch.
2. Otherwise, get the current branch with `git branch --show-current`. If it is
   empty (detached HEAD) or contains no ticket, proceed without a ticket.
3. Search the branch name for an uppercase Jira key matching
   `[A-Z][A-Z0-9]+-[0-9]+` on a word boundary, for example `feature/PROJ-123-login`,
   `PROJ-123-login`, or `bugfix/PROJ-42`. Use the first match.
4. If the branch contains several different keys, ask the user which one to
   use instead of guessing.
5. Lowercase names such as `feature-123` are not Jira keys and are ignored.

## Inspect the repository

- Read repository instructions such as `AGENTS.md` and `CONTRIBUTING.md`.
- Inspect recent commit subjects to learn the established message format.
- Inspect all change states with `git status --short`, `git diff --cached`,
  `git diff`, and the contents of relevant untracked files.
- Treat staged and unstaged changes as one set for planning. Staging is useful
  context, not proof that everything staged belongs in one commit.
- Do not modify source files, discard changes, amend, rebase, or push unless
  the user explicitly requests it. Never include secrets or likely generated
  artifacts without confirming they belong in version control.

## Plan logical commits

Group changes by one coherent purpose a reviewer can understand independently.
Keep implementation with its directly related tests and documentation. Separate
unrelated features, fixes, refactors, formatting, dependency updates, and
generated files. A file may contain hunks that belong to different commits.

Prefer the smallest number of commits that remain logically focused. Preserve
dependency order: foundational refactors or schema changes must precede changes
that rely on them. If changes cannot be separated safely, keep them together
and explain the coupling. Ask before proceeding only when intent is genuinely
ambiguous or a safe grouping would require changing the user's code.

## Stage exactly one group

- Before changing the index, note what is already staged so no change is lost.
- Stage whole paths only when every change in those paths belongs to the current
  group. Use patch staging for mixed files.
- If the index mixes groups, unstage only what is necessary with
  `git restore --staged` and then restage the intended paths or hunks. This must
  leave working-tree content unchanged.
- Review `git diff --cached` before every commit. Confirm it contains the whole
  logical change and nothing from another group.
- Never use `git add .`, `git add -A`, or an equivalent blanket command when
  unrelated changes are present.

## Validate the group

Run the narrowest relevant tests, checks, or build available for the staged
change when practical. Record what ran. Do not claim validation unsupported by
command output, and do not bypass failing commit hooks with `--no-verify`.

## Write the message

- Follow the repository's established convention. Do not introduce
  Conventional Commits or another taxonomy unless the history or project
  instructions use it.
- Use an imperative, capitalized subject with no trailing period. Aim for 50
  characters before any ticket prefix and make it specific enough to
  distinguish in a log.
- Add a body unless the change is trivial. Explain why the change exists and
  important trade-offs rather than narrating the diff.
- Keep plans in conversation context, not temporary files. Store the complete
  unformatted message in `MESSAGE`, quoted literally to prevent shell expansion.
  Use blank lines between paragraphs and a separate line for each bullet.
- Set `MESSAGE`, format, and commit in the same shell invocation:

  ```bash
  FORMATTED_MESSAGE=$(printf '%s\n' "$MESSAGE" |
    "$SKILL_DIR/scripts/format-commit-message") &&
    printf '%s\n' "$FORMATTED_MESSAGE" | git commit -F -
  ```

  This keeps both messages in memory; Git reads from standard input.
  Let the formatter add the ticket prefix, wrap body text, and enforce the
  72-character line limit; do not wrap manually.
- When a Jira ticket was resolved, append `--ticket "$JIRA_TICKET"` to the
  formatter command inside the command substitution above.
- Keep the `&&` guard so formatter failure prevents committing. Fix the message
  and retry on failure. Do not use temporary message files or `git commit -m`.

## Commit and repeat

Create the commit, then inspect `git show --stat --oneline HEAD` and
`git status --short`. Confirm hooks did not introduce unexpected changes. Repeat
the staging, validation, and commit steps for each remaining logical group.

Finish by reporting the commits created in order, their short hashes and
subjects, validation performed, and any changes intentionally left uncommitted.
