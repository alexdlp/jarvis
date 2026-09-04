terraform {
  required_version = ">= 1.9"

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

}

provider "aws" {
  region = var.region
}
