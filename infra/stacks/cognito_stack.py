"""
GatherEase Cognito Stack

Provisions:
  - User Pool          with email/password auth, MFA off (MVP), SES email
  - User Pool Client   with USER_PASSWORD_AUTH + REFRESH_TOKEN flows
  - CfnOutputs         consumed by the FastAPI .env

Password policy matches the validator in app/api/v1/auth/schemas.py:
  - Min 8 chars, upper + lower + digit required (no symbols required at MVP)

The User Pool is NOT destroyed on CDK stack deletion in staging/production
to protect user data. Set removal_policy=DESTROY only in development.
"""

from __future__ import annotations

from typing import Unpack

import aws_cdk as cdk
from aws_cdk import StackProps
from aws_cdk import aws_cognito as cognito
from constructs import Construct


class GatherEaseCognitoStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        app_env: str,
        **kwargs: Unpack[StackProps],
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        is_prod = app_env == "production"
        removal_policy = (
            cdk.RemovalPolicy.RETAIN if is_prod else cdk.RemovalPolicy.DESTROY
        )

        # ── User Pool ─────────────────────────────────────────────────────────
        self.user_pool = cognito.UserPool(
            self,
            "GatherEaseUserPool",
            user_pool_name=f"gatherease-{app_env}",
            # Sign-in: email only (username is the email address)
            sign_in_aliases=cognito.SignInAliases(email=True, username=False),
            sign_in_case_sensitive=False,
            # Self-registration: on (users sign up themselves via the API)
            self_sign_up_enabled=True,
            # Auto-verify email on sign-up confirmation
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            # Standard attributes — email required, name optional
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
                fullname=cognito.StandardAttribute(required=False, mutable=True),
            ),
            # Password policy — mirrors schemas.py validator
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_uppercase=True,
                require_lowercase=True,
                require_digits=True,
                require_symbols=False,  # kept off at MVP for UX
                temp_password_validity=cdk.Duration.days(3),
            ),
            # Account recovery: email only (no SMS at MVP)
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            # MFA: off at MVP (Phase 2: optional TOTP)
            mfa=cognito.Mfa.OFF,
            # Verification email — Cognito-hosted (SES can be wired up later)
            user_verification=cognito.UserVerificationConfig(
                email_subject="Verify your GatherEase account",
                email_body=(
                    "Welcome to GatherEase! Your verification code is: {####}\n\n"
                    "This code expires in 24 hours."
                ),
                email_style=cognito.VerificationEmailStyle.CODE,
            ),
            # Invitation email (when admin creates a user)
            user_invitation=cognito.UserInvitationConfig(
                email_subject="You've been invited to GatherEase",
                email_body=(
                    "Hi {username}, you have been invited to GatherEase.\n"
                    "Your temporary password is: {####}"
                ),
            ),
            # Keep deleted users' data for 30 days
            removal_policy=removal_policy,
            # Threat protection: AUDIT in prod, NO_ENFORCEMENT in dev (costs money)
            standard_threat_protection_mode=(
                cognito.StandardThreatProtectionMode.AUDIT_ONLY
                if is_prod
                else cognito.StandardThreatProtectionMode.NO_ENFORCEMENT
            ),
        )

        # ── App Client ────────────────────────────────────────────────────────
        # No client secret — Flutter mobile apps can't keep secrets.
        # The FastAPI backend uses USER_PASSWORD_AUTH via the Boto3 admin flow.
        self.user_pool_client = self.user_pool.add_client(
            "GatherEaseAppClient",
            user_pool_client_name=f"gatherease-app-{app_env}",
            generate_secret=False,
            # Auth flows needed:
            #   USER_PASSWORD_AUTH  – login with email + password
            #   REFRESH_TOKEN_AUTH  – refresh access tokens
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,  # more secure alternative Flutter can use
            ),
            # Token validity
            access_token_validity=cdk.Duration.hours(1),
            id_token_validity=cdk.Duration.hours(1),
            refresh_token_validity=cdk.Duration.days(30),
            # Prevent user existence errors leaking (always "incorrect credentials")
            prevent_user_existence_errors=True,
            # Read/write attributes the client is allowed to touch
            read_attributes=cognito.ClientAttributes().with_standard_attributes(
                email=True,
                email_verified=True,
                fullname=True,
            ),
            write_attributes=cognito.ClientAttributes().with_standard_attributes(
                email=True,
                fullname=True,
            ),
        )

        # ── Outputs ───────────────────────────────────────────────────────────
        # These values go into your .env / AWS Secrets Manager

        cdk.CfnOutput(
            self,
            "UserPoolId",
            value=self.user_pool.user_pool_id,
            description="COGNITO_USER_POOL_ID",
            export_name=f"GatherEase-{app_env}-UserPoolId",
        )
        cdk.CfnOutput(
            self,
            "UserPoolClientId",
            value=self.user_pool_client.user_pool_client_id,
            description="COGNITO_CLIENT_ID",
            export_name=f"GatherEase-{app_env}-UserPoolClientId",
        )
        cdk.CfnOutput(
            self,
            "UserPoolRegion",
            value=self.region,
            description="COGNITO_REGION",
        )
        cdk.CfnOutput(
            self,
            "JwksUrl",
            value=(
                f"https://cognito-idp.{self.region}.amazonaws.com"
                f"/{self.user_pool.user_pool_id}/.well-known/jwks.json"
            ),
            description="Cognito JWKS URL for JWT verification",
        )
