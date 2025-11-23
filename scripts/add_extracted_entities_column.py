#!/usr/bin/env python3
"""Add extracted_entities column to ticket_analyses table."""

import logging
from sqlalchemy import text
from src.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """Add extracted_entities column if it doesn't exist."""
    try:
        with engine.connect() as conn:
            # Check if column exists
            result = conn.execute(
                text(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name='ticket_analyses'
                    AND column_name='extracted_entities'
                    """
                )
            )

            if result.fetchone() is None:
                logger.info("Adding extracted_entities column to ticket_analyses table...")
                conn.execute(
                    text(
                        """
                        ALTER TABLE ticket_analyses
                        ADD COLUMN extracted_entities JSON
                        """
                    )
                )
                conn.commit()
                logger.info("✓ Column added successfully")
            else:
                logger.info("✓ Column already exists, skipping migration")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    migrate()
