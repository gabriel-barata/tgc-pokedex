#!/usr/bin/env bash
# Tests for the PTCG customizations of spec-kit (PTCG-002).
#
# Each test runs the real spec-kit scripts in a throwaway git repo that holds a copy of
# .specify/, so the working repo and its branches are never touched. Requires git and jq.
#
# Run from the repository root: bash .specify/tests/ptcg-customizations.test.sh

set -u

SPECIFY_SRC="$(CDPATH="" cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

# Keep the caller's spec-kit state out of the tests.
unset SPECIFY_FEATURE SPECIFY_FEATURE_DIRECTORY SPECIFY_FEATURE_NO_PERSIST SPECIFY_INIT_DIR

TMP_ROOT="$(mktemp -d)"
TMP_ROOT="$(cd -- "$TMP_ROOT" && pwd -P)"
trap 'rm -rf "$TMP_ROOT"' EXIT
STDERR_FILE="$TMP_ROOT/stderr"

# Creates a repo with a copy of .specify/ and one commit on main, then checks out the
# branch given as $1 (if any). Prints the repo path.
new_repo() {
    local repo
    repo="$(mktemp -d "$TMP_ROOT/repo.XXXXXX")"
    cp -R "$SPECIFY_SRC" "$repo/.specify"
    rm -f "$repo/.specify/feature.json"
    git -C "$repo" init -q
    git -C "$repo" symbolic-ref HEAD refs/heads/main
    git -C "$repo" -c user.name=test -c user.email=test@example.com -c commit.gpgsign=false \
        commit -q --allow-empty -m init
    if [ -n "${1:-}" ]; then
        git -C "$repo" checkout -q -b "$1"
    fi
    printf '%s\n' "$repo"
}

# Runs a spec-kit script from the repo root. Prints its stdout; stderr goes to $STDERR_FILE.
run_in() {
    local repo="$1" script="$2"
    shift 2
    (cd -- "$repo" && bash ".specify/scripts/bash/$script" "$@") 2>"$STDERR_FILE"
}

script_failed() {
    printf '     %s failed:\n' "$1"
    sed 's/^/       /' "$STDERR_FILE"
}

expect_eq() {
    [ "$2" = "$3" ] && return 0
    printf '     %s: expected [%s], got [%s]\n' "$1" "$2" "$3"
    return 1
}

test_specify_names_folder_after_ticket_branch() {
    local repo out
    repo="$(new_repo PTCG-099-demo)"
    out="$(run_in "$repo" create-new-feature.sh --json)" || { script_failed create-new-feature.sh; return 1; }
    expect_eq "BRANCH_NAME" "PTCG-099-demo" "$(jq -r .BRANCH_NAME <<<"$out")" || return 1
    expect_eq "SPEC_FILE" "$repo/specs/PTCG-099-demo/spec.md" "$(jq -r .SPEC_FILE <<<"$out")" || return 1
    expect_eq "spec.md filled from the template" "yes" \
        "$([ -s "$repo/specs/PTCG-099-demo/spec.md" ] && echo yes || echo no)" || return 1
    expect_eq "branches (none created)" "PTCG-099-demo main" \
        "$(git -C "$repo" for-each-ref --format='%(refname:short)' refs/heads | sort | xargs)" || return 1
    expect_eq "current branch" "PTCG-099-demo" "$(git -C "$repo" branch --show-current)"
}

test_specify_refuses_non_ticket_branch() {
    local repo
    repo="$(new_repo)"
    if run_in "$repo" create-new-feature.sh --json >/dev/null; then
        echo "     expected create-new-feature.sh to fail on main"
        return 1
    fi
    expect_eq "error names the ticket branch" "yes" \
        "$(grep -q 'ticket branch' "$STDERR_FILE" && echo yes || echo no)" || return 1
    expect_eq "spec folders" "" "$(ls "$repo/specs" 2>/dev/null)"
}

test_prerequisites_resolve_ticket_branch() {
    local repo out
    repo="$(new_repo PTCG-099-demo)"
    out="$(run_in "$repo" check-prerequisites.sh --json --paths-only)" || { script_failed check-prerequisites.sh; return 1; }
    expect_eq "FEATURE_DIR" "$repo/specs/PTCG-099-demo" "$(jq -r .FEATURE_DIR <<<"$out")" || return 1
    expect_eq "BRANCH" "PTCG-099-demo" "$(jq -r .BRANCH <<<"$out")"
}

test_ticket_branch_wins_over_stale_feature_json() {
    local repo out
    repo="$(new_repo PTCG-011-new)"
    echo '{"feature_directory":"specs/PTCG-010-old"}' >"$repo/.specify/feature.json"
    out="$(run_in "$repo" check-prerequisites.sh --json --paths-only)" || { script_failed check-prerequisites.sh; return 1; }
    expect_eq "FEATURE_DIR" "$repo/specs/PTCG-011-new" "$(jq -r .FEATURE_DIR <<<"$out")"
}

test_env_override_wins_over_ticket_branch() {
    local repo out
    repo="$(new_repo PTCG-011-new)"
    out="$(SPECIFY_FEATURE_DIRECTORY=specs/custom run_in "$repo" check-prerequisites.sh --json --paths-only)" \
        || { script_failed check-prerequisites.sh; return 1; }
    expect_eq "FEATURE_DIR" "$repo/specs/custom" "$(jq -r .FEATURE_DIR <<<"$out")"
}

test_feature_json_used_off_ticket_branch() {
    local repo out
    repo="$(new_repo)"
    echo '{"feature_directory":"specs/PTCG-010-old"}' >"$repo/.specify/feature.json"
    out="$(run_in "$repo" check-prerequisites.sh --json --paths-only)" || { script_failed check-prerequisites.sh; return 1; }
    expect_eq "FEATURE_DIR" "$repo/specs/PTCG-010-old" "$(jq -r .FEATURE_DIR <<<"$out")"
}

FAILURES=0
for test_name in $(declare -F | awk '{print $3}' | grep '^test_'); do
    if ("$test_name"); then
        printf 'ok   %s\n' "$test_name"
    else
        printf 'FAIL %s\n' "$test_name"
        FAILURES=$((FAILURES + 1))
    fi
done

if [ "$FAILURES" -gt 0 ]; then
    printf '\n%d test(s) failed\n' "$FAILURES"
    exit 1
fi
printf '\nall tests passed\n'
