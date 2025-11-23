"""Tests for statistical analyzer."""

import pytest
from datetime import datetime, timedelta

from src.analyzer.stats_analyzer import StatisticalAnalyzer
from src.models import Ticket, TicketAnalysis


def test_analyze_categories(db_session):
    """Test category statistical analysis."""
    # Create tickets with analysis across different categories
    categories_data = [
        ("Billing", "Payment Failed", "negative", 0.8),
        ("Billing", "Invoice Question", "neutral", 0.5),
        ("Billing", "Payment Failed", "negative", 0.9),
        ("Technical Issue", "Bug", "negative", 0.7),
        ("Technical Issue", "Crash", "negative", 0.95),
        ("Feature Request", "UI Enhancement", "positive", 0.3),
    ]

    for i, (category, subcategory, sentiment, urgency) in enumerate(categories_data):
        ticket = Ticket(
            helpscout_id=1000 + i,
            number=i + 1,
            subject=f"Test ticket {i}",
            status="active",
            mailbox_id=1,
            mailbox_name="Support",
            customer_email=f"test{i}@example.com",
            customer_name=f"Test User {i}",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(ticket)
        db_session.flush()

        analysis = TicketAnalysis(
            ticket_id=ticket.id,
            category=category,
            subcategory=subcategory,
            pain_points=["test issue"],
            topics=["test"],
            sentiment=sentiment,
            urgency_score=urgency,
            suggested_tags=["test"],
            summary="Test",
            llm_provider="mock",
            llm_model="mock",
        )
        db_session.add(analysis)

    db_session.commit()

    # Run statistical analysis
    analyzer = StatisticalAnalyzer(db_session)
    stats = analyzer.analyze_categories(days=7)

    # Verify results
    assert stats["total_analyzed"] == 6

    # Check category distribution
    categories = {cat["category"]: cat for cat in stats["categories"]}
    assert "Billing" in categories
    assert "Technical Issue" in categories
    assert "Feature Request" in categories

    billing = categories["Billing"]
    assert billing["count"] == 3
    assert billing["percentage"] == 50.0  # 3/6 * 100

    # Check subcategories
    billing_subcats = {sub["name"]: sub for sub in billing["subcategories"]}
    assert "Payment Failed" in billing_subcats
    assert billing_subcats["Payment Failed"]["count"] == 2
    assert "Invoice Question" in billing_subcats
    assert billing_subcats["Invoice Question"]["count"] == 1

    # Check sentiment analysis
    assert "Billing" in stats["category_sentiment_analysis"]
    billing_sentiment = stats["category_sentiment_analysis"]["Billing"]
    assert billing_sentiment["negative"]["count"] == 2
    assert billing_sentiment["neutral"]["count"] == 1

    # Check urgency analysis
    assert "Billing" in stats["category_urgency_analysis"]
    billing_urgency = stats["category_urgency_analysis"]["Billing"]
    assert billing_urgency["count"] == 3
    # Average of 0.8, 0.5, 0.9 = 0.73
    assert 0.72 <= billing_urgency["average"] <= 0.74


def test_category_breakdown(db_session):
    """Test detailed category breakdown."""
    # Create tickets in "Billing" category
    for i in range(3):
        ticket = Ticket(
            helpscout_id=2000 + i,
            number=i + 1,
            subject=f"Billing issue {i}",
            status="active",
            mailbox_id=1,
            mailbox_name="Support",
            customer_email=f"customer{i}@example.com",
            customer_name=f"Customer {i}",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(ticket)
        db_session.flush()

        analysis = TicketAnalysis(
            ticket_id=ticket.id,
            category="Billing",
            subcategory="Payment Failed" if i < 2 else "Refund Request",
            pain_points=["payment declined", "card error"] if i == 0 else ["payment declined"],
            topics=["billing", "payments"],
            sentiment="negative",
            urgency_score=0.7 + (i * 0.1),
            suggested_tags=["billing"],
            summary="Billing issue",
            llm_provider="mock",
            llm_model="mock",
        )
        db_session.add(analysis)

    db_session.commit()

    # Get breakdown
    analyzer = StatisticalAnalyzer(db_session)
    breakdown = analyzer.get_category_breakdown("Billing", days=7)

    # Verify
    assert breakdown["category"] == "Billing"
    assert breakdown["count"] == 3
    assert breakdown["sentiment_distribution"]["negative"] == 3

    # Check subcategories
    subcats = {sub["name"]: sub for sub in breakdown["subcategories"]}
    assert "Payment Failed" in subcats
    assert subcats["Payment Failed"]["count"] == 2
    assert "Refund Request" in subcats
    assert subcats["Refund Request"]["count"] == 1

    # Check pain points
    pain_points = {pp["pain_point"]: pp for pp in breakdown["top_pain_points"]}
    assert "payment declined" in pain_points
    assert pain_points["payment declined"]["count"] == 3


def test_empty_category(db_session):
    """Test breakdown for non-existent category."""
    analyzer = StatisticalAnalyzer(db_session)
    breakdown = analyzer.get_category_breakdown("NonExistent", days=7)

    assert breakdown["category"] == "NonExistent"
    assert breakdown["count"] == 0
