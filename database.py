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
        Base.metadata.create_all(engine)
        
        print("Running database migrations...")
        db = SessionLocal()
        try:
            # Set timeout for SQLite locks
            db.execute(text("PRAGMA busy_timeout = 5000"))
            
            # Add columns directly with SQL
            db.execute(text("""
                ALTER TABLE venues ADD COLUMN IF NOT EXISTS neighborhood VARCHAR;
                ALTER TABLE venues ADD COLUMN IF NOT EXISTS genres JSON;
            """))
            
            # Update venue data
            from migrations.add_venue_fields import venue_data
            
            # Update in batches to avoid locks
            for venue in db.query(Venue).all():
                if venue.name in venue_data:
                    venue.neighborhood = venue_data[venue.name]['neighborhood']
                    venue.genres = venue_data[venue.name]['genres']
            
            # Set default values for NULL fields
            db.execute(text("""
                UPDATE venues 
                SET neighborhood = 'Other'
                WHERE neighborhood IS NULL OR neighborhood = '';
            """))
            
            db.execute(text("""
                UPDATE venues 
                SET genres = '[]'
                WHERE genres IS NULL;
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
        # Set a shorter timeout for SQLite locks
        db.execute(text("PRAGMA busy_timeout = 5000"))
        yield db
    finally:
        db.close()
