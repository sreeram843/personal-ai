"""Add assistant_id to conversations for sticky assistant selection."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_conversation_assistant"
down_revision: Union[str, None] = "002_conversation_pin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("assistant_id", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "assistant_id")
