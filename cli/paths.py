"""Path containment checks shared by configuration and task artifacts."""

from pathlib import Path


def safe_file(root: Path, relative: str) -> Path:
    path = root / relative
    if Path(relative).is_absolute() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Context path must stay inside {root}: {relative}")
    return path
