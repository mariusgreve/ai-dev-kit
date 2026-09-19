"""Built-in content and the current kit checkout location."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_STACKS = ("java", "spring", "postgres", "react", "typescript")
DEFAULT_PLAYBOOKS = ("implement-feature", "fix-bug", "review-change")
DEFAULT_PRINCIPLES = ("architecture", "testing", "security")
DEFAULT_TEMPLATES = ("feature-spec", "architecture-overview", "adr")
