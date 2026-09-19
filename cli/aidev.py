#!/usr/bin/env python3
"""Parse command-line arguments and dispatch to the responsible module."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Support the executable launcher, direct script execution and python -m cli.aidev.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cli import installation, project, tasks
from cli.catalog import SUPPORTED_STACKS, DEFAULT_PLAYBOOKS, DEFAULT_PRINCIPLES


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
    p_skills = sub.add_parser("install-skills", help="install stable kit skills for local AI tools")
    p_skills.add_argument("--remote", help="Git remote to install from (defaults to origin)")
    sub.add_parser("update", help="install the latest stable version tag, falling back to origin/main")
    p_uninstall = sub.add_parser("uninstall", help="remove an installation created by install.sh")
    p_uninstall.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    for name in ("task", "inspect", "explain"):
        command = sub.add_parser(name, help={
            "task": "compile task context and prepare an RPI handoff",
            "inspect": "preview task context without writing files",
            "explain": "explain context selection without writing files",
        }[name])
        command.add_argument("description", nargs="?", default="")
        command.add_argument("--project", default=".", help="project root (default: current directory)")
        command.add_argument("--spec", help="spec path, relative to the project root")
        command.add_argument("--playbook", help="override automatic playbook selection")
        if name == "task":
            command.add_argument("--agent", nargs=argparse.REMAINDER,
                                 help="executable and arguments receiving the handoff on stdin; must be last")
        else:
            command.add_argument("--json", action="store_true", help="emit structured context and selection reasons")
    args = parser.parse_args()
    if args.command in {"task", "inspect", "explain"}:
        return tasks.task_command(args)
    if args.command == "init":
        return project.init(args)
    if args.command == "validate":
        return project.validate_project(Path(args.project).resolve())
    if args.command == "install-skills":
        return installation.install_skills(args.remote)
    if args.command == "update":
        return installation.update_kit()
    if args.command == "uninstall":
        return installation.uninstall_kit(args.yes)
    print("Stacks: " + ", ".join(SUPPORTED_STACKS))
    print("Playbooks: " + ", ".join(DEFAULT_PLAYBOOKS))
    print("Principles: " + ", ".join(DEFAULT_PRINCIPLES))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
