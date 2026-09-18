# AI Dev Kit

A small, portable foundation for spec-driven, agentic software development.
The kit keeps reusable engineering guidance in one canonical repository and
generates a thin, project-owned AI harness for Claude Code, Codex and GitHub
Copilot.

## Quick start

Requires Git and Python 3; standalone installation also requires curl.
No initial repository clone is needed:

```bash
curl -fsSL https://raw.githubusercontent.com/mariusgreve/ai-dev-kit/main/install.sh | bash
```

Then initialize and validate your project:

```bash
cd /path/to/project
aidev init
aidev validate
```

To inspect the installer before running it:

```bash
curl -fsSL https://raw.githubusercontent.com/mariusgreve/ai-dev-kit/main/install.sh -o /tmp/ai-dev-kit-install.sh
less /tmp/ai-dev-kit-install.sh
bash /tmp/ai-dev-kit-install.sh
```

From an existing development checkout, `./install.sh` works too. Both methods
fetch published content from origin, never local uncommitted changes.
The bootstrap installer comes from `main`; the installed kit and skills use the
release selection policy below.

With no `--stacks` argument, `aidev init` inspects common build, dependency and
container files, explains the detected stacks, and asks for confirmation. Use
`--yes` for non-interactive acceptance, or override detection explicitly:

```bash
aidev init --yes
aidev init . --stacks java spring postgres react typescript
```

The installer keeps a separate, stable checkout in `~/.local/share/ai-dev-kit`,
links `aidev` into `~/.local/bin`, and adds that directory to the shell PATH
when needed. It refuses to overwrite unrelated installations or skills.

All skills (including `bootstrap-from-reference`) become available across
projects automatically. Each skill directory is linked from `~/.agents/skills/`
(shared by Codex CLI and Copilot CLI) and `~/.claude/skills/` (Claude Code) to
one canonical directory in the stable installed kit, never the development checkout. Supporting files stay together;
there are no per-tool copies or extra `.codex`/`.copilot` skill registrations.
`CLAUDE_CONFIG_DIR` is respected when set. Restart existing agent sessions after
installation. Other tools that discover `~/.agents/skills/` can use the same links.

Installation and `aidev update` use the same policy:

1. Fetch tags from origin and select the highest stable semantic version tag
   (`v1.10.0` or `1.10.0`, sorted numerically). Prerelease and unrelated tags are ignored.
2. If no stable version tag exists, use the latest committed `origin/main`.
   Local branches, local-only tags and uncommitted files are never installed.
3. Prepare a clean, detached checkout before replacing the installed version.
   Fetch failures and modified installed checkouts leave the active installation intact.

The selected ref and exact commit are recorded in `.aidev-release.json` inside
the installation. There is one installed copy shared by all tools; temporary
update checkouts and the previous installed copy are removed after success.
`aidev update` also refreshes registrations, adds new skills and removes obsolete
kit-owned links. `aidev uninstall` removes only registered links still pointing
to this kit, preserving unrelated skills. `aidev install-skills` uses the same stable installation policy and can migrate
kit-owned links left by older installations pointing at a development checkout.

```bash
aidev update
aidev uninstall
```

Override locations with `AIDEV_HOME` and `AIDEV_BIN_DIR` (or `XDG_DATA_HOME`
for the default data directory). Keep the same overrides for future commands.
For a fork, set `AIDEV_REPOSITORY_URL` and `AIDEV_BOOTSTRAP_URL` on the installer.
With a pipeline, pass these variables to `bash`, not to `curl`.

`init` never overwrites existing files. Re-run it after adding stacks to create
new missing files, then review the generated configuration and verification
commands.

## Design

- `skills/`: reusable, task-oriented capabilities loaded only when relevant.
- `playbooks/`: end-to-end workflows that can compose several skills.
- `principles/`: general engineering defaults, overridden by project decisions.
- `templates/`: project-owned specs, acceptance criteria and ADRs.
- `adapters/`: mappings from the neutral core to tool-specific instruction files.
- project `architecture/` and `specs/`: facts and intent that stay in the project.

Precedence is: feature spec → project architecture/rules → stack skill → global
principle. More specific, explicit guidance wins.

## Commands

```bash
./aidev init . --stacks java spring postgres react typescript
./aidev validate .
./aidev list
```

The generated `.ai/config.json` records the selected stacks, playbooks and principles. The
generated `.ai/verify.sh` is deliberately project-local: edit it to reflect the
real build. Agent instructions call this single verification entrypoint.

## Versioning

Tag stable releases of this repository. Projects retain their own generated
files, so updating the kit cannot silently change a project's instructions.
Re-run `init` to add newly available missing files; deliberate project overrides
remain untouched. Each selected stack has one portable snapshot under
`.ai/skills/`, with relative directory links under `.agents/skills/` and
`.claude/skills/` for automatic discovery. Commit these links along with the
snapshot; no machine-specific installation path is stored in the project.
Re-running `init` upgrades older projects by linking their existing skills,
including local edits. A conflicting discovery entry is reported, never replaced.
Global skills follow kit updates; project snapshots remain project-owned.

## Bootstrap from an example repository

Use `skills/bootstrap-from-reference/SKILL.md` with an AI coding agent. Provide
the reference repository, destination, new project name and requirements spec.
The skill derives the stack and conventions from source evidence, separates
reusable setup from domain behavior, and builds a verified project foundation.
It supports applications, services, libraries, CLIs and other project types.

Example prompt:

> Use skills/bootstrap-from-reference/SKILL.md. Reference: ../example.
> Destination: ../new-project. Requirements: ./requirements.md.
> Create the base structure and document what remains to implement.

This is a task skill, not a value for `aidev init --stacks`. The installer
registers it globally, including its references; no manual copying is needed.
Invoke `/bootstrap-from-reference` in Claude Code or Copilot CLI, or select the
skill in Codex.

Discovery locations follow the official documentation for
[Codex](https://developers.openai.com/codex/skills/),
[Claude Code](https://code.claude.com/docs/en/skills), and
[Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills).
