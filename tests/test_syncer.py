"""Tests for HelpScout syncer."""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock

from src.syncer.helpscout import HelpScoutClient, HelpScoutSyncer
from src.models import Ticket, Thread, SyncState


@pytest.fixture
def mock_client():
    """Create mock HelpScout client."""
    client = Mock(spec=HelpScoutClient)
    return client


def test_sync_conversation_new(db_session, mock_client):
    """Test syncing a new conversation."""
    syncer = HelpScoutSyncer(db_session, client=mock_client)

    # Mock conversation data
    conv_data = {
        "id": 12345,
        "number": 1,
        "subject": "Test ticket",
        "status": "active",
        "type": "email",
        "createdAt": "2024-01-01T10:00:00Z",
        "userUpdatedAt": "2024-01-01T10:00:00Z",
        "closedAt": None,
        "primaryCustomer": {"email": "test@example.com", "first": "Test", "last": "User"},
        "tags": ["billing", "urgent"],
    }

    # Mock threads response
    mock_client.get_conversation_threads.return_value = [
        {
            "id": 1,
            "type": "customer",
            "body": "<p>Test message</p>",
            "createdAt": "2024-01-01T10:00:00Z",
            "createdBy": {"email": "test@example.com", "first": "Test", "last": "User"},
        }
    ]

    # Sync conversation
    syncer._sync_conversation(conv_data, 1, "Support")

    # Verify ticket was created
    ticket = db_session.query(Ticket).filter_by(helpscout_id=12345).first()
    assert ticket is not None
    assert ticket.subject == "Test ticket"
    assert ticket.status == "active"
    assert ticket.customer_email == "test@example.com"
    assert ticket.tags == ["billing", "urgent"]

    # Verify thread was created
    threads = db_session.query(Thread).filter_by(ticket_id=ticket.id).all()
    assert len(threads) == 1
    assert threads[0].type == "customer"


def test_sync_conversation_update(db_session, mock_client):
    """Test updating an existing conversation."""
    syncer = HelpScoutSyncer(db_session, client=mock_client)

    # Create existing ticket
    existing_ticket = Ticket(
        helpscout_id=12345,
        number=1,
        subject="Old subject",
        status="active",
        mailbox_id=1,
        mailbox_name="Support",
        customer_email="test@example.com",
        customer_name="Test User",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(existing_ticket)
    db_session.commit()

    # Mock updated conversation data
    conv_data = {
        "id": 12345,
        "number": 1,
        "subject": "Updated subject",
        "status": "closed",
        "type": "email",
        "createdAt": "2024-01-01T10:00:00Z",
        "userUpdatedAt": "2024-01-02T10:00:00Z",
        "closedAt": "2024-01-02T10:00:00Z",
        "primaryCustomer": {"email": "test@example.com", "first": "Test", "last": "User"},
        "tags": ["resolved"],
    }

    mock_client.get_conversation_threads.return_value = []

    # Sync conversation
    syncer._sync_conversation(conv_data, 1, "Support")

    # Verify ticket was updated
    ticket = db_session.query(Ticket).filter_by(helpscout_id=12345).first()
    assert ticket.subject == "Updated subject"
    assert ticket.status == "closed"
    assert ticket.tags == ["resolved"]
