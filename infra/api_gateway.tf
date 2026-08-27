# API Gateway HTTP API and the stage that publishes it.
#
# HTTP API (apigatewayv2) rather than REST API (apigateway): roughly a third of
# the per-request cost, less configuration, and native JWT authorizers — the
# mechanism that will let the gateway reject invalid tokens before any lambda
# is invoked, once authentication exists.
#
# What this choice gives up: AWS WAF cannot attach to an HTTP API, and HTTP
# APIs cannot stream a lambda response. Response streaming is REST-only so 
# emitting MCP progress notifications or SSE would mean moving the front 
# door to a REST API or a lambda function URL. Neither is needed while every 
# tool is a short request/response call.

resource "aws_apigatewayv2_api" "main" {
  name = "jarvis-api"

  # "HTTP" as opposed to "WEBSOCKET". MCP's streamable transport runs over
  # plain HTTP; the long-lived SSE half of that transport is the part this
  # deployment deliberately does not use.
  protocol_type = "HTTP"
}

# API Gateway derives an execute-api endpoint from the api's id. The stage
# publishes a deployment at that endpoint and, unless it is named "$default",
# contributes its own name as the first path segment:
#
#   stage "$default"  ->  https://<id>.execute-api.<region>.amazonaws.com/mcp
#   stage "prod"      ->  https://<id>.execute-api.<region>.amazonaws.com/prod/mcp
#
# One api can carry several stages at once, each publishing a different
# snapshot at a different path. That one-to-many relationship is why these are
# two resources rather than one.
resource "aws_apigatewayv2_stage" "default" {
  api_id = aws_apigatewayv2_api.main.id
  name   = "$default"

  # Route and integration changes go live as soon as terraform applies them.
  # Without this, every change also needs an aws_apigatewayv2_deployment
  # resource to snapshot the definition — ceremony that only earns its keep
  # when several stages must sit at different versions.
  auto_deploy = true
}