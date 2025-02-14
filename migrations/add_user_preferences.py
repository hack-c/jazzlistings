from alembic import op
import sqlalchemy as sa
from sqlalchemy import Column, JSON
from database import SessionLocal, engine
from models import User

def upgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(Column('preferred_venues', JSON))
        batch_op.add_column(Column('preferred_genres', JSON))
        batch_op.add_column(Column('preferred_neighborhoods', JSON))

    # Initialize with empty lists
    db = SessionLocal()
    try:
        for user in db.query(User).all():
            user.preferred_venues = []
            user.preferred_genres = []
            user.preferred_neighborhoods = []
        db.commit()
    except Exception as e:
        print(f"Error initializing preferences: {e}")
        db.rollback()
    finally:
        db.close()

def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('preferred_venues')
        batch_op.drop_column('preferred_genres')
        batch_op.drop_column('preferred_neighborhoods') 