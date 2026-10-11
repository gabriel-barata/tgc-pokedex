#!/usr/bin/env bash
# Create the spec folder for the current ticket.
#
# PTCG customization: one card = one branch = one spec folder (see CLAUDE.md). The branch
# is created from the card's Branch field before spec-kit runs, and the spec folder is named
# after it: on branch PTCG-NNN-<short-slug> this creates specs/PTCG-NNN-<short-slug>/spec.md.
# It never creates or switches branches, and spec-kit's sequential/timestamp numbering is
# not used.

set -e

JSON_MODE=false
ALLOW_EXISTING=false
for arg in "$@"; do
    case "$arg" in
        --json)
            JSON_MODE=true
            ;;
        --allow-existing-branch)
            ALLOW_EXISTING=true
            ;;
        --help|-h)
            echo "Usage: $0 [--json] [--allow-existing-branch]"
            echo ""
            echo "Run on a PTCG-NNN-<short-slug> ticket branch. Creates specs/<branch>/spec.md"
            echo "from the spec template."
            echo ""
            echo "Options:"
            echo "  --json                   Output in JSON format"
            echo "  --allow-existing-branch  Reuse the feature directory if it already exists"
            echo "  --help, -h               Show this help message"
            exit 0
            ;;
        *)
            echo "ERROR: Unknown argument '$arg'. Use --help for usage information." >&2
            exit 1
            ;;
    esac
done

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

REPO_ROOT=$(get_repo_root) || exit 1
cd "$REPO_ROOT"

if ! BRANCH_NAME=$(get_ticket_branch "$REPO_ROOT"); then
    echo "ERROR: Not on a ticket branch. Switch to the card's PTCG-NNN-<short-slug> branch (see CLAUDE.md) and run the specify command again." >&2
    exit 1
fi

FEATURE_DIR="$REPO_ROOT/specs/$BRANCH_NAME"
SPEC_FILE="$FEATURE_DIR/spec.md"

if [ -d "$FEATURE_DIR" ] && [ "$ALLOW_EXISTING" != true ]; then
    echo "ERROR: Feature directory '$FEATURE_DIR' already exists. Use --allow-existing-branch to reuse it." >&2
    exit 1
fi

if [ ! -f "$SPEC_FILE" ]; then
    # Resolve the template before creating the directory, so a resolution error leaves nothing behind.
    if SPEC_TEMPLATE_CONTENT=$(resolve_template_content "spec-template" "$REPO_ROOT"; status=$?; printf x; exit "$status"); then
        SPEC_TEMPLATE_CONTENT="${SPEC_TEMPLATE_CONTENT%x}"
        mkdir -p "$FEATURE_DIR"
        printf '%s' "$SPEC_TEMPLATE_CONTENT" > "$SPEC_FILE"
    else
        resolve_status=$?
        if [ "$resolve_status" -ne 1 ]; then
            exit "$resolve_status"
        fi
        echo "Warning: Spec template not found; created empty spec file" >&2
        mkdir -p "$FEATURE_DIR"
        touch "$SPEC_FILE"
    fi
fi

# Keep .specify/feature.json in step, so it stays a usable fallback off ticket branches,
# unless the orchestrator opted out via SPECIFY_FEATURE_NO_PERSIST.
if [[ "${SPECIFY_FEATURE_NO_PERSIST:-}" != "1" && "${SPECIFY_FEATURE_NO_PERSIST:-}" != "true" ]]; then
    _persist_feature_json "$REPO_ROOT" "$FEATURE_DIR"
fi

if $JSON_MODE; then
    if has_jq; then
        jq -cn \
            --arg branch_name "$BRANCH_NAME" \
            --arg feature_dir "$FEATURE_DIR" \
            --arg spec_file "$SPEC_FILE" \
            '{BRANCH_NAME:$branch_name,FEATURE_DIR:$feature_dir,SPEC_FILE:$spec_file}'
    else
        printf '{"BRANCH_NAME":"%s","FEATURE_DIR":"%s","SPEC_FILE":"%s"}\n' \
            "$(json_escape "$BRANCH_NAME")" "$(json_escape "$FEATURE_DIR")" "$(json_escape "$SPEC_FILE")"
    fi
else
    echo "BRANCH_NAME: $BRANCH_NAME"
    echo "FEATURE_DIR: $FEATURE_DIR"
    echo "SPEC_FILE: $SPEC_FILE"
fi
