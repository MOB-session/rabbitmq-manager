import json
import os
import urllib.parse
import pika
import requests

# -----------------------------------------------------------------------------
# Configuration & Environment Variables
# -----------------------------------------------------------------------------
# Host and port for AMQP (broker TCP listener)
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))

# Credentials for RabbitMQ authentication
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "rabbitmq")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "rabbitmq")

# Default virtual host and Management HTTP API port
VHOST = os.getenv("VHOST", "/fish")
MGMT_PORT = int(os.getenv("RABBITMQ_MGMT_PORT", "15672"))


# -----------------------------------------------------------------------------
# AMQP Connection Factory
# -----------------------------------------------------------------------------
def get_connection(vhost=None):
    """
    Creates a new blocking AMQP connection to RabbitMQ.
    If no vhost is explicitly passed, falls back to the default VHOST.
    Sets socket_timeout to 10 seconds to detect network issues promptly.
    """
    target_vhost = vhost if vhost is not None and vhost.strip() else VHOST
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        virtual_host=target_vhost,
        credentials=credentials,
        socket_timeout=10,
    )
    return pika.BlockingConnection(parameters)


# -----------------------------------------------------------------------------
# Header Serialization Helper
# -----------------------------------------------------------------------------
def sanitize_headers(headers):
    """
    AMQP headers in Pika often contain raw bytes for keys and values.
    This helper recursively traverses dictionaries and lists to decode
    any byte sequences into clean UTF-8 strings so they can be serialized to JSON.
    """
    if not headers or not isinstance(headers, dict):
        return {}
    sanitized = {}
    for k, v in headers.items():
        key = str(k)
        if isinstance(v, (bytes, bytearray)):
            try:
                sanitized[key] = v.decode("utf-8")
            except Exception:
                sanitized[key] = str(v)
        elif isinstance(v, dict):
            sanitized[key] = sanitize_headers(v)
        elif isinstance(v, list):
            sanitized[key] = [
                x.decode("utf-8") if isinstance(x, (bytes, bytearray)) else x for x in v
            ]
        else:
            sanitized[key] = v
    return sanitized


# -----------------------------------------------------------------------------
# Primary ID Extraction Helper (for UI Display)
# -----------------------------------------------------------------------------
def extract_primary_id(properties, body_bytes):
    """
    Extracts the most descriptive identifier to display in the UI table for a message.
    Checks in the following priority order:
      1. Standard AMQP properties.message_id
      2. Standard AMQP properties.correlation_id
      3. Common identifier keys in AMQP headers ('id', 'message_id', 'eventId')
      4. Recursive search inside JSON payload (e.g. payload.payload.id, id, etc.)
    """
    # 1. Check basic AMQP properties
    if properties.message_id:
        return str(properties.message_id).strip()
    if properties.correlation_id:
        return str(properties.correlation_id).strip()

    # 2. Check AMQP headers
    if properties.headers:
        for k in ("message_id", "messageId", "id", "eventId", "event_id"):
            val = properties.headers.get(k)
            if val is not None:
                return str(val.decode() if isinstance(val, (bytes, bytearray)) else val).strip()

    # 3. Check JSON payload recursively for any key matching 'id' / 'message_id' / etc.
    try:
        data = json.loads(body_bytes)

        def walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k.lower() in ("id", "message_id", "messageid", "eventid", "event_id"):
                        if isinstance(v, (str, int)):
                            return str(v).strip()
                    res = walk(v)
                    if res:
                        return res
            elif isinstance(obj, list):
                for item in obj:
                    res = walk(item)
                    if res:
                        return res
            return None

        json_id = walk(data)
        if json_id:
            return json_id
    except Exception:
        pass

    return None


# -----------------------------------------------------------------------------
# Target ID Matcher (for Targeted Move/Delete)
# -----------------------------------------------------------------------------
def find_matching_target_id(properties, body_bytes, target_ids):
    """
    Determines if the current message matches any ID in the `target_ids` set.
    Returns the specific matched ID string, or None if no match is found.
    Performs deep inspection across:
      - AMQP message_id and correlation_id
      - AMQP header dictionary (nested)
      - JSON body (any nested dictionary, list, or field value)
      - Raw text body containment (fallback for plain text payloads)
    """
    if not target_ids:
        return None

    # 1. AMQP standard properties
    if properties.message_id and str(properties.message_id).strip() in target_ids:
        return str(properties.message_id).strip()
    if properties.correlation_id and str(properties.correlation_id).strip() in target_ids:
        return str(properties.correlation_id).strip()

    # 2. AMQP headers (recursively check dicts/lists for matching values)
    if properties.headers:
        def check_headers(obj):
            if isinstance(obj, dict):
                for v in obj.values():
                    val = str(v.decode() if isinstance(v, (bytes, bytearray)) else v).strip()
                    if val in target_ids:
                        return val
                    res = check_headers(v)
                    if res is not None:
                        return res
            elif isinstance(obj, list):
                for item in obj:
                    res = check_headers(item)
                    if res is not None:
                        return res
            return None

        matched = check_headers(properties.headers)
        if matched is not None:
            return matched

    # 3. JSON body (deep search across all nested objects and leaf values)
    try:
        data = json.loads(body_bytes)

        def check_json(obj):
            if isinstance(obj, dict):
                for v in obj.values():
                    if isinstance(v, (str, int)) and str(v).strip() in target_ids:
                        return str(v).strip()
                    res = check_json(v)
                    if res is not None:
                        return res
            elif isinstance(obj, list):
                for item in obj:
                    res = check_json(item)
                    if res is not None:
                        return res
            return None

        matched = check_json(data)
        if matched is not None:
            return matched
    except Exception:
        # 4. Fallback raw text search if body is not valid JSON
        try:
            body_str = body_bytes.decode("utf-8", errors="ignore")
            for tid in target_ids:
                if tid in body_str:
                    return tid
        except Exception:
            pass

    return None


# -----------------------------------------------------------------------------
# Management API: List Virtual Hosts
# -----------------------------------------------------------------------------
def list_vhosts():
    """
    Queries RabbitMQ's Management HTTP API (GET /api/vhosts) to list all available
    virtual hosts in the cluster. Returns a list of vhost names.
    """
    url = f"http://{RABBITMQ_HOST}:{MGMT_PORT}/api/vhosts"
    try:
        resp = requests.get(url, auth=(RABBITMQ_USER, RABBITMQ_PASSWORD), timeout=5)
        if resp.status_code == 200:
            names = [v.get("name") for v in resp.json()]
            if names:
                return names
    except Exception as exc:
        print(f"Failed to query RabbitMQ Management API for vhosts: {exc}")
    return [VHOST]


# -----------------------------------------------------------------------------
# Management API: List Queues
# -----------------------------------------------------------------------------
def list_queues(vhost=None):
    """
    Queries RabbitMQ's Management HTTP API (GET /api/queues/{vhost}) to list all queues
    and their metrics in the given virtual host (e.g. ready messages, consumers).
    Used to populate dropdowns and autocompletion in the UI.
    """
    target_vhost = vhost if vhost is not None and vhost.strip() else VHOST
    encoded_vhost = urllib.parse.quote(target_vhost, safe="")
    url = f"http://{RABBITMQ_HOST}:{MGMT_PORT}/api/queues/{encoded_vhost}"
    try:
        resp = requests.get(url, auth=(RABBITMQ_USER, RABBITMQ_PASSWORD), timeout=5)
        if resp.status_code == 200:
            queues = resp.json()
            return [
                {
                    "name": q.get("name"),
                    "messages": q.get("messages", 0),
                    "messages_ready": q.get("messages_ready", 0),
                    "messages_unacknowledged": q.get("messages_unacknowledged", 0),
                    "consumers": q.get("consumers", 0),
                }
                for q in queues
            ]
    except Exception as exc:
        print(f"Failed to query RabbitMQ Management API for queues in vhost [{target_vhost}]: {exc}")
    return []


# -----------------------------------------------------------------------------
# Non-destructive Message Peek (Order-Preserving)
# -----------------------------------------------------------------------------
def peek_messages(queue_name, limit=500, vhost=None):
    """
    Safely inspects up to `limit` messages in a queue without modifying their order or removing them.
    How it works:
      1. Consumes messages one-by-one with `auto_ack=False` (locking them as unacknowledged).
      2. Extracts headers, extracted ID, and payload preview for each message.
      3. In the finally block, issues `basic_nack(requeue=True)` for all delivery tags.
         RabbitMQ places requeued messages back at the head of the queue in their exact relative order.
    """
    conn = get_connection(vhost=vhost)
    channel = conn.channel()
    unacked_tags = []
    messages = []

    try:
        # Pre-flight check: ensure queue exists
        channel.queue_declare(queue=queue_name, passive=True)

        while len(messages) < limit:
            method, properties, body = channel.basic_get(queue=queue_name, auto_ack=False)
            if method is None:
                break

            unacked_tags.append(method.delivery_tag)

            # Parse payload
            payload_str = body.decode("utf-8", errors="replace")
            parsed_json = None
            try:
                parsed_json = json.loads(payload_str)
            except Exception:
                pass

            extracted_id = extract_primary_id(properties, body)
            if not extracted_id:
                extracted_id = f"tag-{method.delivery_tag}"

            headers = sanitize_headers(properties.headers)
            # Fallback: if AMQP headers are empty, check if JSON payload has a 'headers' field
            if not headers and parsed_json and isinstance(parsed_json, dict) and "headers" in parsed_json:
                if isinstance(parsed_json["headers"], dict):
                    headers = sanitize_headers(parsed_json["headers"])

            messages.append(
                {
                    "delivery_tag": method.delivery_tag,
                    "id": extracted_id,
                    "message_id": properties.message_id or "",
                    "correlation_id": properties.correlation_id or "",
                    "routing_key": method.routing_key or "",
                    "headers": headers,
                    "payload_preview": (payload_str[:160] + "...") if len(payload_str) > 160 else payload_str,
                    "payload_full": payload_str,
                    "is_json": parsed_json is not None,
                }
            )

        # Release and requeue all inspected messages in original order
        if unacked_tags:
            for tag in unacked_tags:
                try:
                    if channel.is_open:
                        channel.basic_nack(delivery_tag=tag, requeue=True)
                except Exception:
                    pass
            unacked_tags.clear()

        return messages

    finally:
        # Safety net: ensure no messages remain locked if an error or disconnect occurs
        if unacked_tags:
            for tag in unacked_tags:
                try:
                    if channel.is_open:
                        channel.basic_nack(delivery_tag=tag, requeue=True)
                except Exception:
                    pass
        try:
            if conn.is_open:
                conn.close()
        except Exception:
            pass


# -----------------------------------------------------------------------------
# Move All Messages (Batch Move)
# -----------------------------------------------------------------------------
def move_all_messages(from_queue, to_queue, max_messages=0, vhost=None):
    """
    Transfers all messages from `from_queue` to `to_queue` in FIFO order.
    Safety guarantees:
      - Publisher Confirms (`confirm_delivery`): Python waits for broker confirmation of target publish.
      - `mandatory=True`: Prevents silent loss if destination queue is unroutable.
      - Source message is acknowledged (`basic_ack`) ONLY after target publish succeeds.
    """
    if from_queue == to_queue:
        raise ValueError("Source and destination queues cannot be identical.")

    conn = get_connection(vhost=vhost)
    channel = conn.channel()
    channel.confirm_delivery()

    try:
        # Validate that both queues exist before touching messages
        channel.queue_declare(queue=from_queue, passive=True)
        channel.queue_declare(queue=to_queue, passive=True)

        moved_count = 0
        while True:
            # Check optional limit
            if 0 < max_messages <= moved_count:
                break

            method, properties, body = channel.basic_get(queue=from_queue, auto_ack=False)
            if method is None:
                break

            try:
                # Publish to destination queue
                channel.basic_publish(
                    exchange="",
                    routing_key=to_queue,
                    body=body,
                    properties=properties,
                    mandatory=True,
                )
                # Acknowledge source message only after publish is confirmed
                channel.basic_ack(method.delivery_tag)
                moved_count += 1
            except Exception as exc:
                # On failure, requeue the message back to the source queue
                try:
                    if channel.is_open:
                        channel.basic_nack(method.delivery_tag, requeue=True)
                except Exception:
                    pass
                raise exc

        return {"moved": moved_count, "from": from_queue, "to": to_queue, "vhost": vhost or VHOST}

    finally:
        try:
            if conn.is_open:
                conn.close()
        except Exception:
            pass


# -----------------------------------------------------------------------------
# Move Selected Messages by ID (Single-Pass & Order-Preserving)
# -----------------------------------------------------------------------------
def move_selected_messages(from_queue, to_queue, target_ids, vhost=None):
    """
    Moves specific messages matching `target_ids` from `from_queue` to `to_queue`.
    How order is preserved:
      1. Non-matching messages are kept unacknowledged on the channel while scanning.
      2. When a matching message is found, it is published to `to_queue` and acknowledged.
      3. As soon as all target IDs are found, scanning terminates early (untouched messages stay in place).
      4. All preceding/held non-matching messages are requeued (`basic_nack(requeue=True)`).
         RabbitMQ places them back at the front of `from_queue` in their relative original order.
    """
    if from_queue == to_queue:
        raise ValueError("Source and destination queues cannot be identical.")

    target_set = {str(tid).strip() for tid in target_ids if str(tid).strip()}
    if not target_set:
        raise ValueError("No target message IDs provided.")

    conn = get_connection(vhost=vhost)
    channel = conn.channel()
    channel.confirm_delivery()

    unacked_tags = []
    remaining_targets = set(target_set)
    moved_ids = []

    try:
        # Pre-flight check
        channel.queue_declare(queue=from_queue, passive=True)
        channel.queue_declare(queue=to_queue, passive=True)

        while remaining_targets:
            method, properties, body = channel.basic_get(queue=from_queue, auto_ack=False)
            if method is None:
                break

            matched_id = find_matching_target_id(properties, body, remaining_targets)
            if matched_id:
                try:
                    channel.basic_publish(
                        exchange="",
                        routing_key=to_queue,
                        body=body,
                        properties=properties,
                        mandatory=True,
                    )
                    channel.basic_ack(method.delivery_tag)
                    moved_ids.append(matched_id)
                    remaining_targets.remove(matched_id)
                except Exception as exc:
                    unacked_tags.append(method.delivery_tag)
                    raise exc
            else:
                # Hold non-matching message unacknowledged to read the next one behind it
                unacked_tags.append(method.delivery_tag)

        # Requeue all preceding non-matching messages in original relative order
        if unacked_tags:
            for tag in unacked_tags:
                try:
                    if channel.is_open:
                        channel.basic_nack(delivery_tag=tag, requeue=True)
                except Exception:
                    pass
            unacked_tags.clear()

        return {
            "requested_count": len(target_set),
            "moved_count": len(moved_ids),
            "moved_ids": moved_ids,
            "missing_ids": list(remaining_targets),
            "from": from_queue,
            "to": to_queue,
            "vhost": vhost or VHOST,
        }

    finally:
        # Ensure unacked messages are requeued if an unhandled crash or interrupt occurs
        if unacked_tags:
            for tag in unacked_tags:
                try:
                    if channel.is_open:
                        channel.basic_nack(delivery_tag=tag, requeue=True)
                except Exception:
                    pass
        try:
            if conn.is_open:
                conn.close()
        except Exception:
            pass


# -----------------------------------------------------------------------------
# Delete Selected Messages by ID
# -----------------------------------------------------------------------------
def delete_selected_messages(queue_name, target_ids, vhost=None):
    """
    Deletes specific messages matching `target_ids` from `queue_name`.
    Matches are acknowledged (`basic_ack`) without being republished, effectively
    removing them from RabbitMQ storage. Non-matching messages are requeued in original order.
    """
    target_set = {str(tid).strip() for tid in target_ids if str(tid).strip()}
    if not target_set:
        raise ValueError("No target message IDs provided.")

    conn = get_connection(vhost=vhost)
    channel = conn.channel()
    unacked_tags = []
    remaining_targets = set(target_set)
    deleted_ids = []

    try:
        channel.queue_declare(queue=queue_name, passive=True)

        while remaining_targets:
            method, properties, body = channel.basic_get(queue=queue_name, auto_ack=False)
            if method is None:
                break

            matched_id = find_matching_target_id(properties, body, remaining_targets)
            if matched_id:
                # Acknowledging without republishing removes the message permanently
                channel.basic_ack(method.delivery_tag)
                deleted_ids.append(matched_id)
                remaining_targets.remove(matched_id)
            else:
                unacked_tags.append(method.delivery_tag)

        # Requeue non-matching messages
        if unacked_tags:
            for tag in unacked_tags:
                try:
                    if channel.is_open:
                        channel.basic_nack(delivery_tag=tag, requeue=True)
                except Exception:
                    pass
            unacked_tags.clear()

        return {
            "requested_count": len(target_set),
            "deleted_count": len(deleted_ids),
            "deleted_ids": deleted_ids,
            "missing_ids": list(remaining_targets),
            "queue": queue_name,
            "vhost": vhost or VHOST,
        }

    finally:
        if unacked_tags:
            for tag in unacked_tags:
                try:
                    if channel.is_open:
                        channel.basic_nack(delivery_tag=tag, requeue=True)
                except Exception:
                    pass
        try:
            if conn.is_open:
                conn.close()
        except Exception:
            pass


# -----------------------------------------------------------------------------
# Purge Entire Queue
# -----------------------------------------------------------------------------
def purge_queue(queue_name, vhost=None):
    """
    Atomically purges all messages from the specified queue using RabbitMQ's
    AMQP `queue_purge` method. Returns the number of messages purged.
    """
    conn = get_connection(vhost=vhost)
    channel = conn.channel()
    try:
        purge_res = channel.queue_purge(queue=queue_name)
        return {"purged_count": purge_res.method.message_count, "queue": queue_name, "vhost": vhost or VHOST}
    finally:
        try:
            if conn.is_open:
                conn.close()
        except Exception:
            pass
