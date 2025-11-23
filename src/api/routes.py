"""API routes for insights and tickets."""

import logging
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.database import get_db
from src.models import Ticket, TicketAnalysis, AggregatedInsight, SyncState
from src.analyzer.aggregator import InsightAggregator
from src.analyzer.pipeline import AnalysisPipeline
from src.syncer.helpscout import HelpScoutSyncer
from src.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# Response models
class PainPointResponse(BaseModel):
    pain_point: str
    count: int
    percentage: float


class TopicResponse(BaseModel):
    topic: str
    count: int
    percentage: float


class InsightsResponse(BaseModel):
    period_start: datetime
    period_end: datetime
    total_tickets_analyzed: int
    top_pain_points: List[PainPointResponse]
    top_topics: List[TopicResponse]
    sentiment_distribution: dict
    average_urgency: float


class TicketSummary(BaseModel):
    id: int
    helpscout_id: int
    number: int
    subject: Optional[str]
    status: str
    customer_name: Optional[str]
    created_at: datetime
    sentiment: Optional[str] = None
    urgency_score: Optional[float] = None
    pain_points: Optional[List[str]] = None


class SyncStatusResponse(BaseModel):
    mailbox_id: int
    last_sync_at: datetime
    total_tickets_synced: int


@router.get("/insights", response_model=InsightsResponse)
def get_insights(
    days: int = Query(default=7, ge=1, le=90),
    mailbox_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get aggregated insights for the specified period."""
    aggregator = InsightAggregator(db)

    # Try to get existing aggregated data
    latest = aggregator.get_latest_insights(mailbox_id=mailbox_id)

    # Check if we need fresh aggregation
    if not latest or (datetime.utcnow() - latest.updated_at).total_seconds() > 3600:
        # Aggregate fresh data
        logger.info("Generating fresh insights")
        aggregator.aggregate_insights(days=days, mailbox_id=mailbox_id)
        latest = aggregator.get_latest_insights(mailbox_id=mailbox_id)

    if not latest:
        raise HTTPException(status_code=404, detail="No insights available")

    return InsightsResponse(
        period_start=latest.period_start,
        period_end=latest.period_end,
        total_tickets_analyzed=latest.total_tickets_analyzed,
        top_pain_points=[PainPointResponse(**pp) for pp in latest.top_pain_points],
        top_topics=[TopicResponse(**t) for t in latest.top_topics],
        sentiment_distribution=latest.sentiment_distribution,
        average_urgency=latest.average_urgency,
    )


@router.get("/tickets", response_model=List[TicketSummary])
def get_tickets(
    status: Optional[str] = None,
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Get recent tickets with analysis."""
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    query = (
        db.query(Ticket, TicketAnalysis)
        .outerjoin(TicketAnalysis)
        .filter(Ticket.created_at >= cutoff_date)
        .order_by(Ticket.created_at.desc())
        .limit(limit)
    )

    if status:
        query = query.filter(Ticket.status == status)

    results = query.all()

    return [
        TicketSummary(
            id=ticket.id,
            helpscout_id=ticket.helpscout_id,
            number=ticket.number,
            subject=ticket.subject,
            status=ticket.status,
            customer_name=ticket.customer_name,
            created_at=ticket.created_at,
            sentiment=analysis.sentiment if analysis else None,
            urgency_score=analysis.urgency_score if analysis else None,
            pain_points=analysis.pain_points if analysis else None,
        )
        for ticket, analysis in results
    ]


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    """Get detailed ticket information."""
    ticket = db.query(Ticket).filter_by(id=ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    analysis = db.query(TicketAnalysis).filter_by(ticket_id=ticket_id).first()

    return {
        "ticket": {
            "id": ticket.id,
            "helpscout_id": ticket.helpscout_id,
            "number": ticket.number,
            "subject": ticket.subject,
            "status": ticket.status,
            "customer_email": ticket.customer_email,
            "customer_name": ticket.customer_name,
            "created_at": ticket.created_at,
            "updated_at": ticket.updated_at,
            "tags": ticket.tags,
        },
        "analysis": {
            "pain_points": analysis.pain_points if analysis else [],
            "topics": analysis.topics if analysis else [],
            "sentiment": analysis.sentiment if analysis else None,
            "urgency_score": analysis.urgency_score if analysis else None,
            "suggested_tags": analysis.suggested_tags if analysis else [],
            "summary": analysis.summary if analysis else None,
            "analyzed_at": analysis.analyzed_at if analysis else None,
        }
        if analysis
        else None,
    }


@router.post("/sync")
def trigger_sync(
    background_tasks: BackgroundTasks,
    full_sync: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    """Trigger a manual sync."""

    def run_sync():
        with get_db() as db:
            syncer = HelpScoutSyncer(db)
            stats = syncer.sync_all_mailboxes(full_sync=full_sync)
            logger.info(f"Manual sync complete: {stats}")

    background_tasks.add_task(run_sync)
    return {"message": "Sync started", "full_sync": full_sync}


@router.post("/analyze")
def trigger_analysis(
    background_tasks: BackgroundTasks,
    limit: Optional[int] = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Trigger analysis of pending tickets."""

    def run_analysis():
        with get_db() as db:
            pipeline = AnalysisPipeline(db)
            stats = pipeline.analyze_pending_tickets(limit=limit)
            logger.info(f"Manual analysis complete: {stats}")

    background_tasks.add_task(run_analysis)
    return {"message": "Analysis started", "limit": limit}


@router.get("/sync-status", response_model=List[SyncStatusResponse])
def get_sync_status(db: Session = Depends(get_db)):
    """Get sync status for all mailboxes."""
    sync_states = db.query(SyncState).all()

    return [
        SyncStatusResponse(
            mailbox_id=state.mailbox_id,
            last_sync_at=state.last_sync_at,
            total_tickets_synced=state.total_tickets_synced,
        )
        for state in sync_states
    ]
