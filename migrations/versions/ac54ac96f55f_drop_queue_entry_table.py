"""Drop queue_entry table

Revision ID: ac54ac96f55f
Revises: c70f55d56ce5
Create Date: 2025-06-12 19:34:09.952921

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ac54ac96f55f'
down_revision = 'c70f55d56ce5'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('queue_entry')


def downgrade():
    op.create_table(
        'queue_entry',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('office_id', sa.Integer, sa.ForeignKey('office.id'), nullable=False),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('user.id'), nullable=False),
        sa.Column('joined_at', sa.DateTime, nullable=True),
        sa.Column('active', sa.Boolean, nullable=True),
    )
