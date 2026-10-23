# AI Dev Kit

Reusable coding skills, short project instructions and one command for project
checks. The kit gives projects a consistent starting point and lets you adapt
instructions and checks to the way you work.

## Quick start

Requires Git, Python 3.10+ and Bash. Standalone installation also requires curl.

```bash
curl -fsSL https://raw.githubusercontent.com/mariusgreve/ai-dev-kit/main/install.sh | bash

cd /path/to/project
aidev init --yes
./.ai/verify.sh
```

Review the generated `AGENTS.md` and `.ai/verify.sh` once. Then give your coding
agent the task directly, for example:

> Fix the exercise search. Follow the project conventions, add a regression
> test where useful, and run the project checks.

Give routine fixes directly to the agent, and use a short spec for larger or
ambiguous changes. The agent can search the repository as needed.

To inspect the installer first, download `install.sh` and read it before running
it. From a development checkout, `./install.sh` also works. Installation fetches
published content from origin, not local uncommitted changes.

## Assess before initializing an existing project

Run `aidev init --assess` to inspect an existing repository without changing it.
The report identifies existing AI instructions, common project documentation,
CI configuration and detected stacks. It highlights when generated instructions
or verification would duplicate project-owned setup. This is a lightweight
inventory, not an AI architecture analysis or a guarantee that checks work.

## What init creates

- `AGENTS.md`: a short, editable set of working instructions.
- `.ai/verify.sh`: project-owned checks, independent of the installed kit.
- `.ai/config.json`: the stack skills installed in this project.
- `.ai/skills/`: portable copies of relevant skills, linked from `.agents/skills/`
  and `.claude/skills/` for discovery.
- `CLAUDE.md` and `.github/copilot-instructions.md`: thin pointers to the same
  project instructions. Codex uses `AGENTS.md` directly.

Commit this setup, including the relative skill links. It works for other
contributors without your machine's installation path.

Init detects Java, Spring, PostgreSQL, React and TypeScript from project files.
Without `--yes`, it asks before accepting detected stacks. To choose explicitly:

```bash
aidev init --stacks java spring postgres react typescript
```

Other stacks can still use the base instructions; supply their real checks in
`.ai/verify.sh`. The kit does not invent language guidance for unsupported stacks.

Existing instructions, verification scripts and skill contents are preserved.
Re-running init adds missing files and skills and merges selected stacks into the
configuration. It does not replace existing skills with newer kit versions.
When `AGENTS.md` already exists, add the verification command to it if appropriate.

Optional [feature spec](templates/feature-spec.md),
[architecture overview](templates/architecture-overview.md) and
[decision](templates/adr.md) templates are available when the project needs them.
Use your project's existing documentation locations.

## Verification

Run `./.ai/verify.sh` from any directory. The generated script checks the project
root and up to three directory levels below it, skipping hidden, dependency and
build directories. It supports common `backend/` and `frontend/` layouts:

- Gradle wrapper: `check`; Maven wrapper: `verify`.
- Node projects: defined, nonempty `lint`, `typecheck`, `test:ci` (or `test`) and
  `build` scripts, in that order.
- npm, pnpm, Yarn or Bun, selected from `packageManager` or lockfiles, with npm
  as the fallback. The selected tool and project dependencies must be installed.
- Java multi-module builds and declared Node workspaces use their root checks;
  the root scripts must cover the child modules.

Checks run in their own module directories, print the command and stop on the
first failure. `CI=true` is set; define `test:ci` if your normal test script watches
for changes. No dependency installation or network setup is performed by the
runner itself.

A discovered Java or Node project without supported checks makes verification
incomplete, even if another module passes. No checks also means failure. A
successful build alone does not prove that tests exist or cover the task.

**The generated script is a starting point.** Edit it to use the commands your
project and CI actually need, especially for other languages, deeper layouts,
external services or unusual build systems. New modules within supported layouts
are discovered on each run. Maintain the project-owned script as your build
and verification needs change.

`aidev validate` checks setup files, executable verification and skill links. It
does not run builds or tests and does not certify the project's quality.

## Skills

Installation makes all kit skills available globally. Project init copies only
selected stack skills so project conventions remain stable across kit updates.

- Stack guidance: Java, Spring, PostgreSQL, React and TypeScript.
- `git-commit`: analyze staged, unstaged and untracked changes, split unrelated
  work, and create one or more focused commits.
- `bootstrap-from-reference`: create a runnable foundation from an existing
  repository and requirements while preserving its stack and integration contracts.
- `jira-implementation-analysis`: turn a Jira ticket into a read-only, evidence-based,
  file-by-file implementation proposal.

Example:

> Use bootstrap-from-reference. Reference: ../example. Destination: ../new-app.
> Requirements: ./requirements.md. Create the base structure and document what
> remains to implement.

> Use jira-implementation-analysis. Ticket: PROJ-123.

The Jira skill includes a Python 3.10+ reader for self-hosted Jira Data
Center/Server. Set `JIRA_BASE_URL` and `JIRA_TOKEN` in the agent's environment;
see [Jira reader setup and usage](skills/jira-implementation-analysis/README.md).
It only reads relevant ticket fields and prints a compact JSON summary without
truncating the contents of those fields; it never changes Jira or repository files.

Project instructions and explicit requirements take precedence over generic
skill defaults. Load skills when relevant to the task.

## Commands and updates

```bash
aidev init [project] [--yes] [--assess] [--stacks java react ...]
aidev validate [project]
aidev list
aidev update
aidev uninstall
```

Installation uses a stable checkout in `~/.local/share/ai-dev-kit`, exposes
`aidev` in `~/.local/bin` and links global skills under `~/.agents/skills/` and
`~/.claude/skills/`. `CLAUDE_CONFIG_DIR` is respected. Restart agent sessions after
installation or updates.

Install and update select the highest stable semantic version tag from origin,
falling back to `origin/main` only when no stable tag exists. The exact commit is
recorded in `.aidev-release.json`. Local-only tags, branches and uncommitted changes
are not installed. Fetch failures and modified installed checkouts leave the
active installation intact; unrelated skills are never overwritten.

`aidev install-skills` installs the stable kit's global skills. Uninstall removes
registered links still owned by the kit; it preserves project files and unrelated
skills. Location overrides: `AIDEV_HOME`,
`AIDEV_BIN_DIR`, `XDG_DATA_HOME` and `CLAUDE_CONFIG_DIR`. Use the same overrides for
future commands. Fork installers can set `AIDEV_REPOSITORY_URL` and
`AIDEV_BOOTSTRAP_URL`; with a pipeline, pass them to Bash rather than curl.

## Development

The CLI uses the Python standard library. Installation, project setup, stack
detection and verification each have a small module under `cli/`. The installer
bootstrap (`cli/installation.py`) remains self-contained.

```bash
python3 -m unittest discover -s tests
```

Keep new features tied to recurring practical needs. Prefer improving the
existing instructions or checks over adding another workflow or configuration
layer. Changes should preserve project-owned work and prove behavior with
focused tests.
