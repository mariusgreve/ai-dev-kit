"""Detect project stacks from build and dependency evidence."""

from __future__ import annotations

import os
from pathlib import Path

from .catalog import SUPPORTED_STACKS


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
