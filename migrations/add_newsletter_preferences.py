# add_newsletter_preferences.py

from sqlalchemy import Column, Boolean, String, DateTime
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add the new columns for newsletter preferences
    op.add_column('users', sa.Column('newsletter_subscribed', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('users', sa.Column('newsletter_frequency', sa.String(), nullable=True, server_default='weekly'))
    op.add_column('users', sa.Column('last_newsletter_sent', sa.DateTime(timezone=True), nullable=True))

def downgrade():
    # Remove the new columns
    op.drop_column('users', 'newsletter_subscribed')
    op.drop_column('users', 'newsletter_frequency')
    op.drop_column('users', 'last_newsletter_sent')