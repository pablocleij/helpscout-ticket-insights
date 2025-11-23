"""OpenAI LLM provider for ticket analysis."""

import logging
from typing import Dict, Any, Optional
import json

from src.config import settings

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """OpenAI GPT-based provider."""

    def __init__(self, api_key: str, model: str = "gpt-4-turbo-preview"):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package is required. Install with: pip install openai")

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def analyze_ticket(self, ticket_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze ticket using OpenAI."""
        context = context or {}

        system_prompt = """You are an expert support ticket analyzer specializing in categorization and issue identification.

Analyze the ticket and provide:
1. category: Primary category (e.g., "Billing", "Technical Issue", "Feature Request", "Account Access", "Integration", "Performance", "Data Management", "UI/UX")
2. subcategory: Specific subcategory under the main category (e.g., for "Billing" → "Payment Failed", "Invoice Question", "Refund Request")
3. pain_points: List of specific customer pain points or issues (max 5)
4. topics: Related topics or themes (max 5)
5. sentiment: Overall sentiment (positive/neutral/negative)
6. urgency_score: Urgency from 0.0 (low) to 1.0 (critical)
7. suggested_tags: Relevant tags for quick filtering (max 5)
8. summary: Brief 1-2 sentence summary of the issue

Return response as valid JSON matching this structure:
{
    "category": "string",
    "subcategory": "string",
    "pain_points": ["string"],
    "topics": ["string"],
    "sentiment": "string",
    "urgency_score": 0.0,
    "suggested_tags": ["string"],
    "summary": "string"
}"""

        user_prompt = f"Analyze this support ticket:\n\n{ticket_text}"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
            return {
                "category": result.get("category", "Uncategorized"),
                "subcategory": result.get("subcategory", "General"),
                "pain_points": result.get("pain_points", []),
                "topics": result.get("topics", []),
                "sentiment": result.get("sentiment", "neutral"),
                "urgency_score": float(result.get("urgency_score", 0.5)),
                "suggested_tags": result.get("suggested_tags", []),
                "summary": result.get("summary", ""),
                "raw_response": result,
            }
        except Exception as e:
            logger.error(f"OpenAI analysis error: {e}")
            raise


def get_llm_provider() -> OpenAIProvider:
    """Get configured OpenAI provider."""
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY not configured")
    return OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model)
