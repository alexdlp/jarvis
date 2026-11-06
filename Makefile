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
.PHONY: help init plan apply destroy url outputs logs create-user list-users list-db build select-workspace

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

# Terminal colors for the help output. Defined once so the targets below stay
# readable.
# Terminal colors for the help output.
RESET := \033[0m
BOLD  := \033[1m
GREEN := \033[0;32m
RED   := \033[0;31m
BLUE  := \033[0;34m
DIM   := \033[2m

# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

## Show this help
help:
	@printf "\n  $(BOLD)Jarvis — MCP server on AWS$(RESET)\n"
	@printf "\n  $(BOLD)Commands$(RESET)\n"
	@printf "    $(GREEN)%-12s$(RESET) $(DIM)%s$(RESET)\n" "make init"    "initialize terraform and create or select the branch workspace"
	@printf "    $(GREEN)%-12s$(RESET) $(DIM)%s$(RESET)\n" "make plan"    "preview the changes terraform would make"
	@printf "    $(GREEN)%-12s$(RESET) $(DIM)%s$(RESET)\n" "make apply"   "create or update the infrastructure"
	@printf "    $(GREEN)%-12s$(RESET) $(DIM)%s$(RESET)\n" "make url"     "print the gateway's public url"
	@printf "    $(GREEN)%-12s$(RESET) $(DIM)%s$(RESET)\n" "make outputs" "print every terraform output"
	@printf "    $(GREEN)%-12s$(RESET) $(DIM)%s$(RESET)\n" "make logs"    "follow all logs (or use MINUTES=15 for history)"
	@printf "    $(GREEN)%-12s$(RESET) $(DIM)%s$(RESET)\n" "make list-db"  "list every item stored in DynamoDB"
	@printf "    $(GREEN)%-12s$(RESET) $(DIM)%s$(RESET)\n" "make destroy" "tear everything down"
	@printf "    $(GREEN)%-14s$(RESET) $(DIM)%s$(RESET)\n" "make create-user" "create a cognito user (EMAIL=...)"
	@printf "    $(GREEN)%-14s$(RESET) $(DIM)%s$(RESET)\n" "make list-users"  "list cognito users and their status"
	@printf "\n  $(BOLD)Configuration$(RESET)  $(DIM)override per run, e.g. make apply REGION=eu-west-3$(RESET)\n"
	@printf "    $(BLUE)%-12s$(RESET) %s\n" "REGION" "$(REGION)"
	@printf "\n"

## Initialize the backend and select the workspace associated with the branch.
##
## Resolve the branch before entering infra/. Stop inmediately it its name 
## is invalid, initialization fails, or workspace selection fails.
init:
	@jarvis_workspace="$$(bash scripts/workspace-name.sh)" && \
	cd "$(INFRA)" && terraform init && \
	terraform workspace select -or-create "$$jarvis_workspace"

# Select the workspace associated with the current branch.
# This command requires the workspace to already exists.
select-workspace:
	@jarvis_workspace="$$(bash scripts/workspace-name.sh)" && \
	terraform -chdir="$(INFRA)" workspace select "$$jarvis_workspace"

## Preview the changes terraform would make, without making them.
##
## Worth reading every time: this is the only point where "2 to add, 0 to
## destroy" is visible before it happens rather than after.
plan: select-workspace build
	@cd $(INFRA) && terraform plan

## Create or update the infrastructure. Prompts for confirmation.
apply: select-workspace build
	@cd $(INFRA) && terraform apply

## Destroy every resource in this configuration. Prompts for confirmation.
destroy: select-workspace build
	@cd $(INFRA) && terraform destroy

## Print the gateway's public base URL.
url: select-workspace 
	@cd $(INFRA) && terraform output -raw api_url

## Print every terraform output: urls, the issuer, the pool id, the client ids.
##
## Unlike plan and apply this reads the state rather than the configuration, so
## it needs no TF_VAR_ values and no build. What it prints is whatever the last
## apply recorded — it will not notice a change that has not been applied yet.
##
## A thin wrapper around one terraform command, and it earns its place for the
## same reason as the rest of this file: knowing where the state directory
## lives should not be a prerequisite for reading a client id.
outputs: select-workspace 
	@cd $(INFRA) && terraform output

## Show the API Gateway and Lambda logs together.
##
## With no MINUTES value this follows new events until Ctrl+C. Setting MINUTES
## runs a finite historical query instead: `make logs MINUTES=15`.
logs: select-workspace 
	@REGION="$(REGION)" MINUTES="$(MINUTES)" ./scripts/logs.sh

## List every item currently stored in DynamoDB.
list-db: select-workspace 
	@REGION="$(REGION)" ./scripts/list-db.sh

## Create a Cognito user. Usage: make create-user EMAIL=you@example.com
##
## The script prompts for the password and keeps this target as the stable
## public command for the operation.
create-user: select-workspace 
	@REGION="$(REGION)" EMAIL="$(EMAIL)" ./scripts/create-user.sh

## List the users in the Cognito pool and their status.
list-users: select-workspace 
	@REGION="$(REGION)" ./scripts/list-users.sh

## Assemble the Lambda deployment package in build/.
build:
	@./scripts/build.sh
