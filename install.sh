#!/usr/bin/env bash
set -euo pipefail

source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
install_dir="${AIDEV_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/ai-dev-kit}"
bin_dir="${AIDEV_BIN_DIR:-$HOME/.local/bin}"
command_path="$bin_dir/aidev"

fail() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

command -v git >/dev/null 2>&1 || fail "git is required"
command -v python3 >/dev/null 2>&1 || fail "python3 is required"

source_remote="$(git -C "$source_dir" remote get-url origin 2>/dev/null || true)"
[[ -n "$source_remote" ]] || fail "this checkout needs a Git remote named 'origin'"

if [[ -e "$install_dir" && ! -d "$install_dir/.git" ]]; then
  fail "$install_dir already exists but is not an ai-dev-kit Git checkout"
fi

if [[ -d "$install_dir/.git" ]]; then
  installed_remote="$(git -C "$install_dir" remote get-url origin 2>/dev/null || true)"
  [[ "$installed_remote" == "$source_remote" ]] || fail "$install_dir belongs to another Git remote"
  git -C "$install_dir" pull --ff-only
else
  mkdir -p "$(dirname "$install_dir")"
  git clone "$source_remote" "$install_dir"
fi

touch "$install_dir/.aidev-install"
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
