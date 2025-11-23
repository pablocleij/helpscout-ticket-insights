"""Pluggable LLM provider interface."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json

from src.config import settings

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def analyze_ticket(self, ticket_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze ticket and return structured insights."""
        pass


class OpenAIProvider(LLMProvider):
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

        system_prompt = """You are an expert support ticket analyzer. Analyze the ticket and provide:
1. pain_points: List of specific customer pain points or issues (max 5)
2. topics: Main topics/categories (max 5)
3. sentiment: Overall sentiment (positive/neutral/negative)
4. urgency_score: Urgency from 0.0 (low) to 1.0 (critical)
5. suggested_tags: Relevant tags for categorization (max 5)
6. summary: Brief 1-2 sentence summary

Return response as valid JSON matching this structure:
{
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


class AnthropicProvider(LLMProvider):
    """Anthropic Claude-based provider."""

    def __init__(self, api_key: str, model: str = "claude-3-sonnet-20240229"):
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError("anthropic package is required. Install with: pip install anthropic")

        self.client = Anthropic(api_key=api_key)
        self.model = model

    def analyze_ticket(self, ticket_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze ticket using Anthropic Claude."""
        context = context or {}

        prompt = f"""Analyze this support ticket and provide structured insights.

Ticket:
{ticket_text}

Please provide your analysis in the following JSON format:
{{
    "pain_points": ["specific pain point 1", "pain point 2"],
    "topics": ["topic1", "topic2"],
    "sentiment": "positive|neutral|negative",
    "urgency_score": 0.0-1.0,
    "suggested_tags": ["tag1", "tag2"],
    "summary": "brief summary"
}}

Focus on:
1. Identifying specific customer pain points
2. Categorizing main topics
3. Assessing sentiment and urgency
4. Suggesting relevant tags
5. Providing a concise summary"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            # Parse JSON from response
            content = response.content[0].text
            # Extract JSON from potential markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)
            return {
                "pain_points": result.get("pain_points", []),
                "topics": result.get("topics", []),
                "sentiment": result.get("sentiment", "neutral"),
                "urgency_score": float(result.get("urgency_score", 0.5)),
                "suggested_tags": result.get("suggested_tags", []),
                "summary": result.get("summary", ""),
                "raw_response": result,
            }
        except Exception as e:
            logger.error(f"Anthropic analysis error: {e}")
            raise


def get_llm_provider() -> LLMProvider:
    """Factory function to get configured LLM provider."""
    provider = settings.llm_provider.lower()

    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        return OpenAIProvider(api_key=settings.openai_api_key, model=settings.openai_model)

    elif provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        return AnthropicProvider(api_key=settings.anthropic_api_key)

    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
