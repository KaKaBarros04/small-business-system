"""add google client color mode to companies

Revision ID: 41a6c7e3cd57
Revises: e78acc21a516
Create Date: 2026-04-08 19:02:51.568193

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '41a6c7e3cd57'
down_revision: Union[str, Sequence[str], None] = 'e78acc21a516'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "companies",
        sa.Column(
            "google_client_color_mode",
            sa.String(length=20),
            nullable=False,
            server_default="none",
        ),
    )

    op.execute("""
        UPDATE companies
        SET google_client_color_mode = 'client'
        WHERE lower(slug) = 'lalimpezas'
    """)

    op.execute("""
        UPDATE companies
        SET google_client_color_mode = 'none'
        WHERE lower(slug) <> 'lalimpezas'
    """)


def downgrade() -> None:
    op.drop_column("companies", "google_client_color_mode")