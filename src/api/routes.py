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
            "extracted_entities": analysis.extracted_entities if analysis else {},
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


@router.get("/entities/products")
def get_product_insights(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get insights about mentioned products and their associated issues."""
    from sqlalchemy import func, cast, String
    from collections import Counter

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Get all analyses with extracted entities
    analyses = (
        db.query(TicketAnalysis, Ticket)
        .join(Ticket)
        .filter(Ticket.created_at >= cutoff_date)
        .filter(TicketAnalysis.extracted_entities.isnot(None))
        .all()
    )

    product_stats = {}
    for analysis, ticket in analyses:
        entities = analysis.extracted_entities or {}
        products = entities.get("products", [])

        for product in products:
            if product not in product_stats:
                product_stats[product] = {
                    "product": product,
                    "count": 0,
                    "categories": Counter(),
                    "sentiments": Counter(),
                    "avg_urgency": [],
                    "error_codes": Counter(),
                }

            product_stats[product]["count"] += 1
            product_stats[product]["categories"][analysis.category] += 1
            product_stats[product]["sentiments"][analysis.sentiment] += 1
            product_stats[product]["avg_urgency"].append(analysis.urgency_score or 0.5)

            # Track error codes associated with this product
            error_codes = entities.get("error_codes", [])
            for error in error_codes:
                product_stats[product]["error_codes"][error] += 1

    # Format results
    results = []
    for product, stats in product_stats.items():
        results.append({
            "product": product,
            "ticket_count": stats["count"],
            "avg_urgency": sum(stats["avg_urgency"]) / len(stats["avg_urgency"]) if stats["avg_urgency"] else 0,
            "top_categories": dict(stats["categories"].most_common(3)),
            "sentiment_distribution": dict(stats["sentiments"]),
            "common_errors": dict(stats["error_codes"].most_common(5)),
        })

    # Sort by ticket count
    results.sort(key=lambda x: x["ticket_count"], reverse=True)

    return {
        "period_days": days,
        "total_products": len(results),
        "products": results[:limit],
    }


@router.get("/entities/errors")
def get_error_insights(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get insights about error codes and their patterns."""
    from collections import Counter

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    analyses = (
        db.query(TicketAnalysis, Ticket)
        .join(Ticket)
        .filter(Ticket.created_at >= cutoff_date)
        .filter(TicketAnalysis.extracted_entities.isnot(None))
        .all()
    )

    error_stats = {}
    for analysis, ticket in analyses:
        entities = analysis.extracted_entities or {}
        errors = entities.get("error_codes", [])

        for error in errors:
            if error not in error_stats:
                error_stats[error] = {
                    "error_code": error,
                    "count": 0,
                    "categories": Counter(),
                    "products": Counter(),
                    "avg_urgency": [],
                }

            error_stats[error]["count"] += 1
            error_stats[error]["categories"][analysis.category] += 1
            error_stats[error]["avg_urgency"].append(analysis.urgency_score or 0.5)

            # Track products associated with this error
            products = entities.get("products", [])
            for product in products:
                error_stats[error]["products"][product] += 1

    results = []
    for error, stats in error_stats.items():
        results.append({
            "error_code": error,
            "ticket_count": stats["count"],
            "avg_urgency": sum(stats["avg_urgency"]) / len(stats["avg_urgency"]) if stats["avg_urgency"] else 0,
            "top_categories": dict(stats["categories"].most_common(3)),
            "affected_products": dict(stats["products"].most_common(5)),
        })

    results.sort(key=lambda x: x["ticket_count"], reverse=True)

    return {
        "period_days": days,
        "total_error_types": len(results),
        "errors": results[:limit],
    }


@router.get("/search/tickets")
def search_tickets_by_entity(
    product: Optional[str] = Query(default=None),
    error_code: Optional[str] = Query(default=None),
    complaint_keyword: Optional[str] = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Search tickets by extracted entities (products, errors, keywords)."""
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    query = (
        db.query(Ticket, TicketAnalysis)
        .join(TicketAnalysis)
        .filter(Ticket.created_at >= cutoff_date)
        .filter(TicketAnalysis.extracted_entities.isnot(None))
    )

    results = query.all()
    filtered_tickets = []

    for ticket, analysis in results:
        entities = analysis.extracted_entities or {}
        match = True

        if product:
            products = entities.get("products", [])
            if not any(product.lower() in p.lower() for p in products):
                match = False

        if error_code:
            errors = entities.get("error_codes", [])
            if not any(error_code.lower() in e.lower() for e in errors):
                match = False

        if complaint_keyword:
            keywords = entities.get("complaint_keywords", [])
            if not any(complaint_keyword.lower() in k.lower() for k in keywords):
                match = False

        if match:
            filtered_tickets.append({
                "id": ticket.id,
                "helpscout_id": ticket.helpscout_id,
                "number": ticket.number,
                "subject": ticket.subject,
                "status": ticket.status,
                "created_at": ticket.created_at,
                "category": analysis.category,
                "sentiment": analysis.sentiment,
                "urgency_score": analysis.urgency_score,
                "summary": analysis.summary,
                "extracted_entities": entities,
            })

    return {
        "filters": {
            "product": product,
            "error_code": error_code,
            "complaint_keyword": complaint_keyword,
            "days": days,
        },
        "total_matches": len(filtered_tickets),
        "tickets": filtered_tickets[:limit],
    }


@router.get("/entities/products/{product}/analysis")
def get_product_root_cause_analysis(
    product: str,
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """
    Get deep root cause analysis for a specific product.

    Returns pattern detection, hypotheses, and suggested actions.
    """
    from src.analyzer.root_cause import RootCauseAnalyzer

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Get all tickets mentioning this product
    query = (
        db.query(Ticket, TicketAnalysis)
        .join(TicketAnalysis)
        .filter(Ticket.created_at >= cutoff_date)
        .filter(TicketAnalysis.extracted_entities.isnot(None))
    )

    results = query.all()

    # Filter to tickets mentioning this product
    matching_tickets = []
    for ticket, analysis in results:
        entities = analysis.extracted_entities or {}
        products = entities.get("products", [])

        if any(product.lower() in p.lower() for p in products):
            matching_tickets.append({
                "ticket": {
                    "id": ticket.id,
                    "helpscout_id": ticket.helpscout_id,
                    "number": ticket.number,
                    "subject": ticket.subject,
                    "status": ticket.status,
                    "created_at": ticket.created_at,
                },
                "analysis": {
                    "category": analysis.category,
                    "sentiment": analysis.sentiment,
                    "urgency_score": analysis.urgency_score,
                    "summary": analysis.summary,
                },
                "entities": entities,
            })

    if not matching_tickets:
        raise HTTPException(
            status_code=404,
            detail=f"No tickets found mentioning product '{product}' in last {days} days"
        )

    # Run root cause analysis
    analyzer = RootCauseAnalyzer(matching_tickets)
    analysis_result = analyzer.analyze()

    # Calculate basic stats
    total_tickets = len(matching_tickets)
    sentiments = Counter(t["analysis"]["sentiment"] for t in matching_tickets)
    avg_urgency = sum(t["analysis"]["urgency_score"] for t in matching_tickets) / total_tickets

    # Get top categories
    categories = Counter(t["analysis"]["category"] for t in matching_tickets)

    # Get associated errors
    error_counter = Counter()
    for t in matching_tickets:
        for error in t["entities"].get("error_codes", []):
            error_counter[error] += 1

    return {
        "product": product,
        "period_days": days,
        "summary": {
            "total_tickets": total_tickets,
            "avg_urgency": round(avg_urgency, 2),
            "sentiment_distribution": dict(sentiments),
            "top_categories": dict(categories.most_common(3)),
            "common_errors": dict(error_counter.most_common(5)),
        },
        "root_cause_hints": analysis_result["root_cause_hints"],
        "suggested_actions": analysis_result["suggested_actions"],
        "temporal_analysis": analysis_result["temporal_analysis"],
        "sample_tickets": [
            {
                "id": t["ticket"]["id"],
                "number": t["ticket"]["number"],
                "subject": t["ticket"]["subject"],
                "summary": t["analysis"]["summary"],
                "urgency": t["analysis"]["urgency_score"],
            }
            for t in matching_tickets[:5]
        ],
    }


@router.get("/entities/errors/{error_code}/analysis")
def get_error_root_cause_analysis(
    error_code: str,
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """
    Get deep root cause analysis for a specific error code.

    Returns pattern detection, hypotheses, and suggested actions.
    """
    from src.analyzer.root_cause import RootCauseAnalyzer

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Get all tickets mentioning this error
    query = (
        db.query(Ticket, TicketAnalysis)
        .join(TicketAnalysis)
        .filter(Ticket.created_at >= cutoff_date)
        .filter(TicketAnalysis.extracted_entities.isnot(None))
    )

    results = query.all()

    # Filter to tickets mentioning this error
    matching_tickets = []
    for ticket, analysis in results:
        entities = analysis.extracted_entities or {}
        errors = entities.get("error_codes", [])

        if any(error_code.lower() in e.lower() for e in errors):
            matching_tickets.append({
                "ticket": {
                    "id": ticket.id,
                    "helpscout_id": ticket.helpscout_id,
                    "number": ticket.number,
                    "subject": ticket.subject,
                    "status": ticket.status,
                    "created_at": ticket.created_at,
                },
                "analysis": {
                    "category": analysis.category,
                    "sentiment": analysis.sentiment,
                    "urgency_score": analysis.urgency_score,
                    "summary": analysis.summary,
                },
                "entities": entities,
            })

    if not matching_tickets:
        raise HTTPException(
            status_code=404,
            detail=f"No tickets found with error code '{error_code}' in last {days} days"
        )

    # Run root cause analysis
    analyzer = RootCauseAnalyzer(matching_tickets)
    analysis_result = analyzer.analyze()

    # Calculate basic stats
    total_tickets = len(matching_tickets)
    sentiments = Counter(t["analysis"]["sentiment"] for t in matching_tickets)
    avg_urgency = sum(t["analysis"]["urgency_score"] for t in matching_tickets) / total_tickets

    # Get top categories
    categories = Counter(t["analysis"]["category"] for t in matching_tickets)

    # Get affected products
    product_counter = Counter()
    for t in matching_tickets:
        for prod in t["entities"].get("products", []):
            product_counter[prod] += 1

    return {
        "error_code": error_code,
        "period_days": days,
        "summary": {
            "total_tickets": total_tickets,
            "avg_urgency": round(avg_urgency, 2),
            "sentiment_distribution": dict(sentiments),
            "top_categories": dict(categories.most_common(3)),
            "affected_products": dict(product_counter.most_common(5)),
        },
        "root_cause_hints": analysis_result["root_cause_hints"],
        "suggested_actions": analysis_result["suggested_actions"],
        "temporal_analysis": analysis_result["temporal_analysis"],
        "sample_tickets": [
            {
                "id": t["ticket"]["id"],
                "number": t["ticket"]["number"],
                "subject": t["ticket"]["subject"],
                "summary": t["analysis"]["summary"],
                "urgency": t["analysis"]["urgency_score"],
            }
            for t in matching_tickets[:5]
        ],
    }
