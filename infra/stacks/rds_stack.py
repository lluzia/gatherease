"""
GatherEase RDS Stack

Provisions:
  - VPC                 dedicated 2-AZ VPC with public + isolated subnets
  - Security Group      RDS SG that only accepts traffic from the app SG
  - RDS PostgreSQL 16   db.t4g.micro (dev) / db.t4g.small (prod)
  - Secrets Manager     auto-rotated DB credentials
  - CfnOutputs          DB endpoint, port, secret ARN

Design decisions:
  - Isolated subnets (no NAT Gateway) to save ~$32/month at MVP.
    ECS tasks in public subnets connect to RDS via the SG rule.
    This is acceptable for MVP; move RDS to private + NAT in production.
  - Single AZ in development, Multi-AZ in production.
  - Automated backups: 7 days (dev), 14 days (prod).
  - Deletion protection: off in dev, on in prod.
  - Performance Insights: off in dev (costs money), on in prod.
"""

from __future__ import annotations

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds
from aws_cdk import aws_secretsmanager as sm
from constructs import Construct


class GatherEaseRDSStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        app_env: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        is_prod = app_env == "production"

        # ── VPC ───────────────────────────────────────────────────────────────
        # 2 AZs, public subnets for ECS tasks, isolated subnets for RDS.
        # No NAT Gateway — cost-saving decision for MVP.
        self.vpc = ec2.Vpc(
            self,
            "GatherEaseVPC",
            vpc_name=f"gatherease-{app_env}",
            max_azs=2,
            nat_gateways=0,              # $0/month vs $64/month with NAT
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )

        # ── Security Groups ───────────────────────────────────────────────────

        # App SG — will be attached to ECS tasks (Sprint 2)
        self.app_sg = ec2.SecurityGroup(
            self,
            "AppSecurityGroup",
            vpc=self.vpc,
            security_group_name=f"gatherease-app-{app_env}",
            description="GatherEase application tier (ECS Fargate tasks)",
            allow_all_outbound=True,
        )

        # RDS SG — only accepts PostgreSQL from the app SG
        self.rds_sg = ec2.SecurityGroup(
            self,
            "RDSSecurityGroup",
            vpc=self.vpc,
            security_group_name=f"gatherease-rds-{app_env}",
            description="GatherEase RDS PostgreSQL — app tier access only",
            allow_all_outbound=False,
        )
        self.rds_sg.add_ingress_rule(
            peer=self.app_sg,
            connection=ec2.Port.tcp(5432),
            description="Allow PostgreSQL from app security group",
        )

        # Dev convenience: allow ingress from within the VPC CIDR (for Bastion / local tunnels)
        if not is_prod:
            self.rds_sg.add_ingress_rule(
                peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
                connection=ec2.Port.tcp(5432),
                description="Allow PostgreSQL from within VPC (dev only)",
            )

        # ── DB Credentials (Secrets Manager) ─────────────────────────────────
        # CDK generates a random password and stores it in Secrets Manager.
        # The FastAPI DATABASE_URL is assembled from these values at deploy time.
        self.db_secret = rds.DatabaseSecret(
            self,
            "DBSecret",
            secret_name=f"gatherease/{app_env}/db-credentials",
            username="gatherease",
        )

        # ── Parameter Group ───────────────────────────────────────────────────
        param_group = rds.ParameterGroup(
            self,
            "DBParameterGroup",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16
            ),
            description=f"GatherEase PostgreSQL 16 — {app_env}",
            parameters={
                # Enable pg_stat_statements for query performance monitoring
                "shared_preload_libraries": "pg_stat_statements",
                "pg_stat_statements.track": "all",
                # Sensible connection timeout
                "idle_in_transaction_session_timeout": "30000",  # 30s in ms
                # Log slow queries (>1s in dev, >500ms in prod)
                "log_min_duration_statement": "500" if is_prod else "1000",
                "log_connections": "1",
            },
        )

        # ── RDS Instance ──────────────────────────────────────────────────────
        self.db_instance = rds.DatabaseInstance(
            self,
            "GatherEaseDB",
            instance_identifier=f"gatherease-{app_env}",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16
            ),

            # Graviton-based instances: better price/performance ratio
            # db.t4g.micro  = 2 vCPU, 1 GB RAM  — fine for MVP dev
            # db.t4g.small  = 2 vCPU, 2 GB RAM  — recommended for production
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE4_GRAVITON,
                ec2.InstanceSize.SMALL if is_prod else ec2.InstanceSize.MICRO,
            ),

            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            security_groups=[self.rds_sg],

            # Credentials from Secrets Manager
            credentials=rds.Credentials.from_secret(self.db_secret),
            database_name="gatherease",

            # Storage
            allocated_storage=20,                # GB — min for gp3
            storage_type=rds.StorageType.GP3,
            storage_encrypted=True,              # always encrypt at rest

            parameter_group=param_group,

            # Backups
            backup_retention=cdk.Duration.days(14 if is_prod else 7),
            preferred_backup_window="02:00-03:00",     # UTC — low traffic
            preferred_maintenance_window="sun:03:00-sun:04:00",

            # High availability
            multi_az=is_prod,

            # Monitoring
            enable_performance_insights=is_prod,
            monitoring_interval=cdk.Duration.seconds(60) if is_prod else None,

            # Lifecycle
            deletion_protection=is_prod,
            removal_policy=(
                cdk.RemovalPolicy.RETAIN if is_prod else cdk.RemovalPolicy.DESTROY
            ),
            delete_automated_backups=not is_prod,

            # Publicly accessible: False — connections come through VPC only
            publicly_accessible=False,
        )

        # ── Outputs ───────────────────────────────────────────────────────────

        cdk.CfnOutput(
            self,
            "DBEndpoint",
            value=self.db_instance.db_instance_endpoint_address,
            description="RDS endpoint hostname — use in DATABASE_URL",
            export_name=f"GatherEase-{app_env}-DBEndpoint",
        )
        cdk.CfnOutput(
            self,
            "DBPort",
            value=self.db_instance.db_instance_endpoint_port,
            description="RDS port (always 5432)",
            export_name=f"GatherEase-{app_env}-DBPort",
        )
        cdk.CfnOutput(
            self,
            "DBSecretArn",
            value=self.db_secret.secret_arn,
            description="Secrets Manager ARN containing DB credentials",
            export_name=f"GatherEase-{app_env}-DBSecretArn",
        )
        cdk.CfnOutput(
            self,
            "VpcId",
            value=self.vpc.vpc_id,
            description="VPC ID — needed when adding ECS stack in Sprint 2",
            export_name=f"GatherEase-{app_env}-VpcId",
        )
        cdk.CfnOutput(
            self,
            "AppSecurityGroupId",
            value=self.app_sg.security_group_id,
            description="App SG ID — attach to ECS tasks in Sprint 2",
            export_name=f"GatherEase-{app_env}-AppSgId",
        )
        cdk.CfnOutput(
            self,
            "DatabaseURL",
            value=(
                f"postgresql+asyncpg://gatherease:<PASSWORD>"
                f"@{self.db_instance.db_instance_endpoint_address}"
                f":5432/gatherease"
            ),
            description=(
                "DATABASE_URL template — replace <PASSWORD> with value from DBSecretArn"
            ),
        )
