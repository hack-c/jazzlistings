"""
Add Google token column to User model.
Migration to add support for Google authentication.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_google_token'
down_revision = 'add_user_preferences'  # Update this to the previous migration ID
branch_labels = None
depends_on = None

def upgrade():
    """Add google_token column to users table"""
    op.add_column('users', sa.Column('google_token', postgresql.JSON(astext_type=sa.Text()), nullable=True))
    print("Added google_token column to users table")

def downgrade():
    """Remove google_token column from users table"""
    op.drop_column('users', 'google_token')
    print("Removed google_token column from users table")