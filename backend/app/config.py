import json
import os
from pathlib import Path
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DATA_DIR = Path(os.environ.get("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "rabbitmq_config.json"


class RabbitMQConfig(BaseModel):
    host: str = Field(default="localhost", description="RabbitMQ hostname or IP")
    port: int = Field(default=5672, description="AMQP 0-9-1 port")
    management_port: int = Field(default=15672, description="Management HTTP API port")
    vhost: str = Field(default="/", description="RabbitMQ Virtual Host")
    username: str = Field(default="guest", description="Username")
    password: str = Field(default="guest", description="Password")
    use_ssl: bool = Field(default=False, description="Use TLS/SSL")

    @property
    def http_base_url(self) -> str:
        protocol = "https" if self.use_ssl else "http"
        return f"{protocol}://{self.host}:{self.management_port}/api"

    @property
    def amqp_url(self) -> str:
        protocol = "amqps" if self.use_ssl else "amqp"
        import urllib.parse
        encoded_vhost = urllib.parse.quote(self.vhost, safe="")
        return f"{protocol}://{self.username}:{self.password}@{self.host}:{self.port}/{encoded_vhost}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RMQ_APP_")

    app_name: str = "RabbitMQ Message Orchestrator"
    app_version: str = "1.0.0"
    debug: bool = False
    data_dir: Path = DATA_DIR
    default_rmq_host: str = "localhost"
    default_rmq_port: int = 5672
    default_rmq_mgmt_port: int = 15672
    default_rmq_vhost: str = "/"
    default_rmq_user: str = "guest"
    default_rmq_pass: str = "guest"


settings = Settings()


def load_rabbitmq_config() -> RabbitMQConfig:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return RabbitMQConfig(**data)
        except Exception:
            pass

    # Default from environment or fallback
    return RabbitMQConfig(
        host=os.environ.get("RABBITMQ_HOST", settings.default_rmq_host),
        port=int(os.environ.get("RABBITMQ_PORT", settings.default_rmq_port)),
        management_port=int(os.environ.get("RABBITMQ_MANAGEMENT_PORT", settings.default_rmq_mgmt_port)),
        vhost=os.environ.get("RABBITMQ_VHOST", settings.default_rmq_vhost),
        username=os.environ.get("RABBITMQ_USERNAME", settings.default_rmq_user),
        password=os.environ.get("RABBITMQ_PASSWORD", settings.default_rmq_pass),
        use_ssl=os.environ.get("RABBITMQ_USE_SSL", "false").lower() in ("true", "1", "yes"),
    )


def save_rabbitmq_config(config: RabbitMQConfig) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2)
