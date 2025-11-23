"""Automatic category extraction using statistical analysis."""

import logging
import re
from typing import List, Dict, Any, Set, Tuple
from collections import Counter, defaultdict
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func

from src.models import Ticket, Thread, TicketAnalysis
from src.config import settings

logger = logging.getLogger(__name__)


class AutoCategorizer:
    """Automatically extract categories and subcategories from tickets using statistical analysis."""

    # Common support categories (can be customized per domain)
    CATEGORY_KEYWORDS = {
        "billing": ["bill", "invoice", "payment", "charge", "refund", "subscription", "price", "cost"],
        "technical": ["error", "bug", "crash", "broken", "not working", "issue", "problem", "fail"],
        "account": ["login", "password", "access", "account", "sign in", "authentication", "locked"],
        "feature_request": ["feature", "request", "suggestion", "add", "new", "would like", "wish"],
        "integration": ["integration", "api", "connect", "sync", "webhook", "third-party", "plugin"],
        "performance": ["slow", "performance", "speed", "loading", "timeout", "lag", "delay"],
        "data": ["data", "export", "import", "migration", "backup", "restore", "transfer"],
        "ui_ux": ["ui", "ux", "interface", "design", "layout", "navigation", "confusing", "unclear"],
        "mobile": ["mobile", "ios", "android", "app", "phone", "tablet"],
        "security": ["security", "privacy", "gdpr", "encryption", "safe", "protection"],
    }

    def __init__(self, db: Session):
        self.db = db

    def extract_categories(self, days: int = 30) -> Dict[str, Any]:
        """Extract categories from recent tickets using multiple methods."""
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Get tickets with their threads
        tickets = (
            self.db.query(Ticket)
            .filter(Ticket.created_at >= cutoff_date)
            .limit(1000)  # Limit for performance
            .all()
        )

        if not tickets:
            return {"categories": [], "subcategories": {}}

        # Method 1: Keyword-based categorization
        keyword_categories = self._extract_keyword_categories(tickets)

        # Method 2: Tag-based clustering
        tag_clusters = self._extract_tag_clusters(tickets)

        # Method 3: Subject line analysis
        subject_patterns = self._extract_subject_patterns(tickets)

        # Method 4: Extract from existing LLM analysis
        llm_topics = self._extract_from_llm_analysis(tickets)

        # Combine all methods
        combined_categories = self._merge_categories(
            keyword_categories, tag_clusters, subject_patterns, llm_topics
        )

        return combined_categories

    def _extract_keyword_categories(self, tickets: List[Ticket]) -> Dict[str, List[Dict]]:
        """Categorize tickets based on keyword matching."""
        category_counts = defaultdict(list)

        for ticket in tickets:
            # Get ticket text
            text = self._get_ticket_text(ticket)
            text_lower = text.lower()

            # Check each category
            for category, keywords in self.CATEGORY_KEYWORDS.items():
                matches = sum(1 for keyword in keywords if keyword in text_lower)
                if matches > 0:
                    category_counts[category].append(
                        {"ticket_id": ticket.id, "match_count": matches}
                    )

        # Filter by minimum occurrences
        filtered = {
            cat: tickets
            for cat, tickets in category_counts.items()
            if len(tickets) >= settings.category_min_occurrences
        }

        return filtered

    def _extract_tag_clusters(self, tickets: List[Ticket]) -> Dict[str, int]:
        """Extract categories from HelpScout tags."""
        all_tags = []
        for ticket in tickets:
            if ticket.tags:
                all_tags.extend(ticket.tags)

        # Count tag frequencies
        tag_counter = Counter(all_tags)

        # Filter by minimum occurrences
        return {
            tag: count
            for tag, count in tag_counter.items()
            if count >= settings.category_min_occurrences
        }

    def _extract_subject_patterns(self, tickets: List[Ticket]) -> Dict[str, List[str]]:
        """Extract common patterns from subject lines."""
        # Extract first 2-3 words from subjects
        subject_prefixes = []

        for ticket in tickets:
            if ticket.subject:
                # Clean and normalize
                subject = ticket.subject.strip()
                words = re.findall(r"\b\w+\b", subject.lower())
                if len(words) >= 2:
                    prefix = " ".join(words[:2])
                    subject_prefixes.append(prefix)

        # Count frequencies
        prefix_counter = Counter(subject_prefixes)

        # Group similar prefixes
        patterns = defaultdict(list)
        for prefix, count in prefix_counter.items():
            if count >= settings.category_min_occurrences:
                # Use first word as category
                category = prefix.split()[0]
                patterns[category].append({"pattern": prefix, "count": count})

        return dict(patterns)

    def _extract_from_llm_analysis(self, tickets: List[Ticket]) -> Dict[str, List[str]]:
        """Extract topics from existing LLM analysis."""
        all_topics = []
        all_pain_points = []

        for ticket in tickets:
            analysis = self.db.query(TicketAnalysis).filter_by(ticket_id=ticket.id).first()
            if analysis:
                if analysis.topics:
                    all_topics.extend(analysis.topics)
                if analysis.pain_points:
                    all_pain_points.extend(analysis.pain_points)

        topic_counter = Counter(all_topics)
        pain_counter = Counter(all_pain_points)

        return {
            "topics": [
                {"topic": topic, "count": count}
                for topic, count in topic_counter.most_common(20)
                if count >= settings.category_min_occurrences
            ],
            "pain_points": [
                {"pain_point": pp, "count": count}
                for pp, count in pain_counter.most_common(20)
                if count >= settings.category_min_occurrences
            ],
        }

    def _merge_categories(
        self,
        keyword_cats: Dict,
        tag_clusters: Dict,
        subject_patterns: Dict,
        llm_topics: Dict,
    ) -> Dict[str, Any]:
        """Merge categories from all extraction methods."""
        result = {
            "keyword_categories": {
                cat: {"count": len(tickets), "confidence": "keyword_match"}
                for cat, tickets in keyword_cats.items()
            },
            "tag_categories": {
                tag: {"count": count, "confidence": "helpscout_tag"}
                for tag, count in sorted(
                    tag_clusters.items(), key=lambda x: x[1], reverse=True
                )[:20]
            },
            "subject_patterns": subject_patterns,
            "llm_extracted": llm_topics,
        }

        # Create hierarchical structure
        # Main categories from keywords, subcategories from tags and LLM
        hierarchical = {}
        for main_cat in keyword_cats.keys():
            hierarchical[main_cat] = {
                "count": len(keyword_cats[main_cat]),
                "subcategories": self._find_subcategories(main_cat, tag_clusters, llm_topics),
            }

        result["hierarchical"] = hierarchical

        return result

    def _find_subcategories(
        self, main_category: str, tags: Dict, llm_topics: Dict
    ) -> List[str]:
        """Find relevant subcategories for a main category."""
        subcats = []

        # Check if any tags are related to this category
        main_keywords = self.CATEGORY_KEYWORDS.get(main_category, [])
        for tag in tags.keys():
            tag_lower = tag.lower()
            if any(keyword in tag_lower for keyword in main_keywords):
                subcats.append(tag)

        # Check LLM topics
        for topic_info in llm_topics.get("topics", []):
            topic = topic_info.get("topic", "").lower()
            if any(keyword in topic for keyword in main_keywords):
                subcats.append(topic_info["topic"])

        return list(set(subcats))[:5]  # Limit subcategories

    def _get_ticket_text(self, ticket: Ticket) -> str:
        """Get full text content of a ticket for analysis."""
        parts = []

        if ticket.subject:
            parts.append(ticket.subject)

        # Get threads
        threads = self.db.query(Thread).filter_by(ticket_id=ticket.id).limit(5).all()
        for thread in threads:
            if thread.body_plain:
                parts.append(thread.body_plain[:500])  # Limit length

        return " ".join(parts)

    def get_category_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get a clean summary of categories for display."""
        categories = self.extract_categories(days=days)

        # Flatten for easy consumption
        summary = {
            "main_categories": [],
            "top_tags": [],
            "common_patterns": [],
        }

        # Main categories from keyword analysis
        keyword_cats = categories.get("keyword_categories", {})
        for cat, info in sorted(
            keyword_cats.items(), key=lambda x: x[1]["count"], reverse=True
        ):
            summary["main_categories"].append({"category": cat, "count": info["count"]})

        # Top tags
        tag_cats = categories.get("tag_categories", {})
        for tag, info in list(tag_cats.items())[:10]:
            summary["top_tags"].append({"tag": tag, "count": info["count"]})

        # Common subject patterns
        patterns = categories.get("subject_patterns", {})
        for cat, pattern_list in list(patterns.items())[:5]:
            summary["common_patterns"].append(
                {"category": cat, "patterns": pattern_list[:3]}  # Top 3 patterns
            )

        return summary
