---
name: git-commit-message
description: Write or review clear Git commit messages from a diff or change summary. Use when proposing, improving or validating a commit message; do not use merely because a task happens to modify a Git repository.
---

# Git Commit Message

Write a message that accurately describes one logical change and is useful to
someone reading the history later.

## Establish context

- Check `CONTRIBUTING.md` and recent commit subjects; explicit project
  conventions win over the defaults below.
- Base the message on the staged diff (or working-tree diff if nothing is
  staged and that matches the request).
- Never stage, amend, commit or push unless the user explicitly asks for it.
- Don't claim behavior, motivation or verification not supported by the diff.
- If the diff contains unrelated changes, recommend separate commits instead
  of one broad message.

## Write the subject

- Imperative mood: `Add`, `Fix`, `Refactor` — not `Added`/`Fixes`/`Adding`.
- Completes: "If applied, this commit will _<subject>_."
- Aim for 50 characters, capitalized, no trailing period, specific enough to
  distinguish the change in a log (avoid `Update files`, `WIP`).

## Add a body by default

Include a body unless the change is trivial (typo, one-line config tweak,
version bump). Separate it from the subject with a blank line and explain
what changed, why, and any trade-offs — not implementation details the diff
already shows. Put trailers (`Fixes #123`, etc.) after the body.

Wrap prose at 72 characters using a tool, never by eye — manual wrapping is
the most common source of oversized lines:

```sh
fmt -w 72 <<'EOF'
Prose paragraph as one long unwrapped block; fmt decides line breaks.
EOF
```

Leave bullets, code blocks and trailers out of the piped text and check
those lines individually.

## Respect repository formats

Use Conventional Commits, ticket prefixes or another structured format only
when requested or already established, e.g. `feat(cli): detect stacks before
initialization`. Don't introduce a new taxonomy unprompted.

## Commit safely and verify

When actually running `git commit`, never embed a literal `\n` inside a
plain quoted `-m` string — shells pass it through as `\` + `n`, not a
newline, so the message won't split. Use multiple `-m` flags, an ANSI-C
quoted string (`$'Subject\n\nBody'`), or `-F <file>` with real line breaks.

Before and after committing, verify line lengths with a command instead of
eyeballing:

```sh
git log -1 --format=%B | awk '{ print length, $0 }' | sort -rn | head -1
```

Any prose line over 72 characters (subject over 50) must be re-wrapped with
`fmt -w 72` and re-verified, not manually re-split.

## Present the result

Return one ready-to-copy message in a fenced text block, omitting the body
only when the subject fully explains a trivial change. When reviewing an
existing message, name the problem briefly, then give the improved version.

This guidance is based on Chris Beams' article
[How to Write a Git Commit Message](https://cbea.ms/git-commit/), adapted to
defer to repository-specific conventions.

