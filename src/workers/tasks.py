"""RQ worker tasks for background processing."""

import logging
from typing import Dict, Any

from src.database import get_db_context
from src.syncer.helpscout import HelpScoutSyncer
from src.analyzer.pipeline import AnalysisPipeline
from src.analyzer.aggregator import InsightAggregator

logger = logging.getLogger(__name__)


def sync_all_mailboxes(full_sync: bool = False) -> Dict[str, int]:
    """Background task to sync all mailboxes."""
    logger.info(f"Starting sync task (full_sync={full_sync})")
    try:
        with get_db_context() as db:
            syncer = HelpScoutSyncer(db)
            stats = syncer.sync_all_mailboxes(full_sync=full_sync)
            logger.info(f"Sync task complete: {stats}")
            return stats
    except Exception as e:
        logger.error(f"Sync task failed: {e}", exc_info=True)
        raise


def sync_mailbox(mailbox_id: int, mailbox_name: str, full_sync: bool = False) -> Dict[str, int]:
    """Background task to sync a specific mailbox."""
    logger.info(f"Starting mailbox sync task for {mailbox_id}")
    try:
        with get_db_context() as db:
            syncer = HelpScoutSyncer(db)
            stats = syncer.sync_mailbox(mailbox_id, mailbox_name, full_sync=full_sync)
            logger.info(f"Mailbox sync task complete: {stats}")
            return stats
    except Exception as e:
        logger.error(f"Mailbox sync task failed: {e}", exc_info=True)
        raise


def analyze_ticket(ticket_id: int) -> Dict[str, Any]:
    """Background task to analyze a single ticket."""
    logger.info(f"Starting analysis task for ticket {ticket_id}")
    try:
        with get_db_context() as db:
            pipeline = AnalysisPipeline(db)
            analysis = pipeline.analyze_ticket(ticket_id)
            if analysis:
                return {
                    "ticket_id": ticket_id,
                    "pain_points": analysis.pain_points,
                    "topics": analysis.topics,
                    "sentiment": analysis.sentiment,
                }
            else:
                return {"ticket_id": ticket_id, "error": "Analysis failed"}
    except Exception as e:
        logger.error(f"Analysis task failed: {e}", exc_info=True)
        raise


def analyze_pending_tickets(limit: int = 100) -> Dict[str, int]:
    """Background task to analyze pending tickets."""
    logger.info(f"Starting bulk analysis task (limit={limit})")
    try:
        with get_db_context() as db:
            pipeline = AnalysisPipeline(db)
            stats = pipeline.analyze_pending_tickets(limit=limit)
            logger.info(f"Bulk analysis task complete: {stats}")
            return stats
    except Exception as e:
        logger.error(f"Bulk analysis task failed: {e}", exc_info=True)
        raise


def aggregate_insights(days: int = 7, mailbox_id: int = None) -> Dict[str, Any]:
    """Background task to aggregate insights."""
    logger.info(f"Starting aggregation task (days={days}, mailbox={mailbox_id})")
    try:
        with get_db_context() as db:
            aggregator = InsightAggregator(db)
            stats = aggregator.aggregate_insights(days=days, mailbox_id=mailbox_id)
            logger.info(f"Aggregation task complete: {stats}")
            return stats
    except Exception as e:
        logger.error(f"Aggregation task failed: {e}", exc_info=True)
        raise
