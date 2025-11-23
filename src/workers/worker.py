"""RQ worker entry point."""

import logging
from redis import Redis
from rq import Worker, Queue, Connection

from src.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    """Start RQ worker."""
    redis_conn = Redis.from_url(settings.redis_url)

    # Listen on multiple queues
    queues = ["default", "high", "low"]

    logger.info(f"Starting RQ worker listening on queues: {queues}")

    with Connection(redis_conn):
        worker = Worker(queues, connection=redis_conn)
        worker.work()


if __name__ == "__main__":
    main()
