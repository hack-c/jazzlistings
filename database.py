from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, scoped_session
import logging
from config import DATABASE_URL
from base import Base
from models import Venue
import json
import re
import os
import time

# Configure SQLAlchemy to only log errors
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

# Create the SQLAlchemy engine with echo=False to disable SQL logging
# Add appropriate connection parameters for PostgreSQL
is_postgres = DATABASE_URL.startswith('postgresql')

# Connection parameters differ based on database type
if is_postgres:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        # PostgreSQL specific settings with more robust connection management
        pool_size=3,  # Even smaller pool size to reduce connection issues
        max_overflow=5,  # Limit max overflow to avoid overwhelming the database
        pool_timeout=30,  # Increased timeout to allow more time for connections
        pool_recycle=180,  # Recycle connections after 3 minutes to prevent stale connections
        pool_pre_ping=True,  # Test connections before using them
        connect_args={
            "keepalives": 1,  # Enable keepalives
            "keepalives_idle": 20,  # Send keepalive after 20 seconds idle
            "keepalives_interval": 5,  # Check every 5 seconds after first keepalive
            "keepalives_count": 5,  # Allow 5 failed keepalives before dropping
            "connect_timeout": 15,  # Connection timeout in seconds
            "options": "-c statement_timeout=60000",  # 60-second statement timeout
            "sslmode": "require"  # Require SSL connection
        }
    )
else:
    # SQLite settings
    engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

# Venue data for initialization
venue_data = {
    'Village Vanguard': {'neighborhood': 'Greenwich Village', 'genres': ['Jazz']},
    'Smalls Jazz Club': {'neighborhood': 'Greenwich Village', 'genres': ['Jazz']},
    'Dizzy\'s Club': {'neighborhood': 'Columbus Circle', 'genres': ['Jazz']},
    'Mezzrow Jazz Club': {'neighborhood': 'Greenwich Village', 'genres': ['Jazz']},
    'The Jazz Gallery': {'neighborhood': 'Flatiron', 'genres': ['Jazz']},
    'Ornithology Cafe': {'neighborhood': 'Bushwick', 'genres': ['Jazz']},
    'Ornithology Jazz Club': {'neighborhood': 'Bushwick', 'genres': ['Jazz']},
    'Bar LunÀtico': {'neighborhood': 'Bedford-Stuyvesant', 'genres': ['Jazz']},
    'Bar Bayeux': {'neighborhood': 'Prospect Heights', 'genres': ['Jazz']},
    'The Owl Music Parlor': {'neighborhood': 'Prospect Heights', 'genres': ['Jazz']},
    'Marians Jazz Room': {'neighborhood': 'Bedford-Stuyvesant', 'genres': ['Jazz']},
    'Zinc Bar': {'neighborhood': 'Greenwich Village', 'genres': ['Jazz']},
    'The Stone': {'neighborhood': 'East Village', 'genres': ['Jazz']},
    'Nublu 151': {'neighborhood': 'East Village', 'genres': ['Jazz']},
    'Birdland': {'neighborhood': 'Theater District', 'genres': ['Jazz']},
    'Room 623 at B2 Harlem': {'neighborhood': 'Harlem', 'genres': ['Jazz']},
    'Smoke Jazz & Supper Club': {'neighborhood': 'Upper West Side', 'genres': ['Jazz']},
    'Drom': {'neighborhood': 'East Village', 'genres': ['Jazz']},
    'Roulette': {'neighborhood': 'Downtown Brooklyn', 'genres': ['Jazz']},
    'The Django': {'neighborhood': 'Tribeca', 'genres': ['Jazz']},
    'Joe\'s Pub': {'neighborhood': 'NoHo', 'genres': ['Jazz']},
    'Minton\'s Playhouse': {'neighborhood': 'Harlem', 'genres': ['Jazz']},
    'National Sawdust': {'neighborhood': 'Williamsburg', 'genres': ['Jazz']},
    'The Cutting Room': {'neighborhood': 'Flatiron', 'genres': ['Jazz']},
    'Symphony Space': {'neighborhood': 'Upper West Side', 'genres': ['Jazz']},
    'Le Poisson Rouge': {'neighborhood': 'Greenwich Village', 'genres': ['Jazz']},
    'Knockdown Center': {'neighborhood': 'Bushwick', 'genres': ['Clubs']},
    'Bossa Nova Civic Club': {'neighborhood': 'Bushwick', 'genres': ['Clubs']},
    'House of Yes': {'neighborhood': 'Bushwick', 'genres': ['Clubs']},
    'Jupiter Disco': {'neighborhood': 'Bushwick', 'genres': ['Clubs']},
    'Public Records': {'neighborhood': 'Gowanus', 'genres': ['Clubs']},
    'The Sultan Room': {'neighborhood': 'Bushwick', 'genres': ['Clubs']},
    'Mansions': {'neighborhood': 'Bushwick', 'genres': ['Clubs']},
    'Close Up': {'neighborhood': 'Lower East Side', 'genres': ['Jazz']},
    'IFC Center': {'neighborhood': 'Greenwich Village', 'genres': ['Movies']},
    'Film Forum': {'neighborhood': 'Greenwich Village', 'genres': ['Movies']},
    'Quad Cinema': {'neighborhood': 'Greenwich Village', 'genres': ['Movies']},
    'Barbès': {'neighborhood': 'Park Slope', 'genres': ['Jazz', 'World Music']},
    'Pangea': {'neighborhood': 'East Village', 'genres': ['Jazz', 'Cabaret']},
    'Abrons Art Center': {'neighborhood': 'Lower East Side', 'genres': ['Jazz', 'Performance Art']},
    'Umbra Café': {'neighborhood': 'Bushwick', 'genres': ['Jazz']},
    'The Ear Inn': {'neighborhood': 'SoHo', 'genres': ['Jazz']},
    'The Keep': {'neighborhood': 'Bushwick', 'genres': ['Jazz']},
    'Café Erzulie': {'neighborhood': 'Bushwick', 'genres': ['Jazz', 'World Music']},
    'Soapbox Gallery': {'neighborhood': 'Prospect Heights', 'genres': ['Jazz']},
    'Silvana': {'neighborhood': 'Harlem', 'genres': ['Jazz', 'World Music']},
    'Sistas\' Place': {'neighborhood': 'Bedford-Stuyvesant', 'genres': ['Jazz']},
    'Jazzmobile': {'neighborhood': 'Harlem', 'genres': ['Jazz']},
    'Shrine': {'neighborhood': 'Harlem', 'genres': ['Jazz', 'World Music']},
    'Chelsea Table + Stage': {'neighborhood': 'Chelsea', 'genres': ['Jazz', 'Cabaret']},
    'Klavierhaus': {'neighborhood': 'Midtown', 'genres': ['Classical']},
    'Saint Peter\'s Church': {'neighborhood': 'Midtown', 'genres': ['Jazz']},
    'The Appel Room': {'neighborhood': 'Columbus Circle', 'genres': ['Jazz']},
    'Blue Note': {'neighborhood': 'Greenwich Village', 'genres': ['Jazz']},
    'Mona\'s': {'neighborhood': 'East Village', 'genres': ['Jazz']},
    'Arthur\'s Tavern': {'neighborhood': 'Greenwich Village', 'genres': ['Jazz']},
    'Elsewhere': {'neighborhood': 'Bushwick', 'genres': ['Clubs']},
    'Good Room': {'neighborhood': 'Greenpoint', 'genres': ['Clubs']},
    'Nowadays': {'neighborhood': 'Ridgewood', 'genres': ['Clubs']},
    'Black Flamingo': {'neighborhood': 'Williamsburg', 'genres': ['Clubs']},
    '3 Dollar Bill': {'neighborhood': 'East Williamsburg', 'genres': ['Clubs']},
    'Film at Lincoln Center': {'neighborhood': 'Upper West Side', 'genres': ['Movies']},
    '99 Scott': {'neighborhood': 'Bushwick', 'genres': ['Clubs']},
    'Mood Ring': {'neighborhood': 'Bushwick', 'genres': ['Clubs']},
    'Pianos': {'neighborhood': 'Lower East Side', 'genres': ['Clubs']},
    'Market Hotel': {'neighborhood': 'Bushwick', 'genres': ['Clubs']},
    'Paragon': {'neighborhood': 'Bushwick', 'genres': ['Clubs']}
}

# Create a configured "Session" class with query timeout for PostgreSQL
if is_postgres:
    # Import the base Session class
    from sqlalchemy.orm import Session as BaseSession
    
    class TimedSession(BaseSession):
        """A session class that tracks when it was created and auto-closes after a timeout"""
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.created_at = time.time()
            self._active_transaction = False
            
        def begin(self, *args, **kwargs):
            self._active_transaction = True
            return super().begin(*args, **kwargs)
            
        def commit(self, *args, **kwargs):
            try:
                result = super().commit(*args, **kwargs)
                self._active_transaction = False
                return result
            except Exception as e:
                logging.error(f"Error during commit: {e}")
                self.rollback()
                raise
                
        def rollback(self, *args, **kwargs):
            try:
                result = super().rollback(*args, **kwargs)
                self._active_transaction = False
                return result
            except Exception as e:
                logging.error(f"Error during rollback: {e}")
                self._active_transaction = False
                raise
            
        def execute(self, *args, **kwargs):
            if time.time() - self.created_at > 180:  # 3 minutes
                logging.warning("Session timeout exceeded, attempting to clean up")
                try:
                    if self._active_transaction:
                        self.rollback()
                except Exception as e:
                    logging.error(f"Error rolling back timed out session: {e}")
                try:
                    self.close()
                except Exception as e:
                    logging.error(f"Error closing timed out session: {e}")
                from sqlalchemy.exc import SQLAlchemyError
                raise SQLAlchemyError("Session timeout exceeded, please create a new session")
                
            try:
                return super().execute(*args, **kwargs)
            except Exception as e:
                if self._active_transaction:
                    try:
                        self.rollback()
                    except:
                        pass
                raise
    
    # Create the final Session class
    Session = sessionmaker(bind=engine, class_=TimedSession, expire_on_commit=False)
else:
    # Regular session for SQLite
    Session = sessionmaker(bind=engine)

# Create a scoped session that removes sessions when they're done
SessionLocal = scoped_session(Session)

def add_column(engine, table_name, column):
    """Safely add a column to a table if it doesn't exist"""
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns(table_name)]
    if column.name not in columns:
        column_type = column.type.compile(engine.dialect)
        sql = f'ALTER TABLE {table_name} ADD COLUMN {column.name} {column_type}'
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
                print(f"Added column {column.name} to {table_name}")
        except Exception as e:
            print(f"Warning: Could not add column {column.name} to {table_name}: {e}")

def init_db():
    """Initialize the database"""
    try:
        Base.metadata.create_all(engine)
        
        print("Running database migrations...")
        db = SessionLocal()
        try:
            if not is_postgres:
                # SQLite-specific configuration
                db.execute(text("PRAGMA busy_timeout = 30000"))  # 30 second timeout
            
            # Check if tables exist before attempting to modify them
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            if 'venues' in tables:
                # Add columns if they don't exist
                columns = [c['name'] for c in inspector.get_columns('venues')]
                
                if 'neighborhood' not in columns:
                    if is_postgres:
                        db.execute(text("ALTER TABLE venues ADD COLUMN neighborhood VARCHAR"))
                    else:
                        db.execute(text("ALTER TABLE venues ADD COLUMN neighborhood VARCHAR"))
                
                if 'genres' not in columns:
                    if is_postgres:
                        db.execute(text("ALTER TABLE venues ADD COLUMN genres JSONB"))
                    else:
                        db.execute(text("ALTER TABLE venues ADD COLUMN genres JSON"))
                
                # Clean up placeholder events (adapting for PostgreSQL vs SQLite differences)
                if 'concerts' in tables and 'artists' in tables and 'concert_artists' in tables:
                    try:
                        # SQL that works in both PostgreSQL and SQLite
                        db.execute(text("""
                            DELETE FROM concerts 
                            WHERE id IN (
                                SELECT c.id
                                FROM concerts c
                                JOIN concert_artists ca ON c.id = ca.concert_id
                                JOIN artists a ON ca.artist_id = a.id
                                WHERE a.name = 'Artist Name'
                                OR a.name = ''
                                OR a.name IS NULL
                            )
                        """))
                        db.commit()
                    except Exception as e:
                        print(f"Error cleaning up placeholder events: {e}")
                        db.rollback()

                    # Remove duplicate events (same venue, date, time, and artists)
                    try:
                        # This complex query may need to be adapted for PostgreSQL vs SQLite syntax
                        db.execute(text("""
                            DELETE FROM concerts 
                            WHERE id IN (
                                SELECT c1.id
                                FROM concerts c1
                                JOIN concert_times ct1 ON c1.id = ct1.concert_id
                                JOIN concert_artists ca1 ON c1.id = ca1.concert_id
                                JOIN artists a1 ON ca1.artist_id = a1.id
                                JOIN concerts c2 ON c1.venue_id = c2.venue_id 
                                    AND c1.date = c2.date
                                JOIN concert_times ct2 ON c2.id = ct2.concert_id
                                    AND ct1.time = ct2.time
                                JOIN concert_artists ca2 ON c2.id = ca2.concert_id
                                JOIN artists a2 ON ca2.artist_id = a2.id
                                    AND a1.name = a2.name
                                WHERE c1.id > c2.id
                            )
                        """))
                        db.commit()
                    except Exception as e:
                        print(f"Error removing duplicate events: {e}")
                        db.rollback()

                # Update venues
                for venue in db.query(Venue).all():
                    try:
                        if venue.name in venue_data:
                            # Handle JSON formatting differently for PostgreSQL vs SQLite
                            genres_json = json.dumps(venue_data[venue.name]['genres'])
                            
                            db.execute(
                                text("UPDATE venues SET neighborhood = :n, genres = :g WHERE id = :id"),
                                {
                                    'n': venue_data[venue.name]['neighborhood'],
                                    'g': genres_json,
                                    'id': venue.id
                                }
                            )
                            db.commit()
                    except Exception as e:
                        print(f"Error updating venue {venue.name}: {e}")
                        db.rollback()
                
                # Set defaults for any remaining NULL values
                try:
                    db.execute(text("""
                        UPDATE venues 
                        SET neighborhood = 'Other'
                        WHERE neighborhood IS NULL OR neighborhood = ''
                    """))
                    db.commit()
                except Exception as e:
                    print(f"Error setting default neighborhoods: {e}")
                    db.rollback()
                    
                try:
                    # Empty JSON array representation is the same in both databases
                    db.execute(text("""
                        UPDATE venues 
                        SET genres = '[]'
                        WHERE genres IS NULL
                    """))
                    db.commit()
                except Exception as e:
                    print(f"Error setting default genres: {e}")
                    db.rollback()
            
            print("Database migration successful")
            
        except Exception as e:
            print(f"Migration error: {e}")
            db.rollback()
        finally:
            db.close()
            
    except Exception as e:
        print(f"Database initialization error: {e}")

def get_db():
    """Get a new database session."""
    db = SessionLocal()
    try:
        if not is_postgres:
            # SQLite-specific configuration
            db.execute(text("PRAGMA busy_timeout = 5000"))
        yield db
    except Exception as e:
        # Make sure to roll back any failed transactions
        db.rollback()
        logging.error(f"Database error: {e}")
        raise
    finally:
        try:
            db.close()
        except Exception as e:
            logging.error(f"Error closing database connection: {e}")
            pass
