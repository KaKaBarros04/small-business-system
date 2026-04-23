"""update manual_invoice fields

Revision ID: ee841556577c
Revises: 9b142ca56ce2
Create Date: 2026-04-06 20:02:36.118894

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee841556577c'
down_revision: Union[str, Sequence[str], None] = '9b142ca56ce2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. client_id (novo)
    op.add_column(
        'manual_invoices',
        sa.Column('client_id', sa.Integer(), nullable=True)
    )

    # 2. invoice_kind (novo, primeiro nullable)
    op.add_column(
        'manual_invoices',
        sa.Column('invoice_kind', sa.String(length=30), nullable=True)
    )

    # 3. invoice_number passa a nullable
    op.alter_column(
        'manual_invoices',
        'invoice_number',
        existing_type=sa.String(length=80),
        nullable=True
    )

    # 4. preencher invoice_kind
    op.execute(
        "UPDATE manual_invoices SET invoice_kind = 'MANUAL' WHERE invoice_kind IS NULL"
    )

    # 5. agora sim NOT NULL
    op.alter_column(
        'manual_invoices',
        'invoice_kind',
        existing_type=sa.String(length=30),
        nullable=False
    )

    # 6. garantir default no status (já existe!)
    op.execute(
        "UPDATE manual_invoices SET status = 'DRAFT' WHERE status IS NULL"
    )

    op.alter_column(
        'manual_invoices',
        'status',
        existing_type=sa.String(length=20),
        server_default='DRAFT'
    )

def downgrade() -> None:
    op.alter_column(
        'manual_invoices',
        'invoice_number',
        existing_type=sa.String(length=80),
        nullable=False
    )

    op.drop_column('manual_invoices', 'invoice_kind')
    op.drop_column('manual_invoices', 'client_id')