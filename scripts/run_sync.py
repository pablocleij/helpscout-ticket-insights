#!/usr/bin/env python3
"""Run manual sync."""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_db_context
from src.syncer.helpscout import HelpScoutSyncer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Run sync."""
    logger.info("Starting manual sync...")
    with get_db_context() as db:
        syncer = HelpScoutSyncer(db)
        stats = syncer.sync_all_mailboxes(full_sync=False)
        logger.info(f"Sync complete: {stats}")


if __name__ == "__main__":
    main()
