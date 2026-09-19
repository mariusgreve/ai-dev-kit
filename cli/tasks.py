"""Preview task context and prepare or launch an RPI handoff."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from .catalog import ROOT
from .context_compiler import compile_context, render, save_task
from .detection import detect_stacks


def task_command(args: argparse.Namespace) -> int:
    if args.command == "task" and args.agent == []:
        raise ValueError("--agent requires an executable")
    project = Path(args.project).resolve()
    context = compile_context(project, ROOT, args.description, args.spec,
                              detect_stacks(project), args.playbook)
    if args.command != "task":
        if args.json:
            print(json.dumps(context, indent=2))
        else:
            print(render(context, include_content=args.command == "inspect"), end="")
        return 0
    directory = save_task(context, project)
    print(f"Task prepared: {directory / 'task.md'}", flush=True)
    print("RPI notes: research.md → plan.md → implementation.md", flush=True)
    if args.agent:
        prompt = (f"Work in {project}. Start the RPI workflow described in "
                  f"{directory / 'task.md'}. Keep phase notes in {directory}.\n\n"
                  + render(context))
        # The caller chooses an executable accepting a prompt on stdin. Never use a shell.
        return subprocess.run(args.agent, input=prompt, text=True, cwd=project).returncode
    print("Give task.md to your coding agent, or pass --agent COMMAND [ARG ...] to start it.")
    return 0
