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


# Two things will need this: the protected resource metadata document, which
# names it as the authorization server, and the API Gateway JWT authorizer,
# which uses it to fetch the pool's public signing keys.
output "cognito_issuer" {
  value       = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.users.id}"
  description = "OIDC issuer URL of the user pool."
}

# Typed into the MCP client's connector configuration by hand, since Cognito
# cannot register clients dynamically.
output "cognito_client_id" {
  value       = aws_cognito_user_pool_client.claude.id
  description = "OAuth client id for the Claude connector."
}

# Base URL of the hosted OAuth endpoints.
#
# This one breaks the rule stated at the top: the prefix is written by hand in
# cognito.tf, so the URL is knowable without applying. It earns its place
# because it is the base for /oauth2/authorize and /oauth2/token and gets typed
# into a browser repeatedly while testing the flow, where a mistyped region or
# suffix fails with an unhelpful error.
#
# Built from the resource attribute rather than the literal "jarvis-auth" so it
# follows the prefix automatically if a collision ever forces it to change.
output "cognito_domain_url" {
  value       = "https://${aws_cognito_user_pool_domain.auth.domain}.auth.${var.region}.amazoncognito.com"
  description = "Base URL of the hosted OAuth endpoints (/oauth2/authorize, /oauth2/token)."
}


# Required by every `aws cognito-idp` command: creating users, resetting
# passwords, inspecting the pool. It is embedded in the issuer URL above, but
# slicing it back out of a URL on every invocation is worse than publishing it.
output "cognito_user_pool_id" {
  value       = aws_cognito_user_pool.users.id
  description = "User pool id, for the aws cognito-idp CLI."
}