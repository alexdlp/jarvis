# =============================================================================
# Cognito
# =============================================================================
#
# Cognito is the OAuth 2.0 / OpenID Connect authorization server used to
# authenticate users before they can access the Jarvis MCP API.
#
# Authentication flow:
#
#   User
#    ↓
#   Claude
#    ↓ OAuth 2.0 Authorization Code + PKCE
#   Cognito
#    ↓ access_token (JWT)
#   Claude
#    ↓ Authorization: Bearer <JWT>
#   API Gateway
#    ↓
#   Lambda
#    ↓
#   MCP server
#
# Cognito is responsible only for identity, authentication and token issuance.
# It does not execute MCP tools or store Jarvis application data.
# =============================================================================


# -----------------------------------------------------------------------------
# User Pool
# -----------------------------------------------------------------------------
#
# The User Pool is the identity directory and token issuer.
#
# It stores users and credentials and signs the JWT tokens issued after
# successful authentication.
#
resource "aws_cognito_user_pool" "users" {
  name = "jarvis-users"

  # Users authenticate using their email address instead of a separate
  # username.
  #
  # IMPORTANT:
  # Cognito sign-in attributes cannot be changed after the User Pool has been
  # created. Changing this design requires replacing the User Pool and
  # migrating its users.
  username_attributes = ["email"]

  # Cognito manages email verification.
  #
  # A verified email is also required for standard email-based account
  # recovery flows. Without a verified recovery attribute, a forgotten
  # password can leave the user without a self-service recovery path.
  auto_verified_attributes = ["email"]

  # Disable public self-registration.
  #
  # OAuth client IDs are public information. Without this restriction, an
  # external caller could use Cognito's SignUp API to create an account in
  # this User Pool.
  #
  # Jarvis users must therefore be created explicitly by an administrator.
  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  # Password policy for local Cognito users.
  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = true
  }

  # Deliberately not configured yet:
  #
  # - MFA: can be added once the basic OAuth flow works.
  # - External identity providers: Google/SAML/OIDC are not needed yet.
  # - Lambda triggers: no authentication customization is currently needed.
  # - Custom schema attributes: Jarvis currently needs only standard identity
  #   attributes.
}


# -----------------------------------------------------------------------------
# OAuth Domain
# -----------------------------------------------------------------------------
#
# The User Pool exposes AWS service APIs by itself, but browser-based OAuth
# clients need the standard OAuth HTTP surface:
#
#   /oauth2/authorize
#   /oauth2/token
#
# The Cognito domain provides those endpoints together with Cognito's managed
# login UI.
#
# Example:
#
# https://jarvis-auth.auth.eu-west-1.amazoncognito.com/oauth2/authorize
#
resource "aws_cognito_user_pool_domain" "auth" {
  # Cognito domain prefixes must be unique within an AWS Region across AWS
  # accounts because they become part of a shared amazoncognito.com hostname.
  #
  # Change this value if Terraform reports that the prefix is already taken.
  domain = "jarvis-auth"

  user_pool_id = aws_cognito_user_pool.users.id
}


# -----------------------------------------------------------------------------
# OAuth Resource Server
# -----------------------------------------------------------------------------
#
# Despite its AWS name, this resource DOES NOT create an HTTP server.
#
# The actual resource server is:
#
#   API Gateway -> Lambda -> MCP
#
# This Cognito resource only defines application-specific OAuth scopes that can
# be included in access tokens.
#
resource "aws_cognito_resource_server" "mcp" {
  identifier   = "jarvis-mcp"
  name         = "Jarvis MCP"
  user_pool_id = aws_cognito_user_pool.users.id

  # Claude must have this scope in its access token to use the Jarvis MCP
  # task-management capabilities.
  #
  # Resulting OAuth scope:
  #
  #   jarvis-mcp/tasks
  scope {
    scope_name        = "tasks"
    scope_description = "Access Jarvis task-management tools"
  }
}


# -----------------------------------------------------------------------------
# OAuth App Client: Claude
# -----------------------------------------------------------------------------
#
# An App Client is Cognito's registration of an OAuth client.
#
# It does not deploy or host Claude. It tells Cognito:
#
#   - which OAuth flows Claude may use;
#   - which scopes Claude may request;
#   - which redirect URLs Cognito may return authorization codes to.
#
# Cognito generates a client_id for this registration.
#
resource "aws_cognito_user_pool_client" "claude" {
  name         = "claude-connector"
  user_pool_id = aws_cognito_user_pool.users.id

  # Claude is a public OAuth client.
  #
  # No client secret is required. Authorization Code + PKCE protects the
  # authorization flow instead.
  generate_secret = false

  # Enable OAuth configuration for this App Client.
  allowed_oauth_flows_user_pool_client = true

  # Authorization Code Grant:
  #
  #   Claude -> /authorize
  #          -> user login
  #          -> authorization code
  #
  #   Claude -> /token + code + PKCE verifier
  #          -> access / ID / refresh tokens
  allowed_oauth_flows = ["code"]

  # Authentication is currently performed directly by Cognito.
  #
  # No Google, Microsoft, SAML or other external identity provider is used.
  supported_identity_providers = ["COGNITO"]

  # Scopes that Claude is allowed to request.
  #
  # openid/email/profile:
  #   OIDC identity information.
  #
  # jarvis-mcp/tasks:
  #   authorization to access Jarvis task-management capabilities.
  allowed_oauth_scopes = [
    "openid",
    "email",
    "profile",
    "${aws_cognito_resource_server.mcp.identifier}/tasks",
  ]

  # Cognito only redirects authorization codes to explicitly registered URLs.
  #
  # This prevents an attacker from supplying their own redirect_uri and
  # stealing an authorization code.
  callback_urls = [
    # Claude.ai / Claude Desktop connector.
    "https://claude.ai/api/mcp/auth_callback",

    # Claude Code uses a local loopback callback.
    #
    # Cognito requires exact callback URL matching, so a fixed port is used.
    # Configure Claude Code to use the same port.
    "http://localhost:29352/callback",
  ]

  # These explicitly restate Cognito's normal token lifetimes so that the
  # security behaviour is visible in Terraform rather than implicit.
  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # Explicitly preserve Cognito's secure behaviour for newly created clients:
  # refresh tokens can be revoked when the connector is disconnected or access
  # must otherwise be invalidated.
  enable_token_revocation = true

  # Prevent authentication responses from revealing whether a particular user
  # exists in the User Pool.
  prevent_user_existence_errors = "ENABLED"

  # Deliberately not configured:
  #
  # explicit_auth_flows:
  #   Claude uses the OAuth Authorization Code + PKCE flow above.
  #   ALLOW_ADMIN_USER_PASSWORD_AUTH would only be useful temporarily for
  #   direct CLI testing and should not be enabled just for convenience.
}