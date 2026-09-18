#!/usr/bin/env bash
set -euo pipefail

# Also works when read from stdin: curl -fsSL .../install.sh | bash
source_dir=""
if [[ -n "${BASH_SOURCE[0]:-}" && -f "${BASH_SOURCE[0]}" ]]; then
  source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi
install_dir="${AIDEV_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/ai-dev-kit}"
bin_dir="${AIDEV_BIN_DIR:-$HOME/.local/bin}"
command_path="$bin_dir/aidev"

fail() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

command -v git >/dev/null 2>&1 || fail "git is required"
command -v python3 >/dev/null 2>&1 || fail "python3 is required"

source_remote="${AIDEV_REPOSITORY_URL:-}"
bootstrap_dir=""
trap '[[ -z "$bootstrap_dir" ]] || rm -rf "$bootstrap_dir"' EXIT
if [[ -n "$source_dir" && -f "$source_dir/cli/aidev.py" ]]; then
  bootstrap_cli="$source_dir/cli/aidev.py"
  if [[ -z "$source_remote" ]]; then
    source_remote="$(git -C "$source_dir" remote get-url origin 2>/dev/null || true)"
  fi
else
  command -v curl >/dev/null 2>&1 || fail "curl is required for standalone installation"
  bootstrap_dir="$(mktemp -d)"
  bootstrap_cli="$bootstrap_dir/aidev.py"
  bootstrap_url="${AIDEV_BOOTSTRAP_URL:-https://raw.githubusercontent.com/mariusgreve/ai-dev-kit/main/cli/aidev.py}"
  curl --fail --silent --show-error --location "$bootstrap_url" -o "$bootstrap_cli"
fi
source_remote="${source_remote:-https://github.com/mariusgreve/ai-dev-kit.git}"

# The bootstrap selects committed content from origin, never the local worktree.
AIDEV_HOME="$install_dir" python3 "$bootstrap_cli" install-skills --remote "$source_remote"

mkdir -p "$bin_dir"

if [[ -L "$command_path" ]]; then
  existing_target="$(readlink "$command_path")"
  [[ "$existing_target" == "$install_dir/aidev" ]] || fail "$command_path points to $existing_target"
elif [[ -e "$command_path" ]]; then
  fail "$command_path already exists and was not created by ai-dev-kit"
else
  ln -s "$install_dir/aidev" "$command_path"
fi

path_line='export PATH="$HOME/.local/bin:$PATH"'
if [[ ":$PATH:" != *":$bin_dir:"* ]]; then
  case "${SHELL:-}" in
    */zsh) profile="$HOME/.zprofile" ;;
    */bash) profile="$HOME/.bash_profile" ;;
    *) profile="" ;;
  esac
  if [[ -n "$profile" ]]; then
    if [[ ! -f "$profile" ]] || ! grep -Fqx "$path_line" "$profile"; then
      printf '\n%s\n' "$path_line" >> "$profile"
    fi
    path_note="Restart the terminal, or run: source $profile"
  else
    path_note="Add $bin_dir to PATH before using aidev."
  fi
else
  path_note=""
fi

printf '\nInstalled ai-dev-kit in %s\n' "$install_dir"
printf 'Command: %s\n' "$command_path"
[[ -z "$path_note" ]] || printf '%s\n' "$path_note"
printf '\nNext: cd to a project and run `aidev init . --stacks ...`\n'
