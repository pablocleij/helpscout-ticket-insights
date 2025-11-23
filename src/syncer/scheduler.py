"""Scheduler for periodic ticket syncs and analysis."""

import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src.config import settings
from src.database import get_db_context
from src.syncer.helpscout import HelpScoutSyncer

logger = logging.getLogger(__name__)


class SyncScheduler:
    """Scheduler for periodic sync and analysis tasks."""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.is_running = False

    def start(self) -> None:
        """Start the scheduler."""
        if self.is_running:
            logger.warning("Scheduler already running")
            return

        logger.info("Starting sync scheduler")

        # Schedule periodic sync
        self.scheduler.add_job(
            func=self._run_sync,
            trigger=IntervalTrigger(hours=settings.sync_interval_hours),
            id="periodic_sync",
            name="Periodic HelpScout sync",
            replace_existing=True,
        )

        # Schedule nightly analysis aggregation
        self.scheduler.add_job(
            func=self._run_aggregation,
            trigger=CronTrigger(hour=2, minute=0),  # 2 AM daily
            id="nightly_aggregation",
            name="Nightly insight aggregation",
            replace_existing=True,
        )

        self.scheduler.start()
        self.is_running = True
        logger.info("Scheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        if not self.is_running:
            return

        logger.info("Stopping scheduler")
        self.scheduler.shutdown()
        self.is_running = False

    def _run_sync(self) -> None:
        """Run periodic sync job."""
        logger.info("Starting scheduled sync")
        try:
            with get_db_context() as db:
                syncer = HelpScoutSyncer(db)
                stats = syncer.sync_all_mailboxes(full_sync=False)
                logger.info(f"Scheduled sync complete: {stats}")
        except Exception as e:
            logger.error(f"Error in scheduled sync: {e}", exc_info=True)

    def _run_aggregation(self) -> None:
        """Run nightly aggregation job."""
        logger.info("Starting scheduled aggregation")
        try:
            # Import here to avoid circular imports
            from src.analyzer.aggregator import InsightAggregator
            from src.database import get_db_context

            with get_db_context() as db:
                aggregator = InsightAggregator(db)
                stats = aggregator.aggregate_insights()
                logger.info(f"Scheduled aggregation complete: {stats}")
        except Exception as e:
            logger.error(f"Error in scheduled aggregation: {e}", exc_info=True)


# Global scheduler instance
scheduler = SyncScheduler()
