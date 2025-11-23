"""OpenAI LLM provider for ticket analysis."""

import logging
from typing import Dict, Any, Optional
import json

from src.config import settings

logger = logging.getLogger(__name__)


class OpenAIProvider:
    """OpenAI GPT-based provider."""

    def __init__(self, api_key: str, model: str = "gpt-5.1", reasoning_effort: str = "medium"):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package is required. Install with: pip install openai")

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.reasoning_effort = reasoning_effort

    def analyze_ticket(self, ticket_text: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Analyze ticket using OpenAI with robust error handling."""
        context = context or {}

        system_prompt = """You are an expert support ticket analyzer specializing in categorization, issue identification, and entity extraction.

Analyze the ticket and provide:
1. category: Primary category (e.g., "Billing", "Technical Issue", "Feature Request", "Account Access", "Integration", "Performance", "Data Management", "UI/UX")
2. subcategory: Specific subcategory under the main category (e.g., for "Billing" → "Payment Failed", "Invoice Question", "Refund Request")
3. pain_points: List of specific customer pain points or issues (max 5)
4. topics: Related topics or themes (max 5)
5. sentiment: Overall sentiment (positive/neutral/negative)
6. urgency_score: Urgency from 0.0 (low) to 1.0 (critical)
7. suggested_tags: Relevant tags for quick filtering (max 5)
8. summary: Comprehensive 2-4 sentence summary covering the entire conversation arc - initial issue, key developments, current status, and resolution (if closed)
9. extracted_entities: Extract specific entities from the ticket:
   - products: Product/feature names mentioned (e.g., "iOS app", "API v2", "Dashboard", "Stripe integration")
   - error_codes: Error codes or technical identifiers (e.g., "500 error", "ERR_TIMEOUT", "404")
   - complaint_keywords: Key complaint words (e.g., "broken", "slow", "not working", "crash", "bug")
   - dates: Any dates or time references mentioned by customer (e.g., "since yesterday", "Nov 15", "last week")
   - urls: Any URLs or domains mentioned (e.g., "example.com", "api.stripe.com")

Return response as valid JSON matching this structure:
{
    "category": "string",
    "subcategory": "string",
    "pain_points": ["string"],
    "topics": ["string"],
    "sentiment": "string",
    "urgency_score": 0.0,
    "suggested_tags": ["string"],
    "summary": "string",
    "extracted_entities": {
        "products": ["string"],
        "error_codes": ["string"],
        "complaint_keywords": ["string"],
        "dates": ["string"],
        "urls": ["string"]
    }
}"""

        user_prompt = f"Analyze this support ticket:\n\n{ticket_text}"

        # Retry logic for transient failures
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                # Build API parameters
                api_params = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                    "timeout": 60,
                }

                # Add reasoning_effort for GPT-5.1 models
                if "gpt-5" in self.model.lower():
                    api_params["reasoning_effort"] = self.reasoning_effort

                response = self.client.chat.completions.create(**api_params)

                result = json.loads(response.choices[0].message.content)

                # Ensure extracted_entities has proper structure with defaults
                extracted_entities = result.get("extracted_entities", {})
                if not isinstance(extracted_entities, dict):
                    extracted_entities = {}

                # Ensure all entity fields exist with defaults
                extracted_entities = {
                    "products": extracted_entities.get("products", []),
                    "error_codes": extracted_entities.get("error_codes", []),
                    "complaint_keywords": extracted_entities.get("complaint_keywords", []),
                    "dates": extracted_entities.get("dates", []),
                    "urls": extracted_entities.get("urls", []),
                }

                return {
                    "category": result.get("category", "Uncategorized"),
                    "subcategory": result.get("subcategory", "General"),
                    "pain_points": result.get("pain_points", []),
                    "topics": result.get("topics", []),
                    "sentiment": result.get("sentiment", "neutral"),
                    "urgency_score": float(result.get("urgency_score", 0.5)),
                    "suggested_tags": result.get("suggested_tags", []),
                    "summary": result.get("summary", ""),
                    "extracted_entities": extracted_entities,
                    "raw_response": result,
                }

            except json.JSONDecodeError as e:
                error_msg = (
                    "Failed to parse OpenAI response as JSON.\n"
                    "💡 This might indicate:\n"
                    "   1. OpenAI returned invalid JSON format\n"
                    "   2. The model hallucinated non-JSON text\n"
                    f"   → Raw response: {response.choices[0].message.content[:200] if response else 'N/A'}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

            except Exception as e:
                error_str = str(e)
                error_type = type(e).__name__

                # Authentication error
                if "401" in error_str or "Incorrect API key" in error_str or "invalid_api_key" in error_str:
                    error_msg = (
                        "OpenAI API authentication failed.\n"
                        "💡 Action required:\n"
                        "   1. Verify OPENAI_API_KEY is correct in .env\n"
                        "   2. Generate new key at: https://platform.openai.com/api-keys\n"
                        "   3. Ensure the key starts with 'sk-'\n"
                        f"   Error: {error_str}"
                    )
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                # Rate limit error
                elif "429" in error_str or "rate_limit" in error_str.lower():
                    if attempt < max_retries - 1:
                        import time
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(
                            f"OpenAI rate limit hit. Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})..."
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        error_msg = (
                            "OpenAI API rate limit exceeded after retries.\n"
                            "💡 Action required:\n"
                            "   1. Wait a few minutes and try again\n"
                            "   2. Check your rate limits at: https://platform.openai.com/account/limits\n"
                            "   3. Consider upgrading your OpenAI plan\n"
                            "   4. Reduce analysis_batch_size in .env"
                        )
                        logger.error(error_msg)
                        raise RuntimeError(error_msg)

                # Quota/billing error
                elif "quota" in error_str.lower() or "insufficient_quota" in error_str:
                    error_msg = (
                        "OpenAI API quota exceeded.\n"
                        "💡 Action required:\n"
                        "   1. Check usage at: https://platform.openai.com/usage\n"
                        "   2. Add billing/credits at: https://platform.openai.com/account/billing\n"
                        "   3. Verify your payment method is valid\n"
                        f"   Error: {error_str}"
                    )
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

                # Timeout error
                elif "timeout" in error_str.lower() or error_type == "Timeout":
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"OpenAI API timeout. Retrying (attempt {attempt + 1}/{max_retries})..."
                        )
                        continue
                    else:
                        error_msg = (
                            "OpenAI API request timed out after retries.\n"
                            "💡 This might indicate:\n"
                            "   1. OpenAI API is experiencing high latency\n"
                            "   2. Network connectivity issues\n"
                            "   → Try again in a few minutes"
                        )
                        logger.error(error_msg)
                        raise RuntimeError(error_msg)

                # Model not found error
                elif "model_not_found" in error_str or "does not exist" in error_str:
                    error_msg = (
                        f"OpenAI model '{self.model}' not found.\n"
                        "💡 Action required:\n"
                        "   1. Verify OPENAI_MODEL in .env is correct\n"
                        "   2. Use a supported model: gpt-5.1 (recommended), gpt-5.1-chat-latest\n"
                        "   3. Check available models at: https://platform.openai.com/docs/models\n"
                        f"   Current model: {self.model}"
                    )
                    logger.error(error_msg)
                    raise ValueError(error_msg)

                # Connection error
                elif "connection" in error_str.lower() or error_type == "ConnectionError":
                    if attempt < max_retries - 1:
                        import time
                        logger.warning(
                            f"OpenAI connection error. Retrying (attempt {attempt + 1}/{max_retries})..."
                        )
                        time.sleep(retry_delay)
                        continue
                    else:
                        error_msg = (
                            "Cannot connect to OpenAI API after retries.\n"
                            "💡 Action required:\n"
                            "   1. Check your internet connection\n"
                            "   2. Verify firewall allows HTTPS to api.openai.com\n"
                            f"   Error: {error_str}"
                        )
                        logger.error(error_msg)
                        raise RuntimeError(error_msg)

                # Generic error
                else:
                    error_msg = (
                        f"OpenAI API error: {error_type}: {error_str}\n"
                        "💡 Action required:\n"
                        "   1. Check the error message above\n"
                        "   2. Verify your OpenAI account status\n"
                        "   3. If issue persists, report this error"
                    )
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

        # Should never reach here
        raise RuntimeError("OpenAI analysis failed after all retries")


def get_llm_provider() -> OpenAIProvider:
    """Get configured OpenAI provider."""
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY not configured")
    return OpenAIProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        reasoning_effort=settings.openai_reasoning_effort
    )
