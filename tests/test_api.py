"""Tests for API endpoints."""

import pytest
from datetime import datetime

from src.models import Ticket, TicketAnalysis, AggregatedInsight


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_get_insights_no_data(client):
    """Test insights endpoint with no data."""
    response = client.get("/api/insights")
    assert response.status_code == 404


def test_get_insights_with_data(client, db_session):
    """Test insights endpoint with aggregated data."""
    # Create aggregated insight
    insight = AggregatedInsight(
        period_start=datetime.utcnow(),
        period_end=datetime.utcnow(),
        top_pain_points=[
            {"pain_point": "slow response", "count": 10, "percentage": 50.0},
            {"pain_point": "confusing UI", "count": 5, "percentage": 25.0},
        ],
        top_topics=[{"topic": "billing", "count": 8, "percentage": 40.0}],
        sentiment_distribution={"positive": 5, "neutral": 10, "negative": 5},
        average_urgency=0.6,
        total_tickets_analyzed=20,
    )
    db_session.add(insight)
    db_session.commit()

    response = client.get("/api/insights")
    assert response.status_code == 200
    data = response.json()
    assert data["total_tickets_analyzed"] == 20
    assert len(data["top_pain_points"]) == 2
    assert data["top_pain_points"][0]["pain_point"] == "slow response"


def test_get_tickets_empty(client):
    """Test tickets endpoint with no tickets."""
    response = client.get("/api/tickets")
    assert response.status_code == 200
    data = response.json()
    assert data == []


def test_get_tickets_with_data(client, db_session):
    """Test tickets endpoint with data."""
    # Create ticket
    ticket = Ticket(
        helpscout_id=12345,
        number=1,
        subject="Test ticket",
        status="active",
        mailbox_id=1,
        mailbox_name="Support",
        customer_email="test@example.com",
        customer_name="Test User",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(ticket)
    db_session.commit()

    response = client.get("/api/tickets")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["subject"] == "Test ticket"
    assert data[0]["helpscout_id"] == 12345


def test_get_ticket_not_found(client):
    """Test get single ticket that doesn't exist."""
    response = client.get("/api/tickets/999")
    assert response.status_code == 404


def test_get_ticket_with_analysis(client, db_session):
    """Test get single ticket with analysis."""
    # Create ticket
    ticket = Ticket(
        helpscout_id=12345,
        number=1,
        subject="Test ticket",
        status="active",
        mailbox_id=1,
        mailbox_name="Support",
        customer_email="test@example.com",
        customer_name="Test User",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(ticket)
    db_session.flush()

    # Create analysis
    analysis = TicketAnalysis(
        ticket_id=ticket.id,
        pain_points=["slow response"],
        topics=["billing"],
        sentiment="negative",
        urgency_score=0.8,
        suggested_tags=["urgent", "billing"],
        summary="Customer complains about slow billing response",
        llm_provider="openai",
        llm_model="gpt-4",
    )
    db_session.add(analysis)
    db_session.commit()

    response = client.get(f"/api/tickets/{ticket.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["ticket"]["subject"] == "Test ticket"
    assert data["analysis"]["sentiment"] == "negative"
    assert data["analysis"]["urgency_score"] == 0.8
