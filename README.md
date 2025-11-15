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

### Asynchronous Processing Implementation

The system implements asynchronous event processing using a **hybrid queue architecture** that combines in-memory speed with file-based persistence for cross-process communication.

#### How the Queue Works

The asynchronous processing is implemented through a two-layer queue system:

1. **Ingestion API Layer (Fast Path)**:
   - Uses Python's `queue.Queue` (thread-safe in-memory queue) for immediate event storage
   - Events are simultaneously written to a JSONL (JSON Lines) file (`event_queue.jsonl`) for persistence
   - This dual-write approach ensures:
     - **Speed**: In-memory queue provides instant queuing (microseconds)
     - **Durability**: File persistence ensures events survive process restarts
     - **Cross-Process Communication**: File allows separate processes to share the queue

2. **Processor Layer (Consumer)**:
   - Reads directly from the file-based queue (since it runs in a separate process)
   - Uses file locking (`fcntl` on Linux/Mac, OS-level on Windows) to prevent race conditions
   - Implements a polling loop with timeout to check for new events
   - Removes processed events from the queue file atomically

#### Implementation Details

```python
# Ingestion API: Fast queuing
event_queue.put(event_data)  # In-memory + file write
return {"message": "Event received"}  # Immediate response

# Processor: Background consumption
while True:
    event = event_queue.get(timeout=1)  # Read from file
    process_event(event)  # Insert into database
```

#### Why This Approach?

1. **Minimal Latency**: 
   - Events are queued in microseconds without waiting for database I/O
   - HTTP response is sent immediately after queuing
   - Database writes happen asynchronously in the background

2. **Simplicity**: 
   - No external dependencies (Redis, Kafka, etc.) required
   - Works out-of-the-box with Python standard library
   - Easy to understand and debug

3. **Reliability**:
   - File-based persistence ensures events aren't lost if the processor restarts
   - Cross-process file locking prevents data corruption
   - Queue file acts as a buffer during high traffic

4. **Separation of Concerns**:
   - Ingestion API focuses solely on receiving and queuing events
   - Processor handles all database operations independently
   - Services can be scaled or restarted independently

#### Real-World Alternatives

For production environments, consider these alternatives:

- **Redis**: In-memory data store with pub/sub capabilities, excellent for high-throughput queuing
  - Pros: Fast, supports pub/sub, built-in persistence options
  - Cons: Requires separate service, additional infrastructure

- **Apache Kafka**: Distributed event streaming platform, ideal for large-scale event processing
  - Pros: High throughput, distributed, durable, supports replay
  - Cons: Complex setup, requires Zookeeper/Kafka cluster

- **RabbitMQ**: Message broker with advanced routing and reliability features
  - Pros: Reliable, supports complex routing, message acknowledgments
  - Cons: Requires separate service, more complex than needed for simple queuing

- **Amazon SQS / Google Cloud Pub/Sub**: Managed queue services for cloud deployments
  - Pros: Fully managed, scalable, no infrastructure to maintain
  - Cons: Vendor lock-in, costs scale with usage

These alternatives provide:
- Better scalability and distributed processing
- Enhanced durability and message persistence
- Advanced features like message acknowledgments, retries, and dead-letter queues
- Better monitoring and observability
- Production-grade reliability and fault tolerance

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

### Database Overview

The system uses a **SQLite database** (`analytics.db`) to store all analytics events. SQLite is chosen for simplicity and zero-configuration setup, making it ideal for development and small-to-medium scale deployments.

### Events Table

The database contains a single `events` table that stores all analytics events.

#### Schema Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        events                                │
├─────────────┬──────────┬──────────────┬──────┬──────┬───────┤
│ id          │ site_id  │ event_type   │ path │ user │ time  │
│ (PK, AI)    │ (NN)     │ (NN)         │      │ _id  │ stamp │
├─────────────┼──────────┼──────────────┼──────┼──────┼───────┤
│ INTEGER     │ TEXT     │ TEXT         │ TEXT │ TEXT │ TEXT  │
└─────────────┴──────────┴──────────────┴──────┴──────┴───────┘
```

#### Table Structure

| Column      | Type    | Constraints              | Description                          |
|-------------|---------|--------------------------|--------------------------------------|
| `id`        | INTEGER | PRIMARY KEY AUTOINCREMENT| Unique identifier for each event     |
| `site_id`   | TEXT    | NOT NULL                 | Identifier for the website/site      |
| `event_type`| TEXT    | NOT NULL                 | Type of event (e.g., "page_view")    |
| `path`      | TEXT    | NULL                     | URL path of the page                 |
| `user_id`   | TEXT    | NULL                     | Identifier for the user              |
| `timestamp` | TEXT    | NULL                     | ISO 8601 timestamp of the event      |

#### SQL Definition

```sql
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    path TEXT,
    user_id TEXT,
    timestamp TEXT
);
```

#### Example Data

```
id | site_id      | event_type | path         | user_id    | timestamp
---|--------------|------------|--------------|------------|-------------------
1  | site-abc-123 | page_view  | /pricing     | user-xyz-1 | 2025-11-12T19:30:01Z
2  | site-abc-123 | page_view  | /blog        | user-xyz-2 | 2025-11-12T19:31:15Z
3  | site-abc-123 | click      | /pricing     | user-xyz-1 | 2025-11-12T19:32:00Z
4  | site-def-456 | page_view  | /home        | user-abc-1 | 2025-11-12T19:33:00Z
```

#### Database Initialization

The database file (`analytics.db`) is **automatically created and initialized** when the Processor service starts. No manual setup is required. The Processor will:

1. Check if `analytics.db` exists
2. Create the database file if it doesn't exist
3. Create the `events` table with the proper schema
4. Log the initialization status

#### Notes

- **File Location**: The database file is created in the same directory as the application
- **Concurrency**: SQLite handles concurrent reads well, but writes are serialized
- **Scalability**: For high-traffic production use, consider migrating to PostgreSQL or MySQL
- **Backup**: The database is a single file that can be easily backed up or copied

## Setup Instructions

### Prerequisites

- **Python 3.7 or higher** (Python 3.8+ recommended)
- **pip** (Python package manager - usually comes with Python)
- **Git** (optional, for cloning the repository)

### Step 1: Get the Project

#### Option A: Clone from Git Repository

```bash
git clone <repository-url>
cd tjra
```

#### Option B: Download and Extract

Download the project files and extract them to a directory, then navigate to it:

```bash
cd tjra
```

### Step 2: Install Dependencies

Install the required Python packages using pip.

#### On Linux/Mac:

```bash
pip install -r requirements.txt
```

Or if you need to use `pip3`:

```bash
pip3 install -r requirements.txt
```

#### On Windows:

```cmd
pip install -r requirements.txt
```

Or if you need to use `python -m pip`:

```cmd
python -m pip install -r requirements.txt
```

**Note:** If you encounter permission errors, you may need to use:
- Linux/Mac: `pip install --user -r requirements.txt`
- Windows: Run Command Prompt as Administrator

This will install:
- **Flask 3.0.0** - HTTP framework for the API
- **Werkzeug 3.0.1** - WSGI utilities (dependency of Flask)
- **requests 2.31.0** - HTTP library for test scripts

### Step 3: Verify Installation

Verify that Python and required packages are installed:

```bash
python --version  # Should show Python 3.7 or higher
python -c "import flask; print(flask.__version__)"  # Should show 3.0.0
```

### Step 4: Initialize the Database

**No manual database setup required!** The database is automatically initialized when you start the Processor service. The Processor will:

- Create the `analytics.db` SQLite database file (if it doesn't exist)
- Create the `events` table with the proper schema
- Log the initialization status

Simply proceed to starting the services.

### Step 5: Start the Services

The system requires **two services** to be running simultaneously. You'll need **two terminal/command prompt windows**.

---

## Running on Windows

### Terminal 1: Start the Ingestion/Reporting API

1. Open **Command Prompt** or **PowerShell**
2. Navigate to the project directory:
   ```cmd
   cd C:\Users\HP\Desktop\tjra
   ```
3. Start the API service:
   ```cmd
   python ingestion_api.py
   ```

You should see:
```
 * Running on http://0.0.0.0:5000
 * Debug mode: on
```

The service is now running on `http://localhost:5000`

### Terminal 2: Start the Processor

1. Open a **new Command Prompt** or **PowerShell** window
2. Navigate to the project directory:
   ```cmd
   cd C:\Users\HP\Desktop\tjra
   ```
3. Start the Processor service:
   ```cmd
   python processor.py
   ```

You should see:
```
INFO - Database initialized: analytics.db
INFO - Processor is running. Waiting for events...
```

The Processor is now running and ready to process events.

---

## Running on Linux/Mac

### Terminal 1: Start the Ingestion/Reporting API

1. Open a terminal
2. Navigate to the project directory:
   ```bash
   cd ~/Desktop/tjra
   # or wherever you placed the project
   ```
3. Start the API service:
   ```bash
   python3 ingestion_api.py
   ```
   (Use `python3` if `python` points to Python 2.x)

You should see:
```
 * Running on http://0.0.0.0:5000
 * Debug mode: on
```

The service is now running on `http://localhost:5000`

### Terminal 2: Start the Processor

1. Open a **new terminal** window
2. Navigate to the project directory:
   ```bash
   cd ~/Desktop/tjra
   ```
3. Start the Processor service:
   ```bash
   python3 processor.py
   ```

You should see:
```
INFO - Database initialized: analytics.db
INFO - Processor is running. Waiting for events...
```

The Processor is now running and ready to process events.

---

### Important Notes

- **Both services must be running** for the system to function properly:
  - The Ingestion API receives and queues events
  - The Processor processes queued events and stores them in the database
  - The Reporting API queries the database for analytics

- **Keep both terminals open** while using the system

- **To stop the services**: Press `Ctrl+C` in each terminal window

- **Port 5000**: If port 5000 is already in use, you'll see an error. Either:
  - Stop the service using port 5000, or
  - Modify the port in `ingestion_api.py` (last line: `app.run(host='0.0.0.0', port=5000)`)

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

This section provides example `curl` commands to test the API endpoints. Make sure both services are running before testing.

### POST /event

Send analytics events to the system. This endpoint receives events and queues them for asynchronous processing.

#### Example 1: Full Event with All Fields

**Linux/Mac:**
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

**Windows (Command Prompt):**
```cmd
curl -X POST http://localhost:5000/event -H "Content-Type: application/json" -d "{\"site_id\": \"site-abc-123\", \"event_type\": \"page_view\", \"path\": \"/pricing\", \"user_id\": \"user-xyz-789\", \"timestamp\": \"2025-11-12T19:30:01Z\"}"
```

**Windows (PowerShell):**
```powershell
curl.exe -X POST http://localhost:5000/event -H "Content-Type: application/json" -d '{\"site_id\": \"site-abc-123\", \"event_type\": \"page_view\", \"path\": \"/pricing\", \"user_id\": \"user-xyz-789\", \"timestamp\": \"2025-11-12T19:30:01Z\"}'
```

#### Example 2: Minimal Event (Required Fields Only)

**Linux/Mac:**
```bash
curl -X POST http://localhost:5000/event \
  -H "Content-Type: application/json" \
  -d '{
    "site_id": "site-abc-123",
    "event_type": "page_view"
  }'
```

**Windows (Command Prompt):**
```cmd
curl -X POST http://localhost:5000/event -H "Content-Type: application/json" -d "{\"site_id\": \"site-abc-123\", \"event_type\": \"page_view\"}"
```

**Note:** If `timestamp` is not provided, it will be automatically added with the current UTC time.

#### Success Response (200 OK)

```json
{
  "message": "Event received"
}
```

#### Error Response (400 Bad Request)

```json
{
  "error": "Missing required field: site_id"
}
```

---

### GET /stats

Retrieve aggregated analytics data from the database. This endpoint queries the database and returns statistics.

#### Example 1: Get All-Time Stats for a Site

**Linux/Mac:**
```bash
curl "http://localhost:5000/stats?site_id=site-abc-123"
```

**Windows:**
```cmd
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

#### Example 2: Get Daily Stats for a Site

**Linux/Mac:**
```bash
curl "http://localhost:5000/stats?site_id=site-abc-123&date=2025-11-12"
```

**Windows:**
```cmd
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

#### Example 3: No Data Found

**Linux/Mac/Windows:**
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

**Missing site_id parameter:**
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

---

### GET /health

Check the health status of the Ingestion API and view the current queue size.

**Linux/Mac/Windows:**
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

---

### Testing Tips

1. **Send multiple events** to see meaningful statistics:
   ```bash
   # Send several events with different paths
   curl -X POST http://localhost:5000/event -H "Content-Type: application/json" -d '{"site_id": "site-abc-123", "event_type": "page_view", "path": "/pricing"}'
   curl -X POST http://localhost:5000/event -H "Content-Type: application/json" -d '{"site_id": "site-abc-123", "event_type": "page_view", "path": "/blog"}'
   curl -X POST http://localhost:5000/event -H "Content-Type: application/json" -d '{"site_id": "site-abc-123", "event_type": "page_view", "path": "/pricing"}'
   ```

2. **Wait a moment** after sending events before querying stats (to allow the Processor to process them)

3. **Check the Processor terminal** to see events being processed in real-time

4. **Use the test scripts** for automated testing:
   ```bash
   python test_ingestion.py
   python test_reporting.py
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


