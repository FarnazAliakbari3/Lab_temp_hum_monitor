IOT Temperature-Humidity Controller

Overview
This project is a local IoT controller for multiple labs (lab1-lab3). Sensors publish temperature and humidity over MQTT. A controller applies threshold rules and sends actuator commands. A CherryPy registry exposes REST endpoints for a dashboard and Telegram bot. ThingSpeak upload is optional. Configuration is stored in JSON files; no database is used.

Key goals
- Collect temperature and humidity data from multiple labs.
- Apply threshold logic with hysteresis and off-delay to control actuators.
- Provide REST endpoints, Telegram control, and a local dashboard.
- Keep the system local, lightweight, and database-free.

Architecture at a glance
- MQTT broker (Mosquitto) handles sensor and actuator messaging.
- Controller service owns the live in-memory state and control logic.
- Registry service exposes REST endpoints and combines catalog data with live state.
- Frontend and Telegram bot consume the registry REST API.
- ThingSpeak adaptor is optional and uploads data using REST.

Services
- mqtt: Mosquitto broker for sensor and actuator messages.
- controller: MQTT client, sensor/actuator bridges, in-memory state, control logic, watchdog, and a small HTTP API.
- registry: REST API for catalog CRUD and /status. Reads live state from the controller.
- telegram_bot: Bot that polls /status, sends alerts, and issues /command requests.
- thingspeak: Optional adaptor that reads /status and writes configured fields to ThingSpeak.
- frontend: Static UI that polls /status and renders lab cards.

Real-time data flow
Sensors to controller
- MQTT topic: labs/<lab_id>/sensors/<sensor_id>/state
- Payload: {"t": float, "h": float, "ts": unix_ts, "sensor_id": "..."}
- QoS 1, retain true

Controller to actuators
- MQTT topic: labs/<lab_id>/actuators/<actuator_id>/cmd
- Payload: {"action": "ON|OFF", "source": "controller|bot|ui", "ts": unix_ts}

Actuator feedback
- MQTT topic: labs/<lab_id>/actuators/<actuator_id>/state
- Payload: {"state": "ON|OFF", "ts": unix_ts, "actuator_id": "..."}

REST data flow
- controller exposes GET /snapshot for live state.
- registry exposes GET /status combining catalog + snapshot.
- frontend and telegram_bot read from registry /status.
- telegram_bot posts to registry /command for manual control.
- thingspeak adaptor reads registry /status and posts to ThingSpeak.

Control logic (rules.py)
- Each lab has thresholds in catalog/thresholds.json.
- Hysteresis prevents rapid toggling.
- off_delay_sec ensures a minimum OFF time between cycles.
- Fan: ON when temp or humidity exceeds high thresholds, OFF only when both fall below low thresholds.
- Heater, humidifier, dehumidifier use thresholds with hysteresis.

Catalog files (JSON, no database)
- catalog/labs.json: lab metadata (id, name, notes).
- catalog/devices.json: sensors and actuators mapped to labs.
- catalog/thresholds.json: per-lab thresholds and delays.
- catalog/permissions.json: Telegram chat IDs and roles.
- catalog/catalog_store.py: atomic read/write for JSON files.

REST API (registry)
- GET /health: service health.
- GET /status: combined live status for all labs.
- POST /command: manual actuator command.
- CRUD: /labs, /lab/{id}, /sensors, /sensor/{id}, /actuators, /actuator/{id}
- GET/PUT: /thresholds, /threshold/{lab_id}
- GET/PUT: /permissions

Telegram bot
- Reads /status for alerts and status display.
- Sends /command for manual actuator control.
- Uses catalog/permissions.json for allowed chat IDs.

Frontend dashboard
- Static UI polls /status every few seconds.
- Shows lab cards, thresholds, sensor values, and actuator states.
- Marks stale and out-of-range values for quick scanning.

ThingSpeak
- ThingSpeak/adaptor.py reads /status from the registry and posts mapped fields.
- Configure channels and fields in ThingSpeak/keys.json.

Repository layout
- catalog/: JSON catalogs and atomic read/write helper.
- catalog_registry/: REST API and validators.
- controller/: control logic, state memory, rules, controller API.
- Device_connectors/: MQTT client, sensor bridge, actuator bridge.
- simulators/: lab simulator for mock sensor data.
- User_awareness/: Telegram bot.
- ThingSpeak/: adaptor and keys.json.
- frontEnd/: static dashboard.
- docker-compose.yml: service orchestration.

Getting started
Prerequisites
- Docker and Docker Compose.

Start with Docker
1) Build and start:
   docker compose up -d --build
2) Open dashboard:
   http://localhost
3) Registry API:
   http://localhost:8080/status

Run locally (no Docker)
1) Create and activate a virtual environment.
2) Install dependencies:
   pip install -r requirements.txt
3) Start Mosquitto locally.
4) Start controller:
   python -m controller.controller_api
5) Start registry:
   python -m catalog_registry.registry_api
6) Start Telegram bot or ThingSpeak if needed.

Environment variables
- TELEGRAM_BOT_TOKEN: Telegram bot token.
- REGISTRY_API_URL: Base URL for registry (default http://localhost:8080).
- PERMISSIONS_PATH: Path to permissions.json (default ./catalog/permissions.json).
- THINGSPEAK_KEYS_PATH: Path to ThingSpeak keys.json.
- THINGSPEAK_POLL_SEC: Polling interval for ThingSpeak updates.
- THINGSPEAK_UPDATE_URL: ThingSpeak update endpoint.
- CONTROL_LOOP_SEC: Controller loop interval.
- SIM_LOOP_SEC: Sensor simulator interval.
- MOCK_SENSORS: Enable simulator (1/0).

Permissions
catalog/permissions.json controls which chat IDs can use the bot and receive alerts.
Add your chat ID to owners or operators and restart the telegram_bot container.

Notes
- JSON files are the source of truth for catalogs. No database is used.
- The controller is the only component that holds live sensor/actuator state.
- The registry aggregates catalogs with live controller state into /status.
