# RabbitMQ 4.1.0 Message Orchestrator

A modern, high-reliability solution and web application designed for **RabbitMQ 4.1.0** that allows moving or deleting (purging) a specific message from a queue based on its **Message ID**, while preserving the exact relative order of all remaining messages and preventing data loss.

![RabbitMQ 4.1.0 Ready](https://img.shields.io/badge/RabbitMQ-4.1.0-orange.svg)
![Python](https://img.shields.io/badge/Python-3.12-blue.svg)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-teal.svg)
![React](https://img.shields.io/badge/Frontend-React_19_+_Vite-indigo.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## Features

- **Selective Message Move/Delete by ID:** Locate any message across the entire queue without manual CLI or destructive scripts.
- **Strict FIFO Ordering Preservation:** Drains, filters, and restores queues through temporary staging queues using confirmed AMQP streams.
- **Concurrent Producer Isolation:** Diverts exchange bindings to an ingress buffer queue during execution so newly arriving messages are not lost or interleaved.
- **Zero-Loss Guarantees:** Publisher confirms (`channel.confirm_delivery()`) ensure messages are persisted before source acknowledgments (`basic.ack`).
- **Crash Detection & 1-Click Rollback:** Persistent write-ahead journal prevents orphaned messages and lets administrators roll back interrupted operations.
- **Non-Destructive Queue Inspection:** Sample queue head messages, view payloads and headers, and pick target IDs with one click.
- **Real-Time Visual Pipeline:** Progress tracker with Server-Sent Events (SSE) streaming live counts, metrics, and logs.

---

## Quick Start (Docker Compose)

The easiest way to run the application alongside RabbitMQ 4.1.0 is with Docker Compose:

```bash
# 1. Start RabbitMQ 4.1.0 and the Manager UI
docker compose up -d

# 2. Access the Web Application
open http://localhost:8000

# 3. Access the RabbitMQ Management UI
open http://localhost:15672 (guest/guest)
```

---

## Local Development Setup

### Prerequisites
- **Python 3.12+** (managed via `uv` or system Python)
- **Node.js 20+** and `npm`
- **RabbitMQ 4.1.0** instance (or any RabbitMQ 3.12+ / 4.x broker)

### 1. Backend Setup
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies (if not already done)
pip install -r backend/requirements.txt

# Run FastAPI backend with live reload
PYTHONPATH=. uvicorn backend.app.main:app --reload --port 8000
```

### 2. Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Run Vite dev server with proxy to backend
npm run dev
```
Visit `http://localhost:5173` for the Vite hot-reloading frontend.

---

## Seeding Test Data

You can seed any queue with ordered sample messages to test selective purge/move:

```bash
source .venv/bin/activate
python backend/scripts/seed_sample_queue.py --queue demo_orders --count 20 --target-id TARGET-MSG-777 --target-index 7
```

This will publish 20 ordered messages into `demo_orders`, with the 7th message having `message_id="TARGET-MSG-777"`.

---

## Running the Automated Test Suite

Run the full pytest suite for queue locking, journal persistence, API routes, and orchestrator lifecycle:

```bash
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests -v
```

---

## Project Structure

```
rabbitmq-manager/
├── ARCHITECTURE.md                 # In-depth technical report & ordering proofs
├── Dockerfile                      # Multi-stage production container
├── docker-compose.yml              # RabbitMQ 4.1.0 + App compose
├── prompt.txt                      # Original technical specification
├── backend/
│   ├── app/
│   │   ├── config.py               # Dynamic settings & RabbitMQ credentials
│   │   ├── main.py                 # FastAPI application entry point
│   │   ├── models/
│   │   │   └── schemas.py          # Pydantic schemas (Queues, Ops, Recovery)
│   │   ├── routers/
│   │   │   ├── config.py           # /api/config endpoints
│   │   │   ├── operations.py       # /api/operations (SSE streaming, recovery)
│   │   │   ├── queues.py           # /api/queues (sampling, metrics, locks)
│   │   │   └── system.py           # /api/system/status
│   │   └── services/
│   │       ├── journal.py          # Write-ahead log & queue mutex locks
│   │       ├── orchestrator.py     # 4-Phase execution lifecycle & rollback
│   │       ├── rabbitmq_amqp.py    # Confirmed streaming AMQP 0-9-1 worker
│   │       └── rabbitmq_api.py     # HTTP Management API client
│   ├── scripts/
│   │   └── seed_sample_queue.py    # Test queue seeder script
│   └── tests/
│       ├── test_api.py             # FastAPI endpoint integration tests
│       ├── test_journal.py         # WAL persistence & lock contention tests
│       └── test_orchestrator.py    # End-to-end operation lifecycle tests
└── frontend/
    ├── src/
    │   ├── App.tsx                 # Main layout & dashboard state
    │   ├── components/
    │   │   ├── ConfirmationModal.tsx   # Safety confirmation dialog
    │   │   ├── ConnectionModal.tsx     # Broker settings & test tool
    │   │   ├── ExecutionMonitor.tsx    # Live pipeline stepper & SSE logs
    │   │   ├── HistoryTable.tsx        # Audit log of past executions
    │   │   ├── MessageSampleModal.tsx  # Non-destructive queue inspector
    │   │   ├── Navbar.tsx              # Status header
    │   │   ├── OperationForm.tsx       # Move/Delete configuration form
    │   │   ├── QueueSelector.tsx       # Queue picker with consumer warnings
    │   │   └── RecoveryAlert.tsx       # Emergency rollback & recovery banner
    │   ├── services/
    │   │   └── api.ts                  # REST API client
    │   └── types/
    │       └── index.ts                # TypeScript interfaces
    └── vite.config.ts
```

---

## Safety Recommendations for Production Queues

1. **Pause External Consumers:** Prior to initiating an operation, pause consumers bound to the source queue to prevent them from reading messages out of sequence during the drain phase.
2. **Quorum Queues vs Classic Queues:** Both queue types are supported. For Quorum queues, ensure delivery limits are appropriately sized so redeliveries during recovery are not dropped.
3. **Emergency Recovery:** If the backend server stops during execution, on restart it will flag any interrupted queue with a prominent **Recovery Alert**, preventing further modifications until a 1-click **Rollback to Source** is performed.
