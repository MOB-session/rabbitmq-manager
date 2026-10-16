import asyncio
from fastapi import APIRouter, HTTPException
from ..config import RabbitMQConfig, load_rabbitmq_config, save_rabbitmq_config
from ..models.schemas import ConnectionTestResult
from ..services.orchestrator import orchestrator

router = APIRouter(prefix="/api/config", tags=["Configuration"])


@router.get("", response_model=RabbitMQConfig)
async def get_config() -> RabbitMQConfig:
    cfg = load_rabbitmq_config()
    # Mask password for safety in response
    return cfg


@router.put("", response_model=RabbitMQConfig)
async def update_config(new_config: RabbitMQConfig) -> RabbitMQConfig:
    save_rabbitmq_config(new_config)
    orchestrator._config = new_config
    return new_config


@router.post("/test", response_model=ConnectionTestResult)
async def test_connection(config: RabbitMQConfig = None) -> ConnectionTestResult:
    target_config = config or load_rabbitmq_config()
    api_client = orchestrator.get_api_client()
    api_client.config = target_config

    # Test HTTP API
    http_result = await api_client.test_connection()
    if not http_result.success:
        return http_result

    # Test AMQP connection in threadpool
    amqp_worker = orchestrator.get_amqp_worker()
    amqp_worker.config = target_config
    amqp_ok, amqp_msg = await asyncio.to_thread(amqp_worker.test_amqp_connection)

    http_result.amqp_connected = amqp_ok
    if not amqp_ok:
        http_result.message = f"Management API OK, but {amqp_msg}"
    else:
        http_result.message = "Connected successfully to both HTTP Management API and AMQP 0-9-1 broker."

    return http_result
