#!/usr/bin/env python3
"""Dependency-free CLI for installing and validating the AI development harness."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED_STACKS = ("java", "spring", "postgres", "react", "typescript")
DEFAULT_PLAYBOOKS = ("implement-feature", "fix-bug", "review-change")
DEFAULT_PRINCIPLES = ("architecture", "testing", "security")
DEFAULT_TEMPLATES = ("feature-spec", "architecture-overview", "adr")


def write_new(path: Path, content: str, executable: bool = False) -> str:
    if path.exists():
        return f"kept    {path}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return f"created {path}"


def ensure_skill_link(path: Path, target: Path) -> str:
    if path.is_symlink() and path.resolve() == target.resolve():
        return f"kept    {path}"
    if path.exists() or path.is_symlink():
        raise ValueError(f"{path} already exists; refusing to replace another skill")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(os.path.relpath(target.resolve(), path.parent.resolve()), target_is_directory=True)
    return f"linked  {path}"


def global_skill_roots() -> list[Path]:
    # Codex and Copilot share .agents; Claude needs its own discovery path.
    return [Path.home() / ".agents/skills",
            Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")) / "skills"]


def installation_root() -> Path:
    return Path(os.environ.get("AIDEV_HOME", Path(os.environ.get(
        "XDG_DATA_HOME", Path.home() / ".local/share")) / "ai-dev-kit")).expanduser().resolve()


def skill_manifest(root: Path | None = None) -> Path:
    return (root or installation_root()) / ".aidev-skill-links.json"


def read_skill_links(root: Path | None = None) -> dict[str, str]:
    path = skill_manifest(root)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def remove_skill_links(links: dict[str, str]) -> None:
    for name, target in links.items():
        path = Path(name)
        if path.is_symlink() and path.resolve() == Path(target).resolve():
            path.unlink()


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], text=True, capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Git operation failed")
    return result.stdout.strip()


def remote_identity(remote: str) -> str:
    # GitHub SSH and HTTPS URLs can refer to the same repository. This matters
    # when switching from a local checkout installer to the curl bootstrap.
    if remote.startswith("git@github.com:"):
        return "github.com/" + remote.split(":", 1)[1].removesuffix(".git").rstrip("/")
    parsed = urlparse(remote)
    if parsed.hostname == "github.com" and parsed.scheme in {"https", "ssh"}:
        return "github.com/" + parsed.path.strip("/").removesuffix(".git")
    return remote


def stable_revision(checkout: Path) -> tuple[str, str]:
    # Only final semantic-version tags count as published stable releases.
    versions = []
    for tag in git(checkout, "tag", "--list").splitlines():
        match = re.fullmatch(r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", tag)
        if match:
            versions.append((tuple(map(int, match.groups())), tag))
    ref = "refs/tags/" + max(versions)[1] if versions else "refs/remotes/origin/main"
    return ref, git(checkout, "rev-parse", "--verify", ref + "^{commit}")


def install_skills(remote: str | None = None) -> int:
    destination = installation_root()
    remote = remote or git(ROOT, "remote", "get-url", "origin")
    if destination == ROOT.resolve() and not (ROOT / ".aidev-install").is_file():
        raise ValueError("AIDEV_HOME must not point to the development checkout")
    if destination.exists():
        if not (destination / ".aidev-install").is_file():
            raise ValueError(f"Refusing to replace unmarked installation: {destination}")
        if remote_identity(git(destination, "remote", "get-url", "origin")) != remote_identity(remote):
            raise ValueError(f"{destination} belongs to another Git remote")
        # Ignore only installer metadata, not arbitrary user changes.
        changed = git(destination, "status", "--porcelain", "--untracked-files=all", "--",
                      ".", ":(exclude).aidev-install", ":(exclude).aidev-skill-links.json",
                      ":(exclude).aidev-release.json")
        if changed:
            raise ValueError(f"Installed checkout has local changes; refusing to replace {destination}")
    previous = read_skill_links(destination)
    # Migrate links created by older versions directly into a development repo.
    legacy = read_skill_links(ROOT) if ROOT.resolve() != destination else {}
    owned = {**legacy, **previous}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".aidev-stage-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "checkout"
        # Fetch origin, never the development worktree or its local-only tags.
        result = subprocess.run(["git", "clone", "--no-checkout", "--", remote, str(staged)],
                                text=True, capture_output=True)
        if result.returncode:
            raise ValueError(result.stderr.strip())
        ref, commit = stable_revision(staged)
        git(staged, "checkout", "--detach", commit)
        skills = sorted(path.name for path in (staged / "skills").iterdir()
                        if (path / "SKILL.md").is_file())
        if not skills:
            raise ValueError(f"No skills found in {ref}")
        desired = {str(directory / name): str(destination / "skills" / name)
                   for directory in global_skill_roots() for name in skills}
        for name, target in desired.items():
            path = Path(name)
            if (path.exists() or path.is_symlink()) and not (
                path.is_symlink() and (path.resolve() == Path(target).resolve() or
                    (name in owned and path.resolve() == Path(owned[name]).resolve()))
            ):
                raise ValueError(f"{path} already exists; refusing to replace another skill")
        (staged / ".aidev-install").touch()
        skill_manifest(staged).write_text(json.dumps(desired, indent=2) + "\n", encoding="utf-8")
        (staged / ".aidev-release.json").write_text(json.dumps(
            {"remote": remote, "ref": ref, "commit": commit}, indent=2) + "\n", encoding="utf-8")
        with (staged / ".git/info/exclude").open("a", encoding="utf-8") as exclude:
            exclude.write("\n.aidev-install\n.aidev-skill-links.json\n.aidev-release.json\n")
        backup = Path(temporary) / "previous"
        if destination.exists():
            destination.rename(backup)
        try:
            staged.rename(destination)
        except OSError:
            if backup.exists():
                backup.rename(destination)
            raise
        for name, target in desired.items():
            path = Path(name)
            if path.is_symlink() and path.resolve() != Path(target).resolve():
                path.unlink()  # Preflight verified this was a kit-owned legacy link.
            print(ensure_skill_link(path, Path(target)))
        remove_skill_links({name: target for name, target in owned.items() if name not in desired})
    if legacy:
        skill_manifest(ROOT).unlink()
    print(f"Installed stable skills from {ref} ({commit[:12]}) in {destination}")
    print("Restart existing agent sessions to reload skills.")
    return 0


def install_project_skill(project: Path, name: str) -> list[str]:
    # One portable project snapshot, including supporting resources. All tool
    # discovery entries reference it, and existing project overrides survive.
    target = project / ".ai/skills" / name
    outputs = []
    if not target.exists() and not target.is_symlink():
        shutil.copytree(ROOT / "skills" / name, target)
        outputs.append(f"created {target}")
    for directory in (".agents/skills", ".claude/skills"):
        outputs.append(ensure_skill_link(project / directory / name, target))
    return outputs


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


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


def choose_detected_stacks(project: Path, assume_yes: bool) -> set[str] | None:
    detected = detect_stacks(project)
    if not detected:
        print("No supported stacks were detected.", file=sys.stderr)
        print("Specify them explicitly with `--stacks`, or run `aidev list`.", file=sys.stderr)
        return None
    print("Detected stacks:")
    for name in SUPPORTED_STACKS:
        if name in detected:
            print(f"  - {name}: {', '.join(detected[name])}")
    if assume_yes:
        return set(detected)
    if not sys.stdin.isatty():
        print("Re-run with `--yes` to accept, or specify `--stacks` explicitly.", file=sys.stderr)
        return None
    answer = input("Initialize with these stacks? [Y/n] ").strip().lower()
    if answer in {"", "y", "yes"}:
        return set(detected)
    print("Cancelled. Re-run with `--stacks <names>` to choose manually.")
    return None


def project_agents() -> str:
    return """# Agent instructions

Treat repository documentation and executable checks as the source of truth.

Before changing code:
- read the relevant spec and acceptance criteria
- inspect affected architecture and existing conventions
- load only the skills needed for the task
- use the matching playbook under `.ai/playbooks/`

Prefer the smallest coherent change. Delegate only when context isolation,
parallel work, or genuine specialization provides a clear benefit.

Do not declare completion until `./.ai/verify.sh` passes and every acceptance
criterion has been checked. Deterministic checks precede AI review.
"""


def verify_script(stacks: set[str]) -> str:
    blocks = ["#!/usr/bin/env bash", "set -euo pipefail", "", "repo_root=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")/..\" && pwd)\"", "cd \"$repo_root\"", "", "ran=0"]
    if "java" in stacks or "spring" in stacks:
        blocks += [
            "if [[ -x ./gradlew ]]; then ./gradlew check; ran=1",
            "elif [[ -x ./mvnw ]]; then ./mvnw verify; ran=1",
            "fi",
        ]
    if {"react", "typescript"} & stacks:
        blocks += [
            "if [[ -f package.json ]]; then",
            "  npm run --if-present lint",
            "  npm run --if-present typecheck",
            "  npm run --if-present test",
            "  ran=1",
            "fi",
        ]
    blocks += ["", "if [[ $ran -eq 0 ]]; then", "  echo 'No build detected. Edit .ai/verify.sh for this project.' >&2", "  exit 2", "fi", ""]
    return "\n".join(blocks)


def init(args: argparse.Namespace) -> int:
    project = Path(args.project).resolve()
    project.mkdir(parents=True, exist_ok=True)
    if args.stacks is None:
        chosen = choose_detected_stacks(project, args.yes)
        if chosen is None:
            return 1
        stacks = chosen
    else:
        stacks = set(args.stacks)
    config = {
        "kit_version": "0.1.0",
        "stacks": sorted(stacks),
        "playbooks": list(DEFAULT_PLAYBOOKS),
        "principles": list(DEFAULT_PRINCIPLES),
        "verification": "./.ai/verify.sh",
    }
    outputs = [
        write_new(project / "AGENTS.md", project_agents()),
        write_new(project / ".ai/config.json", json.dumps(config, indent=2) + "\n"),
        write_new(project / ".ai/verify.sh", verify_script(stacks), executable=True),
        write_new(project / "architecture/overview.md", read("templates/architecture-overview.md")),
        write_new(project / "architecture/decisions/.gitkeep", ""),
        write_new(project / "specs/features/.gitkeep", ""),
    ]
    for name in DEFAULT_PLAYBOOKS:
        outputs.append(write_new(project / f".ai/playbooks/{name}.md", read(f"playbooks/{name}.md")))
    for name in DEFAULT_PRINCIPLES:
        outputs.append(write_new(project / f".ai/principles/{name}.md", read(f"principles/{name}.md")))
    for name in DEFAULT_TEMPLATES:
        outputs.append(write_new(project / f".ai/templates/{name}.md", read(f"templates/{name}.md")))
    for stack in sorted(stacks):
        outputs.extend(install_project_skill(project, stack))
    outputs += [
        write_new(project / "CLAUDE.md", read("adapters/claude/CLAUDE.md")),
        write_new(project / ".github/copilot-instructions.md", read("adapters/copilot/copilot-instructions.md")),
    ]
    print("\n".join(outputs))
    return validate_project(project)


def validate_project(project: Path) -> int:
    required = ["AGENTS.md", ".ai/config.json", ".ai/verify.sh", "architecture/overview.md"]
    missing = [name for name in required if not (project / name).exists()]
    errors: list[str] = []
    if missing:
        errors.append("missing: " + ", ".join(missing))
    config_path = project / ".ai/config.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            unknown = set(config.get("stacks", [])) - set(SUPPORTED_STACKS)
            for name in set(config.get("stacks", [])) - unknown:
                for directory in (".agents/skills", ".claude/skills"):
                    if not (project / directory / name / "SKILL.md").is_file():
                        errors.append(f"skill not discoverable: {directory}/{name}; re-run aidev init")
            if unknown:
                errors.append("unknown stacks: " + ", ".join(sorted(unknown)))
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"invalid .ai/config.json: {exc}")
    if errors:
        print("Validation failed:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 1
    print(f"Valid AI harness: {project}")
    return 0


def update_kit() -> int:
    # Install and update use exactly the same remote release selection policy.
    return install_skills()


def uninstall_kit(yes: bool) -> int:
    marker = ROOT / ".aidev-install"
    command_path = Path(os.environ.get("AIDEV_BIN_DIR", Path.home() / ".local/bin")) / "aidev"
    if not marker.is_file():
        print(f"Refusing to remove unmarked checkout: {ROOT}", file=sys.stderr)
        return 1
    if not yes:
        if not sys.stdin.isatty():
            print("Re-run with `aidev uninstall --yes`.", file=sys.stderr)
            return 1
        answer = input(f"Remove ai-dev-kit from {ROOT}? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            print("Cancelled.")
            return 0
    if command_path.is_symlink() and command_path.resolve() == (ROOT / "aidev").resolve():
        command_path.unlink()
    remove_skill_links(read_skill_links(ROOT))
    shutil.rmtree(ROOT)
    print("ai-dev-kit was uninstalled. Shell PATH configuration was left unchanged.")
    return 0


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
    args = parser.parse_args()
    if args.command == "init":
        return init(args)
    if args.command == "validate":
        return validate_project(Path(args.project).resolve())
    if args.command == "install-skills":
        return install_skills(args.remote)
    if args.command == "update":
        return update_kit()
    if args.command == "uninstall":
        return uninstall_kit(args.yes)
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
