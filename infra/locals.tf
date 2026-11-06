locals {
  # Preserve existing names in main.
  # Other workspaces append their name after a hyphen.
  resource_suffix = terraform.workspace == "main" ? "" : "-${terraform.workspace}"
}