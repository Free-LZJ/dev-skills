#!/usr/bin/env bash
#
# Check superpowers availability for requirements-delivery skill.
#
# Output: installed | declined | not-installed
# Exit code: 0=installed, 1=declined, 2=not-installed
#
# Cache file: ~/.agents/.superpowers-status
#   installed  — superpowers is available, skip prompt
#   declined   — user previously declined, skip prompt
#   (empty)    — not yet checked, prompt user

set -e

CACHE="$HOME/.agents/.superpowers-status"
CORE_SKILLS=("brainstorming" "writing-plans" "systematic-debugging")
SEARCH_DIRS=("$HOME/.agents/skills" "$HOME/.claude/skills")

# Read cache
if [ -f "$CACHE" ]; then
    STATUS=$(cat "$CACHE" | tr -d '[:space:]')
    if [ "$STATUS" = "installed" ]; then
        echo "installed"
        exit 0
    fi
    if [ "$STATUS" = "declined" ]; then
        echo "declined"
        exit 1
    fi
fi

# No valid cache — check actual installation
FOUND=0
for dir in "${SEARCH_DIRS[@]}"; do
    for skill in "${CORE_SKILLS[@]}"; do
        if [ -d "$dir/$skill" ]; then
            FOUND=1
            break 2
        fi
    done
done

if [ "$FOUND" -eq 1 ]; then
    mkdir -p "$HOME/.agents"
    echo "installed" > "$CACHE"
    echo "installed"
    exit 0
fi

echo "not-installed"
exit 2