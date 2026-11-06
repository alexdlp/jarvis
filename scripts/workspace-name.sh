#!/usr/bin/env bash

# Stop on unhandled errors, undefined variables and failed pipeline commands.
set -euo pipefail

# Read the active Git branch.
# A detached HEAD has no branch name, so it must not select a deployment.
if ! branch="$(git symbolic-ref --quiet --short HEAD)"; then
    printf 'An active Git branch is required to identify the workspace.\n' >&2
    exit 1
fi

# Accept lowercase words and numbers, with single hyphens inside each segment
# and slashes between segments. Examples: main, feature/add-task, fix/oauth.
#
# Rejecting double hyphens in branch names reserves "--" for encoding "/".
# This keeps feature/add-task distinct from feature-add-task.
branch_pattern='^[a-z0-9]+(-[a-z0-9]+)*(/[a-z0-9]+(-[a-z0-9]+)*)*$'

if [[ ! "$branch" =~ $branch_pattern ]]; then
    printf 'Unsupported branch name: %s\n' "$branch" >&2
    printf 'Use lowercase words and numbers, single hyphens and slashes.\n' >&2
    exit 1
fi

# Convert each slash into two hyphens.
# Example: feature/add-task becomes feature--add-task.
workspace="${branch//\//--}"

# IAM role names allow at most 64 characters.
# "jarvis-mcp-server-role-" uses 23, leaving 41 for the workspace.
# Reject longer names instead of truncating them and risking collisions.
if (( ${#workspace} > 41 )); then
    printf 'Workspace name exceeds the 41-character limit: %s\n' "$workspace" >&2
    exit 1
fi

# Terraform reserves "default" for its built-in workspace.
# Jarvis deployments use explicitly named workspaces instead.
if [[ "$workspace" == "default" ]]; then
    printf 'The branch name "default" is reserved and cannot be deployed.\n' >&2
    exit 1
fi

# Print only the workspace name so other scripts can consume this value.
printf '%s\n' "$workspace"
