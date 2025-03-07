# add_newsletter_preferences.py

from database import SessionLocal, engine
from sqlalchemy import Column, Boolean, String, DateTime, text
import logging
from sqlalchemy import inspect

def upgrade():
    db = SessionLocal()
    try:
        # First check if columns exist
        inspector = inspect(engine)
        columns = [c['name'] for c in inspector.get_columns('users')]
        
        # Add columns only if they don't exist
        with engine.begin() as conn:
            if 'newsletter_subscribed' not in columns:
                conn.execute(text("""
                    ALTER TABLE users
                    ADD COLUMN newsletter_subscribed BOOLEAN DEFAULT FALSE;
                """))
                logging.info("Added newsletter_subscribed column")
                
            if 'newsletter_frequency' not in columns:
                conn.execute(text("""
                    ALTER TABLE users
                    ADD COLUMN newsletter_frequency VARCHAR DEFAULT 'weekly';
                """))
                logging.info("Added newsletter_frequency column")
                
            if 'last_newsletter_sent' not in columns:
                conn.execute(text("""
                    ALTER TABLE users
                    ADD COLUMN last_newsletter_sent TIMESTAMP WITH TIME ZONE;
                """))
                logging.info("Added last_newsletter_sent column")
        
        db.commit()
        logging.info("Successfully added newsletter preference columns")
        
    except Exception as e:
        logging.error(f"Error adding newsletter columns: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def downgrade():
    # Don't drop columns in production, just log
    logging.warning("Downgrade requested but skipped for safety in production")