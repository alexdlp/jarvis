# Jarvis — MCP server on AWS
#
# Every operation goes through this Makefile. The reason is not convenience:
# it is that the deployment identity (region, resource names) must be declared
# exactly once. Terraform reads these values through the TF_VAR_ convention,
# which is why they never appear inside the .tf files.
#
# Run `make` with no target for the list of commands.

SHELL := /bin/bash
.DEFAULT_GOAL := help
.PHONY: help init plan apply destroy url create-user list-users

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# AWS region every resource is created in.
##
# ?= rather than := so an environment variable of the same name, or a
# command-line override (`make init REGION=eu-west-3`), wins over this default.
REGION ?= eu-west-1

# Terraform reads inputs from environment entries named TF_VAR_<name>. Exporting
# them here is what lets the Makefile stay the single source of truth: the
# matching `variable` blocks in infra/variables.tf declare them but hold no
# values of their own.
export TF_VAR_region := $(REGION)

# Directory holding the terraform configuration.
INFRA := infra
BUILD := build

# Terminal colors for the help output. Defined once so the targets below stay
# readable.
# Terminal colors for the help output.
RESET := \033[0m
BOLD  := \033[1m
GREEN := \033[0;32m
BLUE  := \033[0;34m
DIM   := \033[2m

# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

## Show this help
help:
	@printf "\n  $(BOLD)Jarvis — MCP server on AWS$(RESET)\n"
	@printf "\n  $(BOLD)Commands$(RESET)\n"
	@printf "    $(GREEN)%-12s$(RESET) $(DIM)%s$(RESET)\n" "make init"    "download the terraform providers"
	@printf "    $(GREEN)%-12s$(RESET) $(DIM)%s$(RESET)\n" "make plan"    "preview the changes terraform would make"
	@printf "    $(GREEN)%-12s$(RESET) $(DIM)%s$(RESET)\n" "make apply"   "create or update the infrastructure"
	@printf "    $(GREEN)%-12s$(RESET) $(DIM)%s$(RESET)\n" "make url"     "print the gateway's public url"
	@printf "    $(GREEN)%-12s$(RESET) $(DIM)%s$(RESET)\n" "make destroy" "tear everything down"
	@printf "    $(GREEN)%-14s$(RESET) $(DIM)%s$(RESET)\n" "make create-user" "create a cognito user (EMAIL=...)"
	@printf "    $(GREEN)%-14s$(RESET) $(DIM)%s$(RESET)\n" "make list-users"  "list cognito users and their status"
	@printf "\n  $(BOLD)Configuration$(RESET)  $(DIM)override per run, e.g. make apply REGION=eu-west-3$(RESET)\n"
	@printf "    $(BLUE)%-12s$(RESET) %s\n" "REGION" "$(REGION)"
	@printf "\n"

## Download the provider plugins and pin their versions.
##
## Needed once per clone, and again whenever a provider version or the state
## backend changes. plan and apply refuse to run before it.
init:
	@cd $(INFRA) && terraform init

## Preview the changes terraform would make, without making them.
##
## Worth reading every time: this is the only point where "2 to add, 0 to
## destroy" is visible before it happens rather than after.
plan: build
	@cd $(INFRA) && terraform plan

## Create or update the infrastructure. Prompts for confirmation.
apply: build
	@cd $(INFRA) && terraform apply

## Destroy every resource in this configuration. Prompts for confirmation.
destroy: build
	@cd $(INFRA) && terraform destroy

## Print the gateway's public base URL.
url:
	@cd $(INFRA) && terraform output -raw api_url

## Create a Cognito user. Usage: make create-user EMAIL=you@example.com
##
## One-off bootstrap, deliberately kept out of `apply`: creating a user is not
## idempotent, so folding it into a deploy would make every redeploy fail once
## the user exists.
##
## The password is read from the terminal rather than taken as a variable, so
## it never lands in shell history or in the process list, where `ps` would
## expose it to any other user on the machine.
##
## email_verified is set by hand because --message-action SUPPRESS skips the
## verification email. Without the attribute, Cognito refuses to send a
## password reset later and a forgotten password means being locked out.
create-user:
	@test -n "$(EMAIL)" || { printf "  $(RED)EMAIL is required$(RESET)  $(DIM)make create-user EMAIL=you@example.com$(RESET)\n"; exit 1; }
	@set -e; \
	 pool=$$(cd $(INFRA) && terraform output -raw cognito_user_pool_id); \
	 read -rs -p "  Password for $(EMAIL): " pw; echo; \
	 aws cognito-idp admin-create-user \
	   --user-pool-id "$$pool" \
	   --username "$(EMAIL)" \
	   --user-attributes Name=email,Value=$(EMAIL) Name=email_verified,Value=true \
	   --message-action SUPPRESS \
	   --region $(REGION) >/dev/null; \
	 aws cognito-idp admin-set-user-password \
	   --user-pool-id "$$pool" \
	   --username "$(EMAIL)" \
	   --password "$$pw" \
	   --permanent \
	   --region $(REGION); \
	 printf "  $(GREEN)created$(RESET)  $(DIM)%s$(RESET)\n" "$(EMAIL)"


## List the users in the pool and their status.
##
## UserStatus should read CONFIRMED. FORCE_CHANGE_PASSWORD means the permanent
## password was never set and the first login will demand a change.
list-users:
	@set -e; \
	 pool=$$(cd $(INFRA) && terraform output -raw cognito_user_pool_id); \
	 aws cognito-idp list-users --user-pool-id "$$pool" --region $(REGION) \
	   --query 'Users[].[Username,UserStatus]' --output table

## Assemble the lambda deployment package in build/.
##
## Today this is only a copy: the handler has no dependencies. When the MCP SDK
## arrives its wheels get installed into this same directory and nothing else
## in the pipeline changes.
##
## The directory is rebuilt from scratch rather than updated in place, so a
## file deleted from src/ cannot linger in a stale build and get deployed.
build:
	@rm -rf $(BUILD) && mkdir -p $(BUILD)
	@cp -R src/jarvis $(BUILD)/jarvis
	@printf "  $(GREEN)package ready$(RESET)  $(DIM)%s$(RESET)\n" "$$(du -sh $(BUILD) | cut -f1)"
