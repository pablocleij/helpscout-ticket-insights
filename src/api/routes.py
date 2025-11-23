"""API routes for insights and tickets."""

import logging
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.database import get_db
from src.models import Ticket, TicketAnalysis
from src.analyzer.pipeline import AnalysisPipeline
from src.analyzer.stats_analyzer import StatisticalAnalyzer
from src.syncer.helpscout import HelpScoutSyncer

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    from src.database import engine
    from sqlalchemy import text

    try:
        # Check database connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = f"unhealthy: {str(e)}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "timestamp": datetime.utcnow().isoformat(),
    }


# Response models
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
    category: Optional[str] = None
    subcategory: Optional[str] = None


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
            category=analysis.category if analysis else None,
            subcategory=analysis.subcategory if analysis else None,
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
            "category": analysis.category if analysis else None,
            "subcategory": analysis.subcategory if analysis else None,
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


@router.get("/categories/stats")
def get_category_statistics(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """
    Get statistical analysis of LLM-assigned categories.

    This runs AFTER LLM labeling and provides distribution analysis,
    cross-analysis with sentiment/urgency, and trending data.
    """
    analyzer = StatisticalAnalyzer(db)
    stats = analyzer.analyze_categories(days=days)

    return stats


@router.get("/categories/{category}")
def get_category_breakdown(
    category: str,
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """Get detailed breakdown for a specific LLM category."""
    analyzer = StatisticalAnalyzer(db)
    breakdown = analyzer.get_category_breakdown(category, days=days)

    if breakdown.get("count", 0) == 0:
        raise HTTPException(status_code=404, detail=f"No tickets found in category '{category}'")

    return breakdown
