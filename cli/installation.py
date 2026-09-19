"""Install, update and uninstall the stable kit and global skill links.

This module also serves as the standalone installer bootstrap. Keep its
imports limited to the standard library: install.sh downloads it alone.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

# Independent of catalog.py so the downloaded bootstrap is self-contained.
ROOT = Path(__file__).resolve().parents[1]


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


def bootstrap() -> int:
    parser = argparse.ArgumentParser(description="Install the stable AI development kit")
    parser.add_argument("command", choices=("install-skills",))
    parser.add_argument("--remote", required=True, help="Git remote to install from")
    return install_skills(parser.parse_args().remote)


if __name__ == "__main__":
    try:
        raise SystemExit(bootstrap())
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
