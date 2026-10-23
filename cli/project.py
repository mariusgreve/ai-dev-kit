"""Create a small project setup without replacing project-owned instructions."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
from pathlib import Path

from .catalog import ROOT, SUPPORTED_STACKS
from .config import load_config
from .detection import detect_stacks
from .installation import ensure_skill_link
from .paths import safe_file


def write_new(path: Path, content: str, executable: bool = False) -> str:
    if path.exists() or path.is_symlink():
        return f"kept    {path}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return f"created {path}"


def install_project_skill(project: Path, name: str) -> list[str]:
    target = safe_file(project, f".ai/skills/{name}")
    outputs = []
    if not target.exists():
        shutil.copytree(ROOT / "skills" / name, target)
        outputs.append(f"created {target}")
    for directory in (".agents/skills", ".claude/skills"):
        outputs.append(ensure_skill_link(safe_file(project, f"{directory}/{name}"), target))
    return outputs


def choose_detected_stacks(project: Path, assume_yes: bool) -> set[str] | None:
    detected = detect_stacks(project)
    if not detected:
        print("No supported stack skills detected. Creating base instructions and verification only.")
        return set()
    print("Detected stacks:")
    for name in SUPPORTED_STACKS:
        if name in detected:
            print(f"  - {name}: {', '.join(detected[name])}")
    if assume_yes:
        return set(detected)
    if not sys.stdin.isatty():
        print("Re-run with `--yes` to accept, or specify `--stacks` explicitly.", file=sys.stderr)
        return None
    if input("Initialize with these stacks? [Y/n] ").strip().lower() in {"", "y", "yes"}:
        return set(detected)
    print("Cancelled.")
    return None


def project_agents() -> str:
    return (ROOT / "templates/AGENTS.md").read_text(encoding="utf-8")


def verify_script() -> str:
    runner = (ROOT / "cli/verification.py").read_text(encoding="utf-8")
    return ('#!/usr/bin/env bash\n'
            '# Project-owned checks. Edit this file to match your build and CI.\n'
            'set -euo pipefail\n'
            'cd "$(dirname "${BASH_SOURCE[0]}")/.."\n'
            "export CI=true\n"
            "python3 - <<'AIDEV_VERIFY_PY'\n" + runner + "AIDEV_VERIFY_PY\n")



def assess(project: Path) -> int:
    """Report existing project onboarding evidence without modifying files."""
    if not project.is_dir():
        print(f"Project directory does not exist: {project}", file=sys.stderr)
        return 1
    print(f"AI onboarding assessment: {project}")
    instructions = ("AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md")
    present = [name for name in instructions if (project / name).is_file()]
    print("Existing AI instructions: " + (", ".join(present) if present else "none"))
    if (project / "AGENTS.md").is_file():
        print("- AGENTS.md already exists; init will preserve it unchanged.")
    else:
        print("- init would create a generic AGENTS.md; review project conventions.")

    documents = ("README.md", "CONTRIBUTING.md", "docs/architecture.md",
                 "docs/ARCHITECTURE.md")
    found_docs = [name for name in documents if (project / name).is_file()]
    print("Project documentation: " + (", ".join(found_docs) if found_docs else "none at common paths"))
    workflows = project / ".github/workflows"
    ci = sorted(str(p.relative_to(project)) for p in workflows.glob("*.yml"))
    ci += sorted(str(p.relative_to(project)) for p in workflows.glob("*.yaml"))
    ci += [name for name in ("Jenkinsfile", ".gitlab-ci.yml") if (project / name).is_file()]
    print("Existing CI: " + (", ".join(ci) if ci else "none detected at common paths"))
    if (project / ".ai/verify.sh").is_file():
        print("- Project verification already exists; init will preserve it.")
    elif ci:
        print("- Review existing CI commands before accepting the generated .ai/verify.sh.")
    else:
        print("- Review the generated .ai/verify.sh against actual project checks.")

    detected = detect_stacks(project)
    print("Detected stacks: " + (", ".join(sorted(detected)) if detected else "none supported"))
    print("Assessment only: no files were created or modified.")
    return 0


def init(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    config = load_config(project)
    chosen = set(args.stacks) if args.stacks is not None else choose_detected_stacks(project, args.yes)
    if chosen is None:
        return 1
    stacks = set(config.get("stacks", [])) | chosen
    files = {
        "AGENTS.md": project_agents(),
        ".ai/verify.sh": verify_script(),
        "CLAUDE.md": (ROOT / "adapters/claude/CLAUDE.md").read_text(encoding="utf-8"),
        ".github/copilot-instructions.md": (ROOT / "adapters/copilot/copilot-instructions.md").read_text(encoding="utf-8"),
    }
    # Check containment and discovery conflicts before making partial changes.
    for name in files:
        safe_file(project, name)
    for stack in stacks:
        target = safe_file(project, f".ai/skills/{stack}")
        for directory in (".agents/skills", ".claude/skills"):
            link = safe_file(project, f"{directory}/{stack}")
            if (link.exists() or link.is_symlink()) and not (link.is_symlink() and link.resolve() == target.resolve()):
                raise ValueError(f"{link} already exists; refusing to replace another skill")
    project.mkdir(parents=True, exist_ok=True)
    outputs = [write_new(project / name, content, name == ".ai/verify.sh") for name, content in files.items()]
    for stack in sorted(stacks):
        outputs.extend(install_project_skill(project, stack))
    updated = {**config, "stacks": sorted(stacks)}
    path = safe_file(project, ".ai/config.json")
    if not path.exists() or updated != config:
        path.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
        outputs.append(f"updated {path}")
    print("\n".join(outputs))
    print("Project-owned instructions, checks and skill contents are preserved on re-runs.")
    print("Review AGENTS.md and .ai/verify.sh, then run ./.ai/verify.sh.")
    return validate_project(project)


def validate_project(project: Path) -> int:
    errors = []
    try:
        config = load_config(project)
        for name in ("AGENTS.md", ".ai/config.json", ".ai/verify.sh"):
            if not safe_file(project, name).is_file():
                errors.append(f"missing file: {name}")
        script = safe_file(project, ".ai/verify.sh")
        if script.is_file() and not os.access(script, os.X_OK):
            errors.append(".ai/verify.sh is not executable")
        for name in config.get("stacks", []):
            target = safe_file(project, f".ai/skills/{name}/SKILL.md")
            for directory in (".agents/skills", ".claude/skills"):
                link = safe_file(project, f"{directory}/{name}/SKILL.md")
                if not target.is_file() or not link.is_file() or not link.samefile(target):
                    errors.append(f"skill not discoverable from project snapshot: {directory}/{name}; re-run aidev init")
    except (OSError, ValueError) as exc:
        errors.append(str(exc))
    if errors:
        print("Setup validation failed:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    print(f"Setup files and skill links are valid: {project}")
    print("Builds and tests were not run. Run ./.ai/verify.sh to check the project.")
    return 0
