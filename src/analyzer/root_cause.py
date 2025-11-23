"""Root cause analysis for ticket patterns."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from collections import Counter
import re

logger = logging.getLogger(__name__)


class RootCauseAnalyzer:
    """Analyze patterns in tickets to suggest root causes and actions."""

    def __init__(self, tickets_data: List[Dict[str, Any]]):
        """
        Initialize with ticket data.

        Args:
            tickets_data: List of dicts with keys: ticket, analysis, entities
        """
        self.tickets = tickets_data
        self.total_tickets = len(tickets_data)

    def analyze(self) -> Dict[str, Any]:
        """Run full root cause analysis."""
        return {
            "root_cause_hints": self._detect_patterns(),
            "suggested_actions": self._generate_actions(),
            "temporal_analysis": self._analyze_timeline(),
        }

    def _detect_patterns(self) -> List[Dict[str, Any]]:
        """Detect patterns that suggest root causes."""
        patterns = []

        # Pattern 1: Date clustering (release/update issues)
        date_pattern = self._detect_date_clustering()
        if date_pattern:
            patterns.append(date_pattern)

        # Pattern 2: Error co-occurrence
        error_pattern = self._detect_error_cooccurrence()
        if error_pattern:
            patterns.append(error_pattern)

        # Pattern 3: Complaint keyword clustering
        complaint_pattern = self._detect_complaint_clustering()
        if complaint_pattern:
            patterns.append(complaint_pattern)

        # Pattern 4: URL/domain patterns
        url_pattern = self._detect_url_patterns()
        if url_pattern:
            patterns.append(url_pattern)

        # Sort by confidence
        patterns.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        return patterns

    def _detect_date_clustering(self) -> Optional[Dict[str, Any]]:
        """Detect if many tickets mention dates around the same time."""
        date_mentions = []
        tickets_with_dates = []

        for item in self.tickets:
            entities = item.get("entities", {})
            dates = entities.get("dates", [])

            if dates:
                tickets_with_dates.append(item)
                for date_str in dates:
                    # Extract common date patterns
                    parsed_date = self._parse_date_mention(date_str)
                    if parsed_date:
                        date_mentions.append(parsed_date)

        if not date_mentions or len(tickets_with_dates) < 3:
            return None

        # Find most common date
        date_counter = Counter(date_mentions)
        most_common_date, count = date_counter.most_common(1)[0]

        # Calculate confidence based on % of tickets mentioning this date
        confidence = min(count / self.total_tickets * 2, 0.95)  # Cap at 95%

        if confidence < 0.2:  # Less than 20% mention this date
            return None

        # Get example mentions
        example_mentions = []
        for item in tickets_with_dates[:5]:
            entities = item.get("entities", {})
            dates = entities.get("dates", [])
            example_mentions.extend(dates[:2])

        return {
            "pattern": "date_clustering",
            "confidence": round(confidence, 2),
            "evidence": {
                "clustered_date": most_common_date,
                "tickets_mentioning_date": count,
                "total_tickets": self.total_tickets,
                "percentage": round(count / self.total_tickets * 100, 1),
                "example_mentions": list(set(example_mentions))[:5],
            },
            "hypothesis": f"Issues started around {most_common_date} - potential release, update, or external event trigger"
        }

    def _detect_error_cooccurrence(self) -> Optional[Dict[str, Any]]:
        """Detect if certain errors frequently appear together."""
        error_pairs = Counter()
        all_errors = Counter()

        for item in self.tickets:
            entities = item.get("entities", {})
            errors = entities.get("error_codes", [])

            for error in errors:
                all_errors[error] += 1

            # Track pairs
            if len(errors) >= 2:
                for i, err1 in enumerate(errors):
                    for err2 in errors[i+1:]:
                        pair = tuple(sorted([err1, err2]))
                        error_pairs[pair] += 1

        if not error_pairs:
            return None

        # Find most common pair
        most_common_pair, pair_count = error_pairs.most_common(1)[0]

        # Calculate confidence based on co-occurrence rate
        # If pair appears in >30% of tickets with errors, it's significant
        tickets_with_errors = sum(1 for item in self.tickets if item.get("entities", {}).get("error_codes"))
        if tickets_with_errors == 0:
            return None

        confidence = min(pair_count / tickets_with_errors * 1.5, 0.92)

        if confidence < 0.25:
            return None

        return {
            "pattern": "error_cooccurrence",
            "confidence": round(confidence, 2),
            "evidence": {
                "error_pair": list(most_common_pair),
                "cooccurrence_count": pair_count,
                "tickets_with_errors": tickets_with_errors,
                "individual_counts": {
                    most_common_pair[0]: all_errors[most_common_pair[0]],
                    most_common_pair[1]: all_errors[most_common_pair[1]],
                }
            },
            "hypothesis": f"Errors '{most_common_pair[0]}' and '{most_common_pair[1]}' appear together frequently - likely related to same underlying issue"
        }

    def _detect_complaint_clustering(self) -> Optional[Dict[str, Any]]:
        """Detect if specific complaints dominate."""
        complaint_counter = Counter()

        for item in self.tickets:
            entities = item.get("entities", {})
            keywords = entities.get("complaint_keywords", [])
            for keyword in keywords:
                complaint_counter[keyword] += 1

        if not complaint_counter:
            return None

        # Get top complaints
        top_complaints = complaint_counter.most_common(3)
        top_complaint, top_count = top_complaints[0]

        # Confidence based on dominance
        confidence = min(top_count / self.total_tickets * 1.8, 0.88)

        if confidence < 0.3:
            return None

        return {
            "pattern": "complaint_clustering",
            "confidence": round(confidence, 2),
            "evidence": {
                "dominant_complaint": top_complaint,
                "count": top_count,
                "percentage": round(top_count / self.total_tickets * 100, 1),
                "top_3_complaints": dict(top_complaints),
            },
            "hypothesis": f"'{top_complaint}' is the dominant complaint ({round(top_count / self.total_tickets * 100, 1)}% of tickets) - primary symptom of underlying issue"
        }

    def _detect_url_patterns(self) -> Optional[Dict[str, Any]]:
        """Detect if URLs/domains are frequently mentioned."""
        url_counter = Counter()

        for item in self.tickets:
            entities = item.get("entities", {})
            urls = entities.get("urls", [])
            for url in urls:
                # Extract domain
                domain = self._extract_domain(url)
                if domain:
                    url_counter[domain] += 1

        if not url_counter:
            return None

        top_domain, count = url_counter.most_common(1)[0]
        confidence = min(count / self.total_tickets * 2.5, 0.80)

        if confidence < 0.2 or count < 2:
            return None

        return {
            "pattern": "url_domain_pattern",
            "confidence": round(confidence, 2),
            "evidence": {
                "domain": top_domain,
                "mention_count": count,
                "percentage": round(count / self.total_tickets * 100, 1),
            },
            "hypothesis": f"Multiple tickets reference '{top_domain}' - possible integration or external service issue"
        }

    def _generate_actions(self) -> List[Dict[str, Any]]:
        """Generate prioritized action items based on patterns."""
        actions = []
        patterns = self._detect_patterns()

        # Collect all unique entities
        all_errors = Counter()
        all_products = Counter()
        all_complaints = Counter()
        high_urgency_count = 0
        negative_sentiment_count = 0

        for item in self.tickets:
            analysis = item.get("analysis", {})
            entities = item.get("entities", {})

            if analysis.get("urgency_score", 0) >= 0.7:
                high_urgency_count += 1
            if analysis.get("sentiment") == "negative":
                negative_sentiment_count += 1

            for error in entities.get("error_codes", []):
                all_errors[error] += 1
            for product in entities.get("products", []):
                all_products[product] += 1
            for complaint in entities.get("complaint_keywords", []):
                all_complaints[complaint] += 1

        priority = 1

        # Action 1: Address date-clustered issues (likely release problems)
        date_pattern = next((p for p in patterns if p["pattern"] == "date_clustering"), None)
        if date_pattern and date_pattern["confidence"] > 0.5:
            clustered_date = date_pattern["evidence"]["clustered_date"]
            count = date_pattern["evidence"]["tickets_mentioning_date"]

            actions.append({
                "priority": priority,
                "action": f"Investigate changes/releases around {clustered_date}",
                "reasoning": f"{date_pattern['confidence']*100:.0f}% confidence that issues started around {clustered_date}",
                "estimated_impact": f"Could resolve {count}/{self.total_tickets} tickets",
                "next_steps": [
                    "Check deployment logs for releases near this date",
                    "Review code changes merged around this time",
                    "Consider rollback if recent release"
                ]
            })
            priority += 1

        # Action 2: Fix error co-occurrences
        error_pattern = next((p for p in patterns if p["pattern"] == "error_cooccurrence"), None)
        if error_pattern and error_pattern["confidence"] > 0.4:
            errors = error_pattern["evidence"]["error_pair"]
            count = error_pattern["evidence"]["cooccurrence_count"]

            actions.append({
                "priority": priority,
                "action": f"Investigate connection between '{errors[0]}' and '{errors[1]}'",
                "reasoning": f"These errors co-occur in {count} tickets - likely same root cause",
                "estimated_impact": f"Could resolve {count}/{self.total_tickets} tickets",
                "next_steps": [
                    f"Search logs for '{errors[0]}' AND '{errors[1]}'",
                    "Check if these errors are in same code path",
                    "Review error handling in affected module"
                ]
            })
            priority += 1

        # Action 3: Address top complaint
        if all_complaints:
            top_complaint, complaint_count = all_complaints.most_common(1)[0]
            if complaint_count >= max(3, self.total_tickets * 0.3):  # At least 30% or 3 tickets
                actions.append({
                    "priority": priority,
                    "action": f"Fix '{top_complaint}' issue",
                    "reasoning": f"Most common complaint ({complaint_count} tickets, {complaint_count/self.total_tickets*100:.0f}%)",
                    "estimated_impact": f"Could improve {complaint_count}/{self.total_tickets} tickets",
                    "next_steps": [
                        f"Search tickets with complaint_keyword='{top_complaint}'",
                        "Identify common factors in these tickets",
                        "Assign to relevant team based on category"
                    ]
                })
                priority += 1

        # Action 4: Notify customers (if high impact)
        if high_urgency_count >= max(3, self.total_tickets * 0.4):
            actions.append({
                "priority": priority,
                "action": "Proactive customer communication",
                "reasoning": f"{high_urgency_count} high-urgency tickets indicate significant customer impact",
                "estimated_impact": f"{negative_sentiment_count} customers with negative sentiment need reassurance",
                "next_steps": [
                    "Draft status update for affected customers",
                    "Set up dedicated support channel",
                    "Create FAQ for common questions"
                ]
            })
            priority += 1

        # Action 5: Investigation query for top product
        if all_products:
            top_product, product_count = all_products.most_common(1)[0]
            if product_count >= max(2, self.total_tickets * 0.5):
                actions.append({
                    "priority": priority,
                    "action": f"Deep dive into '{top_product}' issues",
                    "reasoning": f"{product_count} tickets mention this product",
                    "query": f"/api/search/tickets?product={top_product}",
                    "next_steps": [
                        f"Run: curl 'http://localhost:8000/api/search/tickets?product={top_product}'",
                        "Review all tickets for common patterns",
                        "Check recent changes to this product"
                    ]
                })

        return actions[:5]  # Return top 5 actions

    def _analyze_timeline(self) -> Dict[str, Any]:
        """Analyze when tickets occurred."""
        # Group tickets by date
        tickets_by_date = Counter()

        for item in self.tickets:
            ticket = item.get("ticket", {})
            created_at = ticket.get("created_at")
            if created_at:
                if isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                date_key = created_at.date().isoformat()
                tickets_by_date[date_key] += 1

        if not tickets_by_date:
            return {}

        # Find peak day
        peak_date, peak_count = tickets_by_date.most_common(1)[0]

        # Calculate if there's a spike
        avg_per_day = sum(tickets_by_date.values()) / len(tickets_by_date)
        spike_ratio = peak_count / avg_per_day if avg_per_day > 0 else 1

        return {
            "peak_date": peak_date,
            "peak_ticket_count": peak_count,
            "average_per_day": round(avg_per_day, 1),
            "spike_ratio": round(spike_ratio, 2),
            "is_spike": spike_ratio > 2.0,
            "timeline": dict(sorted(tickets_by_date.items())[-7:])  # Last 7 days
        }

    def _parse_date_mention(self, date_str: str) -> Optional[str]:
        """Parse date mentions into normalized format."""
        date_str = date_str.lower().strip()

        # Try to extract specific dates
        # Pattern: "Nov 15", "November 15", "11/15"
        patterns = [
            (r'(\w+)\s+(\d{1,2})', lambda m: f"{m.group(1)} {m.group(2)}"),
            (r'(\d{1,2})/(\d{1,2})', lambda m: f"{m.group(1)}/{m.group(2)}"),
        ]

        for pattern, formatter in patterns:
            match = re.search(pattern, date_str)
            if match:
                return formatter(match)

        # Relative dates
        if "yesterday" in date_str or "last night" in date_str:
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%b %d")
            return yesterday
        elif "today" in date_str or "this morning" in date_str:
            today = datetime.now().strftime("%b %d")
            return today
        elif "last week" in date_str:
            return "last week"
        elif "days ago" in date_str:
            # Extract number
            match = re.search(r'(\d+)\s+days?\s+ago', date_str)
            if match:
                days = int(match.group(1))
                date = (datetime.now() - timedelta(days=days)).strftime("%b %d")
                return date

        return None

    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        # Remove protocol
        url = re.sub(r'^https?://', '', url)
        # Remove path
        url = re.sub(r'/.*$', '', url)
        # Remove www
        url = re.sub(r'^www\.', '', url)

        return url if url else None
