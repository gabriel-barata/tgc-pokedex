#!/usr/bin/env bash
# PR-title gate. The title becomes the squash commit on main, so it must read
# "[PTCG-NNN] summary".
#
# Usage: check-pr-title.sh TITLE

set -euo pipefail

title="${1-}"
pattern='^\[PTCG-[0-9]{3}\] [^[:space:]]'

if [[ "$title" =~ $pattern && "$title" != *$'\n'* ]]; then
    printf 'PR title OK\n'
    exit 0
fi
printf 'PR title [%s] must follow "[PTCG-NNN] summary".\n' "$title"
exit 1
