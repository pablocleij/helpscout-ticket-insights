"""Statistical analysis on LLM-labeled ticket data."""

import logging
from typing import Dict, Any, List, Optional
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from src.models import Ticket, TicketAnalysis
from src.config import settings

logger = logging.getLogger(__name__)


class StatisticalAnalyzer:
    """Run statistical analysis on LLM-categorized tickets."""

    def __init__(self, db: Session):
        self.db = db

    def analyze_categories(self, days: Optional[int] = None) -> Dict[str, Any]:
        """
        Statistical analysis of LLM-assigned categories.

        This runs AFTER LLM labeling and provides:
        - Category distribution
        - Subcategory breakdown per category
        - Cross-analysis with other dimensions (sentiment, urgency)
        - Trends over time
        """
        days = days or settings.analysis_lookback_days
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Get all analyzed tickets in period
        results = (
            self.db.query(Ticket, TicketAnalysis)
            .join(TicketAnalysis)
            .filter(Ticket.created_at >= cutoff_date)
            .all()
        )

        if not results:
            logger.warning("No analyzed tickets found for statistical analysis")
            return {"total_analyzed": 0}

        total = len(results)
        logger.info(f"Running statistical analysis on {total} LLM-labeled tickets")

        # 1. Category distribution
        category_counts = Counter()
        subcategory_map = defaultdict(Counter)  # category -> {subcategory: count}
        category_tickets = defaultdict(list)  # category -> [ticket_ids]

        # 2. Category × Sentiment cross-analysis
        category_sentiment = defaultdict(Counter)  # category -> {sentiment: count}

        # 3. Category × Urgency analysis
        category_urgency = defaultdict(list)  # category -> [urgency_scores]

        # 4. Time series for trending
        category_by_date = defaultdict(lambda: defaultdict(int))  # date -> {category: count}

        for ticket, analysis in results:
            category = analysis.category or "Uncategorized"
            subcategory = analysis.subcategory or "General"

            # Count categories
            category_counts[category] += 1
            subcategory_map[category][subcategory] += 1
            category_tickets[category].append(ticket.id)

            # Cross-analysis
            if analysis.sentiment:
                category_sentiment[category][analysis.sentiment] += 1

            if analysis.urgency_score is not None:
                category_urgency[category].append(analysis.urgency_score)

            # Time series
            date_key = ticket.created_at.date().isoformat()
            category_by_date[date_key][category] += 1

        # Build results
        return {
            "total_analyzed": total,
            "analysis_period_days": days,
            "categories": self._format_category_distribution(
                category_counts, subcategory_map, category_tickets, total
            ),
            "category_sentiment_analysis": self._format_sentiment_analysis(
                category_sentiment, category_counts
            ),
            "category_urgency_analysis": self._format_urgency_analysis(
                category_urgency, category_counts
            ),
            "trending": self._format_trending(category_by_date),
        }

    def _format_category_distribution(
        self,
        category_counts: Counter,
        subcategory_map: Dict,
        category_tickets: Dict,
        total: int,
    ) -> List[Dict]:
        """Format category distribution with subcategories."""
        categories = []

        for category, count in category_counts.most_common():
            percentage = (count / total) * 100

            # Get subcategories for this category
            subcats = [
                {
                    "name": subcat,
                    "count": subcount,
                    "percentage": (subcount / count) * 100,
                }
                for subcat, subcount in subcategory_map[category].most_common()
            ]

            categories.append(
                {
                    "category": category,
                    "count": count,
                    "percentage": round(percentage, 1),
                    "ticket_ids": category_tickets[category][:10],  # Sample
                    "subcategories": subcats,
                }
            )

        return categories

    def _format_sentiment_analysis(
        self, category_sentiment: Dict, category_counts: Counter
    ) -> Dict[str, Dict]:
        """Analyze sentiment distribution per category."""
        result = {}

        for category in category_counts.keys():
            sentiments = category_sentiment[category]
            total_with_sentiment = sum(sentiments.values())

            if total_with_sentiment > 0:
                result[category] = {
                    sentiment: {
                        "count": count,
                        "percentage": round((count / total_with_sentiment) * 100, 1),
                    }
                    for sentiment, count in sentiments.items()
                }

        return result

    def _format_urgency_analysis(
        self, category_urgency: Dict, category_counts: Counter
    ) -> Dict[str, Dict]:
        """Analyze urgency scores per category."""
        result = {}

        for category in category_counts.keys():
            urgency_scores = category_urgency[category]

            if urgency_scores:
                avg_urgency = sum(urgency_scores) / len(urgency_scores)
                max_urgency = max(urgency_scores)
                min_urgency = min(urgency_scores)

                result[category] = {
                    "average": round(avg_urgency, 2),
                    "max": round(max_urgency, 2),
                    "min": round(min_urgency, 2),
                    "count": len(urgency_scores),
                }

        return result

    def _format_trending(self, category_by_date: Dict) -> Dict[str, Any]:
        """Format trending data."""
        # Get last 7 days
        dates = sorted(category_by_date.keys())[-7:]

        if not dates:
            return {"dates": [], "series": {}}

        # Build series data per category
        all_categories = set()
        for date in dates:
            all_categories.update(category_by_date[date].keys())

        series = {}
        for category in all_categories:
            series[category] = [category_by_date[date].get(category, 0) for date in dates]

        return {"dates": dates, "series": series}

    def get_category_breakdown(self, category: str, days: Optional[int] = None) -> Dict[str, Any]:
        """Get detailed breakdown for a specific category."""
        days = days or settings.analysis_lookback_days
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Get tickets in this category
        results = (
            self.db.query(Ticket, TicketAnalysis)
            .join(TicketAnalysis)
            .filter(
                and_(
                    Ticket.created_at >= cutoff_date, TicketAnalysis.category == category
                )
            )
            .all()
        )

        if not results:
            return {"category": category, "count": 0}

        # Subcategory distribution
        subcategories = Counter(
            analysis.subcategory for _, analysis in results if analysis.subcategory
        )

        # Top pain points in this category
        pain_points = []
        for _, analysis in results:
            if analysis.pain_points:
                pain_points.extend(analysis.pain_points)
        top_pain_points = Counter(pain_points).most_common(10)

        # Sentiment distribution
        sentiments = Counter(
            analysis.sentiment for _, analysis in results if analysis.sentiment
        )

        # Average urgency
        urgencies = [
            analysis.urgency_score
            for _, analysis in results
            if analysis.urgency_score is not None
        ]
        avg_urgency = sum(urgencies) / len(urgencies) if urgencies else 0

        return {
            "category": category,
            "count": len(results),
            "subcategories": [
                {"name": name, "count": count} for name, count in subcategories.most_common()
            ],
            "top_pain_points": [
                {"pain_point": pp, "count": count} for pp, count in top_pain_points
            ],
            "sentiment_distribution": dict(sentiments),
            "average_urgency": round(avg_urgency, 2),
        }
