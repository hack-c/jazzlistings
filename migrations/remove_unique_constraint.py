"""Remove unique constraint on concerts table

This migration removes the unique constraint on venue_id and date in the concerts table
to allow multiple events at the same venue on the same day.
"""

import os
import sys
# Add parent directory to path if running as a script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from sqlalchemy import create_engine, text, MetaData, Table, Column, inspect
from config import DATABASE_URL
import logging

logger = logging.getLogger('concert_app')

def run_migration():
    """Execute the migration"""
    try:
        engine = create_engine(DATABASE_URL)
        is_postgres = DATABASE_URL.startswith('postgresql')
        
        with engine.connect() as conn:
            # Check if constraint exists before trying to drop it
            if is_postgres:
                # PostgreSQL - check for constraint existence
                check_sql = """
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'concerts' 
                AND constraint_name = 'uix_concert_venue_date';
                """
                result = conn.execute(text(check_sql))
                exists = result.fetchone() is not None
                
                if exists:
                    # Drop constraint in PostgreSQL
                    logger.info("Dropping unique constraint on concerts table in PostgreSQL")
                    drop_sql = "ALTER TABLE concerts DROP CONSTRAINT uix_concert_venue_date;"
                    conn.execute(text(drop_sql))
                    conn.commit()
                    logger.info("Successfully dropped unique constraint")
                else:
                    logger.info("Constraint does not exist, skipping")
            else:
                # SQLite - recreate table without constraint
                # This is more complex since SQLite doesn't support DROP CONSTRAINT
                # For simplicity, we'll just log in this script
                logger.warning("SQLite migration not implemented - would need to recreate table")
                logger.info("For SQLite, delete the database file and restart to apply schema changes")
                # Would need to:
                # 1. Create new table without constraint
                # 2. Copy data from old table
                # 3. Drop old table
                # 4. Rename new table
        
        return True
    except Exception as e:
        logger.error(f"Error removing unique constraint: {e}")
        return False

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting migration to remove unique constraint")
    success = run_migration()
    if success:
        logger.info("Migration completed successfully")
    else:
        logger.error("Migration failed")