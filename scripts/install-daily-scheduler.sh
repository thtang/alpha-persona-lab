#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="${LABEL:-com.thtang.alpha-persona-lab.daily-update}"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/$LABEL.plist"

HOUR=7
MINUTE=30
WORKERS=3
JOBS="all"
THEME_PROFILE="codex"
SOURCE_LIMIT=60
LOAD=true
UNINSTALL=false

usage() {
  cat <<'EOF'
Install or remove the Alpha Persona Lab daily data scheduler.

Usage:
  scripts/install-daily-scheduler.sh [options]

Options:
  --hour N                 Local-hour StartCalendarInterval. Default: 7
  --minute N               Local-minute StartCalendarInterval. Default: 30
  --workers N              Parallel source/Codex workers. Default: 3
  --jobs VALUE             all, corpus, theme, or comma-separated subset. Default: all
  --theme-profile VALUE    codex, light, or skip. Default: codex
  --source-limit N         ThemeMiner source rows per shard; 0 means all. Default: 60
  --no-load                Write plist but do not load it.
  --uninstall              Unload and remove the LaunchAgent plist.
  --help                   Show this help text.

Environment overrides:
  PYTHON                   Python executable used by launchd. Defaults to repo .venv/bin/python, then python3.
  THEMEMINER_CODEX_COMMAND Absolute codex CLI path. Auto-detected when unset.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hour)
      HOUR="$2"
      shift 2
      ;;
    --minute)
      MINUTE="$2"
      shift 2
      ;;
    --workers)
      WORKERS="$2"
      shift 2
      ;;
    --jobs)
      JOBS="$2"
      shift 2
      ;;
    --theme-profile)
      THEME_PROFILE="$2"
      shift 2
      ;;
    --source-limit)
      SOURCE_LIMIT="$2"
      shift 2
      ;;
    --no-load)
      LOAD=false
      shift
      ;;
    --uninstall)
      UNINSTALL=true
      shift
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

if ! [[ "$HOUR" =~ ^[0-9]+$ ]] || (( HOUR < 0 || HOUR > 23 )); then
  echo "--hour must be an integer from 0 to 23" >&2
  exit 2
fi

if ! [[ "$MINUTE" =~ ^[0-9]+$ ]] || (( MINUTE < 0 || MINUTE > 59 )); then
  echo "--minute must be an integer from 0 to 59" >&2
  exit 2
fi

if ! [[ "$WORKERS" =~ ^[0-9]+$ ]] || (( WORKERS < 1 )); then
  echo "--workers must be a positive integer" >&2
  exit 2
fi

if [[ "$THEME_PROFILE" != "codex" && "$THEME_PROFILE" != "light" && "$THEME_PROFILE" != "skip" ]]; then
  echo "--theme-profile must be codex, light, or skip" >&2
  exit 2
fi

uid_value="$(id -u)"

if [[ "$UNINSTALL" == true ]]; then
  if [[ -f "$PLIST_PATH" ]]; then
    launchctl bootout "gui/$uid_value" "$PLIST_PATH" >/dev/null 2>&1 || true
    rm -f "$PLIST_PATH"
    echo "Removed $PLIST_PATH"
  else
    echo "No scheduler plist found at $PLIST_PATH"
  fi
  exit 0
fi

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="${PYTHON:-$ROOT_DIR/.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON:-$(command -v python3)}"
fi

CODEX_BIN="${THEMEMINER_CODEX_COMMAND:-}"
if [[ -z "$CODEX_BIN" ]]; then
  if command -v codex >/dev/null 2>&1; then
    CODEX_BIN="$(command -v codex)"
  elif [[ -x "/Applications/Codex.app/Contents/Resources/codex" ]]; then
    CODEX_BIN="/Applications/Codex.app/Contents/Resources/codex"
  else
    CODEX_BIN="codex"
  fi
fi

mkdir -p "$PLIST_DIR" "$ROOT_DIR/logs/daily_update" "$ROOT_DIR/.runtime/daily_update"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>WorkingDirectory</key>
  <string>$ROOT_DIR</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_BIN</string>
    <string>$ROOT_DIR/scripts/daily_update.py</string>
    <string>--jobs</string>
    <string>$JOBS</string>
    <string>--workers</string>
    <string>$WORKERS</string>
    <string>--theme-profile</string>
    <string>$THEME_PROFILE</string>
    <string>--source-limit</string>
    <string>$SOURCE_LIMIT</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>$HOUR</integer>
    <key>Minute</key>
    <integer>$MINUTE</integer>
  </dict>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>$ROOT_DIR/.venv/bin:/Applications/Codex.app/Contents/Resources:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
    <key>THEMEMINER_CODEX_COMMAND</key>
    <string>$CODEX_BIN</string>
  </dict>
  <key>StandardOutPath</key>
  <string>$ROOT_DIR/logs/daily_update/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>$ROOT_DIR/logs/daily_update/launchd.err.log</string>
  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
EOF

plutil -lint "$PLIST_PATH"

if [[ "$LOAD" == true ]]; then
  launchctl bootout "gui/$uid_value" "$PLIST_PATH" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$uid_value" "$PLIST_PATH"
  launchctl enable "gui/$uid_value/$LABEL" >/dev/null 2>&1 || true
  echo "Loaded $LABEL"
fi

echo "Scheduler plist: $PLIST_PATH"
printf 'Daily run time: %d:%02d local time\n' "$HOUR" "$MINUTE"
echo "Command: $PYTHON_BIN $ROOT_DIR/scripts/daily_update.py --jobs $JOBS --workers $WORKERS --theme-profile $THEME_PROFILE --source-limit $SOURCE_LIMIT"
