#!/usr/bin/env python3
"""Initialize database and run first sync."""

import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import init_db, get_db_context
from src.syncer.helpscout import HelpScoutSyncer
from src.analyzer.pipeline import AnalysisPipeline
from src.analyzer.aggregator import InsightAggregator

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Initialize database and run initial sync."""
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized!")

    logger.info("Running initial sync...")
    with get_db_context() as db:
        syncer = HelpScoutSyncer(db)
        stats = syncer.sync_all_mailboxes(full_sync=True)
        logger.info(f"Initial sync complete: {stats}")

        # Run analysis on synced tickets
        logger.info("Analyzing tickets...")
        pipeline = AnalysisPipeline(db)
        analysis_stats = pipeline.analyze_pending_tickets(limit=50)
        logger.info(f"Analysis complete: {analysis_stats}")

        # Generate insights
        logger.info("Generating insights...")
        aggregator = InsightAggregator(db)
        insight_stats = aggregator.aggregate_insights()
        logger.info(f"Insights generated: {insight_stats}")

    logger.info("Setup complete! Visit http://localhost:8000 to view insights.")


if __name__ == "__main__":
    main()
