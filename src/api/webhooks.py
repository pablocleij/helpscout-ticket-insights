"""Webhook receiver for HelpScout events."""

import logging
import hmac
import hashlib
from typing import Any, Dict

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from src.config import settings
from src.database import get_db
from src.syncer.helpscout import HelpScoutSyncer
from src.analyzer.pipeline import AnalysisPipeline

logger = logging.getLogger(__name__)
router = APIRouter()


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify HelpScout webhook signature."""
    if not settings.helpscout_webhook_secret:
        logger.warning("Webhook secret not configured, skipping verification")
        return True

    expected_signature = hmac.new(
        settings.helpscout_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


@router.post("/helpscout")
async def helpscout_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Receive HelpScout webhook events."""
    # Get raw body for signature verification
    body = await request.body()

    # Verify signature
    signature = request.headers.get("X-HelpScout-Signature", "")
    if not verify_webhook_signature(body, signature):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse JSON
    try:
        event = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_type = event.get("type")
    logger.info(f"Received webhook event: {event_type}")

    # Handle different event types
    if event_type == "convo.created":
        background_tasks.add_task(handle_conversation_created, event, db)
    elif event_type == "convo.updated":
        background_tasks.add_task(handle_conversation_updated, event, db)
    elif event_type == "convo.deleted":
        background_tasks.add_task(handle_conversation_deleted, event, db)
    elif event_type == "customer.created":
        logger.info("Customer created event received (not implemented)")
    else:
        logger.info(f"Unhandled event type: {event_type}")

    return {"status": "received", "event_type": event_type}


def handle_conversation_created(event: Dict[str, Any], db: Session):
    """Handle conversation created event."""
    try:
        conversation_id = event.get("id")
        if not conversation_id:
            logger.error("No conversation ID in webhook event")
            return

        # Fetch and sync the conversation
        syncer = HelpScoutSyncer(db)
        conversation = syncer.client.get_conversation(conversation_id)

        # Get mailbox info from the conversation
        mailbox_id = conversation.get("mailbox", {}).get("id")
        mailbox_name = conversation.get("mailbox", {}).get("name", "Unknown")

        # Sync the conversation
        syncer._sync_conversation(conversation, mailbox_id, mailbox_name)
        db.commit()

        logger.info(f"Synced new conversation {conversation_id}")

        # Trigger analysis
        ticket = db.query(Ticket).filter_by(helpscout_id=conversation_id).first()
        if ticket:
            pipeline = AnalysisPipeline(db)
            pipeline.analyze_ticket(ticket.id)
            logger.info(f"Analyzed conversation {conversation_id}")

    except Exception as e:
        logger.error(f"Error handling conversation created: {e}", exc_info=True)


def handle_conversation_updated(event: Dict[str, Any], db: Session):
    """Handle conversation updated event."""
    try:
        conversation_id = event.get("id")
        if not conversation_id:
            logger.error("No conversation ID in webhook event")
            return

        # Fetch and sync the conversation
        syncer = HelpScoutSyncer(db)
        conversation = syncer.client.get_conversation(conversation_id)

        # Get mailbox info
        mailbox_id = conversation.get("mailbox", {}).get("id")
        mailbox_name = conversation.get("mailbox", {}).get("name", "Unknown")

        # Sync the conversation
        syncer._sync_conversation(conversation, mailbox_id, mailbox_name)
        db.commit()

        logger.info(f"Updated conversation {conversation_id}")

        # Re-analyze if significant changes
        ticket = db.query(Ticket).filter_by(helpscout_id=conversation_id).first()
        if ticket and ticket.status == "active":
            pipeline = AnalysisPipeline(db)
            pipeline.analyze_ticket(ticket.id)
            logger.info(f"Re-analyzed conversation {conversation_id}")

    except Exception as e:
        logger.error(f"Error handling conversation updated: {e}", exc_info=True)


def handle_conversation_deleted(event: Dict[str, Any], db: Session):
    """Handle conversation deleted event."""
    try:
        conversation_id = event.get("id")
        if not conversation_id:
            logger.error("No conversation ID in webhook event")
            return

        # Delete from database
        ticket = db.query(Ticket).filter_by(helpscout_id=conversation_id).first()
        if ticket:
            db.delete(ticket)
            db.commit()
            logger.info(f"Deleted conversation {conversation_id}")

    except Exception as e:
        logger.error(f"Error handling conversation deleted: {e}", exc_info=True)
