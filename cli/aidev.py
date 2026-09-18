#!/usr/bin/env python3
"""Dependency-free CLI for installing and validating the AI development harness."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_STACKS = ("java", "spring", "postgres", "react", "typescript")
DEFAULT_PLAYBOOKS = ("implement-feature", "fix-bug", "review-change")
DEFAULT_PRINCIPLES = ("architecture", "testing", "security")
DEFAULT_TEMPLATES = ("feature-spec", "architecture-overview", "adr")


def write_new(path: Path, content: str, executable: bool = False) -> str:
    if path.exists():
        return f"kept    {path}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return f"created {path}"


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def inspectable_files(project: Path) -> list[Path]:
    names = {
        "build.gradle", "build.gradle.kts", "pom.xml", "package.json",
        "tsconfig.json", "compose.yaml", "compose.yml", "docker-compose.yaml",
        "docker-compose.yml",
    }
    ignored = {".git", ".idea", ".gradle", "node_modules", "build", "dist", "target"}
    matches: list[Path] = []
    for current, directories, files in os.walk(project):
        relative = Path(current).relative_to(project)
        if len(relative.parts) >= 3:
            directories[:] = []
        else:
            directories[:] = [name for name in directories if name not in ignored and not name.startswith(".")]
        matches.extend(Path(current) / name for name in files if name in names)
    return sorted(matches)


def detect_stacks(project: Path) -> dict[str, list[str]]:
    evidence: dict[str, list[str]] = {name: [] for name in SUPPORTED_STACKS}
    files = inspectable_files(project)
    for path in files:
        relative = str(path.relative_to(project))
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")[:1_000_000].lower()
        except OSError:
            continue
        if path.name in {"pom.xml", "build.gradle", "build.gradle.kts"}:
            if "src/main/java" in content or "java" in content or path.name == "pom.xml":
                evidence["java"].append(relative)
            if "spring-boot" in content or "org.springframework" in content:
                evidence["spring"].append(relative)
            if "org.postgresql" in content or "postgresql" in content:
                evidence["postgres"].append(relative)
        if path.name == "package.json":
            if '"react"' in content or '"react-dom"' in content:
                evidence["react"].append(relative)
            if '"typescript"' in content:
                evidence["typescript"].append(relative)
        if path.name == "tsconfig.json":
            evidence["typescript"].append(relative)
        if path.name in {"compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"}:
            if "postgres" in content:
                evidence["postgres"].append(relative)
    if any((project / path).is_dir() for path in ("src/main/java", "src/test/java")):
        evidence["java"].append("src/.../java")
    return {name: sorted(set(paths)) for name, paths in evidence.items() if paths}


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
        outputs.append(write_new(project / f".ai/skills/{stack}/SKILL.md", read(f"skills/{stack}/SKILL.md")))
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
            if unknown:
                errors.append("unknown stacks: " + ", ".join(sorted(unknown)))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"invalid .ai/config.json: {exc}")
    if errors:
        print("Validation failed:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    print(f"Valid AI harness: {project}")
    return 0


def update_kit() -> int:
    if not (ROOT / ".git").is_dir():
        print("This installation is not a Git checkout and cannot update itself.", file=sys.stderr)
        return 1
    completed = subprocess.run(["git", "-C", str(ROOT), "pull", "--ff-only"], check=False)
    return completed.returncode


def uninstall_kit(yes: bool) -> int:
    marker = ROOT / ".aidev-install"
    command_path = Path(os.environ.get("AIDEV_BIN_DIR", Path.home() / ".local/bin")) / "aidev"
    if not marker.is_file():
        print(f"Refusing to remove unmarked checkout: {ROOT}", file=sys.stderr)
        return 1
    if not yes:
        if not sys.stdin.isatty():
            print("Re-run with `aidev uninstall --yes`.", file=sys.stderr)
            return 1
        answer = input(f"Remove ai-dev-kit from {ROOT}? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print("Cancelled.")
            return 0
    if command_path.is_symlink() and command_path.resolve() == (ROOT / "aidev").resolve():
        command_path.unlink()
    shutil.rmtree(ROOT)
    print("ai-dev-kit was uninstalled. Shell PATH configuration was left unchanged.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="aidev")
    sub = parser.add_subparsers(dest="command", required=True)
    p_init = sub.add_parser("init", help="initialize a project harness")
    p_init.add_argument("project", nargs="?", default=".")
    p_init.add_argument("--stacks", nargs="+", choices=SUPPORTED_STACKS, default=None)
    p_init.add_argument("--yes", action="store_true", help="accept detected stacks without prompting")
    p_validate = sub.add_parser("validate", help="validate a project harness")
    p_validate.add_argument("project", nargs="?", default=".")
    sub.add_parser("list", help="list available reusable content")
    sub.add_parser("update", help="update the installed kit with git pull --ff-only")
    p_uninstall = sub.add_parser("uninstall", help="remove an installation created by install.sh")
    p_uninstall.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    args = parser.parse_args()
    if args.command == "init":
        return init(args)
    if args.command == "validate":
        return validate_project(Path(args.project).resolve())
    if args.command == "update":
        return update_kit()
    if args.command == "uninstall":
        return uninstall_kit(args.yes)
    print("Stacks: " + ", ".join(SUPPORTED_STACKS))
    print("Playbooks: " + ", ".join(DEFAULT_PLAYBOOKS))
    print("Principles: " + ", ".join(DEFAULT_PRINCIPLES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
