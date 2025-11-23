"""Add category and subcategory to ticket_analyses

Revision ID: 001_category_subcategory
Revises:
Create Date: 2024-11-23

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_category_subcategory'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add category and subcategory columns to ticket_analyses
    op.add_column('ticket_analyses', sa.Column('category', sa.String(length=100), nullable=True))
    op.add_column('ticket_analyses', sa.Column('subcategory', sa.String(length=100), nullable=True))

    # Create indexes for better query performance
    op.create_index('idx_analysis_category', 'ticket_analyses', ['category', 'subcategory'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_analysis_category', table_name='ticket_analyses')

    # Drop columns
    op.drop_column('ticket_analyses', 'subcategory')
    op.drop_column('ticket_analyses', 'category')
