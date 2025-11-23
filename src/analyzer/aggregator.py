"""Aggregate insights across tickets."""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import Counter

from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from src.models import Ticket, TicketAnalysis, AggregatedInsight
from src.config import settings

logger = logging.getLogger(__name__)


class InsightAggregator:
    """Aggregates insights across multiple tickets."""

    def __init__(self, db: Session):
        self.db = db

    def aggregate_insights(
        self,
        days: Optional[int] = None,
        mailbox_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Aggregate insights for a time period."""
        days = days or settings.analysis_lookback_days
        period_end = datetime.utcnow()
        period_start = period_end - timedelta(days=days)

        logger.info(f"Aggregating insights from {period_start} to {period_end}")

        # Query tickets with analysis in the period
        query = (
            self.db.query(Ticket, TicketAnalysis)
            .join(TicketAnalysis)
            .filter(Ticket.created_at >= period_start)
            .filter(Ticket.created_at <= period_end)
        )

        if mailbox_id:
            query = query.filter(Ticket.mailbox_id == mailbox_id)

        results = query.all()

        if not results:
            logger.warning("No analyzed tickets found for aggregation")
            return {"total_tickets": 0}

        # Aggregate data
        pain_points = []
        topics = []
        sentiments = []
        urgency_scores = []

        for ticket, analysis in results:
            if analysis.pain_points:
                pain_points.extend(analysis.pain_points)
            if analysis.topics:
                topics.extend(analysis.topics)
            if analysis.sentiment:
                sentiments.append(analysis.sentiment)
            if analysis.urgency_score is not None:
                urgency_scores.append(analysis.urgency_score)

        # Calculate top pain points
        pain_point_counter = Counter(pain_points)
        top_pain_points = [
            {"pain_point": pp, "count": count, "percentage": (count / len(results)) * 100}
            for pp, count in pain_point_counter.most_common(settings.top_insights_limit)
        ]

        # Calculate top topics
        topic_counter = Counter(topics)
        top_topics = [
            {"topic": topic, "count": count, "percentage": (count / len(results)) * 100}
            for topic, count in topic_counter.most_common(settings.top_insights_limit)
        ]

        # Calculate sentiment distribution
        sentiment_counter = Counter(sentiments)
        sentiment_distribution = {
            sentiment: count for sentiment, count in sentiment_counter.items()
        }

        # Calculate average urgency
        avg_urgency = sum(urgency_scores) / len(urgency_scores) if urgency_scores else 0

        # Save aggregated insight
        insight = AggregatedInsight(
            period_start=period_start,
            period_end=period_end,
            mailbox_id=mailbox_id,
            top_pain_points=top_pain_points,
            top_topics=top_topics,
            sentiment_distribution=sentiment_distribution,
            average_urgency=avg_urgency,
            total_tickets_analyzed=len(results),
        )

        self.db.add(insight)
        self.db.commit()

        logger.info(f"Aggregated insights for {len(results)} tickets")

        return {
            "total_tickets": len(results),
            "top_pain_points": top_pain_points,
            "top_topics": top_topics,
            "sentiment_distribution": sentiment_distribution,
            "average_urgency": avg_urgency,
        }

    def get_latest_insights(
        self, mailbox_id: Optional[int] = None
    ) -> Optional[AggregatedInsight]:
        """Get the most recent aggregated insights."""
        query = self.db.query(AggregatedInsight).order_by(
            AggregatedInsight.created_at.desc()
        )

        if mailbox_id:
            query = query.filter(AggregatedInsight.mailbox_id == mailbox_id)

        return query.first()

    def get_pain_point_trends(
        self, pain_point: str, days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get trend data for a specific pain point over time."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Query tickets with this pain point
        results = (
            self.db.query(
                func.date(Ticket.created_at).label("date"),
                func.count(Ticket.id).label("count"),
            )
            .join(TicketAnalysis)
            .filter(Ticket.created_at >= start_date)
            .filter(TicketAnalysis.pain_points.contains([pain_point]))
            .group_by(func.date(Ticket.created_at))
            .order_by(func.date(Ticket.created_at))
            .all()
        )

        return [{"date": str(row.date), "count": row.count} for row in results]
