#!/usr/bin/env python3
"""
Preflight checks to validate configuration before startup.

This script checks:
- Required environment variables are set
- API keys are valid
- Database is accessible
- Required dependencies are installed
"""

import logging
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_env_vars():
    """Check required environment variables."""
    logger.info("✓ Checking environment variables...")

    required_vars = {
        "HELPSCOUT_API_KEY": "HelpScout API key for syncing tickets",
        "OPENAI_API_KEY": "OpenAI API key for LLM categorization",
        "DATABASE_URL": "PostgreSQL database connection string",
    }

    missing = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing.append(f"  ❌ {var} - {description}")

    if missing:
        logger.error("Missing required environment variables:\n" + "\n".join(missing))
        logger.error("\n💡 Action required:")
        logger.error("   1. Copy .env.example to .env")
        logger.error("   2. Fill in the missing values")
        logger.error("   3. Restart the application")
        return False

    logger.info("  ✓ All required environment variables are set")
    return True


def check_database():
    """Check database connectivity."""
    logger.info("✓ Checking database connectivity...")

    try:
        from src.database import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        logger.info("  ✓ Database connection successful")
        return True

    except ImportError as e:
        logger.error(f"  ❌ Failed to import database module: {e}")
        logger.error("\n💡 Action required:")
        logger.error("   Install dependencies: pip install -r requirements.txt")
        return False

    except Exception as e:
        logger.error(f"  ❌ Database connection failed: {e}")
        logger.error("\n💡 Action required:")
        logger.error("   1. Verify DATABASE_URL is correct")
        logger.error("   2. Ensure PostgreSQL is running")
        logger.error("   3. Check network connectivity")
        logger.error(f"   Current DATABASE_URL: {os.getenv('DATABASE_URL', 'not set')}")
        return False


def check_helpscout_api():
    """Check HelpScout API accessibility."""
    logger.info("✓ Checking HelpScout API...")

    try:
        import requests
        from src.config import settings

        # Try to fetch mailboxes (lightweight endpoint)
        response = requests.get(
            "https://api.helpscout.net/v2/mailboxes",
            headers={"Authorization": f"Bearer {settings.helpscout_api_key}"},
            timeout=10,
        )

        if response.status_code == 401:
            logger.error("  ❌ HelpScout API authentication failed")
            logger.error("\n💡 Action required:")
            logger.error("   1. Verify your HELPSCOUT_API_KEY is correct")
            logger.error("   2. Check if the API key has expired")
            logger.error("   3. Generate a new API key at: https://secure.helpscout.net/apps/custom/")
            return False

        elif response.status_code == 403:
            logger.error("  ❌ HelpScout API access forbidden")
            logger.error("\n💡 Action required:")
            logger.error("   Your API key doesn't have permission to access mailboxes")
            logger.error("   Ensure the app has 'Read' permission for Conversations")
            return False

        elif response.status_code >= 500:
            logger.warning(f"  ⚠️  HelpScout API is experiencing issues (HTTP {response.status_code})")
            logger.warning("   This is likely temporary. The app will retry automatically.")
            return True  # Don't fail startup for HelpScout server issues

        elif response.status_code == 200:
            data = response.json()
            mailbox_count = len(data.get("_embedded", {}).get("mailboxes", []))
            logger.info(f"  ✓ HelpScout API connection successful ({mailbox_count} mailboxes found)")
            return True

        else:
            logger.warning(f"  ⚠️  Unexpected HelpScout API response: HTTP {response.status_code}")
            logger.warning("   The app will attempt to continue, but sync may fail")
            return True

    except requests.exceptions.Timeout:
        logger.error("  ❌ HelpScout API request timed out")
        logger.error("\n💡 Action required:")
        logger.error("   Check your network connection to api.helpscout.net")
        return False

    except requests.exceptions.ConnectionError:
        logger.error("  ❌ Cannot connect to HelpScout API")
        logger.error("\n💡 Action required:")
        logger.error("   1. Check your internet connection")
        logger.error("   2. Verify firewall settings allow HTTPS to api.helpscout.net")
        return False

    except Exception as e:
        logger.error(f"  ❌ HelpScout API check failed: {e}")
        logger.error("\n💡 Action required:")
        logger.error("   Review the error above and verify your HelpScout configuration")
        return False


def check_openai_api():
    """Check OpenAI API accessibility."""
    logger.info("✓ Checking OpenAI API...")

    try:
        from openai import OpenAI
        from src.config import settings

        if not settings.openai_api_key:
            logger.error("  ❌ OpenAI API key not configured")
            logger.error("\n💡 Action required:")
            logger.error("   Set OPENAI_API_KEY in your .env file")
            logger.error("   Get your API key at: https://platform.openai.com/api-keys")
            return False

        client = OpenAI(api_key=settings.openai_api_key)

        # Try a minimal API call to validate the key
        try:
            client.models.list()
            logger.info("  ✓ OpenAI API connection successful")
            return True

        except Exception as e:
            error_str = str(e)

            if "401" in error_str or "Incorrect API key" in error_str:
                logger.error("  ❌ OpenAI API key is invalid")
                logger.error("\n💡 Action required:")
                logger.error("   1. Verify your OPENAI_API_KEY is correct")
                logger.error("   2. Generate a new API key at: https://platform.openai.com/api-keys")
                return False

            elif "429" in error_str or "rate_limit" in error_str:
                logger.warning("  ⚠️  OpenAI API rate limit reached")
                logger.warning("   This is temporary. The app will retry with backoff.")
                return True

            elif "quota" in error_str.lower():
                logger.error("  ❌ OpenAI API quota exceeded")
                logger.error("\n💡 Action required:")
                logger.error("   1. Check your OpenAI usage at: https://platform.openai.com/usage")
                logger.error("   2. Add billing/credits to your account")
                logger.error("   3. Or upgrade your plan")
                return False

            else:
                logger.error(f"  ❌ OpenAI API error: {e}")
                logger.error("\n💡 Action required:")
                logger.error("   Review the error above and check your OpenAI account status")
                return False

    except ImportError:
        logger.error("  ❌ OpenAI package not installed")
        logger.error("\n💡 Action required:")
        logger.error("   Install dependencies: pip install -r requirements.txt")
        return False

    except Exception as e:
        logger.error(f"  ❌ OpenAI API check failed: {e}")
        logger.error("\n💡 Action required:")
        logger.error("   Review the error above and verify your OpenAI configuration")
        return False


def check_dependencies():
    """Check required Python packages."""
    logger.info("✓ Checking required dependencies...")

    required_packages = [
        ("fastapi", "Web framework"),
        ("sqlalchemy", "Database ORM"),
        ("psycopg2", "PostgreSQL driver"),
        ("requests", "HTTP client"),
        ("openai", "OpenAI API client"),
        ("pydantic", "Configuration management"),
    ]

    missing = []
    for package, description in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(f"  ❌ {package} - {description}")

    if missing:
        logger.error("Missing required Python packages:\n" + "\n".join(missing))
        logger.error("\n💡 Action required:")
        logger.error("   Install dependencies: pip install -r requirements.txt")
        return False

    logger.info("  ✓ All required dependencies are installed")
    return True


def main():
    """Run all preflight checks."""
    logger.info("=" * 60)
    logger.info("HelpScout Ticket Insights - Preflight Checks")
    logger.info("=" * 60)
    logger.info("")

    checks = [
        ("Environment Variables", check_env_vars),
        ("Dependencies", check_dependencies),
        ("Database", check_database),
        ("HelpScout API", check_helpscout_api),
        ("OpenAI API", check_openai_api),
    ]

    results = []
    for name, check_fn in checks:
        try:
            result = check_fn()
            results.append((name, result))
        except Exception as e:
            logger.error(f"  ❌ {name} check crashed: {e}", exc_info=True)
            results.append((name, False))
        logger.info("")

    # Summary
    logger.info("=" * 60)
    logger.info("Preflight Check Summary")
    logger.info("=" * 60)

    for name, result in results:
        status = "✓ PASS" if result else "❌ FAIL"
        logger.info(f"  {status} - {name}")

    failed_checks = [name for name, result in results if not result]

    if failed_checks:
        logger.info("")
        logger.error("=" * 60)
        logger.error("⚠️  PREFLIGHT CHECKS FAILED")
        logger.error("=" * 60)
        logger.error("")
        logger.error("The following checks failed:")
        for name in failed_checks:
            logger.error(f"  • {name}")
        logger.error("")
        logger.error("Please fix the issues above before starting the application.")
        logger.error("Scroll up to see specific action items for each failure.")
        logger.error("")
        return 1

    logger.info("")
    logger.info("=" * 60)
    logger.info("✅ ALL PREFLIGHT CHECKS PASSED")
    logger.info("=" * 60)
    logger.info("")
    logger.info("System is ready to start!")
    logger.info("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
