# RabbitMQ Queue Manager

A lightweight, web-based management tool built with Flask and Pika to safely **inspect**, **move**, and **delete** messages between RabbitMQ queues with **zero message loss** and **strict FIFO order preservation**.

---

## Features

- **Multi-VHost Support:** Discover and switch between RabbitMQ Virtual Hosts dynamically from the UI.
- **Non-Destructive Safe Peeking:** Inspect messages (IDs, AMQP headers, JSON payloads) without consuming or altering their queue sequence.
- **Deep Identifier Extraction:** Automatically finds message identifiers across AMQP standard properties (`message_id`, `correlation_id`), custom headers, and deeply nested JSON structures (e.g. `payload.payload.id`).
- **Batch Move (All Messages):** Reliably transfers entire queues with AMQP Publisher Confirms and `mandatory=True` routing guarantees.
- **Targeted Move (Selected Messages):** Move only chosen messages by ID in a single-pass scan. Unselected messages are automatically returned to the head of the source queue in their exact relative order.
- **Delete Management:** Selectively delete individual messages by ID, or atomically purge an entire queue.

---

## Core Project Files

| File | Description |
| :--- | :--- |
| [`app.py`](./app.py) | **Flask Web Server & API:** Serves the frontend interface and provides REST endpoints (`/api/vhosts`, `/api/queues`, `/api/messages/...`). |
| [`rabbitmq_service.py`](./rabbitmq_service.py) | **RabbitMQ Core Service Layer:** Handles all AMQP communication via `pika` and cluster discovery via RabbitMQ's Management HTTP API. Encapsulates connection pooling, deep ID matching, safe peeking, and transactional message transfer logic. |
| [`templates/index.html`](./templates/index.html) | **Web Dashboard:** Clean, responsive UI with two main tabs (**Move** and **Delete**), autocomplete queue suggestions, search/filter bar, payload inspection modal, and instant status banners. Styled with Bootstrap 5 (CDN). |
| [`run_web.sh`](./run_web.sh) | **Launcher Script:** Activates the local virtual environment (`.venv`) and boots up the Flask web application on port 5000. |

---

## Prerequisites

- **Python 3.10+**
- **Running RabbitMQ broker** (with `rabbitmq_management` plugin enabled)
- Required Python packages: `flask`, `pika`, `requests`

---

## Quick Start

### 1. Start RabbitMQ (Optional / Local Dev)

If you are using the included Dockerized RabbitMQ instance:

```bash
bash rabbitmq/run.sh
```

- **AMQP Broker Port:** `localhost:5672`
- **Management UI:** [http://localhost:15672](http://localhost:15672)
- **Credentials:** `rabbitmq` / `rabbitmq`

### 2. Install Dependencies

In your virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install flask pika requests
```

### 3. Launch the Web Application

Run the helper script:

```bash
./run_web.sh
```

Or run directly with Python:

```bash
python3 app.py
```

Open your browser at:  
👉 **[http://localhost:5000](http://localhost:5000)**

---

## Configuration & Environment Variables

All settings can be customized using environment variables:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `RABBITMQ_HOST` | `localhost` | RabbitMQ server hostname or IP address |
| `RABBITMQ_PORT` | `5672` | AMQP TCP listener port |
| `RABBITMQ_USER` | `rabbitmq` | RabbitMQ username |
| `RABBITMQ_PASSWORD` | `rabbitmq` | RabbitMQ password |
| `VHOST` | `/fish` | Default virtual host |
| `RABBITMQ_MGMT_PORT` | `15672` | RabbitMQ Management HTTP API port |
| `PORT` | `5000` | Port for the Flask web server |

Example with custom settings:

```bash
RABBITMQ_HOST="192.168.1.50" RABBITMQ_USER="admin" RABBITMQ_PASSWORD="secret" ./run_web.sh
```

---

## REST API Reference

The web UI communicates with `app.py` via the following JSON endpoints:

| Endpoint | Method | Payload / Query | Description |
| :--- | :---: | :--- | :--- |
| `/api/vhosts` | `GET` | — | Lists all virtual hosts discovered in the RabbitMQ cluster. |
| `/api/queues` | `GET` | `?vhost=/fish` | Lists queues, ready message counts, and consumer numbers. |
| `/api/messages/peek` | `POST` | `{"queue": "q1", "vhost": "/fish", "limit": 200}` | Non-destructively inspects messages from a queue. |
| `/api/messages/move-all` | `POST` | `{"from_queue": "q1", "to_queue": "q2", "vhost": "/fish"}` | Moves all messages from source to target queue. |
| `/api/messages/move-selected` | `POST` | `{"from_queue": "q1", "to_queue": "q2", "message_ids": ["id1"], "vhost": "/fish"}` | Moves only specified message IDs, preserving order of the rest. |
| `/api/messages/delete-selected` | `POST` | `{"queue": "q1", "message_ids": ["id1"], "vhost": "/fish"}` | Removes selected message IDs from the queue. |
| `/api/messages/purge-queue` | `POST` | `{"queue": "q1", "vhost": "/fish"}` | Atomically deletes all messages in the queue. |

---

## Message Safety & Order Preservation

### Why Messages Cannot Be Lost (At-Least-Once Delivery)
1. **Unacknowledged State (`auto_ack=False`):** While a message is being processed or inspected, RabbitMQ locks it in an `unacknowledged` state on the broker.
2. **Publisher Confirms (`channel.confirm_delivery()`):** Python waits for positive broker confirmation that the target queue has persisted the message before acknowledging the original.
3. **Automatic Broker Requeue:** If the network drops or the process crashes mid-transfer, RabbitMQ automatically releases all unacknowledged messages back into the source queue.

### How Order Is Preserved During Targeted Moves
AMQP queues are strictly FIFO. When moving specific messages:
1. Non-matching messages are temporarily held unacknowledged on the channel while scanning ahead for the target ID.
2. When the target message is found, it is published to the destination queue and acknowledged.
3. Preceding non-matching messages are requeued with `channel.basic_nack(requeue=True)`.
4. RabbitMQ places them right back at the **head of the source queue in their relative original order**.
5. Subsequent messages further down the queue are left untouched.
