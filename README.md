# AI Dev Kit

A small, portable foundation for spec-driven, agentic software development.
The kit keeps reusable engineering guidance in one canonical repository and
generates a thin, project-owned AI harness for Claude Code, Codex and GitHub
Copilot.

## Quick start

Requires Git and Python 3.10+; standalone installation also requires curl.
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
The self-contained `cli/installation.py` bootstrap comes from `main`; the installed kit and skills use the
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
- `cli/context_compiler.py`: local context selection and agent-neutral RPI handoffs.
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

Generated verification reports each command it runs and stops on the first
failure. For npm projects it reads `package.json` and runs only explicitly defined,
nonempty `lint`, `typecheck` and `test` scripts. Missing or empty scripts do not
count as checks. If no check runs across the selected stacks, verification exits
with status 2 instead of reporting success. Malformed package metadata fails
with an error. The generated npm check discovery uses Python 3, already required
by aidev; running the checks still requires npm and the project's dependencies.
A successful command is execution evidence, not proof that its script contains
meaningful assertions; maintain project-owned checks accordingly.

Existing `.ai/verify.sh` files remain untouched by `init`. To adopt this behavior
in a previously initialized project, deliberately update its verification script
while preserving any project-specific checks.

`init`, `validate`, `task`, `inspect` and `explain` share configuration shape
validation, including positive context limits and correctly typed rules. Invalid
configuration produces an error naming `.ai/config.json`; `init` checks it before
creating files. Task previews still support projects without configuration, while
`validate` additionally checks that the project harness and skill links exist.
Older configurations without a `context` section use defaults without being rewritten.

## Task context and RPI

Run these commands in the project you want to change, or pass `--project /path/to/project`:

```bash
aidev inspect "Implement password reset"
aidev explain "Implement password reset"
aidev task "Implement password reset"
aidev task --spec specs/features/password-reset.md
```

`inspect` previews selected files and guidance, with bounded content excerpts.
`explain` shows selection reasons without guidance excerpts. Both are read-only;
`--json` returns the same structured context, including reasons, hashes, selection
limits and project inventory. `task` uses the same compiler and writes a unique
`.ai/tasks/<id>/` directory containing:

- `task.md`: task, spec, selected context and Research → Plan → Implement handoff.
- `context.json`: the structured selection and project snapshot.
- `research.md`, `plan.md`, `implementation.md`: pending notes for the agent to fill.

Give `task.md` to your coding agent. To start an agent directly, append
`--agent COMMAND [ARG ...]`; the command must accept its prompt on standard input.
For example, with your own agent wrapper:

```bash
aidev task --spec specs/features/password-reset.md --agent ./scripts/coding-agent
```

All aidev options must precede `--agent`. The executable receives the handoff on
stdin, runs in the project directory without shell interpolation, inherits the
terminal output, and returns its exit status. Without `--agent`, `task` prepares
the workflow for handoff; it does not claim research, implementation or tests
have run. Existing playbooks still govern the work. Feature tasks use
`implement-feature`; explicit review and bug-fix task wording selects
`review-change` and `fix-bug`. Override with `--playbook NAME`.

### Selection and project customization

The compiler scores task/spec terms against file paths and bounded text content,
weighting path matches and uncommon terms. It reads tracked and non-ignored
untracked files with Git; a directory walk supports projects outside Git.
Dependency/build folders, hidden files (except `.github`), private-key extensions,
common lockfiles, binary/non-UTF-8 files, external symlinks and files above
128 KB are excluded. Project `AGENTS.md` instructions governing selected paths
are included even when Git-ignored. Specs are explicit inputs and must be
nonempty UTF-8 files inside the project, at most 128 KB.

Architecture comes from `architecture/` and `docs/architecture/`: overviews are
always selected, other documents match the task. Configured principles form the
engineering baseline. Skills match task names/descriptions or selected file
languages plus stack evidence. Custom stacks and domain relationships can be
expressed through rules; no framework-specific domain map is required.

Project `.ai/skills/`, `.ai/principles/` and `.ai/playbooks/` entries override kit
entries of the same name. Custom entries in those directories are also eligible.
Automatic discovery does not read arbitrary global agent skill directories.
Existing `.ai/config.json` files work without migration. Add an optional
`context` section to tune selection:

```json
{
  "context": {
    "max_files": 20,
    "max_chars": 32000,
    "rules": [
      {
        "terms": ["password reset", "authentication"],
        "files": ["backend/auth/*", "frontend/login/*"],
        "skills": ["spring", "react"],
        "principles": ["security"],
        "architecture": ["architecture/authentication.md"],
        "playbook": "implement-feature"
      }
    ]
  }
}
```

A rule matches when all significant words in any one of its `terms` appear in
the task or spec. File patterns use case-sensitive `fnmatch` matching against
project-relative paths (`*` can span `/`). Rules add selections before ranked
files. Referenced guidance names must exist; unmatched file patterns generate
warnings. Conflicting rule playbooks require `--playbook`. The existing
`playbooks` configuration, when present, restricts allowed selections.

`max_files` bounds selected ordinary files; explicit rules exceeding it fail
rather than silently dropping requested files. `max_chars` bounds combined
guidance/source excerpts; the full explicit spec is separate. Half of this
budget is reserved for selected files, and either files or guidance can reuse
space the other does not need. Selected files share their allocation, so one
large file cannot consume all of it. Within guidance, governing instructions
and the playbook take priority; principles, architecture and skills share the
remaining guidance space.

When a selected file needs truncation, the compiler chooses a contiguous
excerpt around the first term on the line matching the most distinct task/spec
terms. Ties prefer the earlier line. Files chosen only by path or rule, with no
content match, retain a prefix excerpt. Guidance stays in its original order.
Selection remains lexical; the excerpt is not guaranteed to contain a complete
function or every relevant match. Open the original when more context is needed.

Truncated excerpts show source line and column references in `inspect`,
`explain` and task handoffs. JSON retains the full-file hash and `original_chars`,
and adds `excerpt` locations: one-based inclusive lines/columns, plus zero-based
character offsets with an exclusive `end_offset`. An omitted or empty excerpt
has `excerpt: null`. The `budget` summary reports actual characters used by
category. The bound covers excerpt bodies, not metadata, headings or the full
explicit spec. Very small budgets can still omit content; truncation warnings
and original paths remain visible. Inventory is limited to 20,000 candidate
files; use a narrower project root for larger repositories.

`task` saves the observed file hashes, architecture paths and stack evidence in
`.ai/context/project-model.json`. Each command scans current files again, so
changes and deletions cannot silently reuse stale context. The model is an
auditable snapshot, not a semantic dependency graph. Selection is heuristic:
Research must confirm affected call paths and load additional context as needed.
Re-run `inspect` between phases to refresh the view without overwriting notes.
Choose whether to commit task notes; `.ai/tasks/` and `.ai/context/` can be added
to the project's `.gitignore` when they should remain local.

### Spec-driven development

`--spec` includes the full spec as intent and marks the RPI handoff as SDD.
Explicit `REQ-*` identifiers are preserved. Bullet/numbered items without IDs
receive source-line references (`SPEC-L12`) for review; these are candidates,
not an assertion that all bullets are requirements. Prose-only specs remain
intact, and Research must extract their acceptance criteria. Line references
change if the spec is edited; explicit requirement IDs are preferable.

Research confirms requirements against current repository behavior. Plan maps
each requirement to implementation steps and proof. Implement records changed
files and actual verification evidence, using `.ai/config.json`'s `verification`
command (default `./.ai/verify.sh`). Generated requirement statuses stay
`unverified` until the agent supplies evidence; compilation never marks them done.

## CLI structure

The CLI uses the Python standard library and keeps responsibilities separate:

- `cli/aidev.py`: argument parsing and command dispatch.
- `cli/installation.py`: stable releases, global skill links, updates and uninstall.
- `cli/project.py`: project scaffolding, local skill snapshots and validation.
- `cli/detection.py`: stack detection and supporting evidence.
- `cli/tasks.py`: task previews, handoff files and agent execution.
- `cli/context_compiler.py`: context selection and RPI handoff rendering.
- `cli/excerpts.py`: context budget allocation and source excerpt locations.
- `cli/catalog.py`: shared content names and kit location.
- `cli/config.py`: common configuration validation and defaults.
- `cli/paths.py`: shared checks that paths stay inside the project.

`cli` is a regular Python package. Both `./aidev` and `python3 cli/aidev.py`
remain supported. The installer downloads `cli/installation.py` alone before
fetching the stable kit with Git, so that module must remain self-contained
and import only standard-library modules. Project setup reuses its skill-link
helper; installation does not depend on project or task commands.

## Development checks

```bash
python3 -m unittest discover -s tests
```

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

Ask your AI coding agent to use the `bootstrap-from-reference` skill.
Provide the reference repository, destination, new project name and requirements
spec.
The skill derives the stack and conventions from source evidence, separates
reusable setup from domain behavior, and builds a verified project foundation.
It supports applications, services, libraries, CLIs and other project types.

Example prompt:

> Use the bootstrap-from-reference skill. Reference repository: ../example.
> Destination: ../new-project. Project name: new-project.
> Requirements: ./requirements.md.
> Create the base structure and document what remains to implement.

This is a task skill, not a value for `aidev init --stacks`. The installer
registers it globally, including its references; no manual copying is needed.
Invoke `/bootstrap-from-reference` in Claude Code or Copilot CLI, or select the
skill in Codex.

Discovery locations follow the official documentation for
[Codex](https://developers.openai.com/codex/skills/),
[Claude Code](https://code.claude.com/docs/en/skills), and
[Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills).
