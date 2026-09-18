# AI Dev Kit

A small, portable foundation for spec-driven, agentic software development.
The kit keeps reusable engineering guidance in one canonical repository and
generates a thin, project-owned AI harness for Claude Code, Codex and GitHub
Copilot.

## Quick start

```bash
git clone <your-repository-url> ai-dev-kit
cd ai-dev-kit
./install.sh

cd /path/to/project
aidev init
aidev validate
```

With no `--stacks` argument, `aidev init` inspects common build, dependency and
container files, explains the detected stacks, and asks for confirmation. Use
`--yes` for non-interactive acceptance, or override detection explicitly:

```bash
aidev init --yes
aidev init . --stacks java spring postgres react typescript
```

The installer keeps the canonical checkout in `~/.local/share/ai-dev-kit`,
links `aidev` into `~/.local/bin`, and adds that directory to the shell PATH
when needed. It refuses to overwrite unrelated installations.

```bash
aidev update
aidev uninstall
```

Override locations with `AIDEV_HOME` and `AIDEV_BIN_DIR`.

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
remain untouched.

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

This is a task skill, not a value for `aidev init --stacks`. The existing CLI
continues to install its supported stack skills. To make this skill available
inside a project, copy its entire directory (including references) to
`.ai/skills/bootstrap-from-reference/` and reference it in project instructions.
