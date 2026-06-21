"""Add pinned_at to conversations for sidebar pinning."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_conversation_pin"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "pinned_at")
