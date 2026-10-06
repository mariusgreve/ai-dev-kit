---
name: git-commit
description: Analyze staged, unstaged, and untracked Git changes, split them into logical commits when needed, write repository-appropriate messages, and create the commits. Use when asked to commit changes, make commits, or organize a working tree into commits.
---

# Git Commit

Turn the current working tree into one or more focused, reviewable commits.
Do not stop after proposing messages: create the commits unless the user asks
only for a plan or message review.

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
  Conventional Commits, ticket prefixes, or another taxonomy unless the
  history or project instructions use it.
- Use an imperative, capitalized subject with no trailing period. Aim for 50
  characters and make it specific enough to distinguish in a log.
- Add a body unless the change is trivial. Explain why the change exists and
  important trade-offs rather than narrating the diff.
- Write the complete unformatted commit message to a temporary file. Use a
  blank line between paragraphs and write each bullet as a separate line.
  Do not manually wrap text to satisfy the line-length limit.
- Format and validate the message using exactly:
  `"$SKILL_DIR/scripts/format-commit-message" < "$MESSAGE_FILE" > "$FORMATTED_MESSAGE_FILE"`
  The formatter is the sole authority for commit-message line wrapping.
  Never use `fmt`, `fold`, manual wrapping, or another wrapping command.
- If the formatter exits non-zero, do not create the commit. Fix the message
  content and run the formatter again.
- Create the commit using exactly:
  `git commit -F "$FORMATTED_MESSAGE_FILE"`
  Do not construct the final commit message using `git commit -m`.
- After creating the commit, validate the committed message with:
  `git log -1 --format=%B | awk '{ print length, $0 }' | sort -nr | head`
  The longest line must be 72 characters or fewer. If it is longer, amend the
  commit with a corrected message before continuing.

## Commit and repeat

Create the commit, then inspect `git show --stat --oneline HEAD` and
`git status --short`. Confirm hooks did not introduce unexpected changes. Repeat
the staging, validation, and commit steps for each remaining logical group.

Finish by reporting the commits created in order, their short hashes and
subjects, validation performed, and any changes intentionally left uncommitted.
