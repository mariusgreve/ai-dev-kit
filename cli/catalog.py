"""Built-in skills and the current kit checkout location."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_STACKS = ("java", "spring", "postgres", "react", "typescript")
