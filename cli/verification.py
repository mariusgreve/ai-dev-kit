"""Standalone verification runner embedded in each project's editable verify.sh."""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

IGNORED = {"node_modules", "build", "dist", "target", "coverage", "venv"}


def run(command, directory):
    print(f"Running in {directory}: {shlex.join(command)}", flush=True)
    result = subprocess.run(command, cwd=directory)
    if result.returncode:
        raise SystemExit(result.returncode)


def package_manager(directory, root, package):
    declared = package.get("packageManager")
    if declared:
        manager = declared.split("@", 1)[0] if isinstance(declared, str) else ""
        if manager not in {"npm", "pnpm", "yarn", "bun"}:
            raise ValueError(f"Unsupported packageManager in {directory}/package.json; edit .ai/verify.sh")
        return manager
    for current in (directory, *directory.parents):
        if current != directory and (current / "package.json").is_file():
            parent = json.loads((current / "package.json").read_text(encoding="utf-8"))
            if isinstance(parent, dict) and parent.get("packageManager"):
                return package_manager(current, root, parent)
        managers = {manager for lock, manager in (
            ("package-lock.json", "npm"), ("pnpm-lock.yaml", "pnpm"),
            ("yarn.lock", "yarn"), ("bun.lock", "bun"), ("bun.lockb", "bun"))
            if (current / lock).is_file()}
        if len(managers) > 1:
            raise ValueError(f"Conflicting lockfiles in {current}; declare packageManager or edit .ai/verify.sh")
        if managers:
            return managers.pop()
        if current == root:
            break
    return "npm"


def verify(root):
    ran = 0
    java_roots, node_roots = [], []
    missing = []
    for current, directories, files in os.walk(root):
        directory = Path(current)
        relative = directory.relative_to(root)
        directories[:] = sorted(name for name in directories
                                if name not in IGNORED and not name.startswith(".")
                                and not (directory / name).is_symlink()) if len(relative.parts) < 3 else []
        if any(name in files for name in ("pom.xml", "build.gradle", "build.gradle.kts", "gradlew", "mvnw")):
            if not any(directory.is_relative_to(parent) for parent in java_roots):
                java_roots.append(directory)
                wrapper = next((name for name in ("gradlew", "mvnw") if (directory / name).is_file()), None)
                if wrapper:
                    run(["bash", f"./{wrapper}", "check" if wrapper == "gradlew" else "verify"], directory)
                    ran += 1
                else:
                    missing.append(f"{relative}: no Gradle/Maven wrapper; edit .ai/verify.sh")
        if "package.json" in files and not any(directory.is_relative_to(parent) for parent in node_roots):
            package = json.loads((directory / "package.json").read_text(encoding="utf-8"))
            if not isinstance(package, dict) or not isinstance(package.get("scripts", {}), dict):
                raise ValueError(f"Invalid package.json or scripts in {relative}")
            scripts = package.get("scripts", {})
            for name in ("lint", "typecheck", "test:ci", "test", "build"):
                if name in scripts and not isinstance(scripts[name], str):
                    raise ValueError(f"scripts.{name} must be a string in {relative}/package.json")
            names = ("lint", "typecheck", "test:ci" if scripts.get("test:ci", "").strip() else "test", "build")
            checks = [name for name in names if scripts.get(name, "").strip()]
            if checks:
                manager = package_manager(directory, root, package)
                for name in checks:
                    run([manager, "run", name], directory)
                    ran += 1
            else:
                missing.append(f"{relative}: no lint, typecheck, test:ci/test or build scripts")
            # Workspace scripts are owned by the workspace root, not guessed per package.
            if package.get("workspaces") or (directory / "pnpm-workspace.yaml").is_file():
                node_roots.append(directory)
    if missing or not ran:
        for message in missing:
            print(f"Unverified: {message}", file=sys.stderr)
        print("Verification incomplete. Edit .ai/verify.sh for this project's real checks.", file=sys.stderr)
        return 2
    print(f"Verification passed: {ran} check(s).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(verify(Path.cwd().resolve()))
    except (OSError, ValueError) as exc:
        print(f"Verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
