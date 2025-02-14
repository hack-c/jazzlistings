from database import SessionLocal, engine
from sqlalchemy import Column, JSON
from models import User
from alembic import op

def upgrade():
    # Add the new columns
    op.add_column('users', Column('preferred_venues', JSON))
    op.add_column('users', Column('preferred_genres', JSON))
    op.add_column('users', Column('preferred_neighborhoods', JSON))

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
    op.drop_column('users', 'preferred_venues')
    op.drop_column('users', 'preferred_genres')
    op.drop_column('users', 'preferred_neighborhoods') 