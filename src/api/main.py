"""FastAPI application main file."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from src.config import settings
from src.syncer.scheduler import scheduler
from src.api import routes, webhooks

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting HelpScout Ticket Insights API")
    scheduler.start()
    yield
    # Shutdown
    logger.info("Shutting down")
    scheduler.stop()


# Create FastAPI app
app = FastAPI(
    title="HelpScout Ticket Insights",
    description="LLM-powered analysis of HelpScout support tickets",
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(routes.router, prefix="/api", tags=["insights"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

# Mount static files for UI
try:
    app.mount("/static", StaticFiles(directory="src/ui/static"), name="static")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main UI."""
    try:
        with open("src/ui/static/index.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return HTMLResponse(
            content="""
            <html>
                <head><title>HelpScout Ticket Insights</title></head>
                <body>
                    <h1>HelpScout Ticket Insights</h1>
                    <p>API is running. UI not found.</p>
                    <p>Visit <a href="/docs">/docs</a> for API documentation.</p>
                </body>
            </html>
            """,
            status_code=200,
        )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "scheduler_running": scheduler.is_running,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.is_development,
    )
