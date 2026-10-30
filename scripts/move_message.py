import os
import pika

#local test
ENV = os.getenv("ENV", "dev")
LOCATION = os.getenv("LOCATION", "bra")
FROM_QUEUE = os.getenv("FROM", "queue1-events")
TO_QUEUE = os.getenv("TO", "queue1-deadletter")
USERNAME = os.getenv("RABBITMQ_USER", "rabbitmq")
PASSWORD = os.getenv("RABBITMQ_PASSWORD", "rabbitmq")
VHOST = os.getenv("VHOST", "/fish")

required = [
    FROM_QUEUE,
    TO_QUEUE,
    LOCATION,
    USERNAME,
    PASSWORD,
    ENV,
    VHOST
]
if not all(required):
    raise ValueError("Missing required environment variable")

VALID_ENVS = {"dev", "stg", "prod"}
if ENV not in VALID_ENVS:
    raise ValueError(
        f"Invalid ENV [{ENV}]. Allowed values: {VALID_ENVS}"
    )

RABBITMQ_HOST = ("localhost")
RABBITMQ_PORT = 5672

credentials = pika.PlainCredentials(USERNAME, PASSWORD)

try:
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            virtual_host=VHOST,
            credentials=credentials,
        )
    )
except Exception as exc:
    raise RuntimeError(
        f"Failed to connect to RabbitMQ host [{RABBITMQ_HOST}] "
        f"vhost [{VHOST}]: {exc}"
    )

channel = connection.channel()
channel.confirm_delivery()

moved_count = 0
try:
    while True:
        # Fetch one message without auto-ack
        method, properties, body = channel.basic_get(
            queue=FROM_QUEUE,
            auto_ack=False #Lock/unacknowledge message - The message is not deleted and not requeued yet.
        )

        # Exit if no messages
        if method is None and moved_count == 0:
            print(f"No messages found in queue {FROM_QUEUE}")
            break
        elif method is None:
            print("No more messages found")
            connection.close()
            print(f"Moved [{moved_count}] messages from {FROM_QUEUE} to {TO_QUEUE}")
            break

        print(f"Message received from {FROM_QUEUE}")

        try:
            channel.basic_publish(
                exchange="",
                routing_key=TO_QUEUE,
                body=body,
                properties=properties,
                mandatory=True
            )

            channel.basic_ack(method.delivery_tag)
            moved_count += 1
            print(f"{moved_count} message moved successfully")

        except Exception as exc:
            print(f"Publish failed: {exc}")

            channel.basic_nack(
                method.delivery_tag,
                requeue=True
            )

            raise

finally:
    try:
        if connection.is_open:
            connection.close()
    except:
        pass