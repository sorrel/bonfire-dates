#!/bin/sh
# The background refresh: check the data, then bring the Bonfire calendar in
# line. Run daily by launchd (tools/install-refresh.sh). It fetches nothing:
# new dates still come from research by hand (/tidy). What it does is keep the
# calendar right as the days pass: the 18-month horizon rolls on, this year
# drops to known dates once Lewes night has passed, events deleted by hand
# come back, and failed writes retry.
set -u
cd "$(dirname "$0")/.." || exit 1
bonfire=.venv/bin/bonfire

echo "── $(date '+%a %d %b %Y %H:%M') ─────────────────────────────"
if ! "$bonfire" check; then
    echo "Data problems: calendar left alone until they are fixed."
    exit 1
fi
"$bonfire" sync
status=$?
echo
exit $status
