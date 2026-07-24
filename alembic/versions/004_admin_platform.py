"""Add admin platform tables: roles, invites, providers, routing, usage, flags."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_admin_platform"
down_revision: Union[str, None] = "003_conversation_assistant"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
    )
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "user_invites",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("token", name="uq_user_invites_token"),
    )
    op.create_index("ix_user_invites_email", "user_invites", ["email"])

    op.create_table(
        "llm_providers",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("key_last4", sa.String(length=8), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", name="uq_llm_providers_name"),
    )

    op.create_table(
        "llm_routing",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("default_provider", sa.String(length=64), nullable=False, server_default="openai"),
        sa.Column("default_model", sa.String(length=128), nullable=False, server_default="llama-3.1-8b-instant"),
        sa.Column("planner_provider", sa.String(length=64), nullable=False, server_default="openai"),
        sa.Column("planner_model", sa.String(length=128), nullable=False, server_default="llama-3.1-8b-instant"),
        sa.Column("synthesizer_provider", sa.String(length=64), nullable=False, server_default="openai"),
        sa.Column("synthesizer_model", sa.String(length=128), nullable=False, server_default="llama-3.3-70b-versatile"),
        sa.Column("reviewer_provider", sa.String(length=64), nullable=False, server_default="openai"),
        sa.Column("reviewer_model", sa.String(length=128), nullable=False, server_default="llama-3.1-8b-instant"),
        sa.Column("writer_provider", sa.String(length=64), nullable=False, server_default="openai"),
        sa.Column("writer_model", sa.String(length=128), nullable=False, server_default="llama-3.3-70b-versatile"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "llm_usage_events",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("route", sa.String(length=64), nullable=False, server_default="chat"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_llm_usage_events_user_created", "llm_usage_events", ["user_id", "created_at"])
    op.create_index("ix_llm_usage_events_created", "llm_usage_events", ["created_at"])

    op.create_table(
        "system_flags",
        sa.Column("key", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("system_flags")
    op.drop_index("ix_llm_usage_events_created", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_user_created", table_name="llm_usage_events")
    op.drop_table("llm_usage_events")
    op.drop_table("llm_routing")
    op.drop_table("llm_providers")
    op.drop_index("ix_user_invites_email", table_name="user_invites")
    op.drop_table("user_invites")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "role")
