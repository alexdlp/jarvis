

# Select the Lambda execution role based on the current workspace.
#
# Main uses its existing execution role.
# All other branches share the development execution role.
#
# Both roles are managed directly in AWS IAM, outside this Terraform
# configuration. Developers can deploy Lambdas but cannot change
# their execution permissions.
locals {
  lambda_execution_role_name = terraform.workspace == "main" ? (
    "jarvis-mcp-server-role"
  ) : (
    "jarvis-mcp-server-dev-role"
  )
}

# Retrieve the existing IAM role.
#
# A data source reads AWS resources without creating or managing them.
# Terraform uses the resulting ARN when deploying the Lambda function.
data "aws_iam_role" "lambda" {
  name = local.lambda_execution_role_name
}


# Zips whatever the Makefile assembled in build/.
#
# A data source rather than a resource: it creates nothing remote. Reading it
# has the side effect of writing the zip locally, and terraform reads it during
# both plan and destroy — which is why `make destroy` also builds first.
#
# This is the seam between application and infrastructure, and the one piece of
# this configuration that does not really belong to terraform. When the project
# grows, CI builds the zip and uploads it to S3 with a version, and this block
# is replaced by a reference to that object.
data "archive_file" "lambda" {
  type       = "zip"
  source_dir = "${path.module}/../build"

  # dist/ rather than infra/: this is a build artifact and has no business
  # sitting among the terraform configuration. Nor can it live inside build/ —
  # that is source_dir, so the archive would be writing into the very tree it
  # reads and would end up trying to include itself.
  #
  # The provider creates the directory, so nothing has to mkdir it first.
  output_path = "${path.module}/../dist/lambda.zip"
}

# Declared explicitly rather than left to Lambda.
#
# Two reasons. Lambda creates the group on first invocation with no expiry, so
# logs accumulate forever and nobody notices. And a group created that way is
# not tracked by terraform, so `destroy` leaves it behind.
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/jarvis-mcp-server${local.resource_suffix}"
  retention_in_days = 14
}

resource "aws_lambda_function" "mcp_server" {
  function_name = "jarvis-mcp-server${local.resource_suffix}"
  role = data.aws_iam_role.lambda.arn
  runtime       = "python3.13"

  # arm64 costs roughly 20% less per GB-second than x86_64 for identical work.
  # The trade is wheel availability for compiled dependencies, which is good
  # for everything this project needs.
  architectures = ["arm64"]

  # "package.module.function". For this to resolve, the zip must contain a
  # jarvis/ directory with an __init__.py — which is why the build copies the
  # folder rather than the single file.
  handler = "jarvis.lambda_handler.handler"

  filename = data.archive_file.lambda.output_path

  # What makes terraform notice the code changed. `filename` is the same string
  # on every apply, so without this a code change produces "No changes" and the
  # old zip stays deployed.
  source_code_hash = data.archive_file.lambda.output_base64sha256

  # The default is 3 seconds, which is not enough for a cold start once the MCP
  # SDK and pydantic have to be imported.
  timeout = 30

  # Memory also determines CPU share in Lambda: they are not separate dials.
  # Raising this speeds up cold starts, and can lower the bill rather than
  # raise it, because duration drops faster than the per-millisecond price
  # rises.
  memory_size = 512

  # The Lambda log group must exist before the function is deployed.
  #
  # IAM permissions are managed outside this Terraform configuration,
  # so no IAM policy resources are required as dependencies.
  depends_on = [
    aws_cloudwatch_log_group.lambda,
  ]

  # The metadata document has to name its own URL and its issuer, and neither
  # exists until apply. Passing them in from terraform keeps the values in the
  # one place that knows them, instead of hardcoding account-specific ids into
  # the source.
  #
  # Built from the api id rather than the stage's invoke_url on purpose: the
  # stage would add a dependency the function does not otherwise need.
  environment {
    variables = {
      MCP_RESOURCE_URL    = "https://${aws_apigatewayv2_api.main.id}.execute-api.${var.region}.amazonaws.com/mcp"
      COGNITO_ISSUER      = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.users.id}"
      MCP_AUTH_SERVER_URL = "https://${aws_apigatewayv2_api.main.id}.execute-api.${var.region}.amazonaws.com"
      COGNITO_DOMAIN_URL  = "https://${aws_cognito_user_pool_domain.auth.domain}.auth.${var.region}.amazoncognito.com"

      # Read from the resource rather than written as "jarvis" a second time.
      # The name is knowable without applying, so this buys nothing at deploy
      # time — it buys the dependency edge, which makes terraform create the
      # table before the function that reads it.
      JARVIS_TABLE_NAME = aws_dynamodb_table.main.name
    }
  }
}

