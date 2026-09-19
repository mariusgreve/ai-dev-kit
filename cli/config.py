"""Shared project configuration loading, defaults and shape validation."""

from __future__ import annotations

import json
from pathlib import Path

from .paths import safe_file


def load_config(project: Path) -> dict:
    """Allow absent config for task previews; reject invalid config consistently."""
    try:
        return _load_config(project)
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid .ai/config.json: {exc}") from exc


def _load_config(project: Path) -> dict:
    path = safe_file(project, ".ai/config.json")
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if not isinstance(config, dict):
        raise ValueError(".ai/config.json must be an object")
    for key in ("stacks", "principles", "playbooks"):
        if key in config and (not isinstance(config[key], list)
                              or not all(isinstance(v, str) and v.strip() for v in config[key])):
            raise ValueError(f"{key} must be a list of names")
    if "verification" in config and (not isinstance(config["verification"], str)
                                     or not config["verification"].strip()):
        raise ValueError("verification must be a nonempty command string")
    context = config.get("context", {})
    if not isinstance(context, dict):
        raise ValueError("context must be an object")
    for key, default in (("max_files", 20), ("max_chars", 32_000)):
        value = context.get(key, default)
        if type(value) is not int or value < 1:
            raise ValueError(f"context.{key} must be a positive integer")
        context[key] = value
    rules = context.get("rules", [])
    if not isinstance(rules, list):
        raise ValueError("context.rules must be a list")
    for rule in rules:
        if not isinstance(rule, dict) or not rule.get("terms"):
            raise ValueError("Each context rule needs nonempty terms")
        for key in ("terms", "files", "skills", "principles", "architecture"):
            values = rule.get(key, [])
            if not isinstance(values, list) or not all(isinstance(v, str) and v.strip() for v in values):
                raise ValueError(f"Rule {key} must be a list of nonempty strings")
        if "playbook" in rule and (not isinstance(rule["playbook"], str) or not rule["playbook"].strip()):
            raise ValueError("Rule playbook must be a name")
        for pattern in rule.get("files", []) + rule.get("architecture", []):
            safe_file(project, pattern)
    config["context"] = context
    return config
