"""Tests for analyzer pipeline."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from src.analyzer.pipeline import AnalysisPipeline
from src.analyzer.aggregator import InsightAggregator
from src.models import Ticket, Thread, TicketAnalysis


@pytest.fixture
def sample_ticket(db_session):
    """Create a sample ticket for testing."""
    ticket = Ticket(
        helpscout_id=12345,
        number=1,
        subject="Billing issue",
        status="active",
        mailbox_id=1,
        mailbox_name="Support",
        customer_email="test@example.com",
        customer_name="Test User",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(ticket)

    # Add thread
    thread = Thread(
        helpscout_id=1,
        ticket_id=1,
        type="customer",
        body="<p>I have a billing problem</p>",
        body_plain="I have a billing problem",
        created_at=datetime.utcnow(),
        is_customer=True,
    )
    db_session.add(thread)
    db_session.commit()

    return ticket


@patch("src.analyzer.pipeline.get_llm_provider")
def test_analyze_ticket(mock_get_provider, db_session, sample_ticket):
    """Test ticket analysis."""
    # Mock LLM provider
    mock_provider = Mock()
    mock_provider.analyze_ticket.return_value = {
        "pain_points": ["slow billing", "confusing invoice"],
        "topics": ["billing", "payments"],
        "sentiment": "negative",
        "urgency_score": 0.7,
        "suggested_tags": ["billing", "urgent"],
        "summary": "Customer has billing issues",
        "raw_response": {},
    }
    mock_get_provider.return_value = mock_provider

    # Run analysis
    pipeline = AnalysisPipeline(db_session)
    analysis = pipeline.analyze_ticket(sample_ticket.id)

    # Verify analysis was created
    assert analysis is not None
    assert analysis.ticket_id == sample_ticket.id
    assert "slow billing" in analysis.pain_points
    assert analysis.sentiment == "negative"
    assert analysis.urgency_score == 0.7


@patch("src.analyzer.pipeline.get_llm_provider")
def test_analyze_pending_tickets(mock_get_provider, db_session):
    """Test analyzing pending tickets."""
    # Create tickets without analysis
    for i in range(3):
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
    db_session.commit()

    # Mock LLM provider
    mock_provider = Mock()
    mock_provider.analyze_ticket.return_value = {
        "pain_points": ["test"],
        "topics": ["test"],
        "sentiment": "neutral",
        "urgency_score": 0.5,
        "suggested_tags": ["test"],
        "summary": "Test",
        "raw_response": {},
    }
    mock_get_provider.return_value = mock_provider

    # Analyze pending tickets
    pipeline = AnalysisPipeline(db_session)
    stats = pipeline.analyze_pending_tickets(limit=5)

    assert stats["total"] == 3
    assert stats["success"] == 3
    assert stats["failed"] == 0


def test_aggregate_insights(db_session):
    """Test insight aggregation."""
    # Create tickets with analysis
    for i in range(5):
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
            pain_points=["slow response", "confusing UI"] if i % 2 == 0 else ["slow response"],
            topics=["billing"],
            sentiment="negative" if i < 2 else "neutral",
            urgency_score=0.5 + (i * 0.1),
            suggested_tags=["test"],
            summary="Test",
            llm_provider="openai",
            llm_model="gpt-4",
        )
        db_session.add(analysis)
    db_session.commit()

    # Aggregate insights
    aggregator = InsightAggregator(db_session)
    stats = aggregator.aggregate_insights(days=7)

    assert stats["total_tickets"] == 5
    assert len(stats["top_pain_points"]) > 0
    assert stats["top_pain_points"][0]["pain_point"] == "slow response"
    assert stats["sentiment_distribution"]["negative"] == 2
    assert stats["sentiment_distribution"]["neutral"] == 3
