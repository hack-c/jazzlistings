from database import SessionLocal, engine
from sqlalchemy import Column, DateTime
from models import Venue
from alembic import op

def upgrade():
    # Add the new column
    op.add_column('venues', Column('last_scraped', DateTime(timezone=True)))

def downgrade():
    op.drop_column('venues', 'last_scraped') 