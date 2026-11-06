# Read the AWS account ID to build the parameter's exact ARN.
data "aws_caller_identity" "current" {}

locals {
  # All branches use the same externally managed parameter.
  google_oauth_client_parameter_name = "jarvis-google-oauth-client"
}

