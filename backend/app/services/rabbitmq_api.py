import base64
import json
import logging
from typing import Any, Dict, List, Optional
import httpx
from ..config import RabbitMQConfig
from ..models.schemas import (
    ConnectionTestResult,
    MessageProperties,
    MessageSample,
    QueueDetails,
)

logger = logging.getLogger("rmq.api")


class RabbitMQManagementClient:
    def __init__(self, config: RabbitMQConfig):
        self.config = config

    def _get_auth(self) -> httpx.BasicAuth:
        return httpx.BasicAuth(self.config.username, self.config.password)

    def _encode_vhost(self, vhost: str) -> str:
        if vhost == "/":
            return "%2F"
        import urllib.parse
        return urllib.parse.quote(vhost, safe="")

    async def test_connection(self) -> ConnectionTestResult:
        url = f"{self.config.http_base_url}/overview"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(url, auth=self._get_auth())
                if res.status_code == 200:
                    data = res.json()
                    version = data.get("rabbitmq_version", "unknown")
                    erlang_ver = data.get("erlang_version", "unknown")
                    cluster_name = data.get("cluster_name", "rabbitmq")
                    return ConnectionTestResult(
                        success=True,
                        message="Successfully connected to RabbitMQ Management API",
                        rabbitmq_version=version,
                        erlang_version=erlang_ver,
                        cluster_name=cluster_name,
                        amqp_connected=False,
                    )
                elif res.status_code == 401:
                    return ConnectionTestResult(
                        success=False,
                        message="Authentication failed: invalid username or password",
                    )
                else:
                    return ConnectionTestResult(
                        success=False,
                        message=f"HTTP API returned status {res.status_code}: {res.text[:200]}",
                    )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                message=f"Connection error: {str(e)}",
            )

    async def list_queues(self, vhost: Optional[str] = None) -> List[QueueDetails]:
        target_vhost = vhost or self.config.vhost
        vhost_encoded = self._encode_vhost(target_vhost)
        url = f"{self.config.http_base_url}/queues/{vhost_encoded}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, auth=self._get_auth())
            if res.status_code != 200:
                logger.error(f"Failed to list queues: {res.status_code} {res.text}")
                return []
            items = res.json()
            queues = []
            for item in items:
                q_type = item.get("type", "classic")
                queues.append(
                    QueueDetails(
                        name=item.get("name", ""),
                        vhost=item.get("vhost", target_vhost),
                        type=q_type,
                        state=item.get("state", "running"),
                        messages=item.get("messages", 0),
                        messages_ready=item.get("messages_ready", 0),
                        messages_unacknowledged=item.get("messages_unacknowledged", 0),
                        consumers=item.get("consumers", 0),
                        durable=item.get("durable", True),
                        auto_delete=item.get("auto_delete", False),
                        policy=item.get("policy"),
                        node=item.get("node"),
                    )
                )
            return queues

    async def get_queue(self, queue_name: str, vhost: Optional[str] = None) -> Optional[QueueDetails]:
        target_vhost = vhost or self.config.vhost
        vhost_encoded = self._encode_vhost(target_vhost)
        url = f"{self.config.http_base_url}/queues/{vhost_encoded}/{queue_name}"
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(url, auth=self._get_auth())
            if res.status_code == 404:
                return None
            if res.status_code != 200:
                raise RuntimeError(f"Error fetching queue {queue_name}: {res.status_code} {res.text}")
            item = res.json()
            return QueueDetails(
                name=item.get("name", ""),
                vhost=item.get("vhost", target_vhost),
                type=item.get("type", "classic"),
                state=item.get("state", "running"),
                messages=item.get("messages", 0),
                messages_ready=item.get("messages_ready", 0),
                messages_unacknowledged=item.get("messages_unacknowledged", 0),
                consumers=item.get("consumers", 0),
                durable=item.get("durable", True),
                auto_delete=item.get("auto_delete", False),
                policy=item.get("policy"),
                node=item.get("node"),
            )

    async def create_queue(
        self,
        queue_name: str,
        queue_type: str = "classic",
        durable: bool = True,
        auto_delete: bool = False,
        arguments: Optional[Dict[str, Any]] = None,
        vhost: Optional[str] = None,
    ) -> bool:
        target_vhost = vhost or self.config.vhost
        vhost_encoded = self._encode_vhost(target_vhost)
        url = f"{self.config.http_base_url}/queues/{vhost_encoded}/{queue_name}"
        payload: Dict[str, Any] = {
            "durable": durable,
            "auto_delete": auto_delete,
            "arguments": arguments or {},
        }
        if queue_type and queue_type != "classic":
            payload["arguments"]["x-queue-type"] = queue_type
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.put(url, json=payload, auth=self._get_auth())
            if res.status_code in (201, 204):
                return True
            raise RuntimeError(f"Failed to create queue {queue_name}: {res.status_code} {res.text}")

    async def delete_queue(self, queue_name: str, vhost: Optional[str] = None) -> bool:
        target_vhost = vhost or self.config.vhost
        vhost_encoded = self._encode_vhost(target_vhost)
        url = f"{self.config.http_base_url}/queues/{vhost_encoded}/{queue_name}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.delete(url, auth=self._get_auth())
            return res.status_code in (200, 204, 404)

    async def sample_messages(
        self, queue_name: str, count: int = 5, vhost: Optional[str] = None
    ) -> List[MessageSample]:
        target_vhost = vhost or self.config.vhost
        vhost_encoded = self._encode_vhost(target_vhost)
        url = f"{self.config.http_base_url}/queues/{vhost_encoded}/{queue_name}/get"
        payload = {
            "count": count,
            "ackmode": "ack_requeue_true",  # non-destructive inspection
            "encoding": "auto",
            "truncate": 5000,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload, auth=self._get_auth())
            if res.status_code != 200:
                raise RuntimeError(f"Failed to sample messages from {queue_name}: {res.status_code} {res.text}")
            data = res.json()
            samples: List[MessageSample] = []
            for item in data:
                props_raw = item.get("properties", {}) or {}
                headers = props_raw.get("headers", {})
                props = MessageProperties(
                    message_id=props_raw.get("message_id"),
                    correlation_id=props_raw.get("correlation_id"),
                    content_type=props_raw.get("content_type"),
                    content_encoding=props_raw.get("content_encoding"),
                    delivery_mode=props_raw.get("delivery_mode"),
                    priority=props_raw.get("priority"),
                    timestamp=props_raw.get("timestamp"),
                    type=props_raw.get("type"),
                    user_id=props_raw.get("user_id"),
                    app_id=props_raw.get("app_id"),
                    headers=headers if isinstance(headers, dict) else {},
                )
                payload_str = item.get("payload", "")
                samples.append(
                    MessageSample(
                        payload=payload_str,
                        payload_bytes=item.get("payload_bytes", len(payload_str)),
                        payload_encoding=item.get("payload_encoding", "string"),
                        properties=props,
                        routing_key=item.get("routing_key", ""),
                        exchange=item.get("exchange", ""),
                        redelivered=item.get("redelivered", False),
                        message_count=item.get("message_count", 0),
                    )
                )
            return samples

    async def get_queue_bindings(self, queue_name: str, vhost: Optional[str] = None) -> List[Dict[str, Any]]:
        target_vhost = vhost or self.config.vhost
        vhost_encoded = self._encode_vhost(target_vhost)
        url = f"{self.config.http_base_url}/queues/{vhost_encoded}/{queue_name}/bindings"
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(url, auth=self._get_auth())
            if res.status_code != 200:
                return []
            return res.json()

    async def create_binding(
        self,
        exchange: str,
        queue: str,
        routing_key: str = "",
        arguments: Optional[Dict[str, Any]] = None,
        vhost: Optional[str] = None,
    ) -> bool:
        target_vhost = vhost or self.config.vhost
        vhost_encoded = self._encode_vhost(target_vhost)
        exchange_encoded = "%2F" if exchange == "" else exchange
        url = f"{self.config.http_base_url}/bindings/{vhost_encoded}/e/{exchange_encoded}/q/{queue}"
        payload = {"routing_key": routing_key, "arguments": arguments or {}}
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.post(url, json=payload, auth=self._get_auth())
            return res.status_code in (201, 204)

    async def delete_binding(
        self,
        exchange: str,
        queue: str,
        properties_key: str,
        vhost: Optional[str] = None,
    ) -> bool:
        target_vhost = vhost or self.config.vhost
        vhost_encoded = self._encode_vhost(target_vhost)
        exchange_encoded = "%2F" if exchange == "" else exchange
        url = f"{self.config.http_base_url}/bindings/{vhost_encoded}/e/{exchange_encoded}/q/{queue}/{properties_key}"
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.delete(url, auth=self._get_auth())
            return res.status_code in (200, 204, 404)
