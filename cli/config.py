"""Read the small project-owned list of installed stack skills."""

import json
from pathlib import Path

from .catalog import SUPPORTED_STACKS
from .paths import safe_file


def load_config(project: Path) -> dict:
    try:
        path = safe_file(project, ".ai/config.json")
        config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not isinstance(config, dict):
            raise ValueError("must be an object")
        stacks = config.get("stacks", [])
        if not isinstance(stacks, list) or not all(isinstance(name, str) for name in stacks):
            raise ValueError("stacks must be a list of names")
        unknown = set(stacks) - set(SUPPORTED_STACKS)
        if unknown:
            raise ValueError("unknown stacks: " + ", ".join(sorted(unknown)))
        return config
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid .ai/config.json: {exc}") from exc
