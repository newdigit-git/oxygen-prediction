<div align="center">
   <h1 style="margin-bottom: 4px; font-size: 2.6rem;">Newdigit Energy-Oxygen Prediction System</h1>
   <h3 style="margin-top: 0; font-weight: 500;">AI Powered Modeling and Optimisation of Distributed Energy and Oxygen Intelligence System for Climate Resilient Healthcare</h3>
</div>

<p align="center">
  <a href="https://github.com/newdigit-git/oxygen-prediction" target="_blank">
    <img src="https://newdigit.tech/icon.png" alt="oxygen-prediction" width="120"/>
  </a>
</p>

---

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Healthcare](https://img.shields.io/badge/Domain-Healthcare-critical)](https://www.who.int/)
[![Real-time](https://img.shields.io/badge/Real--time-IoT%20Analytics-brightgreen)](#features--methods)
[![Frontend](https://img.shields.io/badge/Frontend-React-61dafb?logo=react&logoColor=white)](https://reactjs.org/)
[![UI](https://img.shields.io/badge/UI-Tailwind%20CSS-38b2ac?logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![Backend](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.9+-3776ab?logo=python&logoColor=white)](https://www.python.org/)
[![Database](https://img.shields.io/badge/Database-PostgreSQL-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Container](https://img.shields.io/badge/Container-Docker-2496ed?logo=docker&logoColor=white)](https://www.docker.com/)

---

## 📖 Table of Contents

1. [What is oxygen-prediction?](#what-is-oxygen-prediction)
2. [Features & Architecture](#features--architecture)
3. [Core Intelligence Layers](#core-intelligence-layers)
4. [Data Ingestion Pipeline](#data-ingestion-pipeline)
5. [API Endpoints](#api-endpoints)
6. [How to Run](#how-to-run)
7. [Configuration & Customization](#configuration--customization)
8. [Database Schema](#database-schema)

---

<p align="center">
  <a href="https://github.com/newdigit-git/oxygen-prediction" target="_blank">
    <img src="assets/dashboard.png" alt="oxygen-prediction" />
  </a>
</p>

## What is Newdigit oxygen prediction?

It is an enterprise grade real time monitoring and analytics platform for smart oxygen regulators and energy management systems in healthcare facilities. It ingests continuous telemetry from IoT devices, performs predictive depletion analytics, correlates climate data with health surge patterns, optimizes production planning, and provides clinical outcome feedback loops all with **privacy first**, fully local processing and **no external dependencies**.

The physical smart regulator on the cylinder doesn't do any complex math locally; it simply transmits basic, anonymized metrics, specifically raw cylinder  pressure drop and real-time flow velocity over a low-power cellular network.
<p align="center">
  <a href="https://github.com/newdigit-git/oxygen-prediction" target="_blank">
    <img src="assets/jaw-oxygen-sensor.png" alt="oxygen-prediction" />
  </a>
</p>


Built for hospitals, clinics, and distributed medical supply chains, it enables predictive maintenance, resource optimization, and intelligent decision-making at scale.

---

## Features & Architecture

### Core Capabilities

- **Real-Time Telemetry Ingestion:** Stream continuous device metrics (pressure, flow, battery, signal strength) at scale
- **Time-Series Analytics:** Partitioned PostgreSQL storage optimized for high volume sensor data
- **Predictive Depletion Engine:** Calculates oxygen tank depletion using pressure drop gradient analysis (ideal gas approximation)
- **Climate Intelligence:** Correlates regional climate data (PM2.5, humidity, temperature) with health surge patterns
- **Production Optimization:** Forecasts demand and optimizes supply chain logistics in real-time
- **Clinical Feedback Loops:** Captures and analyzes clinical outcomes to improve predictions
- **Async Processing:** Celery + Redis for non blocking enrichment pipeline
- **Export & Sharing:** JSON and HTML exports with full audit trails
- **Privacy-First:** All processing local, no cached data retention, no external APIs required

### Enterprise Features

- **Multi-stage Enrichment:** 4-layer AI pipeline (ingestion → detection → enrichment → insights)
- **Fault Detection:** Automatic flagging of anomalies and device failures
- **Device Registry:** Track all IoT devices with last seen timestamps
- **Session Tracking:** Cross device correlation and session level analytics
- **RESTful API:** OpenAPI/Swagger documentation auto generated
- **Docker-Ready:** Containerized backend, database, and Redis with docker-compose
- **Scalable:** Partitioned tables, connection pooling, async workers

---

## Data Ingestion Pipeline

### Real-Time Telemetry Endpoint
```
POST /api/v1/telemetry

Payload:
{
  "id": "ND0000001",           # Device ID
  "t": 1778918224,              # Unix timestamp
  "b": 94,                       # Battery %
  "p": 142.3,                    # Pressure
  "f": 12.5,                     # Flow rate
  "c": -72,                      # Signal strength
  "l": "6.46667N, 3.63333E"     # Location (GPS)
}
```

### Session Summary Endpoint
```
POST /api/v1/sessions

Payload:
{
  "id": "ND0000001",                          # Device ID
  "sid": "19383883BDGA",                      # Session ID
  "lc": "6.46667N, 3.63333E",                 # Location
  "t_start": "2026-05-15T22:00:00Z",          # Start time
  "t_end": "2026-05-16T00:05:00Z",            # End time
  "i_p": 195.0,                               # Initial pressure
  "f_p": 142.3,                               # Final pressure
  "f_r": 46.3,                                # Flow rate
  "fb_pct": 70,                               # Final battery %
  "hf_log": 0,                                # Fault flag
  "c_st": -72                                 # Signal strength
}
```

---

## Core Intelligence Layers

### Stage 1: Predictive Depletion Analytics
**Description:** Once the server receives the raw data, it maps the device ID to a specific hospital asset, pulls its historical time-series baseline, and runs the thermodynamic calculations to output a precise timeline to zero.

**Input:** Telemetry time series + session summaries  
**Process:** Applies pressure drop gradient; converts using ideal gas approximation  
**Output:** Time To Empty prediction, critical threshold alerts  
**Use Case:** Prevent oxygen shortages, schedule refills proactively

**Example Output:**
```json
{
  "stage": "predictive_depletion_analytics",
  "processed_at": "2026-05-16T12:00:02Z",
  "asset_metadata": {
    "device_id": "REG-NG-8842",
    "facility_id": "FAC-LA-04",
    "facility_name": "General Hospital Pediatric Ward",
    "ward_type": "Pediatric ICU",
    "bed_number": "ICU-08",
    "cylinder_type": "J-Type (Standard 47L)"
  },
  "thermodynamic_metrics": {
    "current_pressure_psi": 1200.0,
    "current_flow_rate_lmin": 5.0,
    "calculated_volume_liters": 3835.0,
    "consumption_velocity_psi_per_hour": -75.0
  },
  "projections": {
    "time_to_empty_minutes": 767.0,
    "estimated_depletion_time": "2026-05-17T00:47:00Z",
    "critical_threshold_alert_time": "2026-05-16T22:47:00Z",
    "status": "NORMAL"
  }
}
```

### Stage 2: Climate & Health Surge Correlation
**Description:** At this stage, the AI aggregates the localized data from the hospital cluster and merges it with real-time external environmental APIs to forecast upcoming regional health emergencies.

**Input:** Regional aggregated telemetry + external climate APIs  
**Process:** Risk scoring (PM2.5, humidity, temperature); spike detection  
**Output:** Surge forecasts, facility alerts, intervention recommendations  
**Use Case:** Anticipate respiratory health crises, allocate resources

**Example Output:**
```json
{
  "stage": "climate_health_surge_correlation",
  "processed_at": "2026-05-16T12:05:00Z",
  "geographical_scope": {
    "region_code": "NG-LA-EPE",
    "zone": "Lagos East",
    "monitored_clinics_count": 14
  },
  "environmental_inputs": {
    "pm2_5_aqi": 185.0,
    "humidity_percentage": 22.0,
    "temperature_celsius": 34.5,
    "harmattan_dust_index": "SEVERE",
    "climate_anomaly_detected": true    
  },
  "ml_surge_forecasting": {
    "historical_pattern_match_id": "SURGE_2024_H4",
    "predicted_respiratory_admission_increase_percentage": 42.0,
    "forecast_confidence_score": 0.91,
    "surge_window_start": "2026-05-18T12:00:00Z",
    "time_horizon_hours": 48.0,
    "risk_level": "HIGH"
  }
}
```

### Stage 3: Production Planning Optimization
**Description:** Finally, the AI synthesizes individual asset depletion timelines with the macro level regional surge forecasts. It translates health data into actionable, industrial logistics instructions for your oxygen plant floor.

**Input:** Demand forecasts, utilization metrics, distribution networks  
**Process:** Supply chain optimization, scheduling, warehouse routing  
**Output:** Production plans, action schedules, cost savings  
**Use Case:** Reduce wastage, improve efficiency, lower costs

**Example Output:**
```json
{
  "stage": "closed_loop_production_coordination",
  "processed_at": "2026-05-16T12:10:00Z",
  "target_plant": {
    "plant_id": "NEWDIGIT-PLANT-01",
    "location": "Lagos Hub",
    "current_daily_capacity_liters": 500000
  },
  "ai_demand_forecast": {
    "baseline_regional_demand_liters": 320000,
    "predicted_surge_demand_liters": 465000,
    "deficit_risk_liters": 145000,
    "recommended_plant_utilization_percentage": 93.0
  },
  "automated_action_plan": {
    "production_schedule_shift": "RAMP_UP_IMMEDIATE",
    "priority_routing_queue": [
      {
        "facility_id": "FAC-LA-04",
        "facility_name": "General Hospital Pediatric Ward",
        "urgency_score": 9.8,
        "allocated_cylinders": 25,
        "dispatch_deadline": "2026-05-16T18:00:00Z"
      },
      {
        "facility_id": "FAC-LA-11",
        "facility_name": "St. Mary Maternal Clinic",
        "urgency_score": 8.4,
        "allocated_cylinders": 15,
        "dispatch_deadline": "2026-05-16T21:30:00Z"
      }
    ]
  }
}
```

### Stage 4: Clinical Outcomes Loop
**Description:** This stage ingests aggregated, privacy compliant (no personally identifiable information) clinical records from the ward to analyze the direct health outcomes generated by our predictive supply chain.

**Input:** Patient cohorts, intervention metrics, historical models  
**Process:** Outcome analysis, feedback signals, trend detection  
**Output:** Model refinement, clinical insights, intervention effectiveness  
**Use Case:** Evidence-based decision making, continuous improvement

**Example Output:**
```json
{
  "stage": "patient_outcome_efficacy_loop",
  "processed_at": "2026-05-16T13:00:00Z",
  "clinical_environment": {
    "facility_id": "FAC-LA-04",
    "facility_name": "General Hospital Pediatric Ward",
    "evaluation_period": "2026-05-01T00:00:00Z to 2026-05-15T23:59:59Z"
  },
  "anonymized_patient_cohort_data": [
    {
      "cohort_id": "CH-PED-RESP-01",
      "age_group": "Neonatal (0-28 days)",
      "gender_distribution": {
        "male_percentage": 52.0,
        "female_percentage": 48.0
      },
      "primary_diagnosis": "Severe Neonatal Pneumonia / RDS",
      "total_patients_tracked": 34,
      "clinical_outcomes": {
        "discharged_healthy": 32,
        "transferred_to_tertiary": 1,
        "mortality_count": 1,
        "survival_rate_percentage": 94.1
      }
    },
    {
      "cohort_id": "CH-PED-RESP-02",
      "age_group": "Infant (29 days - 1 year)",
      "gender_distribution": {
        "male_percentage": 45.0,
        "female_percentage": 55.0
      },
      "primary_diagnosis": "Acute Bronchiolitis (Harmattan-induced)",
      "total_patients_tracked": 58,
      "clinical_outcomes": {
        "discharged_healthy": 57,
        "transferred_to_tertiary": 1,
        "mortality_count": 0,
        "survival_rate_percentage": 100.0
      }
    }
  ],
  "ai_intervention_correlation": {
    "predictive_alerts_issued_to_ward": 6,
    "average_delivery_lead_time_hours": 18.5,
    "zero_oxygen_stockout_incidents_maintained": true,
    "historical_cohort_survival_baseline_percentage": 82.4,
    "measured_survival_improvement_percentage": 14.1
  },
  "model_feedback_loop": {
    "supply_adequacy_score": 0.98,
    "clinical_need_met_index": "OPTIMAL",
    "algorithm_tuning_action": "No adjustment required; predictive threshold aligned with clinical demand velocity."
  }
}
```

---



## API Endpoints

### Health & Status
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Root endpoint with service info |
| `GET` | `/health` | Application health check |
| `GET` | `/api/v1/analytics/health` | Service health status |

### Telemetry (Real-Time Data)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/telemetry` | Ingest device telemetry |
| `GET` | `/api/v1/telemetry/device/{device_id}` | Get device telemetry history |

### Sessions (Summary Data)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/sessions` | Ingest session summary |
| `GET` | `/api/v1/sessions/{session_id}` | Get session details |
| `GET` | `/api/v1/sessions/device/{device_id}` | Get device sessions |

### Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/analytics/depletion/{device_id}` | Get oxygen depletion predictions |

---

## How to Run

### Requirements
- **Python** 3.9+
- **Node.js** 18+ (for frontend, optional)
- **PostgreSQL** 12+
- **Docker & Docker Compose** (optional, recommended)
- **Redis** (optional, for Celery workers)

### Option 1: Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/newdigit-git/oxygen-prediction.git
cd oxygen-prediction

# Start all services (PostgreSQL + Redis + API)
docker-compose up --build

```

### Option 2: Local Manual Setup

**Backend:**
```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate
# OR Activate (Linux/macOS)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit .env with your PostgreSQL credentials

# Create database
createdb oxygen_pred

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 3: Bootstrap Scripts

**Windows:**
```cmd
bootstrap.bat
```

**Linux/macOS:**
```bash
chmod +x bootstrap.sh
./bootstrap.sh
```

---

### Customization Points

- **Add Platforms:** Modify `app/models/models.py` to add new table schemas
- **Business Logic:** Extend `app/services/ingestion_service.py` with new engines
- **API Routes:** Add endpoints in `app/api/routes/`
- **Celery Tasks:** Define async jobs in `app/workers/tasks.py`

---

## Database Schema

Seven core tables optimized for time-series and relational data:

| Table | Purpose | Partitioning |
|-------|---------|--------------|
| `devices` | IoT device registry | None |
| `telemetry` | Real-time sensor data | By month (recommended) |
| `sessions` | Session summaries | None |
| `depletion_predictions` | Oxygen depletion forecasts | None |
| `surge_forecasts` | Climate surge predictions | None |
| `production_plans` | Supply chain optimization | None |
| `clinical_outcomes` | Clinical feedback data | None |

**Indexes:** All foreign keys, timestamps, and frequently-queried fields are indexed for optimal performance.

---


## Credits & License

- **Creator:** Newdigit Team
- **Built with:** FastAPI, PostgreSQL, Docker
- **License:** MIT (see [LICENSE](LICENSE))



---
