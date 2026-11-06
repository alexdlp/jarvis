terraform {
  # S3-native state locking requires Terraform 1.10 or newer.
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }

    # Produces the deployment zip. Not an AWS provider: it does nothing remote,
    # it only reads local files and writes an archive. It appears here because
    # any provider a configuration uses must be declared, whether or not it
    # talks to a cloud.
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }

  # Store Terraform state in the existint S3 bucket.
  #
  # Each named workspace has its own state file. The Makefile will select
  # the workspace associated with the current Git branch.
  backend "s3" {
    # Existing bucket shared by all Jarvis deployment environments. 
    # This block uses the bucket; it does not create or manage its lifecycle.
    bucket = "jarvis-tf-state-storage"

    # AWS Region where the bucket was created.
    region = "eu-west-1"

    # State filename within each named workspace.
    # For workspace "main", the resulting S3 key is:
    # main/terraform.tfstate
    key = "terraform.tfstate"

    # An empty prefix places each named workspace directly at the bucket root.
    workspace_key_prefix = ""

    # Request server-side encryption for the state and lock files in S3. 
    encrypt = true

    # Acquire an S3 lock file before operations that requiere state locking.
    # This prevents simultaneous writers to the same workspace's state. 
    # Different workspaces have separated locks. 
    use_lockfile = true
  }

}

provider "aws" {
  region = var.region

  # Identify the application and deployment on resources that support tags. 
  default_tags {
    tags = {
      Application = "jarvis"
      workspace = terraform.workspace
    }
  }
}
