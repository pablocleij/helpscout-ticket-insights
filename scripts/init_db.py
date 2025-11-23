#!/usr/bin/env python3
"""Initialize database schema."""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import init_db

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Initialize database schema using SQLAlchemy create_all."""
    logger.info("Initializing database schema...")
    init_db()
    logger.info("✓ Database schema initialized")


if __name__ == "__main__":
    main()
