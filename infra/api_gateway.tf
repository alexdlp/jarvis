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

  # Default throttling for routes in this stage.
  #
  # API Gateway uses a token bucket:
  # - burst = maximum short spike it can absorb;
  # - rate  = sustained request rate in requests per second.
  #
  # Each request consumes one token. If none are available, API Gateway may
  # return HTTP 429 before invoking Lambda.
  #
  # A connector handshake was measured at 7 requests over 4 seconds, so a burst
  # of 10 refilling at 5/s absorbs it with room to spare while still capping a
  # runaway client. The discovery route will share this same bucket.
  default_route_settings {
    throttling_burst_limit = 10
    throttling_rate_limit  = 5

    # Publish route-level CloudWatch metrics, including throttled requests.
    detailed_metrics_enabled = true
  }
  # What the gateway saw, including requests the JWT authorizer rejected before
  # any lambda ran. Those produce no lambda log at all, so without this an
  # authentication failure is indistinguishable from a missing route: both look
  # like silence.
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api.arn

    # $context.authorizer.error is the field that says *why* a token was
    # refused. It is the whole reason this block exists.
    format = jsonencode({
      requestId      = "$context.requestId"
      httpMethod     = "$context.httpMethod"
      path           = "$context.path"
      status         = "$context.status"
      authorizerErr  = "$context.authorizer.error"
      integrationErr = "$context.integrationErrorMessage"
      responseLength = "$context.responseLength"
    })
  }
}

# Access logs for the API itself, separate from the lambda's own log group.
#
# These two record different things and one cannot replace the other: the
# lambda group holds what the code printed, this one holds what the gateway
# decided. A request the JWT authorizer rejects never invokes the lambda, so it
# leaves no trace whatsoever in the other group.
resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/apigateway/jarvis-api"
  retention_in_days = 14
}
# -----------------------------------------------------------------------------
# API Gateway -> Lambda wiring
# -----------------------------------------------------------------------------
#
# Three resources are required:
#
# - integration: which backend API Gateway invokes;
# - route: which requests use that integration;
# - permission: whether API Gateway may invoke the Lambda.
#

# Lambda proxy integration.
#
# API Gateway forwards the HTTP request as a Lambda event and uses the Lambda
# result as the HTTP response, without request/response mapping templates.
resource "aws_apigatewayv2_integration" "mcp" {
  api_id           = aws_apigatewayv2_api.main.id
  integration_type = "AWS_PROXY"

  # API Gateway requires Lambda's invocation ARN rather than its resource ARN.
  integration_uri = aws_lambda_function.mcp_server.invoke_arn

  # API Gateway invokes Lambda internally using POST, regardless of the HTTP
  # method used by the MCP client on /mcp.
  integration_method = "POST"

  # HTTP API payload format v2.0 defines the event and response structure seen
  # by the Lambda handler.
  payload_format_version = "2.0"
}


# Route all HTTP methods for the MCP endpoint to the Lambda integration.
#
# POST is the main method used by our stateless MCP transport. ANY also keeps
# compatibility with clients that may use GET or DELETE for stream/session
# handling.
#
# Requests to other paths are not matched and therefore do not invoke Lambda.
resource "aws_apigatewayv2_route" "mcp" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "ANY /mcp"

  target = "integrations/${aws_apigatewayv2_integration.mcp.id}"

  # Closes this route. The metadata route deliberately stays open next to it.
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}


# Allow API Gateway to invoke the MCP Lambda.
#
# This is a resource-based policy on the Lambda function. It is independent
# from the Lambda execution role:
#
# - execution role: what Lambda may access;
# - lambda permission: who may invoke Lambda.
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowInvokeFromApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.mcp_server.function_name
  principal     = "apigateway.amazonaws.com"

  # Restrict this permission to requests originating from this API.
  #
  # The wildcards allow every stage, HTTP method and route belonging to it.
  source_arn = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}

# The discovery document, reachable without a token.
#
# A separate route from /mcp because it must stay unauthenticated once the JWT
# authorizer lands on that one: this is what an unauthenticated client reads in
# order to authenticate.
#
# The path is not arbitrary. When a 401 carries no WWW-Authenticate pointer —
# which is exactly what API Gateway's JWT authorizer returns — Claude falls
# back to probing the origin at /.well-known/oauth-protected-resource/<mcp
# path>. That is the path below, and matching it is what makes the plain 401
# from the authorizer good enough.
#
# It shares the stage's throttling bucket with /mcp.
resource "aws_apigatewayv2_route" "oauth_metadata" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /.well-known/oauth-protected-resource/mcp"

  target = "integrations/${aws_apigatewayv2_integration.mcp.id}"
}

# The door itself: API Gateway validates the token before anything else runs.
#
# Doing it here rather than in the lambda means a request without a valid token
# costs nothing — no invocation, no billed duration. It also means AWS owns the
# cryptography: fetching Cognito's public keys, checking the signature, the
# issuer and the expiry. The SDK offers only an empty TokenVerifier interface,
# so the alternative was writing all of that by hand.
#
# The trade is that this component is closed: its 401 carries no body and no
# headers we can add, which is why the metadata document has to be discoverable
# at a conventional path instead of being pointed at from the refusal.
resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id          = aws_apigatewayv2_api.main.id
  name            = "cognito-jwt"
  authorizer_type = "JWT"

  # Where to read the token from. Anything else is rejected before validation.
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    # Who the token must have been issued for. This is what stops a token
    # minted for some other app in the same user pool from opening this door.
    audience = [aws_cognito_user_pool_client.claude.id]

    # Where the public keys come from: the gateway appends
    # /.well-known/jwks.json to this and caches the result.
    issuer = "https://cognito-idp.${var.region}.amazonaws.com/${aws_cognito_user_pool.users.id}"
  }
}