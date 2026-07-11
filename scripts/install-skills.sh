#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_SKILLS=(gooaye yutinghao zhezhe thememiner lagradar serenity)
SELECTED_SKILLS=()
TARGETS=()

usage() {
  cat <<'EOF'
Install alpha-persona-lab skills by symlinking them into a local skills folder.

Usage:
  scripts/install-skills.sh [--codex] [--claude] [--all-targets] [--skill NAME ...]

Options:
  --codex        Install into ${CODEX_HOME:-$HOME/.codex}/skills
  --claude       Install into $HOME/.claude/skills
  --all-targets  Install into both Codex and Claude skills folders
  --skill NAME   Install only the named skill. Can be repeated.
  --help         Show this help text

If no target is supplied, --codex is used.
EOF
}

add_target() {
  local target="$1"
  for existing in "${TARGETS[@]:-}"; do
    if [[ "$existing" == "$target" ]]; then
      return 0
    fi
  done
  TARGETS+=("$target")
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --codex)
      add_target "codex"
      shift
      ;;
    --claude)
      add_target "claude"
      shift
      ;;
    --all-targets)
      add_target "codex"
      add_target "claude"
      shift
      ;;
    --skill)
      if [[ $# -lt 2 ]]; then
        echo "--skill requires a name" >&2
        exit 2
      fi
      SELECTED_SKILLS+=("$2")
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ${#TARGETS[@]} -eq 0 ]]; then
  TARGETS=(codex)
fi

if [[ ${#SELECTED_SKILLS[@]} -eq 0 ]]; then
  SELECTED_SKILLS=("${DEFAULT_SKILLS[@]}")
fi

target_dir_for() {
  case "$1" in
    codex)
      printf '%s\n' "${CODEX_HOME:-$HOME/.codex}/skills"
      ;;
    claude)
      printf '%s\n' "$HOME/.claude/skills"
      ;;
    *)
      echo "Unknown target: $1" >&2
      exit 2
      ;;
  esac
}

for target in "${TARGETS[@]}"; do
  target_dir="$(target_dir_for "$target")"
  mkdir -p "$target_dir"

  for skill in "${SELECTED_SKILLS[@]}"; do
    src="$ROOT_DIR/$skill"
    dest="$target_dir/$skill"

    if [[ ! -f "$src/SKILL.md" ]]; then
      echo "Skipping $skill: $src/SKILL.md not found" >&2
      continue
    fi

    if [[ -e "$dest" && ! -L "$dest" ]]; then
      echo "Skipping $dest: exists and is not a symlink" >&2
      continue
    fi

    ln -sfn "$src" "$dest"
    echo "Installed $skill -> $dest"
  done
done

echo "Done. Restart or reload your app's skill session."
