#!/usr/bin/env bash

# Print the Lambda and API Gateway logs as a single chronological stream.
#
# Usage through the Makefile:
#
#   make logs              Follow new events with CloudWatch Live Tail.
#   make logs MINUTES=15   Print events from the last fifteen minutes.
#
# REGION and MINUTES arrive as environment variables so the Makefile remains
# the public interface. Resolving the repository from this file also keeps the
# script usable when make is invoked outside the repository root.

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
infra_dir="$(cd -- "$script_dir/../infra" && pwd)"
region="${REGION:-eu-west-1}"
minutes_raw="${MINUTES:-}"

# Validate before contacting Terraform or AWS so a typo fails immediately.
if [[ -n "$minutes_raw" ]]; then
    if [[ ! "$minutes_raw" =~ ^[0-9]+$ ]]; then
        printf 'MINUTES must be a positive integer\n' >&2
        exit 2
    fi

    # 10# forces base ten, so values such as 08 are not treated as octal.
    minutes=$((10#$minutes_raw))
    if ((minutes == 0)); then
        printf 'MINUTES must be a positive integer\n' >&2
        exit 2
    fi
fi

# Live Tail requires log group ARNs. Read the deployed resources directly
# from Terraform state so this command does not depend on outputs being added by
# a later apply. state pull is read-only and does not refresh infrastructure.
terraform_state="$(terraform -chdir="$infra_dir" state pull)"

log_group_arn() {
    local resource_name="$1"

    jq -er --arg resource_name "$resource_name" '
        .resources[]
        | select(
            .type == "aws_cloudwatch_log_group"
            and .name == $resource_name
        )
        | .instances[0].attributes.arn
    ' <<<"$terraform_state"
}

lambda_log_arn="$(log_group_arn lambda)"
api_log_arn="$(log_group_arn api)"

if [[ -z "$minutes_raw" ]]; then
    printf 'Following Lambda and API Gateway logs; stop with Ctrl+C\n'

    # exec lets Ctrl+C reach the AWS CLI process directly instead of leaving a
    # wrapper shell between the terminal and the Live Tail session.
    exec aws logs start-live-tail \
        --log-group-identifiers "$lambda_log_arn" "$api_log_arn" \
        --mode print-only \
        --region "$region" \
        --no-cli-pager
fi

end_time="$(date +%s)"
start_time=$((end_time - minutes * 60))

# Logs Insights starts queries asynchronously and returns only an id. Polling
# is required before the final results are complete.
query_id="$(aws logs start-query \
    --log-group-identifiers "$lambda_log_arn" "$api_log_arn" \
    --start-time "$start_time" \
    --end-time "$end_time" \
    --query-string 'fields @timestamp, @log, @message | sort @timestamp asc' \
    --query queryId \
    --output text \
    --region "$region" \
    --no-cli-pager)"

while true; do
    query_status="$(aws logs get-query-results \
        --query-id "$query_id" \
        --query status \
        --output text \
        --region "$region" \
        --no-cli-pager)"

    case "$query_status" in
        Complete)
            break
            ;;
        Scheduled | Running)
            sleep 1
            ;;
        *)
            printf 'Log query ended with status %s\n' "$query_status" >&2
            exit 1
            ;;
    esac
done

printf 'Lambda and API Gateway logs from the last %s minutes\n' "$minutes"

# @ptr is an internal CloudWatch pointer. The other three values are the event
# time, source log group and message, in that order.
aws logs get-query-results \
    --query-id "$query_id" \
    --query 'results[*][?field!=`@ptr`].value' \
    --output text \
    --region "$region" \
    --no-cli-pager
