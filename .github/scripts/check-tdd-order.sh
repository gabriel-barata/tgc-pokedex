#!/usr/bin/env bash
# TDD-order gate (constitution, Principle I). Every feat/fix commit in BASE..HEAD that changes
# source files needs its own test commit, one that changes test files, after the previous
# gated feat/fix. Other commit types and feat/fix commits without source changes are exempt.
#
# Usage: check-tdd-order.sh BASE HEAD

set -euo pipefail

is_test_file() {
    case "$1" in
        backend/tests/* | .specify/tests/* | frontend/src/test-*) return 0 ;;
        frontend/*.test.ts | frontend/*.test.tsx | .github/scripts/*.test.sh) return 0 ;;
    esac
    return 1
}

is_source_file() {
    is_test_file "$1" && return 1
    case "$1" in
        *.gen.ts) return 1 ;;
        backend/src/* | backend/migrations/* | frontend/src/*) return 0 ;;
        .specify/scripts/* | .github/scripts/*) return 0 ;;
    esac
    return 1
}

touches() {
    local predicate="$1" commit="$2" path
    while IFS= read -r path; do
        "$predicate" "$path" && return 0
    done < <(git diff-tree --no-commit-id --name-only -r --root "$commit")
    return 1
}

base="$1"
head="$2"
test_pending=no
checked=0
violations=0

for commit in $(git rev-list --reverse --no-merges "$base..$head"); do
    checked=$((checked + 1))
    subject="$(git log -1 --format=%s "$commit")"
    type="$(sed -nE 's/^([a-z]+)(\([^)]*\))?!?:.*/\1/p' <<<"$subject")"
    case "$type" in
        test)
            if touches is_test_file "$commit"; then
                test_pending=yes
            fi
            ;;
        feat | fix)
            if touches is_source_file "$commit"; then
                if [ "$test_pending" = yes ]; then
                    test_pending=no
                else
                    printf '%s %s: changes source with no test commit since the previous feat/fix\n' \
                        "$(git rev-parse --short "$commit")" "$subject"
                    violations=$((violations + 1))
                fi
            fi
            ;;
    esac
done

if [ "$violations" -gt 0 ]; then
    printf '\n%d commit(s) break the TDD order (Principle I): commit a failing test first, then the feat/fix.\n' \
        "$violations"
    exit 1
fi
printf 'TDD order OK (%d commit(s) checked)\n' "$checked"
