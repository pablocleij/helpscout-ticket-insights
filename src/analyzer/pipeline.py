"""Ticket analysis pipeline."""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from src.models import Ticket, Thread, TicketAnalysis
from src.analyzer.llm_provider import get_llm_provider
from src.config import settings

logger = logging.getLogger(__name__)


class AnalysisPipeline:
    """Pipeline for analyzing tickets with LLM."""

    def __init__(self, db: Session):
        self.db = db
        self.llm_provider = get_llm_provider()

    def analyze_ticket(self, ticket_id: int) -> Optional[TicketAnalysis]:
        """Analyze a single ticket."""
        ticket = self.db.query(Ticket).filter_by(id=ticket_id).first()
        if not ticket:
            logger.warning(f"Ticket {ticket_id} not found")
            return None

        # Prepare ticket text
        ticket_text = self._prepare_ticket_text(ticket)

        # Analyze with LLM
        try:
            analysis_result = self.llm_provider.analyze_ticket(ticket_text)
        except Exception as e:
            logger.error(f"Error analyzing ticket {ticket_id}: {e}")
            return None

        # Check if analysis exists
        analysis = self.db.query(TicketAnalysis).filter_by(ticket_id=ticket_id).first()

        if analysis:
            # Update existing analysis
            analysis.category = analysis_result["category"]
            analysis.subcategory = analysis_result["subcategory"]
            analysis.pain_points = analysis_result["pain_points"]
            analysis.topics = analysis_result["topics"]
            analysis.sentiment = analysis_result["sentiment"]
            analysis.urgency_score = analysis_result["urgency_score"]
            analysis.suggested_tags = analysis_result["suggested_tags"]
            analysis.summary = analysis_result["summary"]
            analysis.analyzed_at = datetime.utcnow()
            analysis.llm_provider = settings.llm_provider
            analysis.llm_model = settings.openai_model
            analysis.raw_response = analysis_result.get("raw_response")
        else:
            # Create new analysis
            analysis = TicketAnalysis(
                ticket_id=ticket_id,
                category=analysis_result["category"],
                subcategory=analysis_result["subcategory"],
                pain_points=analysis_result["pain_points"],
                topics=analysis_result["topics"],
                sentiment=analysis_result["sentiment"],
                urgency_score=analysis_result["urgency_score"],
                suggested_tags=analysis_result["suggested_tags"],
                summary=analysis_result["summary"],
                analyzed_at=datetime.utcnow(),
                llm_provider=settings.llm_provider,
                llm_model=settings.openai_model,
                raw_response=analysis_result.get("raw_response"),
            )
            self.db.add(analysis)

        self.db.commit()
        logger.info(f"Analyzed ticket {ticket_id}")
        return analysis

    def analyze_pending_tickets(self, limit: Optional[int] = None) -> Dict[str, int]:
        """Analyze tickets that don't have analysis yet."""
        # Find tickets without analysis
        query = (
            self.db.query(Ticket)
            .outerjoin(TicketAnalysis)
            .filter(TicketAnalysis.id.is_(None))
            .order_by(Ticket.created_at.desc())
        )

        if limit:
            query = query.limit(limit)

        tickets = query.all()
        stats = {"total": len(tickets), "success": 0, "failed": 0}

        for ticket in tickets:
            try:
                self.analyze_ticket(ticket.id)
                stats["success"] += 1
            except Exception as e:
                logger.error(f"Failed to analyze ticket {ticket.id}: {e}")
                stats["failed"] += 1

        return stats

    def reanalyze_recent_tickets(self, days: int = 7) -> Dict[str, int]:
        """Re-analyze recent tickets."""
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)
        tickets = self.db.query(Ticket).filter(Ticket.created_at >= cutoff_date).all()

        stats = {"total": len(tickets), "success": 0, "failed": 0}

        for ticket in tickets:
            try:
                self.analyze_ticket(ticket.id)
                stats["success"] += 1
            except Exception as e:
                logger.error(f"Failed to analyze ticket {ticket.id}: {e}")
                stats["failed"] += 1

        return stats

    def _prepare_ticket_text(self, ticket: Ticket) -> str:
        """Prepare ticket text for analysis."""
        parts = []

        # Subject
        if ticket.subject:
            parts.append(f"Subject: {ticket.subject}")

        # Customer info
        if ticket.customer_name:
            parts.append(f"Customer: {ticket.customer_name}")

        # Status and metadata
        parts.append(f"Status: {ticket.status}")
        if ticket.tags:
            parts.append(f"Tags: {', '.join(ticket.tags)}")

        # Threads (messages)
        threads = (
            self.db.query(Thread)
            .filter_by(ticket_id=ticket.id)
            .order_by(Thread.created_at)
            .all()
        )

        if threads:
            parts.append("\n--- Conversation ---")
            for thread in threads:
                role = "Customer" if thread.is_customer else "Support"
                if thread.body_plain:
                    parts.append(f"\n{role}: {thread.body_plain[:1000]}")  # Limit length

        return "\n".join(parts)
