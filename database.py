from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session
from config import DATABASE_URL
from models import Venue

# Create the SQLAlchemy engine
engine = create_engine(DATABASE_URL, echo=True)

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
    'Marians Jazz Room': {'neighborhood': 'Williamsburg', 'genres': ['Jazz']},
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
}

# Create a configured "Session" class
Session = sessionmaker(bind=engine)

# Create a scoped session
SessionLocal = scoped_session(Session)

# Create a base class for declarative models
Base = declarative_base()

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
            # Set a longer timeout for SQLite locks
            db.execute(text("PRAGMA busy_timeout = 30000"))  # 30 second timeout
            
            # Add columns if they don't exist
            inspector = inspect(engine)
            columns = [c['name'] for c in inspector.get_columns('venues')]
            
            if 'neighborhood' not in columns:
                db.execute(text("ALTER TABLE venues ADD COLUMN neighborhood VARCHAR"))
            if 'genres' not in columns:
                db.execute(text("ALTER TABLE venues ADD COLUMN genres JSON"))
            
            # Update venues one at a time to avoid locks
            for venue in db.query(Venue).all():
                try:
                    if venue.name in venue_data:
                        db.execute(
                            text("UPDATE venues SET neighborhood = :n, genres = :g WHERE id = :id"),
                            {
                                'n': venue_data[venue.name]['neighborhood'],
                                'g': venue_data[venue.name]['genres'],
                                'id': venue.id
                            }
                        )
                        db.commit()  # Commit each update individually
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
        # Set a shorter timeout for SQLite locks
        db.execute(text("PRAGMA busy_timeout = 5000"))
        yield db
    finally:
        db.close()
