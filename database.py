from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session
from config import DATABASE_URL

# Create the SQLAlchemy engine
engine = create_engine(DATABASE_URL, echo=True)

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
        # Create tables if they don't exist (won't affect existing tables)
        Base.metadata.create_all(engine)
        
        print("Running database migrations...")
        db = SessionLocal()
        try:
            # Add new columns to venues table
            from sqlalchemy import Column, String, JSON, DateTime
            add_column(engine, 'venues', Column('neighborhood', String))
            add_column(engine, 'venues', Column('genres', JSON))
            add_column(engine, 'venues', Column('last_scraped', DateTime))
            
            # Add new columns to users table
            add_column(engine, 'users', Column('preferred_venues', JSON))
            add_column(engine, 'users', Column('preferred_genres', JSON))
            add_column(engine, 'users', Column('preferred_neighborhoods', JSON))
            
            # Populate venue data if needed
            from migrations.add_venue_fields import upgrade as venue_upgrade
            venue_upgrade()
            print("Venue data population complete")
            
            # Initialize any NULL JSON columns with empty lists
            with engine.begin() as conn:
                conn.execute(text("""
                    UPDATE venues 
                    SET genres = '[]' 
                    WHERE genres IS NULL
                """))
                conn.execute(text("""
                    UPDATE users 
                    SET preferred_venues = '[]',
                        preferred_genres = '[]',
                        preferred_neighborhoods = '[]'
                    WHERE preferred_venues IS NULL
                    OR preferred_genres IS NULL
                    OR preferred_neighborhoods IS NULL
                """))
            
            db.commit()
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
        yield db
    finally:
        db.close()
