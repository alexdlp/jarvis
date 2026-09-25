#!/usr/bin/env bash
set -euo pipefail

# Inspect every item in the deployed DynamoDB table. This is an operator-only
# full-table Scan; the Lambda role intentionally remains unable to Scan so this
# debugging command cannot become an application access pattern by accident.

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
infra_dir="$(cd -- "$script_dir/../infra" && pwd)"

region="${REGION:-eu-west-1}"

# Read the deployed resource name from Terraform state instead of copying the
# literal table name into this script. state pull does not refresh or modify
# infrastructure; it only returns Terraform's current state as JSON.
table_name="$(
    terraform -chdir="$infra_dir" state pull |
        jq -er '
            .resources[]
            | select(.type == "aws_dynamodb_table" and .name == "main")
            | .instances[0].attributes.name
        '
)"

# AWS CLI follows DynamoDB pagination automatically, so Items contains the
# whole table even when Scan needs more than one service response. A consistent
# read makes a just-written item visible to this debugging command immediately.
scan_result="$(
    aws dynamodb scan \
        --table-name "$table_name" \
        --consistent-read \
        --region "$region" \
        --output json \
        --no-cli-pager
)"

item_count="$(jq -er '.Items | length' <<<"$scan_result")"

if [[ "$item_count" == "0" ]]; then
    printf '  no items in %s\n' "$table_name"
    exit 0
fi

printf '  %s item(s) in %s\n' "$item_count" "$table_name"

# DynamoDB represents every value with an explicit type wrapper, for example
# {"S":"inbox"} or {"N":"30"}. Decode those wrappers recursively so the
# terminal shows ordinary JSON while retaining every stored attribute.
jq '
    def decode_attribute:
        if has("S") then .S
        elif has("N") then (.N | tonumber)
        elif has("BOOL") then .BOOL
        elif has("NULL") then null
        elif has("B") then .B
        elif has("SS") then .SS
        elif has("NS") then [.NS[] | tonumber]
        elif has("BS") then .BS
        elif has("L") then [.L[] | decode_attribute]
        elif has("M") then (.M | with_entries(.value |= decode_attribute))
        else .
        end;

    [
        .Items[]
        | with_entries(.value |= decode_attribute)
    ]
    | sort_by([.pk, .sk])
' <<<"$scan_result"
