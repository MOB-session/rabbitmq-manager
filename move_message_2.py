import json
import os
import pika

# Configuration
ENV = os.getenv("ENV", "dev")
LOCATION = os.getenv("LOCATION", "bra")
FROM_QUEUE = os.getenv("FROM", "queue1-deadletter")
TO_QUEUE = os.getenv("TO", "queue1-events")
USERNAME = os.getenv("RABBITMQ_USER", "rabbitmq")
PASSWORD = os.getenv("RABBITMQ_PASSWORD", "rabbitmq")
VHOST = os.getenv("VHOST", "/fish")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))

# 0 = unlimited. When TARGET_MESSAGE_ID is set, MAX_MESSAGES can limit how many messages to inspect.
MAX_MESSAGES = int(os.getenv("MAX_MESSAGES", "0"))
TARGET_MESSAGE_ID = os.getenv("MESSAGE_ID", os.getenv("TARGET_MESSAGE_ID", "")).strip()

required = [
    FROM_QUEUE,
    TO_QUEUE,
    LOCATION,
    USERNAME,
    PASSWORD,
    ENV,
    VHOST,
]

# -- VALIDATION
if not all(required):
    raise ValueError("Missing required environment variable")

VALID_ENVS = {"dev", "stg", "prod"}
if ENV not in VALID_ENVS:
    raise ValueError(f"Invalid ENV [{ENV}]. Allowed values: {VALID_ENVS}")

if FROM_QUEUE == TO_QUEUE:
    raise ValueError("Source and destination queues must not be identical")
# -- END VALIDATION


def matches_target_id(properties, body, target_id):
    """
    Check if target_id matches AMQP properties, headers, or any field
    in nested JSON payload (e.g. payload.payload.id).
    """
    if not target_id:
        return False
    target_id = str(target_id).strip()

    # 1. Standard AMQP properties
    if properties.message_id and str(properties.message_id).strip() == target_id:
        return True
    if properties.correlation_id and str(properties.correlation_id).strip() == target_id:
        return True

    # 2. AMQP headers (recursively check dicts/lists)
    if properties.headers:
        def check_headers(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    val = str(v.decode() if isinstance(v, bytes) else v).strip()
                    if val == target_id:
                        return True
                    if check_headers(v):
                        return True
            elif isinstance(obj, list):
                for item in obj:
                    if check_headers(item):
                        return True
            return False

        if check_headers(properties.headers):
            return True

    # 3. JSON body (recursively searches nested dicts, lists, and values)
    try:
        data = json.loads(body)
        def check_json(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, (str, int)) and str(v).strip() == target_id:
                        return True
                    if check_json(v):
                        return True
            elif isinstance(obj, list):
                for item in obj:
                    if check_json(item):
                        return True
            return False

        if check_json(data):
            return True
    except Exception:
        # 4. Fallback: raw body string containment if not valid JSON
        if isinstance(body, (bytes, bytearray)):
            try:
                if target_id in body.decode("utf-8", errors="ignore"):
                    return True
            except Exception:
                pass

    return False


credentials = pika.PlainCredentials(USERNAME, PASSWORD)
parameters = pika.ConnectionParameters(
    host=RABBITMQ_HOST,
    port=RABBITMQ_PORT,
    virtual_host=VHOST,
    credentials=credentials,
)

try:
    connection = pika.BlockingConnection(parameters)
except Exception as exc:
    raise RuntimeError(
        f"Failed to connect to RabbitMQ host [{RABBITMQ_HOST}:{RABBITMQ_PORT}] "
        f"vhost [{VHOST}]: {exc}"
    )

channel = connection.channel()
channel.confirm_delivery()

# Track delivery tags held in unacknowledged state to preserve queue ordering
unacked_tags = []

try:
    # 1. Pre-flight check: ensure both queues exist before moving anything
    channel.queue_declare(queue=FROM_QUEUE, passive=True)
    channel.queue_declare(queue=TO_QUEUE, passive=True)

    # -------------------------------------------------------------------------
    # MODE 1: Move specific message by ID (without altering other messages' order)
    # -------------------------------------------------------------------------
    if TARGET_MESSAGE_ID:
        print(f"Targeted mode: Looking for message ID [{TARGET_MESSAGE_ID}] in [{FROM_QUEUE}]...")
        found = False
        inspected_count = 0

        while True:
            if 0 < MAX_MESSAGES <= inspected_count:
                print(f"Reached inspection limit of {MAX_MESSAGES} messages without finding target ID.")
                break

            # Fetch message without auto-ack to hold position
            method, properties, body = channel.basic_get(queue=FROM_QUEUE, auto_ack=False)
            if method is None:
                break

            inspected_count += 1

            if matches_target_id(properties, body, TARGET_MESSAGE_ID):
                print(f"[+] Found target message (inspected {inspected_count} messages). Moving to [{TO_QUEUE}]...")
                try:
                    # Publish with publisher confirms and mandatory routing
                    channel.basic_publish(
                        exchange="",
                        routing_key=TO_QUEUE,
                        body=body,
                        properties=properties,
                        mandatory=True,
                    )
                    channel.basic_ack(method.delivery_tag)
                    found = True
                    print(f"[✓] Successfully moved message [{TARGET_MESSAGE_ID}] to [{TO_QUEUE}].")
                except Exception as exc:
                    print(f"Publish failed for message [{TARGET_MESSAGE_ID}]: {exc}")
                    unacked_tags.append(method.delivery_tag)
                    raise
                break
            else:
                # Keep unacked so RabbitMQ serves the next message behind it
                unacked_tags.append(method.delivery_tag)

        # Requeue all preceding/inspected messages.
        # In RabbitMQ, requeued messages return to the head in their relative original order.
        if unacked_tags:
            print(f"Requeuing {len(unacked_tags)} inspected message(s) back to [{FROM_QUEUE}] in original order...")
            for tag in unacked_tags:
                try:
                    if channel.is_open:
                        channel.basic_nack(delivery_tag=tag, requeue=True)
                except Exception:
                    pass
            unacked_tags.clear()

        if not found:
            print(f"[-] Message with ID [{TARGET_MESSAGE_ID}] not found in [{FROM_QUEUE}]. "
                  f"All {inspected_count} inspected message(s) remain untouched in original order.")

    # -------------------------------------------------------------------------
    # MODE 2: Move all messages (or up to MAX_MESSAGES) in FIFO order
    # -------------------------------------------------------------------------
    else:
        moved_count = 0
        print(f"Batch mode: Moving messages from [{FROM_QUEUE}] to [{TO_QUEUE}] on {RABBITMQ_HOST}...")

        while True:
            if 0 < MAX_MESSAGES <= moved_count:
                print(f"Reached message limit of {MAX_MESSAGES}.")
                break

            method, properties, body = channel.basic_get(queue=FROM_QUEUE, auto_ack=False)
            if method is None:
                if moved_count == 0:
                    print(f"No messages found in queue [{FROM_QUEUE}]")
                else:
                    print("No more messages found.")
                break

            try:
                channel.basic_publish(
                    exchange="",
                    routing_key=TO_QUEUE,
                    body=body,
                    properties=properties,
                    mandatory=True,
                )
                channel.basic_ack(method.delivery_tag)
                moved_count += 1

                if moved_count % 100 == 0:
                    print(f"Progress: {moved_count} messages moved...")

            except Exception as exc:
                print(f"Publish failed: {exc}")
                try:
                    if channel.is_open:
                        channel.basic_nack(method.delivery_tag, requeue=True)
                except Exception:
                    pass
                raise

        print(f"[✓] Done. Total moved: [{moved_count}] messages from [{FROM_QUEUE}] to [{TO_QUEUE}]")

finally:
    # Safety net: Requeue any unacknowledged delivery tags if an unhandled crash or interrupt occurred
    if unacked_tags:
        for tag in unacked_tags:
            try:
                if channel.is_open:
                    channel.basic_nack(delivery_tag=tag, requeue=True)
            except Exception:
                pass

    try:
        if connection.is_open:
            connection.close()
    except Exception:
        pass
