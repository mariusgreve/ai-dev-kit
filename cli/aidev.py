#!/usr/bin/env python3
"""Parse command-line arguments and dispatch to the responsible module."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Support the executable launcher, direct script execution and python -m cli.aidev.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cli import installation, project
from cli.catalog import ROOT, SUPPORTED_STACKS


def main() -> int:
    parser = argparse.ArgumentParser(prog="aidev")
    sub = parser.add_subparsers(dest="command", required=True)
    p_init = sub.add_parser("init", help="initialize project instructions and checks")
    p_init.add_argument("project", nargs="?", default=".")
    p_init.add_argument("--stacks", nargs="+", choices=SUPPORTED_STACKS, default=None)
    p_init.add_argument("--yes", action="store_true", help="accept detected stacks without prompting")
    p_validate = sub.add_parser("validate", help="check setup files and skill links (does not run tests)")
    p_validate.add_argument("project", nargs="?", default=".")
    sub.add_parser("list", help="list available reusable content")
    p_skills = sub.add_parser("install-skills", help="install stable kit skills for local AI tools")
    p_skills.add_argument("--remote", help="Git remote to install from (defaults to origin)")
    sub.add_parser("update", help="install the latest stable version tag, falling back to origin/main")
    p_uninstall = sub.add_parser("uninstall", help="remove an installation created by install.sh")
    p_uninstall.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    if len(sys.argv) > 1 and sys.argv[1] in {"task", "inspect", "explain"}:
        parser.exit(2, "The task/inspect/explain workflow has been removed. Give your task or spec "
                    "directly to your coding agent; use ./.ai/verify.sh for project checks. "
                    "Existing task notes are unchanged.\n")
    args = parser.parse_args()
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
    print("Task skills: bootstrap-from-reference, git-commit-message")
    print(f"Optional templates: {ROOT / 'templates'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
