# FastAPI Application Structure

## Directory Overview

```
app/
├── __init__.py
├── main.py                    # FastAPI application entry point
├── schemas.py                 # Pydantic models for request/response validation
├── api/
│   ├── __init__.py
│   └── routes/
│       ├── __init__.py
│       ├── telemetry.py      # Real-time telemetry endpoints
│       ├── sessions.py       # Session summary endpoints
│       └── analytics.py      # Analytics and health check endpoints
├── core/
│   ├── __init__.py
│   ├── config.py             # Settings and configuration management
│   └── database.py           # Database connection and session setup
├── models/
│   ├── __init__.py
│   └── models.py             # SQLAlchemy ORM model definitions
├── services/
│   ├── __init__.py
│   └── ingestion_service.py  # Business logic and service layer
└── workers/
    ├── __init__.py
    └── tasks.py              # Celery async task definitions
```

## Module Descriptions

### `main.py`
- Initializes the FastAPI application
- Registers route routers
- Sets up CORS middleware
- Creates database tables on startup
- Defines root and health check endpoints

### `schemas.py`
Pydantic models for request/response validation:
- `TelemetryCreate` - Telemetry ingestion payload
- `SessionCreate` - Session summary ingestion payload
- `DepletionPredictionResponse` - Depletion prediction response
- `DeviceResponse` - Device information response

### `api/routes/`

#### `telemetry.py`
Endpoints:
- `POST /api/v1/telemetry` - Ingest real-time telemetry data
- `GET /api/v1/telemetry/device/{device_id}` - Retrieve device telemetry history

#### `sessions.py`
Endpoints:
- `POST /api/v1/sessions` - Ingest session summary
- `GET /api/v1/sessions/{session_id}` - Get specific session
- `GET /api/v1/sessions/device/{device_id}` - Get device sessions

#### `analytics.py`
Endpoints:
- `GET /api/v1/analytics/depletion/{device_id}` - Get depletion predictions
- `GET /api/v1/analytics/health` - Health check

### `core/`

#### `config.py`
Configuration management using Pydantic Settings:
- Database URL
- API settings
- Server host/port
- Redis/Celery configuration
- Debug mode

#### `database.py`
Database setup:
- Sync engine for migrations
- Async engine for operations
- Session factories
- Base declarative class for ORM models
- Dependency for route handlers

### `models/models.py`
SQLAlchemy ORM models:
- `Device` - IoT devices
- `Telemetry` - Time-series telemetry data
- `Session` - Session summaries
- `DepletionPrediction` - Predicted oxygen depletion
- `SurgeForecast` - Climate surge forecasts
- `ProductionPlan` - Production schedule
- `ClinicalOutcome` - Clinical data

### `services/ingestion_service.py`
Business logic layer:
- `IngestionService` - Telemetry and session ingestion
- `DepletionEngine` - Oxygen depletion calculations
- `ClimateEngine` - Climate risk assessment
- `ProductionEngine` - Production planning optimization
- `ClinicalEngine` - Clinical outcomes evaluation

### `workers/tasks.py`
Celery async tasks:
- `process_telemetry_batch` - Batch telemetry processing
- `generate_depletion_prediction` - Generate predictions
- `generate_surge_forecast` - Climate forecasting

## Data Flow

```
1. IoT Device sends telemetry/session data
   ↓
2. FastAPI endpoint receives and validates with Pydantic schema
   ↓
3. Service layer processes and stores in PostgreSQL
   ↓
4. Optional: Celery task triggers enrichment pipeline
   ↓
5. Response returned to device/client
```

## Database Schema

### Telemetry Table (Time-Series)
```
- id: Primary key
- device_id: Foreign key to devices
- timestamp: Unix timestamp for data point
- battery: Battery percentage
- pressure: Current pressure
- flow: Flow rate
- signal_strength: Signal quality
- location: GPS coordinates
```

### Session Table
```
- sid: Session ID (primary key)
- device_id: Foreign key to devices
- location: GPS coordinates
- t_start/t_end: Session duration
- initial_pressure/final_pressure: Pressure readings
- flow_rate: Average flow during session
- battery_final: Final battery percentage
- fault_flag: Device fault indicator
- signal_strength: Connection quality
```

## Configuration

See `.env.example` for required environment variables:
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis server (for Celery)
- `DEBUG` - Development mode flag
- `HOST/PORT` - Server binding

## Dependencies

See `requirements.txt` for full list:
- FastAPI - Web framework
- SQLAlchemy 2.0 - ORM
- Psycopg2 - PostgreSQL adapter
- Alembic - Database migrations
- Pydantic - Data validation
- Celery - Async tasks
- Redis - Message broker (optional)
- Uvicorn - ASGI server

## Future Enhancements

1. Add database migration support with Alembic
2. Implement async/await throughout with AsyncSession
3. Add query optimization and partitioning for telemetry
4. Implement Celery workers for enrichment pipeline
5. Add authentication/authorization
6. Implement WebSocket for real-time updates
7. Add caching layer with Redis
8. Comprehensive logging and monitoring
