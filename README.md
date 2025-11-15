# Website Analytics Backend System

A high-performance backend system for capturing, processing, and reporting website analytics events. The system is designed with an asynchronous architecture to prioritize extremely fast event ingestion while processing events in the background.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [System Components](#system-components)
- [Architecture Decisions](#architecture-decisions)
- [Database Schema](#database-schema)
- [Setup Instructions](#setup-instructions)
- [Running the Services](#running-the-services)
- [API Usage](#api-usage)
- [Testing](#testing)
- [Project Structure](#project-structure)

## Architecture Overview

The system consists of three distinct services that work together to provide fast event ingestion, asynchronous processing, and analytics reporting:

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│  Ingestion  │─────▶│   Queue      │─────▶│  Processor  │
│     API     │      │  (In-Memory) │      │  (Worker)   │
│  (Service 1)│      │              │      │ (Service 2) │
└─────────────┘      └──────────────┘      └──────┬──────┘
                                                   │
                                                   ▼
                                            ┌─────────────┐
                                            │  SQLite DB  │
                                            │ (analytics) │
                                            └──────┬──────┘
                                                   │
┌─────────────┐                                  │
│  Reporting  │◀─────────────────────────────────┘
│     API     │
│  (Service 3)│
└─────────────┘
```

### Service Flow

1. **Ingestion API** receives events via HTTP POST and immediately queues them
2. **Processor** continuously polls the queue, processes events, and persists them to the database
3. **Reporting API** queries the database to provide aggregated analytics

## System Components

### Service 1: Ingestion API

Fast HTTP endpoint that receives analytics events and queues them for asynchronous processing. Returns immediately after queuing to ensure minimal latency.

**Key Features:**
- High-performance event reception
- Immediate response (does not wait for processing)
- JSON validation
- Thread-safe queueing

### Service 2: Processor

Background worker that continuously consumes events from the queue and persists them to the SQLite database. Runs independently and processes events asynchronously.

**Key Features:**
- Continuous event processing loop
- Database persistence
- Error handling and logging
- Graceful shutdown support

### Service 3: Reporting API

RESTful API for querying and aggregating analytics data from the database. Provides insights on page views, unique users, and popular paths.

**Key Features:**
- Flexible querying by site_id and date
- Real-time aggregation
- Top paths analysis

## Architecture Decisions

### In-Memory Queue Choice

For this exercise, we use an **in-memory queue** (Python's `queue.Queue` with file-based persistence) to achieve extremely fast event ingestion. This design choice prioritizes:

1. **Minimal Latency**: Events are queued immediately without database I/O
2. **Simplicity**: No external dependencies required for the queue
3. **Fast Response Times**: The Ingestion API returns immediately after queuing

**How It Works:**
- The Ingestion API uses an in-memory queue for speed, with events also written to a file for persistence
- The Processor reads directly from the file-based queue (since it's a separate process)
- This hybrid approach provides both speed and cross-process communication

**Real-World Alternatives:**

In production environments, you would typically use:

- **Redis**: In-memory data store with pub/sub capabilities, excellent for high-throughput queuing
- **Apache Kafka**: Distributed event streaming platform, ideal for large-scale event processing
- **RabbitMQ**: Message broker with advanced routing and reliability features
- **Amazon SQS / Google Cloud Pub/Sub**: Managed queue services for cloud deployments

These alternatives provide:
- Better scalability and distributed processing
- Durability and message persistence
- Advanced features like message acknowledgments, retries, and dead-letter queues
- Better monitoring and observability

### Service Interaction

The three services interact as follows:

1. **Ingestion → Queue**: Events are pushed to the queue immediately upon receipt
2. **Queue → Processor**: Processor continuously polls the queue for new events
3. **Processor → Database**: Processed events are written to SQLite
4. **Database → Reporting**: Reporting API queries the database for analytics

This asynchronous pattern ensures that:
- The Ingestion API remains fast and responsive
- Event processing doesn't block event reception
- The system can handle bursts of traffic
- Services can be scaled independently

## Database Schema

### Events Table

The system uses a SQLite database with a single `events` table to store all analytics events.

**Table: `events`**

| Column      | Type    | Constraints              | Description                          |
|-------------|---------|--------------------------|--------------------------------------|
| `id`        | INTEGER | PRIMARY KEY AUTOINCREMENT| Unique identifier for each event     |
| `site_id`   | TEXT    | NOT NULL                 | Identifier for the website/site      |
| `event_type`| TEXT    | NOT NULL                 | Type of event (e.g., "page_view")    |
| `path`      | TEXT    | NULL                     | URL path of the page                 |
| `user_id`   | TEXT    | NULL                     | Identifier for the user              |
| `timestamp` | TEXT    | NULL                     | ISO 8601 timestamp of the event      |

**Example Data:**
```
id | site_id      | event_type | path      | user_id    | timestamp
---|--------------|------------|-----------|------------|-------------------
1  | site-abc-123 | page_view  | /pricing  | user-xyz-1 | 2025-11-12T19:30:01Z
2  | site-abc-123 | page_view  | /blog     | user-xyz-2 | 2025-11-12T19:31:15Z
```

The database file (`analytics.db`) is automatically created and initialized when the Processor service starts.

## Setup Instructions

### Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd tjra
```

### Step 2: Install Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```

This will install:
- Flask 3.0.0 (HTTP framework)
- Werkzeug 3.0.1 (WSGI utilities)

### Step 3: Initialize the Database

The database is automatically initialized when you start the Processor service. The Processor will:
- Create the `analytics.db` SQLite database file (if it doesn't exist)
- Create the `events` table with the proper schema

**Note:** You don't need to manually initialize the database. Simply start the Processor service and it will handle initialization.

### Step 4: Start the Services

The system requires two services to be running:

#### Start the Ingestion/Reporting API (Service 1 & 3)

In one terminal:

```bash
python ingestion_api.py
```

The service will start on `http://localhost:5000`

#### Start the Processor (Service 2)

In another terminal:

```bash
python processor.py
```

The Processor will:
- Initialize the database
- Start processing events from the queue
- Log operations to `processor.log` and console

**Important:** Both services must be running for the system to function properly:
- The Ingestion API receives and queues events
- The Processor processes queued events and stores them in the database
- The Reporting API queries the database for analytics

## Running the Services

### Development Mode

For development, run both services in separate terminals:

**Terminal 1:**
```bash
python ingestion_api.py
```

**Terminal 2:**
```bash
python processor.py
```

### Production Considerations

For production deployments:

1. **Ingestion API**: Use a production WSGI server like Gunicorn or uWSGI
   ```bash
   gunicorn -w 4 -b 0.0.0.0:5000 ingestion_api:app
   ```

2. **Processor**: Run as a systemd service or use a process manager like Supervisor

3. **Database**: Consider migrating to PostgreSQL or MySQL for better performance and scalability

4. **Queue**: Replace the in-memory queue with Redis, Kafka, or another production-grade message queue

## API Usage

### POST /event

Send analytics events to the system.

#### Basic Usage

```bash
curl -X POST http://localhost:5000/event \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "site-abc-123",
    "event_type": "page_view",
    "path": "/pricing",
    "user_id": "user-xyz-789",
    "timestamp": "2025-11-12T19:30:01Z"
  }'
```

#### Minimal Event (Required Fields Only)

```bash
curl -X POST http://localhost:5000/event \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "site-abc-123",
    "event_type": "page_view"
  }'
```

#### Response

**Success (200 OK):**
```json
{
  "message": "Event received"
}
```

**Error (400 Bad Request):**
```json
{
  "error": "Missing required field: site_id"
}
```

### GET /stats

Retrieve aggregated analytics data.

#### Get All-Time Stats for a Site

```bash
curl "http://localhost:5000/stats?site_id=site-abc-123"
```

**Response:**
```json
{
  "site_id": "site-abc-123",
  "date": null,
  "total_views": 1450,
  "unique_users": 212,
  "top_paths": [
    { "path": "/pricing", "views": 700 },
    { "path": "/blog/post-1", "views": 500 },
    { "path": "/", "views": 250 }
  ]
}
```

#### Get Daily Stats for a Site

```bash
curl "http://localhost:5000/stats?site_id=site-abc-123&date=2025-11-12"
```

**Response:**
```json
{
  "site_id": "site-abc-123",
  "date": "2025-11-12",
  "total_views": 450,
  "unique_users": 85,
  "top_paths": [
    { "path": "/pricing", "views": 200 },
    { "path": "/blog/post-1", "views": 150 },
    { "path": "/", "views": 100 }
  ]
}
```

#### No Data Found

```bash
curl "http://localhost:5000/stats?site_id=nonexistent-site"
```

**Response:**
```json
{
  "site_id": "nonexistent-site",
  "date": null,
  "total_views": 0,
  "unique_users": 0,
  "top_paths": []
}
```

#### Error Cases

**Missing site_id:**
```bash
curl "http://localhost:5000/stats"
```

**Response (400 Bad Request):**
```json
{
  "error": "Missing required parameter: site_id"
}
```

**Invalid date format:**
```bash
curl "http://localhost:5000/stats?site_id=site-abc-123&date=invalid-date"
```

**Response (400 Bad Request):**
```json
{
  "error": "Invalid date format. Expected YYYY-MM-DD"
}
```

### GET /health

Check the health status of the Ingestion API.

```bash
curl http://localhost:5000/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "ingestion_api",
  "queue_size": 5
}
```

## Testing

The project includes test scripts to verify functionality:

### Test the Ingestion API

```bash
python test_ingestion.py
```

This will test:
- Valid event submission
- Missing required fields
- Invalid JSON
- Health check endpoint

### Test the Reporting API

```bash
python test_reporting.py
```

This will test:
- Stats retrieval with and without date filters
- Parameter validation
- Error handling

**Note:** For meaningful test results, send some events first using the Ingestion API or `test_ingestion.py`.

## Project Structure

```
tjra/
├── ingestion_api.py      # Service 1 & 3: Ingestion and Reporting API
├── processor.py          # Service 2: Background event processor
├── shared_queue.py       # Shared queue module for cross-process communication
├── requirements.txt      # Python dependencies
├── test_ingestion.py     # Test script for Ingestion API
├── test_reporting.py     # Test script for Reporting API
├── README.md             # This file
├── analytics.db          # SQLite database (created automatically)
├── event_queue.jsonl     # Queue persistence file (created automatically)
└── processor.log         # Processor service logs (created automatically)
```

## Key Design Principles

1. **Fast Ingestion**: Events are queued immediately without blocking on database writes
2. **Asynchronous Processing**: Background worker handles event processing independently
3. **Separation of Concerns**: Each service has a single, well-defined responsibility
4. **Simplicity**: Clean, readable code optimized for clarity and maintainability
5. **Error Handling**: Graceful error handling with informative error messages

## Future Enhancements

For production deployment, consider:

- Replace in-memory queue with Redis or Kafka
- Migrate to PostgreSQL or MySQL for better scalability
- Add authentication and authorization
- Implement rate limiting
- Add monitoring and alerting
- Implement event batching for better performance
- Add database indexes for faster queries
- Implement connection pooling
- Add comprehensive test coverage
- Set up CI/CD pipeline

## License

[Add your license information here]

## Contact

[Add contact information here]
