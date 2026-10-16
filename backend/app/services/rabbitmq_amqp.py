import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, Optional, Tuple
import pika
from ..config import RabbitMQConfig
from ..models.schemas import OperationType

logger = logging.getLogger("rmq.amqp")


class AMQPWorker:
    def __init__(self, config: RabbitMQConfig):
        self.config = config

    def _get_connection_parameters(self) -> pika.ConnectionParameters:
        credentials = pika.PlainCredentials(self.config.username, self.config.password)
        ssl_options = None
        if self.config.use_ssl:
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_options = pika.SSLOptions(ssl_context, self.config.host)

        return pika.ConnectionParameters(
            host=self.config.host,
            port=self.config.port,
            virtual_host=self.config.vhost,
            credentials=credentials,
            ssl_options=ssl_options,
            heartbeat=60,
            blocked_connection_timeout=30,
            connection_attempts=3,
            retry_delay=2,
        )

    def test_amqp_connection(self) -> Tuple[bool, str]:
        try:
            params = self._get_connection_parameters()
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.close()
            connection.close()
            return True, "AMQP connection successful"
        except Exception as e:
            return False, f"AMQP connection failed: {str(e)}"

    def drain_queue(
        self,
        source_queue: str,
        dest_queue: str,
        progress_callback: Optional[Callable[[int], None]] = None,
        max_messages: Optional[int] = None,
    ) -> int:
        """
        Drains all messages from source_queue into dest_queue preserving exact relative order.
        Uses publisher confirms and manual acks for zero message loss.
        """
        params = self._get_connection_parameters()
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.confirm_delivery()

        transferred = 0
        try:
            while True:
                if max_messages is not None and transferred >= max_messages:
                    break

                method, properties, body = channel.basic_get(queue=source_queue, auto_ack=False)
                if method is None:
                    # Queue is empty
                    break

                # Ensure persistent delivery mode unless specified
                props = properties or pika.BasicProperties(delivery_mode=2)
                if not props.delivery_mode:
                    props.delivery_mode = 2

                # Publish to destination queue via default exchange
                channel.basic_publish(
                    exchange="",
                    routing_key=dest_queue,
                    body=body,
                    properties=props,
                    mandatory=True,
                )

                # Acknowledge source message only AFTER destination confirm is received
                channel.basic_ack(delivery_tag=method.delivery_tag)
                transferred += 1

                if progress_callback and transferred % 10 == 0:
                    try:
                        progress_callback(transferred)
                    except Exception as cb_err:
                        logger.warning(f"Drain progress callback error: {cb_err}")

            if progress_callback:
                try:
                    progress_callback(transferred)
                except Exception as cb_err:
                    logger.warning(f"Final drain progress callback error: {cb_err}")

            return transferred
        finally:
            try:
                channel.close()
                connection.close()
            except Exception:
                pass

    def filter_and_route_queue(
        self,
        source_queue: str,
        retained_queue: str,
        target_message_id: str,
        op_type: OperationType,
        destination_queue: Optional[str] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Reads from source_queue one by one in queue order.
        Inspects message ID:
        - If match and DELETE: acks without publishing.
        - If match and MOVE: publishes to destination_queue, confirms, acks.
        - If non-match: publishes to retained_queue (temp2), confirms, acks.
        """
        params = self._get_connection_parameters()
        connection = pika.BlockingConnection(params)
        channel = connection.channel()
        channel.confirm_delivery()

        inspected = 0
        retained = 0
        moved = 0
        deleted = 0
        target_found = False

        stats = {
            "inspected": 0,
            "retained": 0,
            "moved": 0,
            "deleted": 0,
            "target_found": False,
        }

        try:
            while True:
                method, properties, body = channel.basic_get(queue=source_queue, auto_ack=False)
                if method is None:
                    break

                inspected += 1
                props = properties or pika.BasicProperties(delivery_mode=2)
                if not props.delivery_mode:
                    props.delivery_mode = 2

                # Extract message identifier
                extracted_id = self._extract_message_id(props, body)
                is_target = (extracted_id == target_message_id)

                if is_target:
                    target_found = True
                    if op_type == OperationType.DELETE:
                        # Discard target message by acknowledging without republishing
                        channel.basic_ack(delivery_tag=method.delivery_tag)
                        deleted += 1
                    elif op_type == OperationType.MOVE:
                        if not destination_queue:
                            raise ValueError("Destination queue must be specified for MOVE operation")
                        channel.basic_publish(
                            exchange="",
                            routing_key=destination_queue,
                            body=body,
                            properties=props,
                            mandatory=True,
                        )
                        channel.basic_ack(delivery_tag=method.delivery_tag)
                        moved += 1
                else:
                    # Non-target: preserve order by publishing into retained_queue
                    channel.basic_publish(
                        exchange="",
                        routing_key=retained_queue,
                        body=body,
                        properties=props,
                        mandatory=True,
                    )
                    channel.basic_ack(delivery_tag=method.delivery_tag)
                    retained += 1

                stats["inspected"] = inspected
                stats["retained"] = retained
                stats["moved"] = moved
                stats["deleted"] = deleted
                stats["target_found"] = target_found

                if progress_callback and inspected % 10 == 0:
                    try:
                        progress_callback(stats)
                    except Exception as cb_err:
                        logger.warning(f"Filter progress callback error: {cb_err}")

            if progress_callback:
                try:
                    progress_callback(stats)
                except Exception as cb_err:
                    logger.warning(f"Final filter progress callback error: {cb_err}")

            return stats
        finally:
            try:
                channel.close()
                connection.close()
            except Exception:
                pass

    def _extract_message_id(self, props: pika.BasicProperties, body: bytes) -> str:
        """
        Extracts ID from message_id property, custom header, correlation_id, or JSON payload.
        """
        if props.message_id:
            return str(props.message_id).strip()

        # Check headers
        if props.headers:
            for key in ("message_id", "messageId", "id", "MessageID", "ID"):
                if key in props.headers:
                    val = props.headers[key]
                    if val is not None:
                        return str(val).strip()

        # Check correlation_id as fallback
        if props.correlation_id:
            return str(props.correlation_id).strip()

        # Check JSON payload if structured
        try:
            payload_str = body.decode("utf-8", errors="ignore")
            if payload_str.startswith("{") and payload_str.endswith("}"):
                data = json.loads(payload_str)
                if isinstance(data, dict):
                    for key in ("message_id", "messageId", "id", "_id", "ID"):
                        if key in data and data[key] is not None:
                            return str(data[key]).strip()
        except Exception:
            pass

        return ""
