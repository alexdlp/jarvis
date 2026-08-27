# Inputs to this configuration.
#
# None of these declare a default, and that is deliberate. The Makefile is the
# single source of truth and injects every value as TF_VAR_<name>. Running
# terraform by hand from this directory will therefore stop and prompt, which
# is the intended reminder that the Makefile is the entry point — rather than
# silently deploying with a stale default nobody remembered was there.

variable "region" {
  type        = string
  description = "AWS region every resource is created in. Injected by the Makefile as TF_VAR_region."
}