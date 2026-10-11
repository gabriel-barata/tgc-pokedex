#!/usr/bin/env bash
# Skipped-test gate (constitution, Quality Gate 1). Every skipped, expected-to-fail or todo
# test in the tracked Python and TypeScript files must name its ticket (PTCG-NNN) on the same
# line.
#
# Usage: check-skipped-tests.sh (from the repository root)

set -euo pipefail

python_skip='(^|[^A-Za-z0-9_.])pytest\.(mark\.(skip|skipif|xfail)([^A-Za-z0-9_]|$)|skip\()'
vitest_skip='(^|[^A-Za-z0-9_.$])(it|test|describe)\.(skip|skipIf|todo)([^A-Za-z0-9_$]|$)'

unreferenced="$(
    {
        git grep -n -E "$python_skip" -- '*.py' || true
        git grep -n -E "$vitest_skip" -- '*.ts' '*.tsx' || true
    } | grep -vE '^[^:]+:[0-9]+:.*PTCG-[0-9]{3}' || true
)"

if [ -n "$unreferenced" ]; then
    printf '%s\n' "$unreferenced"
    printf '\nSkipped tests must reference their ticket (PTCG-NNN) on the same line (Quality Gate 1).\n'
    exit 1
fi
printf 'Skipped tests OK\n'
