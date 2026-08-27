# Values printed after apply and readable later with `terraform output`. They
# are the boundary between terraform and everything outside it: the Makefile,
# curl, and eventually the connector configuration in ChatGPT.
#
# Outputs are only worth declaring for values that did not exist before apply.
# The region and the resource names are already written in the Makefile; the
# api id inside this URL is invented by AWS and cannot be known in advance.

output "api_url" {
  value       = aws_apigatewayv2_stage.default.invoke_url
  description = "Base URL of the deployed stage. Returns 404 until a route exists."
}