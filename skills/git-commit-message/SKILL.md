---
name: git-commit-message
description: Write or review clear Git commit messages from a diff or change summary. Use when proposing, improving or validating a commit message; do not use merely because a task happens to modify a Git repository.
---

# Git Commit Message

Write a message that accurately describes one logical change and is useful to
someone reading the history later.

## Establish context

- Inspect repository guidance such as `CONTRIBUTING.md` and recent commit
  subjects before choosing a format. Explicit project conventions win.
- When repository access is available, base the message on the staged diff and
  relevant status. If nothing is staged, state that and use the working-tree
  diff only when it matches the user's request.
- Never stage files, amend history, create a commit or push unless the user
  explicitly asks for that action.
- Do not claim behavior, motivation or verification that is not supported by
  the changes or supplied context. Ask only when missing intent would materially
  change the message.

## Write the subject

- Use the imperative mood: `Add`, `Fix`, `Remove`, `Refactor`, not `Added`,
  `Fixes` or `Adding`.
- Check that it completes: "If applied, this commit will _<subject>_."
- Make it specific enough to distinguish the change in a log.
- Aim for 50 characters. Prefer clarity over awkward abbreviation when a few
  extra characters are necessary.
- Start with a capital letter and omit the final period unless the repository's
  established format requires otherwise.
- Avoid vague subjects such as `Update files`, `Various fixes` and `WIP`.

## Add a body by default

Default to including a body unless the change is truly trivial (a typo fix, a
one-line config tweak, a dependency bump with no behavior change). Separate the
body from the subject with a blank line and physically wrap each prose line at
72 characters or fewer. A terminal or editor may visually wrap long lines
without adding newline characters; that does not satisfy this requirement.
When presenting a message, use a formatter or manually insert newlines, then
verify the stored lines are no longer than 72 characters. Explain:

- what changed at a useful level;
- why the change was needed, including the bug or motivating scenario;
- relevant constraints, trade-offs or behavior changes.

Do not narrate implementation details that the diff already makes obvious.
Place issue references, breaking-change notices or other trailers after the
body when appropriate.

If the diff contains unrelated changes, recommend separate commits and propose
a message for each instead of hiding them under a broad subject.

## Respect repository formats

Use Conventional Commits, ticket prefixes, lowercase subjects or another
structured format only when requested or already established by the project.
Keep the description imperative within that format, for example:

```text
feat(cli): detect stacks before initialization
```

Do not introduce a new commit taxonomy as part of an unrelated request.

## Present the result

Return one ready-to-copy message in a fenced text block. Only omit the body
when the change is trivial enough that the subject fully explains it. Add a
short note only when there is an important uncertainty, convention conflict or
recommended commit split.

When reviewing an existing message, identify the material problem briefly and
then provide the improved ready-to-copy version.

This guidance is based on Chris Beams' article
[How to Write a Git Commit Message](https://cbea.ms/git-commit/), adapted to
defer to repository-specific conventions.
