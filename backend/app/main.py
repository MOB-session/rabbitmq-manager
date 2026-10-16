import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .config import settings
from .routers import config_router, operations_router, queues_router, system_router
from .services.journal import journal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rmq.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    recovery_needed = journal.get_recovery_needed_operations()
    if recovery_needed:
        logger.warning(
            f"FOUND {len(recovery_needed)} OPERATIONS REQUIRING RECOVERY from previous runs: "
            f"{[op.id for op in recovery_needed]}"
        )
    yield
    logger.info("Shutting down RabbitMQ Message Orchestrator")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="RabbitMQ 4.1.0 Message Orchestrator for selective Move/Purge operations by Message ID",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(config_router)
app.include_router(queues_router)
app.include_router(operations_router)
app.include_router(system_router)

# Mount frontend static files if available
static_dir = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if static_dir.exists() and (static_dir / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
else:
    @app.get("/")
    async def root():
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "status": "online",
            "docs_url": "/docs",
        }
