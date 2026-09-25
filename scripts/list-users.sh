#!/usr/bin/env bash
set -euo pipefail

# List every user in the Cognito pool managed by this Terraform state.

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
infra_dir="$(cd -- "$script_dir/../infra" && pwd)"

region="${REGION:-eu-west-1}"
user_pool_id="$(terraform -chdir="$infra_dir" output -raw cognito_user_pool_id)"

user_count="$(
    aws cognito-idp list-users \
        --user-pool-id "$user_pool_id" \
        --region "$region" \
        --query 'length(Users)' \
        --output text
)"

# AWS's table formatter prints nothing for an empty list. State that case
# explicitly so silence cannot be confused with a failed command.
if [[ "$user_count" == "0" ]]; then
    printf '  no users in %s\n' "$user_pool_id"
    printf '  create one: make create-user EMAIL=you@example.com\n'
    exit 0
fi

# CONFIRMED means the permanent password was set. FORCE_CHANGE_PASSWORD means
# the user still has Cognito's temporary password and must change it on login.
aws cognito-idp list-users \
    --user-pool-id "$user_pool_id" \
    --region "$region" \
    --query "Users[].[Attributes[?Name=='email'].Value|[0],UserStatus,UserCreateDate]" \
    --output table
