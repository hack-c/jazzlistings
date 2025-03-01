"""Add newsletter fields to User model"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add new columns to users table
    op.add_column('users', sa.Column('newsletter_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('newsletter_frequency', sa.String(), nullable=True, server_default='weekly'))
    op.add_column('users', sa.Column('phone_number', sa.String(), nullable=True))
    op.add_column('users', sa.Column('auth_type', sa.String(), nullable=True))
    op.add_column('users', sa.Column('last_newsletter', sa.DateTime(timezone=True), nullable=True))

def downgrade():
    # Remove the columns
    op.drop_column('users', 'newsletter_enabled')
    op.drop_column('users', 'newsletter_frequency')
    op.drop_column('users', 'phone_number')
    op.drop_column('users', 'auth_type')
    op.drop_column('users', 'last_newsletter') 