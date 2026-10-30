# RabbitMQ 4.1.0 Quick Install & Startup

This directory contains everything needed to run an official **RabbitMQ 4.1.0** instance with the **Management Web UI** and **Dynamic Shovel** plugins enabled.

---

## 1. Prerequisites (Installing Docker on Ubuntu)

If you do not have Docker installed on your machine yet, run this one-time command in your terminal:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
newgrp docker
```

---

## 2. Start RabbitMQ

Simply execute the helper script:

```bash
sudo bash rabbitmq/run.sh
```

Or using Docker Compose directly:

```bash
cd rabbitmq
docker compose up -d
```

### Access Points:
- **AMQP Broker Port:** `localhost:5672` (used by backend & seed script)
- **Management Web UI:** [http://localhost:15672](http://localhost:15672)
- **Default Username:** `rabbitmq`
- **Default Password:** `rabbitmq`

---

## 3. Seed Sample Data & Test

Once RabbitMQ is running:

1. **Seed the queue:**
   ```bash
   .venv/bin/python backend/scripts/seed_sample_queue.py --queue demo_orders --target-id TARGET-MSG-777
   ```
2. **Open the Manager UI:**
   Open [http://localhost:8000](http://localhost:8000) in your browser.
3. **Select `demo_orders`** in the Source Queue list.
4. **Inspect the queue head**, see the messages, select `TARGET-MSG-777`, and test Move or Delete!

---

## 4. Stop RabbitMQ

```bash
bash rabbitmq/stop.sh
```
