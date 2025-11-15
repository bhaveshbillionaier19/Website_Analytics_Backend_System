"""
Service 2: Processor
Background worker that consumes events from the queue and persists them to a database.
"""

import sqlite3
import logging
import time
import sys
import queue
from typing import Dict, Any, Optional
from shared_queue import get_queue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('processor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('processor')

# Database file path
DB_FILE = 'analytics.db'


def init_database():
    """
    Initialize the SQLite database and create the events table if it doesn't exist.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Create events table with the specified schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                path TEXT,
                user_id TEXT,
                timestamp TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {DB_FILE}")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def insert_event(event_data: Dict[str, Any]) -> bool:
    """
    Insert an event into the events table.
    
    Args:
        event_data: Dictionary containing event data
        
    Returns:
        True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Insert event into database
        cursor.execute('''
            INSERT INTO events (site_id, event_type, path, user_id, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            event_data.get('site_id'),
            event_data.get('event_type'),
            event_data.get('path'),
            event_data.get('user_id'),
            event_data.get('timestamp')
        ))
        
        conn.commit()
        event_id = cursor.lastrowid
        conn.close()
        
        logger.info(f"Event processed and inserted: ID={event_id}, site_id={event_data.get('site_id')}, event_type={event_data.get('event_type')}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to insert event: {e}, Event data: {event_data}")
        return False


def process_event(event_data: Dict[str, Any]) -> bool:
    """
    Process a single event: parse and insert into database.
    
    Args:
        event_data: Dictionary containing event data from the queue
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Validate that required fields are present
        if 'site_id' not in event_data or 'event_type' not in event_data:
            logger.warning(f"Event missing required fields: {event_data}")
            return False
        
        # Insert event into database
        return insert_event(event_data)
        
    except Exception as e:
        logger.error(f"Error processing event: {e}, Event data: {event_data}")
        return False


def run_processor():
    """
    Main processor loop: continuously pull events from queue and process them.
    """
    logger.info("Starting Processor service...")
    
    # Initialize database
    try:
        init_database()
    except Exception as e:
        logger.error(f"Failed to initialize database. Exiting: {e}")
        sys.exit(1)
    
    # Get the shared queue (use_file_directly=True for Processor to read from file)
    event_queue = get_queue(use_file_directly=True)
    
    logger.info("Processor is running. Waiting for events...")
    
    # Main processing loop
    while True:
        try:
            # Get event from queue (blocking with timeout to allow graceful shutdown)
            try:
                event_data = event_queue.get(timeout=1)
            except queue.Empty:
                # Timeout occurred, continue loop (allows checking for shutdown signals)
                continue
            
            # Process the event
            if event_data:
                success = process_event(event_data)
                if not success:
                    logger.warning(f"Failed to process event: {event_data}")
                
                # Mark task as done
                event_queue.task_done()
                
        except KeyboardInterrupt:
            logger.info("Processor received interrupt signal. Shutting down...")
            break
        except Exception as e:
            logger.error(f"Unexpected error in processor loop: {e}")
            time.sleep(1)  # Brief pause before retrying
    
    logger.info("Processor stopped.")


if __name__ == '__main__':
    run_processor()

