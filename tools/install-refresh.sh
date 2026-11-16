#!/bin/sh
# Install (or reinstall) the daily background refresh as a launchd agent.
# The plist is written with this checkout's path, so it lives only in
# ~/Library/LaunchAgents, never in the repository. Output goes to
# data/refresh.log (gitignored). Remove with: tools/install-refresh.sh --remove
set -eu
label=bonfire-dates.refresh
plist="$HOME/Library/LaunchAgents/$label.plist"
root=$(cd "$(dirname "$0")/.." && pwd)

launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
if [ "${1:-}" = "--remove" ]; then
    rm -f "$plist"
    echo "Removed $label."
    exit 0
fi

mkdir -p "$root/data"
cat > "$plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$label</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/sh</string>
        <string>$root/tools/refresh.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$root</string>
    <!-- Daily at 07:30. If the Mac is asleep then, launchd runs it on wake. -->
    <key>StartCalendarInterval</key>
    <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>30</integer></dict>
    <key>StandardOutPath</key>
    <string>$root/data/refresh.log</string>
    <key>StandardErrorPath</key>
    <string>$root/data/refresh.log</string>
</dict>
</plist>
EOF
launchctl bootstrap "gui/$(id -u)" "$plist"
echo "Installed $label: daily at 07:30, log in data/refresh.log."
echo "Run it now with: launchctl kickstart gui/$(id -u)/$label"
