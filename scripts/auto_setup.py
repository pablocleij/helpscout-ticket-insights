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
from src.analyzer.stats_analyzer import StatisticalAnalyzer
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
        # Handle different date formats
        date_str = settings.sync_start_date.replace("Z", "+00:00")
        return datetime.fromisoformat(date_str)
    except Exception as e:
        logger.warning(f"Could not parse SYNC_START_DATE '{settings.sync_start_date}': {e}")
        return None


def main():
    """Run automatic setup on first startup."""
    logger.info("=" * 60)
    logger.info("HelpScout Ticket Insights - Automatic Setup")
    logger.info("=" * 60)

    start_date = parse_start_date()

    if start_date:
        logger.info(f"📅 Syncing tickets from: {start_date.strftime('%Y-%m-%d')}")
    else:
        logger.info("📅 Syncing all historic tickets")

    logger.info(f"🎯 Sync limit: {settings.max_tickets_per_sync} tickets per mailbox")

    with get_db_context() as db:
        # Run sync
        logger.info("")
        logger.info("📥 Starting initial sync...")
        logger.info("-" * 60)

        syncer = HelpScoutSyncer(db)
        stats = syncer.sync_all_mailboxes(full_sync=True)

        logger.info("-" * 60)
        logger.info(f"✅ Sync complete!")
        logger.info(f"   Mailboxes: {stats['mailboxes']}")
        logger.info(f"   Tickets: {stats['tickets']}")
        logger.info(f"   Threads: {stats['threads']}")

        # Run analysis if enabled
        if settings.auto_initial_analysis and stats['tickets'] > 0:
            logger.info("")
            logger.info("🤖 Running LLM categorization on synced tickets...")
            logger.info("-" * 60)

            pipeline = AnalysisPipeline(db)
            # Limit initial analysis to avoid high costs
            analysis_limit = min(100, stats['tickets'])
            analysis_stats = pipeline.analyze_pending_tickets(limit=analysis_limit)

            logger.info("-" * 60)
            logger.info(f"✅ LLM categorization complete!")
            logger.info(f"   Analyzed: {analysis_stats['success']}")
            logger.info(f"   Failed: {analysis_stats['failed']}")

            # Run statistical analysis on LLM categories
            if analysis_stats['success'] > 0:
                logger.info("")
                logger.info("📊 Running statistical analysis on categories...")
                logger.info("-" * 60)

                stats_analyzer = StatisticalAnalyzer(db)
                category_stats = stats_analyzer.analyze_categories(days=30)

                logger.info("-" * 60)
                logger.info(f"✅ Statistical analysis complete!")
                logger.info(f"   Total categories: {category_stats.get('total_categories', 0)}")
                logger.info(f"   Total tickets analyzed: {category_stats.get('total_analyzed', 0)}")

                # Display top categories
                if category_stats.get('distribution'):
                    logger.info("")
                    logger.info("   Top Categories:")
                    for cat_info in list(category_stats['distribution'].items())[:5]:
                        cat_name, cat_data = cat_info
                        logger.info(f"     • {cat_name}: {cat_data['count']} tickets ({cat_data['percentage']:.1f}%)")
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
