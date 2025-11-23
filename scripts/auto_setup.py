#!/usr/bin/env python3
"""Automatic setup script for first run - handles date-based sync and analysis."""

import logging
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_db_context
from src.syncer.helpscout import HelpScoutSyncer
from src.analyzer.pipeline import AnalysisPipeline
from src.analyzer.aggregator import InsightAggregator
from src.analyzer.auto_categorizer import AutoCategorizer
from src.config import settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_start_date():
    """Parse SYNC_START_DATE from config."""
    if not settings.sync_start_date:
        return None

    try:
        return datetime.fromisoformat(settings.sync_start_date.replace("Z", "+00:00"))
    except Exception as e:
        logger.warning(f"Could not parse SYNC_START_DATE '{settings.sync_start_date}': {e}")
        return None


def main():
    """Run automatic setup on first startup."""
    logger.info("=" * 60)
    logger.info("HelpScout Ticket Insights - Automatic Setup")
    logger.info("=" * 60)

    start_date = parse_start_date()
    initial_limit = settings.sync_initial_limit if settings.sync_initial_limit > 0 else None

    if start_date:
        logger.info(f"📅 Syncing tickets from: {start_date.strftime('%Y-%m-%d')}")
    else:
        logger.info("📅 Syncing all historic tickets")

    if initial_limit:
        logger.info(f"🎯 Initial sync limit: {initial_limit} tickets")
    else:
        logger.info(f"🎯 Initial sync limit: {settings.max_tickets_per_sync} tickets (from config)")

    with get_db_context() as db:
        # Run sync
        logger.info("")
        logger.info("📥 Starting initial sync...")
        logger.info("-" * 60)

        syncer = HelpScoutSyncer(db)

        # Override max_tickets_per_sync for initial sync if specified
        original_max = settings.max_tickets_per_sync
        if initial_limit:
            settings.max_tickets_per_sync = initial_limit

        try:
            stats = syncer.sync_all_mailboxes(full_sync=True)
            logger.info("-" * 60)
            logger.info(f"✅ Sync complete!")
            logger.info(f"   Mailboxes: {stats['mailboxes']}")
            logger.info(f"   Tickets: {stats['tickets']}")
            logger.info(f"   Threads: {stats['threads']}")
        finally:
            settings.max_tickets_per_sync = original_max

        # Run analysis if enabled
        if settings.auto_initial_analysis and stats['tickets'] > 0:
            logger.info("")
            logger.info("🤖 Running LLM analysis on synced tickets...")
            logger.info("-" * 60)

            pipeline = AnalysisPipeline(db)
            # Limit initial analysis to avoid high costs
            analysis_limit = min(100, stats['tickets'])
            analysis_stats = pipeline.analyze_pending_tickets(limit=analysis_limit)

            logger.info("-" * 60)
            logger.info(f"✅ Analysis complete!")
            logger.info(f"   Analyzed: {analysis_stats['success']}")
            logger.info(f"   Failed: {analysis_stats['failed']}")

            # Generate insights
            logger.info("")
            logger.info("📊 Generating insights and aggregations...")
            logger.info("-" * 60)

            aggregator = InsightAggregator(db)
            insight_stats = aggregator.aggregate_insights()

            logger.info("-" * 60)
            logger.info(f"✅ Insights generated!")
            logger.info(f"   Total tickets analyzed: {insight_stats.get('total_tickets', 0)}")
            logger.info(f"   Top pain points: {len(insight_stats.get('top_pain_points', []))}")
            logger.info(f"   Top topics: {len(insight_stats.get('top_topics', []))}")

            # Run automatic categorization if enabled
            if settings.enable_auto_categorization:
                logger.info("")
                logger.info("🏷️  Extracting automatic categories...")
                logger.info("-" * 60)

                categorizer = AutoCategorizer(db)
                categories = categorizer.get_category_summary(days=30)

                logger.info("-" * 60)
                logger.info(f"✅ Category extraction complete!")
                logger.info(f"   Main categories: {len(categories.get('main_categories', []))}")
                logger.info(f"   Top tags: {len(categories.get('top_tags', []))}")

                # Display top categories
                if categories.get('main_categories'):
                    logger.info("")
                    logger.info("   Top Categories:")
                    for cat in categories['main_categories'][:5]:
                        logger.info(f"     • {cat['category']}: {cat['count']} tickets")
        else:
            if not settings.auto_initial_analysis:
                logger.info("")
                logger.info("⏭️  Auto analysis disabled (AUTO_INITIAL_ANALYSIS=false)")
                logger.info("   Run manually: POST /api/analyze")

    logger.info("")
    logger.info("=" * 60)
    logger.info("✨ Setup Complete!")
    logger.info("=" * 60)
    logger.info("")
    logger.info("🌐 Access the dashboard at: http://localhost:8000")
    logger.info("📚 API documentation at: http://localhost:8000/docs")
    logger.info("")


if __name__ == "__main__":
    main()
