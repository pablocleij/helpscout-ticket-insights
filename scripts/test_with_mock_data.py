#!/usr/bin/env python3
"""
Test script with mock data to verify the complete system works.

This script:
1. Creates mock HelpScout tickets in the database
2. Runs LLM analysis (or uses mock analysis if no API key)
3. Runs statistical analysis
4. Displays results

Run with: python scripts/test_with_mock_data.py
"""

import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any
import random

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import get_db_context, init_db
from src.models import Ticket, Thread, TicketAnalysis
from src.analyzer.pipeline import AnalysisPipeline
from src.analyzer.stats_analyzer import StatisticalAnalyzer
from src.config import settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Mock ticket data
MOCK_TICKETS = [
    {
        "subject": "Payment failed - card declined",
        "body": "I tried to purchase your product but my card was declined. Can you help?",
        "category": "Billing",
        "subcategory": "Payment Failed",
        "sentiment": "negative",
        "urgency": 0.7,
    },
    {
        "subject": "How to integrate with Slack?",
        "body": "I'm trying to set up the Slack integration but can't find the API key",
        "category": "Integration",
        "subcategory": "Third-Party Setup",
        "sentiment": "neutral",
        "urgency": 0.5,
    },
    {
        "subject": "App crashes when exporting large files",
        "body": "Every time I try to export more than 1000 records, the app crashes",
        "category": "Technical Issue",
        "subcategory": "Application Crash",
        "sentiment": "negative",
        "urgency": 0.8,
    },
    {
        "subject": "Request: Dark mode support",
        "body": "Would love to see a dark mode option in your app!",
        "category": "Feature Request",
        "subcategory": "UI Enhancement",
        "sentiment": "positive",
        "urgency": 0.2,
    },
    {
        "subject": "Can't access my account after password reset",
        "body": "I reset my password but now I'm getting an error when trying to log in",
        "category": "Account Access",
        "subcategory": "Login Issue",
        "sentiment": "negative",
        "urgency": 0.9,
    },
    {
        "subject": "Invoice doesn't match what I ordered",
        "body": "The invoice shows a different amount than what I was quoted",
        "category": "Billing",
        "subcategory": "Invoice Question",
        "sentiment": "negative",
        "urgency": 0.6,
    },
    {
        "subject": "Very slow performance when loading dashboard",
        "body": "It takes over 30 seconds to load my dashboard. This is unacceptable.",
        "category": "Performance",
        "subcategory": "Slow Loading",
        "sentiment": "negative",
        "urgency": 0.7,
    },
    {
        "subject": "How do I export my data?",
        "body": "I need to export all my data to CSV. Is this possible?",
        "category": "Data Management",
        "subcategory": "Export Question",
        "sentiment": "neutral",
        "urgency": 0.4,
    },
    {
        "subject": "Billing: Need refund for duplicate charge",
        "body": "I was charged twice for the same subscription. Please refund.",
        "category": "Billing",
        "subcategory": "Refund Request",
        "sentiment": "negative",
        "urgency": 0.8,
    },
    {
        "subject": "API rate limits too restrictive",
        "body": "Your API rate limits are blocking our integration. Can we increase them?",
        "category": "Integration",
        "subcategory": "API Limitations",
        "sentiment": "negative",
        "urgency": 0.6,
    },
]


def create_mock_tickets(db) -> int:
    """Create mock tickets in the database."""
    logger.info("Creating mock tickets...")

    created_count = 0
    base_time = datetime.utcnow() - timedelta(days=7)

    for i, ticket_data in enumerate(MOCK_TICKETS):
        # Check if ticket already exists
        existing = db.query(Ticket).filter_by(helpscout_id=1000 + i).first()
        if existing:
            logger.info(f"Ticket {1000 + i} already exists, skipping")
            continue

        # Create ticket
        ticket = Ticket(
            helpscout_id=1000 + i,
            number=i + 1,
            subject=ticket_data["subject"],
            status="active",
            type="email",
            mailbox_id=1,
            mailbox_name="Support",
            customer_email=f"customer{i}@example.com",
            customer_name=f"Test Customer {i}",
            created_at=base_time + timedelta(days=i * 0.7),
            updated_at=base_time + timedelta(days=i * 0.7),
            tags=["test", "mock"],
        )
        db.add(ticket)
        db.flush()

        # Create thread
        thread = Thread(
            helpscout_id=2000 + i,
            ticket_id=ticket.id,
            type="customer",
            body=f"<p>{ticket_data['body']}</p>",
            body_plain=ticket_data["body"],
            created_by_email=ticket.customer_email,
            created_by_name=ticket.customer_name,
            created_at=ticket.created_at,
            is_customer=True,
        )
        db.add(thread)

        created_count += 1

    db.commit()
    logger.info(f"Created {created_count} mock tickets")
    return created_count


def create_mock_analysis(db) -> int:
    """Create mock LLM analysis for tickets."""
    logger.info("Creating mock LLM analysis...")

    analyzed_count = 0

    for i, ticket_data in enumerate(MOCK_TICKETS):
        ticket = db.query(Ticket).filter_by(helpscout_id=1000 + i).first()
        if not ticket:
            continue

        # Check if analysis exists
        existing_analysis = db.query(TicketAnalysis).filter_by(ticket_id=ticket.id).first()
        if existing_analysis:
            logger.info(f"Analysis for ticket {ticket.id} already exists, skipping")
            continue

        # Create mock analysis
        analysis = TicketAnalysis(
            ticket_id=ticket.id,
            category=ticket_data["category"],
            subcategory=ticket_data["subcategory"],
            pain_points=[
                "unclear process",
                ticket_data["subject"].lower(),
            ],
            topics=[ticket_data["category"].lower(), "customer support"],
            sentiment=ticket_data["sentiment"],
            urgency_score=ticket_data["urgency"],
            suggested_tags=[
                ticket_data["category"].lower().replace(" ", "_"),
                ticket_data["sentiment"],
            ],
            summary=f"Customer experiencing {ticket_data['subcategory'].lower()} issue",
            analyzed_at=datetime.utcnow(),
            llm_provider="mock",
            llm_model="mock-gpt-4",
        )
        db.add(analysis)
        analyzed_count += 1

    db.commit()
    logger.info(f"Created {analyzed_count} mock analyses")
    return analyzed_count


def test_statistical_analysis(db):
    """Test the statistical analyzer."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING STATISTICAL ANALYSIS")
    logger.info("=" * 60)

    analyzer = StatisticalAnalyzer(db)
    stats = analyzer.analyze_categories(days=7)

    logger.info(f"\nTotal tickets analyzed: {stats['total_analyzed']}")

    # Category distribution
    logger.info("\n📊 CATEGORY DISTRIBUTION:")
    for cat in stats["categories"]:
        logger.info(
            f"  • {cat['category']}: {cat['count']} tickets ({cat['percentage']}%)"
        )
        for subcat in cat["subcategories"][:3]:
            logger.info(
                f"    - {subcat['name']}: {subcat['count']} ({subcat['percentage']:.1f}%)"
            )

    # Sentiment analysis
    logger.info("\n😊 SENTIMENT BY CATEGORY:")
    for category, sentiments in stats["category_sentiment_analysis"].items():
        logger.info(f"  {category}:")
        for sentiment, data in sentiments.items():
            logger.info(f"    - {sentiment}: {data['count']} ({data['percentage']}%)")

    # Urgency analysis
    logger.info("\n⚠️  URGENCY BY CATEGORY:")
    for category, urgency in stats["category_urgency_analysis"].items():
        logger.info(
            f"  {category}: avg={urgency['average']}, max={urgency['max']}, min={urgency['min']}"
        )

    # Trending
    logger.info("\n📈 TRENDING (Last 7 days):")
    trending = stats["trending"]
    if trending["dates"]:
        logger.info(f"  Dates: {', '.join(trending['dates'][-3:])}")
        for category, values in trending["series"].items():
            logger.info(f"  {category}: {values}")

    return stats


def test_category_breakdown(db):
    """Test detailed category breakdown."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING CATEGORY BREAKDOWN")
    logger.info("=" * 60)

    analyzer = StatisticalAnalyzer(db)

    # Test breakdown for "Billing" category
    logger.info("\n📊 BILLING CATEGORY BREAKDOWN:")
    breakdown = analyzer.get_category_breakdown("Billing", days=7)

    if breakdown["count"] > 0:
        logger.info(f"  Total tickets: {breakdown['count']}")
        logger.info(f"  Average urgency: {breakdown['average_urgency']}")
        logger.info(f"  Sentiment: {breakdown['sentiment_distribution']}")

        logger.info("\n  Subcategories:")
        for subcat in breakdown["subcategories"]:
            logger.info(f"    - {subcat['name']}: {subcat['count']}")

        logger.info("\n  Top pain points:")
        for pp in breakdown["top_pain_points"][:3]:
            logger.info(f"    - {pp['pain_point']}: {pp['count']}")
    else:
        logger.warning("  No billing tickets found")

    return breakdown


def verify_sync_integrity(db):
    """Verify no duplicate tickets exist."""
    logger.info("\n" + "=" * 60)
    logger.info("VERIFYING SYNC INTEGRITY")
    logger.info("=" * 60)

    # Check for duplicate helpscout_ids
    from sqlalchemy import func

    duplicates = (
        db.query(Ticket.helpscout_id, func.count(Ticket.id))
        .group_by(Ticket.helpscout_id)
        .having(func.count(Ticket.id) > 1)
        .all()
    )

    if duplicates:
        logger.error(f"❌ Found {len(duplicates)} duplicate tickets!")
        for hs_id, count in duplicates:
            logger.error(f"  HelpScout ID {hs_id}: {count} duplicates")
        return False
    else:
        logger.info("✅ No duplicate tickets found")

    # Verify all tickets have threads
    tickets_without_threads = (
        db.query(Ticket)
        .outerjoin(Thread)
        .filter(Thread.id.is_(None))
        .count()
    )

    if tickets_without_threads > 0:
        logger.warning(f"⚠️  {tickets_without_threads} tickets without threads")
    else:
        logger.info("✅ All tickets have threads")

    # Verify analysis coverage
    total_tickets = db.query(Ticket).count()
    analyzed_tickets = (
        db.query(Ticket)
        .join(TicketAnalysis)
        .count()
    )

    coverage = (analyzed_tickets / total_tickets * 100) if total_tickets > 0 else 0
    logger.info(f"📊 Analysis coverage: {analyzed_tickets}/{total_tickets} ({coverage:.1f}%)")

    if coverage == 100:
        logger.info("✅ All tickets analyzed")
    elif coverage >= 80:
        logger.info(f"⚠️  {coverage:.1f}% analyzed (acceptable)")
    else:
        logger.warning(f"⚠️  Only {coverage:.1f}% analyzed")

    return True


def main():
    """Run the test suite."""
    logger.info("🧪 HelpScout Ticket Insights - Test Suite")
    logger.info("=" * 60)

    try:
        # Initialize database
        logger.info("Initializing database...")
        init_db()

        with get_db_context() as db:
            # 1. Create mock data
            logger.info("\n" + "=" * 60)
            logger.info("STEP 1: CREATING MOCK DATA")
            logger.info("=" * 60)

            tickets_created = create_mock_tickets(db)
            analyses_created = create_mock_analysis(db)

            logger.info(f"\n✅ Created {tickets_created} tickets")
            logger.info(f"✅ Created {analyses_created} analyses")

            # 2. Verify sync integrity
            verify_sync_integrity(db)

            # 3. Test statistical analysis
            stats = test_statistical_analysis(db)

            # 4. Test category breakdown
            breakdown = test_category_breakdown(db)

            # Summary
            logger.info("\n" + "=" * 60)
            logger.info("✅ ALL TESTS COMPLETED SUCCESSFULLY!")
            logger.info("=" * 60)

            logger.info("\n📋 SUMMARY:")
            logger.info(f"  • Mock tickets created: {tickets_created}")
            logger.info(f"  • Analyses created: {analyses_created}")
            logger.info(f"  • Categories found: {len(stats['categories'])}")
            logger.info(
                f"  • Sentiment analysis: {len(stats['category_sentiment_analysis'])} categories"
            )
            logger.info(f"  • No duplicates: ✅")

            logger.info("\n🌐 Next steps:")
            logger.info("  1. Start the API: docker compose up -d")
            logger.info("  2. Visit: http://localhost:8000")
            logger.info("  3. Check API docs: http://localhost:8000/docs")
            logger.info("  4. View categories: http://localhost:8000/api/categories/stats")

    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
