from database import SessionLocal, engine
from sqlalchemy import Column, String, JSON
from models import Venue
from alembic import op

def upgrade():
    # Add the new columns
    op.add_column('venues', Column('neighborhood', String))
    op.add_column('venues', Column('genres', JSON))

    # Populate with initial data
    db = SessionLocal()
    try:
        # Define known venue neighborhoods and genres
        venue_data = {
            # Jazz Venues
            'Blue Note': {
                'neighborhood': 'Greenwich Village',
                'genres': ['Jazz']
            },
            'Birdland': {
                'neighborhood': 'Theater District',
                'genres': ['Jazz']
            },
            'Smalls Jazz Club': {
                'neighborhood': 'Greenwich Village',
                'genres': ['Jazz']
            },
            'Village Vanguard': {
                'neighborhood': 'Greenwich Village',
                'genres': ['Jazz']
            },
            'Dizzy\'s Club': {
                'neighborhood': 'Upper West Side',
                'genres': ['Jazz']
            },
            'The Jazz Gallery': {
                'neighborhood': 'Flatiron District',
                'genres': ['Jazz']
            },
            'Mezzrow': {
                'neighborhood': 'Greenwich Village',
                'genres': ['Jazz']
            },
            # Clubs
            'Mansions': {
                'neighborhood': 'Bushwick',
                'genres': ['Clubs']
            },
            'Bossa Nova Civic Club': {
                'neighborhood': 'Bushwick',
                'genres': ['Clubs']
            },
            'House of Yes': {
                'neighborhood': 'Bushwick',
                'genres': ['Clubs']
            },
            'Elsewhere': {
                'neighborhood': 'Bushwick',
                'genres': ['Clubs']
            },
            # Galleries
            'National Sawdust': {
                'neighborhood': 'Williamsburg',
                'genres': ['Jazz', 'Classical']
            },
            'Roulette': {
                'neighborhood': 'Downtown Brooklyn',
                'genres': ['Jazz']
            },
            # Museums
            'MoMA': {
                'neighborhood': 'Midtown',
                'genres': ['Museums']
            }
        }

        # Update existing venues
        for venue in db.query(Venue).all():
            if venue.name in venue_data:
                venue.neighborhood = venue_data[venue.name]['neighborhood']
                venue.genres = venue_data[venue.name]['genres']
        
        db.commit()
        print("Successfully updated venue data")
        
    except Exception as e:
        print(f"Error updating venue data: {e}")
        db.rollback()
    finally:
        db.close()

def downgrade():
    op.drop_column('venues', 'neighborhood')
    op.drop_column('venues', 'genres') 