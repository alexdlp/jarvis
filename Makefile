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
.PHONY: help init plan apply destroy url

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
plan:
	@cd $(INFRA) && terraform plan

## Create or update the infrastructure. Prompts for confirmation.
apply:
	@cd $(INFRA) && terraform apply

## Destroy every resource in this configuration. Prompts for confirmation.
destroy:
	@cd $(INFRA) && terraform destroy

## Print the gateway's public base URL.
url:
	@cd $(INFRA) && terraform output -raw api_url