"""
Utility script to seed a RabbitMQ queue with sample ordered messages
to demonstrate and test the selective move/purge orchestrator.
"""

import argparse
import json
import time
import pika


def seed_queue(
    host: str = "localhost",
    port: int = 5672,
    vhost: str = "/",
    user: str = "guest",
    password: str = "guest",
    queue_name: str = "demo_orders",
    count: int = 20,
    target_index: int = 7,
    target_id: str = "TARGET-MSG-777",
):
    print(f"Connecting to RabbitMQ at {host}:{port} (vhost: {vhost})...")
    credentials = pika.PlainCredentials(user, password)
    params = pika.ConnectionParameters(
        host=host,
        port=port,
        virtual_host=vhost,
        credentials=credentials,
    )
    conn = pika.BlockingConnection(params)
    ch = conn.channel()

    # Declare durable classic queue
    ch.queue_declare(queue=queue_name, durable=True)
    print(f"Queue '{queue_name}' ready. Publishing {count} messages...")

    ch.confirm_delivery()

    for i in range(1, count + 1):
        if i == target_index:
            msg_id = target_id
            payload = {
                "order_id": 1000 + i,
                "customer": "Special Target Customer",
                "item": "TARGET ITEM (To be moved/purged)",
                "amount": 999.99,
                "timestamp": time.time(),
            }
        else:
            msg_id = f"ORDER-{1000 + i}"
            payload = {
                "order_id": 1000 + i,
                "customer": f"Customer #{i}",
                "item": f"Product Standard SKU-{i}",
                "amount": 10.0 * i,
                "timestamp": time.time(),
            }

        body = json.dumps(payload, indent=2).encode("utf-8")
        props = pika.BasicProperties(
            message_id=msg_id,
            content_type="application/json",
            delivery_mode=2,  # persistent
            headers={"app": "seed_script", "index": i},
        )

        ch.basic_publish(
            exchange="",
            routing_key=queue_name,
            body=body,
            properties=props,
            mandatory=True,
        )
        print(f"  [{i}/{count}] Published message_id='{msg_id}'")

    print("\n[SUCCESS] Seed complete!")
    print(f"Target message ID to test with: '{target_id}'")
    ch.close()
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed RabbitMQ queue with sample messages")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5672)
    parser.add_argument("--vhost", default="/")
    parser.add_argument("--user", default="guest")
    parser.add_argument("--password", default="guest")
    parser.add_argument("--queue", default="demo_orders")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--target-id", default="TARGET-MSG-777")
    parser.add_argument("--target-index", type=int, default=7)

    args = parser.parse_args()
    seed_queue(
        host=args.host,
        port=args.port,
        vhost=args.vhost,
        user=args.user,
        password=args.password,
        queue_name=args.queue,
        count=args.count,
        target_id=args.target_id,
        target_index=args.target_index,
    )
