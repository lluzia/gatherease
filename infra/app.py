#!/usr/bin/env python3
"""
GatherEase CDK App — Sprint 1 Infrastructure Bootstrap

Stacks:
  GatherEaseCognitoStack  – Cognito User Pool + App Client
  GatherEaseRDSStack      – PostgreSQL on RDS (+ VPC, subnets, SG)
  GatherEaseS3Stack       – S3 assets bucket

Usage:
  cd infra/
  cdk bootstrap          # one-time per AWS account / region
  cdk synth              # preview CloudFormation templates
  cdk deploy --all       # deploy all stacks
  cdk deploy GatherEaseCognitoStack   # deploy one stack

Environment variables (or set in cdk.json context):
  CDK_DEFAULT_ACCOUNT  – AWS account ID
  CDK_DEFAULT_REGION   – AWS region (default: eu-west-1)
  APP_ENV              – development | staging | production (default: development)
"""

import os

import aws_cdk as cdk
from stacks.cognito_stack import GatherEaseCognitoStack
from stacks.rds_stack import GatherEaseRDSStack
from stacks.s3_stack import GatherEaseS3Stack

app = cdk.App()

env = cdk.Environment(
    account=os.environ.get("CDK_DEFAULT_ACCOUNT", os.environ.get("AWS_ACCOUNT_ID")),
    region=os.environ.get("CDK_DEFAULT_REGION", "eu-west-1"),
)

app_env = app.node.try_get_context("app_env") or os.environ.get(
    "APP_ENV", "development"
)

# ── Cognito ───────────────────────────────────────────────────────────────────
cognito_stack = GatherEaseCognitoStack(
    app,
    "GatherEaseCognitoStack",
    app_env=app_env,
    env=env,
    description="GatherEase — Cognito User Pool and App Client",
)

# ── RDS (depends on nothing — creates its own VPC) ────────────────────────────
rds_stack = GatherEaseRDSStack(
    app,
    "GatherEaseRDSStack",
    app_env=app_env,
    env=env,
    description="GatherEase — PostgreSQL RDS instance in a dedicated VPC",
)

# ── S3 ────────────────────────────────────────────────────────────────────────
s3_stack = GatherEaseS3Stack(
    app,
    "GatherEaseS3Stack",
    app_env=app_env,
    env=env,
    description="GatherEase — S3 assets bucket (avatars, recipe photos)",
)

# Tag every resource in every stack for cost allocation
for stack in [cognito_stack, rds_stack, s3_stack]:
    cdk.Tags.of(stack).add("Project", "GatherEase")
    cdk.Tags.of(stack).add("Environment", app_env)
    cdk.Tags.of(stack).add("ManagedBy", "CDK")

app.synth()
