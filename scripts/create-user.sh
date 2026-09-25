#!/usr/bin/env bash
set -euo pipefail

# Create one Cognito user without making user creation part of Terraform.
# This operation is intentionally separate from deployment because it is not
# idempotent: running it twice for the same email must fail.

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
infra_dir="$(cd -- "$script_dir/../infra" && pwd)"

region="${REGION:-eu-west-1}"
email="${EMAIL:-}"

if [[ -z "$email" ]]; then
    printf '  EMAIL is required  make create-user EMAIL=you@example.com\n' >&2
    exit 1
fi

user_pool_id="$(terraform -chdir="$infra_dir" output -raw cognito_user_pool_id)"

# Reading the password interactively keeps it out of shell history. Cognito's
# CLI accepts the password as an argument, so it can briefly be visible to
# another process owned by the same operating-system user.
read -r -s -p "  Password for $email: " password
printf '\n'

# SUPPRESS avoids sending Cognito's temporary-password invitation. Since that
# also skips email verification, mark the address verified explicitly so that
# Cognito can use it for account recovery later.
aws cognito-idp admin-create-user \
    --user-pool-id "$user_pool_id" \
    --username "$email" \
    --user-attributes "Name=email,Value=$email" Name=email_verified,Value=true \
    --message-action SUPPRESS \
    --region "$region" \
    >/dev/null

# Replace Cognito's temporary password with the chosen permanent password so
# the first login does not enter the FORCE_CHANGE_PASSWORD flow.
aws cognito-idp admin-set-user-password \
    --user-pool-id "$user_pool_id" \
    --username "$email" \
    --password "$password" \
    --permanent \
    --region "$region"

printf '  created  %s\n' "$email"
