#!/usr/bin/env bash
# Tests for the CI gate scripts (PTCG-006).
#
# Each test runs a gate script inside a throwaway git repo, so the working repo is never
# touched. Requires git.
#
# Run from the repository root: bash .github/scripts/ci-gates.test.sh

set -u

SCRIPTS="$(CDPATH="" cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

TMP_ROOT="$(mktemp -d)"
TMP_ROOT="$(cd -- "$TMP_ROOT" && pwd -P)"
trap 'rm -rf "$TMP_ROOT"' EXIT
OUT_FILE="$TMP_ROOT/out"

git_in() {
    local repo="$1"
    shift
    git -C "$repo" -c user.name=test -c user.email=test@example.com -c commit.gpgsign=false "$@"
}

new_repo() {
    local repo
    repo="$(mktemp -d "$TMP_ROOT/repo.XXXXXX")"
    git -C "$repo" init -q
    git -C "$repo" symbolic-ref HEAD refs/heads/main
    git_in "$repo" commit -q --allow-empty -m init
    git -C "$repo" checkout -q -b PTCG-099-demo
    printf '%s\n' "$repo"
}

commit_files() {
    local repo="$1" message="$2" path
    shift 2
    for path in "$@"; do
        mkdir -p "$repo/$(dirname -- "$path")"
        printf '%s\n' "$message" >>"$repo/$path"
        git -C "$repo" add -- "$path"
    done
    git_in "$repo" commit -q -m "$message"
}

write_file() {
    mkdir -p "$1/$(dirname -- "$2")"
    printf '%s\n' "$3" >"$1/$2"
    git -C "$1" add -- "$2"
    git_in "$1" commit -q -m "chore: add $2"
}

run_gate() {
    local repo="$1" script="$2"
    shift 2
    (cd -- "$repo" && bash "$SCRIPTS/$script" "$@") >"$OUT_FILE" 2>&1
}

tdd_gate() {
    run_gate "$1" check-tdd-order.sh main HEAD
}

skipped_gate() {
    run_gate "$1" check-skipped-tests.sh
}

expect_pass() {
    "$@" && return 0
    printf '     expected %s to pass, output:\n' "$1"
    sed 's/^/       /' "$OUT_FILE"
    return 1
}

expect_fail() {
    if "$@"; then
        printf '     expected %s to fail, output:\n' "$1"
        sed 's/^/       /' "$OUT_FILE"
        return 1
    fi
}

expect_output() {
    grep -qF -- "$1" "$OUT_FILE" && return 0
    printf '     expected output to contain [%s], got:\n' "$1"
    sed 's/^/       /' "$OUT_FILE"
    return 1
}

expect_no_output() {
    grep -qF -- "$1" "$OUT_FILE" || return 0
    printf '     expected output not to contain [%s], got:\n' "$1"
    sed 's/^/       /' "$OUT_FILE"
    return 1
}

test_tdd_passes_test_then_feat() {
    local repo
    repo="$(new_repo)"
    commit_files "$repo" "test(PTCG-099): add failing test" backend/tests/test_a.py
    commit_files "$repo" "feat(PTCG-099): make it pass" backend/src/tcg_pokedex/a.py
    expect_pass tdd_gate "$repo"
}

test_tdd_fails_feat_without_test() {
    local repo
    repo="$(new_repo)"
    commit_files "$repo" "feat(PTCG-099): untested feature" backend/src/tcg_pokedex/a.py
    expect_fail tdd_gate "$repo" || return 1
    expect_output "feat(PTCG-099): untested feature"
}

test_tdd_fails_fix_without_test() {
    local repo
    repo="$(new_repo)"
    commit_files "$repo" "fix(PTCG-099): untested fix" frontend/src/App.tsx
    expect_fail tdd_gate "$repo" || return 1
    expect_output "fix(PTCG-099): untested fix"
}

test_tdd_fails_breaking_feat_without_test() {
    local repo
    repo="$(new_repo)"
    commit_files "$repo" "feat!: breaking change" backend/src/tcg_pokedex/a.py
    expect_fail tdd_gate "$repo"
}

test_tdd_requires_one_test_commit_per_feat() {
    local repo
    repo="$(new_repo)"
    commit_files "$repo" "test(PTCG-099): first test" backend/tests/test_a.py
    commit_files "$repo" "feat(PTCG-099): first feature" backend/src/tcg_pokedex/a.py
    commit_files "$repo" "feat(PTCG-099): second feature" backend/src/tcg_pokedex/b.py
    expect_fail tdd_gate "$repo" || return 1
    expect_output "feat(PTCG-099): second feature" || return 1
    expect_no_output "feat(PTCG-099): first feature"
}

test_tdd_allows_other_commits_between_test_and_feat() {
    local repo
    repo="$(new_repo)"
    commit_files "$repo" "test(PTCG-099): add failing test" frontend/src/health/Health.test.tsx
    commit_files "$repo" "build(PTCG-099): add a dependency" frontend/package.json
    commit_files "$repo" "test(PTCG-099): add a test helper" frontend/src/test-utils.tsx
    commit_files "$repo" "feat(PTCG-099): make it pass" frontend/src/health/Health.tsx
    expect_pass tdd_gate "$repo"
}

test_tdd_ignores_test_commit_without_test_files() {
    local repo
    repo="$(new_repo)"
    commit_files "$repo" "test(PTCG-099): mislabelled" backend/src/tcg_pokedex/a.py
    commit_files "$repo" "feat(PTCG-099): feature" backend/src/tcg_pokedex/b.py
    expect_fail tdd_gate "$repo" || return 1
    expect_output "feat(PTCG-099): feature"
}

test_tdd_counts_every_test_location() {
    local repo path
    for path in backend/tests/test_a.py frontend/src/a/A.test.ts frontend/src/a/A.test.tsx \
        frontend/src/test-setup.ts .specify/tests/x.test.sh .github/scripts/ci-gates.test.sh; do
        repo="$(new_repo)"
        commit_files "$repo" "test(PTCG-099): add failing test" "$path"
        commit_files "$repo" "feat(PTCG-099): make it pass" backend/src/tcg_pokedex/a.py
        expect_pass tdd_gate "$repo" || { echo "     test file: $path"; return 1; }
    done
}

test_tdd_gates_every_source_location() {
    local repo path
    for path in backend/src/tcg_pokedex/a.py backend/migrations/versions/0002_x.py \
        frontend/src/a/A.tsx frontend/src/a/a.ts .specify/scripts/bash/common.sh \
        .github/scripts/check-x.sh; do
        repo="$(new_repo)"
        commit_files "$repo" "feat(PTCG-099): untested" "$path"
        expect_fail tdd_gate "$repo" || { echo "     source file: $path"; return 1; }
    done
}

test_tdd_exempts_feat_without_source_changes() {
    local repo
    repo="$(new_repo)"
    commit_files "$repo" "feat(PTCG-099): config, docs and generated code" \
        backend/pyproject.toml frontend/package.json CLAUDE.md .github/workflows/ci.yml \
        frontend/openapi.json frontend/src/api-schema.gen.ts frontend/src/a/A.test.tsx
    expect_pass tdd_gate "$repo"
}

test_tdd_exempt_feat_does_not_consume_the_test_commit() {
    local repo
    repo="$(new_repo)"
    commit_files "$repo" "test(PTCG-099): add failing test" backend/tests/test_a.py
    commit_files "$repo" "feat(PTCG-099): config only" backend/pyproject.toml
    commit_files "$repo" "feat(PTCG-099): make it pass" backend/src/tcg_pokedex/a.py
    expect_pass tdd_gate "$repo"
}

test_tdd_ignores_non_gated_types() {
    local repo
    repo="$(new_repo)"
    commit_files "$repo" "build(PTCG-099): scaffold" frontend/src/main.tsx
    commit_files "$repo" "refactor(PTCG-099): tidy" backend/src/tcg_pokedex/a.py
    commit_files "$repo" "chore: misc" backend/src/tcg_pokedex/b.py
    expect_pass tdd_gate "$repo"
}

test_tdd_checks_only_commits_after_base() {
    local repo
    repo="$(new_repo)"
    git -C "$repo" checkout -q main
    commit_files "$repo" "feat: legacy untested commit on main" backend/src/tcg_pokedex/a.py
    git -C "$repo" checkout -q PTCG-099-demo
    git -C "$repo" rebase -q main
    commit_files "$repo" "test(PTCG-099): add failing test" backend/tests/test_b.py
    commit_files "$repo" "feat(PTCG-099): make it pass" backend/src/tcg_pokedex/b.py
    expect_pass tdd_gate "$repo"
}

test_skipped_passes_without_skips() {
    local repo
    repo="$(new_repo)"
    write_file "$repo" backend/tests/test_a.py $'skipped = 0\n\ndef test_a():\n    assert skipped == 0'
    write_file "$repo" frontend/src/A.test.tsx $'it("skips nothing", () => {\n  expect(skipList).toEqual([]);\n});'
    expect_pass skipped_gate "$repo"
}

test_skipped_fails_unreferenced_skips() {
    local repo line
    for line in '@pytest.mark.skip(reason="flaky")' '@pytest.mark.skip' \
        '@pytest.mark.skipif(sys.platform == "win32", reason="posix only")' \
        '@pytest.mark.xfail(reason="known bug")' '    pytest.skip("not ready")' \
        '@pytest.mark.parametrize("x", [pytest.param(1, marks=pytest.mark.skip)])'; do
        repo="$(new_repo)"
        write_file "$repo" backend/tests/test_a.py $'import pytest\n\n'"$line"
        expect_fail skipped_gate "$repo" || { echo "     line: $line"; return 1; }
        expect_output "backend/tests/test_a.py:3" || return 1
    done
    for line in 'it.skip("later", () => {});' 'test.skip("later", () => {});' \
        'describe.skip("later", () => {});' 'it.skipIf(isCi)("later", () => {});' \
        'it.todo("later");' '  test.todo("later");'; do
        repo="$(new_repo)"
        write_file "$repo" frontend/src/a/A.test.tsx $'import { it } from "vitest";\n\n'"$line"
        expect_fail skipped_gate "$repo" || { echo "     line: $line"; return 1; }
        expect_output "frontend/src/a/A.test.tsx:3" || return 1
    done
}

test_skipped_passes_skips_referencing_a_ticket() {
    local repo
    repo="$(new_repo)"
    write_file "$repo" backend/tests/test_a.py $'import pytest\n\n@pytest.mark.skip(reason="PTCG-031: needs profiles")'
    write_file "$repo" frontend/src/A.test.ts 'it.skip("PTCG-031 shows the profile switcher", () => {});'
    expect_pass skipped_gate "$repo"
}

test_skipped_ignores_non_code_files() {
    local repo
    repo="$(new_repo)"
    write_file "$repo" CLAUDE.md 'Never leave an it.skip or @pytest.mark.skip without a ticket.'
    write_file "$repo" .github/scripts/check-x.sh 'grep -E "pytest\.mark\.skip|it\.skip"'
    expect_pass skipped_gate "$repo"
}

test_skipped_ignores_lookalike_names() {
    local repo
    repo="$(new_repo)"
    write_file "$repo" frontend/src/a.ts $'const audit = { skip: 1 };\nexport const x = edit.skipped + audit.skip;'
    write_file "$repo" backend/src/tcg_pokedex/a.py 'mypytest.skip_all = True'
    expect_pass skipped_gate "$repo"
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
