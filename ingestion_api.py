"""
Service 1: Ingestion API & Service 3: Reporting API
High-performance HTTP service for event reception, queueing, and analytics reporting.
"""

from flask import Flask, request, jsonify
import queue
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional
from shared_queue import get_queue

app = Flask(__name__)

# Shared queue for asynchronous processing (accessible by both Ingestion API and Processor)
event_queue = get_queue()

# Database file path (same as used by Processor)
DB_FILE = 'analytics.db'


def validate_event(data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validate the incoming event data.
    
    Args:
        data: Dictionary containing the event data
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check if site_id is present and is a string
    if 'site_id' not in data:
        return False, "Missing required field: site_id"
    
    if not isinstance(data['site_id'], str) or not data['site_id'].strip():
        return False, "site_id must be a non-empty string"
    
    # Check if event_type is present and is a string
    if 'event_type' not in data:
        return False, "Missing required field: event_type"
    
    if not isinstance(data['event_type'], str) or not data['event_type'].strip():
        return False, "event_type must be a non-empty string"
    
    return True, ""


@app.route('/event', methods=['POST'])
def receive_event():
    """
    POST /event endpoint to receive analytics events.
    
    Expected JSON body:
    {
        "site_id": "site-abc-123",      # Required
        "event_type": "page_view",      # Required
        "path": "/pricing",             # Optional
        "user_id": "user-xyz-789",      # Optional
        "timestamp": "2025-11-12T19:30:01Z"  # Optional
    }
    
    Returns:
        200 OK: Event successfully queued
        400 Bad Request: Invalid JSON or missing required fields
    """
    # Check if request has JSON content
    if not request.is_json:
        return jsonify({
            "error": "Content-Type must be application/json"
        }), 400
    
    try:
        # Parse JSON from request body
        event_data = request.get_json()
        
        if event_data is None:
            return jsonify({
                "error": "Invalid JSON: empty or malformed request body"
            }), 400
        
        # Validate required fields
        is_valid, error_message = validate_event(event_data)
        
        if not is_valid:
            return jsonify({
                "error": error_message
            }), 400
        
        # Add timestamp if not provided
        if 'timestamp' not in event_data:
            event_data['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        
        # Push event to queue (non-blocking, thread-safe)
        event_queue.put(event_data, block=False)
        
        # Immediately return success response
        return jsonify({
            "message": "Event received"
        }), 200
        
    except queue.Full:
        # Queue is full (shouldn't happen with in-memory queue, but good to handle)
        return jsonify({
            "error": "Service temporarily unavailable: queue is full"
        }), 503
        
    except json.JSONDecodeError as e:
        return jsonify({
            "error": f"Invalid JSON: {str(e)}"
        }), 400
        
    except Exception as e:
        # Catch any other unexpected errors
        return jsonify({
            "error": f"Internal server error: {str(e)}"
        }), 500


@app.route('/stats', methods=['GET'])
def get_stats():
    """
    GET /stats endpoint to retrieve aggregated analytics data.
    
    Query Parameters:
        site_id (required): Site identifier to filter events
        date (optional): Date in YYYY-MM-DD format to filter events by date
    
    Returns:
        200 OK: Aggregated statistics
        400 Bad Request: Missing or invalid parameters
        404 Not Found: No data found for the given criteria
    """
    # Get query parameters
    site_id = request.args.get('site_id')
    date = request.args.get('date')
    
    # Validate required parameter
    if not site_id:
        return jsonify({
            "error": "Missing required parameter: site_id"
        }), 400
    
    # Validate date format if provided
    if date:
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            return jsonify({
                "error": "Invalid date format. Expected YYYY-MM-DD"
            }), 400
    
    try:
        # Connect to database
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        cursor = conn.cursor()
        
        # Build query based on whether date is provided
        if date:
            # Filter by site_id and date (timestamp starts with the date)
            query = '''
                SELECT path, user_id, timestamp
                FROM events
                WHERE site_id = ? AND timestamp LIKE ?
            '''
            date_pattern = f"{date}%"
            cursor.execute(query, (site_id, date_pattern))
        else:
            # Filter only by site_id
            query = '''
                SELECT path, user_id, timestamp
                FROM events
                WHERE site_id = ?
            '''
            cursor.execute(query, (site_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        # If no data found, return empty results
        if not rows:
            return jsonify({
                "site_id": site_id,
                "date": date if date else None,
                "total_views": 0,
                "unique_users": 0,
                "top_paths": []
            }), 200
        
        # Aggregate data
        total_views = len(rows)
        
        # Count unique users (excluding NULL/empty user_ids)
        unique_user_ids = set()
        for row in rows:
            user_id = row['user_id']
            if user_id:
                unique_user_ids.add(user_id)
        unique_users = len(unique_user_ids)
        
        # Count views per path
        path_counts = {}
        for row in rows:
            path = row['path']
            if path:
                path_counts[path] = path_counts.get(path, 0) + 1
        
        # Get top 3 paths (or all if less than 3)
        sorted_paths = sorted(path_counts.items(), key=lambda x: x[1], reverse=True)
        top_paths = [
            {"path": path, "views": count}
            for path, count in sorted_paths[:3]
        ]
        
        # Build response
        response = {
            "site_id": site_id,
            "date": date if date else None,
            "total_views": total_views,
            "unique_users": unique_users,
            "top_paths": top_paths
        }
        
        return jsonify(response), 200
        
    except sqlite3.Error as e:
        return jsonify({
            "error": f"Database error: {str(e)}"
        }), 500
    except Exception as e:
        return jsonify({
            "error": f"Internal server error: {str(e)}"
        }), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "ingestion_api",
        "queue_size": event_queue.qsize()
    }), 200


if __name__ == '__main__':
    # Run the Flask app
    # In production, use a production WSGI server like gunicorn
    app.run(host='0.0.0.0', port=5000, debug=True)

