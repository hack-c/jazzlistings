from alembic import op
import sqlalchemy as sa
from sqlalchemy import Column, DateTime

def upgrade():
    with op.batch_alter_table('venues') as batch_op:
        batch_op.add_column(Column('last_scraped', DateTime(timezone=True)))

def downgrade():
    with op.batch_alter_table('venues') as batch_op:
        batch_op.drop_column('last_scraped') 