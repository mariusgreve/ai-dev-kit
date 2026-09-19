"""Initialize and validate the project-owned AI harness."""

from __future__ import annotations

import argparse
import json
import shutil
import stat
import sys
from pathlib import Path

from .catalog import ROOT, SUPPORTED_STACKS, DEFAULT_PLAYBOOKS, DEFAULT_PRINCIPLES, DEFAULT_TEMPLATES
from .detection import detect_stacks
from .installation import ensure_skill_link


def write_new(path: Path, content: str, executable: bool = False) -> str:
    if path.exists():
        return f"kept    {path}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return f"created {path}"


def install_project_skill(project: Path, name: str) -> list[str]:
    # One portable project snapshot, including supporting resources. All tool
    # discovery entries reference it, and existing project overrides survive.
    target = project / ".ai/skills" / name
    outputs = []
    if not target.exists() and not target.is_symlink():
        shutil.copytree(ROOT / "skills" / name, target)
        outputs.append(f"created {target}")
    for directory in (".agents/skills", ".claude/skills"):
        outputs.append(ensure_skill_link(project / directory / name, target))
    return outputs


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def choose_detected_stacks(project: Path, assume_yes: bool) -> set[str] | None:
    detected = detect_stacks(project)
    if not detected:
        print("No supported stacks were detected.", file=sys.stderr)
        print("Specify them explicitly with `--stacks`, or run `aidev list`.", file=sys.stderr)
        return None
    print("Detected stacks:")
    for name in SUPPORTED_STACKS:
        if name in detected:
            print(f"  - {name}: {', '.join(detected[name])}")
    if assume_yes:
        return set(detected)
    if not sys.stdin.isatty():
        print("Re-run with `--yes` to accept, or specify `--stacks` explicitly.", file=sys.stderr)
        return None
    answer = input("Initialize with these stacks? [Y/n] ").strip().lower()
    if answer in {"", "y", "yes"}:
        return set(detected)
    print("Cancelled. Re-run with `--stacks <names>` to choose manually.")
    return None


def project_agents() -> str:
    return """# Agent instructions

Treat repository documentation and executable checks as the source of truth.

Before changing code:
- read the relevant spec and acceptance criteria
- inspect affected architecture and existing conventions
- load only the skills needed for the task
- use the matching playbook under `.ai/playbooks/`
- use `aidev inspect "<task>"` or `aidev task --spec <path>` for an RPI context handoff
- treat selected context as a starting point; confirm affected paths during Research

Prefer the smallest coherent change. Delegate only when context isolation,
parallel work, or genuine specialization provides a clear benefit.

Do not declare completion until `./.ai/verify.sh` passes and every acceptance
criterion has been checked. Deterministic checks precede AI review.
"""


def verify_script(stacks: set[str]) -> str:
    blocks = ["#!/usr/bin/env bash", "set -euo pipefail", "", "repo_root=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")/..\" && pwd)\"", "cd \"$repo_root\"", "", "ran=0"]
    if "java" in stacks or "spring" in stacks:
        blocks += [
            "if [[ -x ./gradlew ]]; then ./gradlew check; ran=1",
            "elif [[ -x ./mvnw ]]; then ./mvnw verify; ran=1",
            "fi",
        ]
    if {"react", "typescript"} & stacks:
        blocks += [
            "if [[ -f package.json ]]; then",
            "  npm run --if-present lint",
            "  npm run --if-present typecheck",
            "  npm run --if-present test",
            "  ran=1",
            "fi",
        ]
    blocks += ["", "if [[ $ran -eq 0 ]]; then", "  echo 'No build detected. Edit .ai/verify.sh for this project.' >&2", "  exit 2", "fi", ""]
    return "\n".join(blocks)


def init(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    project.mkdir(parents=True, exist_ok=True)
    if args.stacks is None:
        chosen = choose_detected_stacks(project, args.yes)
        if chosen is None:
            return 1
        stacks = chosen
    else:
        stacks = set(args.stacks)
    config = {
        "kit_version": "0.1.0",
        "stacks": sorted(stacks),
        "playbooks": list(DEFAULT_PLAYBOOKS),
        "principles": list(DEFAULT_PRINCIPLES),
        "verification": "./.ai/verify.sh",
        "context": {"max_files": 20, "max_chars": 32000, "rules": []},
    }
    outputs = [
        write_new(project / "AGENTS.md", project_agents()),
        write_new(project / ".ai/config.json", json.dumps(config, indent=2) + "\n"),
        write_new(project / ".ai/verify.sh", verify_script(stacks), executable=True),
        write_new(project / "architecture/overview.md", read("templates/architecture-overview.md")),
        write_new(project / "architecture/decisions/.gitkeep", ""),
        write_new(project / "specs/features/.gitkeep", ""),
    ]
    for name in DEFAULT_PLAYBOOKS:
        outputs.append(write_new(project / f".ai/playbooks/{name}.md", read(f"playbooks/{name}.md")))
    for name in DEFAULT_PRINCIPLES:
        outputs.append(write_new(project / f".ai/principles/{name}.md", read(f"principles/{name}.md")))
    for name in DEFAULT_TEMPLATES:
        outputs.append(write_new(project / f".ai/templates/{name}.md", read(f"templates/{name}.md")))
    for stack in sorted(stacks):
        outputs.extend(install_project_skill(project, stack))
    outputs += [
        write_new(project / "CLAUDE.md", read("adapters/claude/CLAUDE.md")),
        write_new(project / ".github/copilot-instructions.md", read("adapters/copilot/copilot-instructions.md")),
    ]
    print("\n".join(outputs))
    return validate_project(project)


def validate_project(project: Path) -> int:
    required = ["AGENTS.md", ".ai/config.json", ".ai/verify.sh", "architecture/overview.md"]
    missing = [name for name in required if not (project / name).exists()]
    errors: list[str] = []
    if missing:
        errors.append("missing: " + ", ".join(missing))
    config_path = project / ".ai/config.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            unknown = set(config.get("stacks", [])) - set(SUPPORTED_STACKS)
            for name in set(config.get("stacks", [])) - unknown:
                for directory in (".agents/skills", ".claude/skills"):
                    if not (project / directory / name / "SKILL.md").is_file():
                        errors.append(f"skill not discoverable: {directory}/{name}; re-run aidev init")
            if unknown:
                errors.append("unknown stacks: " + ", ".join(sorted(unknown)))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"invalid .ai/config.json: {exc}")
    if errors:
        print("Validation failed:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    print(f"Valid AI harness: {project}")
    return 0
