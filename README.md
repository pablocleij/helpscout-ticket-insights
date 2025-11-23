# HelpScout Ticket Insights

> **Lightweight, bulletproof tool** that syncs HelpScout tickets, categorizes them with LLM, and surfaces actionable insights through statistical analysis.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🎯 Core Philosophy

**Three pillars that work flawlessly:**

1. **Sync tickets** from HelpScout without any faults or duplicates
2. **LLM categorization** with hierarchical category → subcategory structure
3. **Statistical analysis** on LLM-labeled data for trends and insights

Everything else has been removed to keep it **simple, fast, and reliable**.

## ✨ Features

- ⚡ **Zero-friction onboarding** - clone, configure .env, docker compose up
- 🛡️ **Failure-proof** - comprehensive error handling with actionable messages
- 🔍 **Preflight validation** - checks all prerequisites before startup
- 🤖 **Smart categorization** - GPT-5.1 with adaptive reasoning for category, subcategory, pain points, sentiment
- 🧬 **Entity extraction** - auto-extract products, error codes, complaint keywords, dates, URLs from tickets
- 📝 **Thread summarization** - comprehensive summaries covering entire conversation arcs
- 🔎 **Entity search** - find tickets by product, error code, or keyword
- 📊 **Product insights** - identify which products generate most issues and common error patterns
- 🧠 **Root cause analysis** - AI-powered pattern detection with actionable suggestions and confidence scores
- 📈 **Statistical analysis** - distribution, trending, cross-analysis on LLM data
- 🔄 **Fault-tolerant sync** - duplicate detection, batch commits, auto-retry
- 🏥 **Health checks** - monitoring endpoint for production deployments
- 🐳 **Docker-first** - single command deployment with PostgreSQL

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- HelpScout API key ([get one here](https://secure.helpscout.net/apps/custom/))
- OpenAI API key ([get one here](https://platform.openai.com/api-keys))

### Installation

**1. Clone and configure**

```bash
git clone https://github.com/yourusername/helpscout-ticket-insights.git
cd helpscout-ticket-insights
cp .env.example .env
```

**2. Edit `.env` with your API keys**

```bash
# Required
HELPSCOUT_API_KEY=your_helpscout_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Optional - sync only recent tickets to save time & LLM costs
SYNC_START_DATE=2024-01-01
MAX_TICKETS_PER_SYNC=100
```

**3. Start everything**

```bash
docker compose up -d
```

**That's it!** 🎉 The system will automatically:

1. ✅ Run preflight validation (checks API keys, database, connectivity)
2. ✅ Initialize database schema
3. ✅ Sync your HelpScout tickets (from `SYNC_START_DATE` if set)
4. ✅ Categorize tickets with GPT-5.1 (category, subcategory, sentiment, urgency)
5. ✅ Generate statistical insights (distribution, trends, cross-analysis)
6. ✅ Start the API server

**Watch it work:**

```bash
docker compose logs -f api
```

You'll see preflight checks, sync progress, and LLM categorization in real-time.

**Access the dashboard:**

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/api/health

## 📋 API Endpoints

### Core Endpoints

```bash
# Health check
GET /api/health

# List recent tickets with analysis
GET /api/tickets?days=7&limit=50

# Get single ticket details (includes extracted entities)
GET /api/tickets/{ticket_id}

# Get statistical analysis of categories
GET /api/categories/stats?days=7

# Get breakdown for specific category
GET /api/categories/Billing?days=30

# Trigger manual sync
POST /api/sync

# Trigger manual analysis
POST /api/analyze
```

### 🆕 Entity Extraction Endpoints

```bash
# Get product insights (which products have most issues)
GET /api/entities/products?days=30&limit=20
# Returns: product mention counts, associated categories, error patterns, sentiment

# Get error code insights (trending errors)
GET /api/entities/errors?days=30&limit=20
# Returns: error code frequency, affected products, urgency scores

# Search tickets by entity
GET /api/search/tickets?product=iOS+app&days=30
GET /api/search/tickets?error_code=500&days=30
GET /api/search/tickets?complaint_keyword=slow&days=30
# Combine filters: ?product=API&error_code=timeout&days=7
```

### 🆕 Root Cause Analysis Endpoints

```bash
# Deep analysis for specific product (includes root cause hints + actions)
GET /api/entities/products/{product}/analysis?days=30
# Example: GET /api/entities/products/iOS%20app/analysis

# Deep analysis for specific error code
GET /api/entities/errors/{error_code}/analysis?days=30
# Example: GET /api/entities/errors/500%20error/analysis
```

**What you get:**
- **Root Cause Hints**: Pattern detection with confidence scores and hypotheses
- **Suggested Actions**: Prioritized action items with reasoning and impact estimates
- **Temporal Analysis**: Timeline of when issues occurred, spike detection
- **Sample Tickets**: Recent examples for investigation

### Example: Product Root Cause Analysis Response

```json
{
  "product": "iOS app",
  "period_days": 30,
  "summary": {
    "total_tickets": 45,
    "avg_urgency": 0.72,
    "sentiment_distribution": {
      "negative": 35,
      "neutral": 8,
      "positive": 2
    },
    "top_categories": {
      "Technical Issue": 30,
      "Performance": 10
    },
    "common_errors": {
      "crash on startup": 12,
      "memory leak": 8
    }
  },
  "root_cause_hints": [
    {
      "pattern": "date_clustering",
      "confidence": 0.87,
      "evidence": {
        "clustered_date": "Nov 15",
        "tickets_mentioning_date": 34,
        "percentage": 75.6,
        "example_mentions": ["since Nov 15", "after update", "yesterday's release"]
      },
      "hypothesis": "Issues started around Nov 15 - potential release, update, or external event trigger"
    },
    {
      "pattern": "error_cooccurrence",
      "confidence": 0.92,
      "evidence": {
        "error_pair": ["crash on startup", "memory leak"],
        "cooccurrence_count": 12
      },
      "hypothesis": "Errors 'crash on startup' and 'memory leak' appear together frequently - likely related to same underlying issue"
    }
  ],
  "suggested_actions": [
    {
      "priority": 1,
      "action": "Investigate changes/releases around Nov 15",
      "reasoning": "87% confidence that issues started around Nov 15",
      "estimated_impact": "Could resolve 34/45 tickets",
      "next_steps": [
        "Check deployment logs for releases near this date",
        "Review code changes merged around this time",
        "Consider rollback if recent release"
      ]
    },
    {
      "priority": 2,
      "action": "Investigate connection between 'crash on startup' and 'memory leak'",
      "reasoning": "These errors co-occur in 12 tickets - likely same root cause",
      "estimated_impact": "Could resolve 12/45 tickets",
      "next_steps": [
        "Search logs for 'crash on startup' AND 'memory leak'",
        "Check if these errors are in same code path",
        "Review error handling in affected module"
      ]
    }
  ],
  "temporal_analysis": {
    "peak_date": "2024-11-15",
    "peak_ticket_count": 18,
    "average_per_day": 5.2,
    "spike_ratio": 3.46,
    "is_spike": true,
    "timeline": {
      "2024-11-14": 3,
      "2024-11-15": 18,
      "2024-11-16": 12,
      "2024-11-17": 7
    }
  },
  "sample_tickets": [
    {
      "id": 123,
      "number": 4567,
      "subject": "iOS app crashing after update",
      "summary": "Customer reports app crashes on startup since Nov 15...",
      "urgency": 0.85
    }
  ]
}
```

### Example: Product Insights Response

```json
{
  "period_days": 30,
  "total_products": 12,
  "products": [
    {
      "product": "iOS app",
      "ticket_count": 45,
      "avg_urgency": 0.72,
      "top_categories": {
        "Technical Issue": 30,
        "Performance": 10,
        "Bug": 5
      },
      "sentiment_distribution": {
        "negative": 35,
        "neutral": 8,
        "positive": 2
      },
      "common_errors": {
        "crash on startup": 12,
        "slow loading": 8
      }
    }
  ]
}
```

Full interactive docs: http://localhost:8000/docs

## 🏗️ Architecture

```
┌─────────────┐
│  HelpScout  │
│     API     │
└──────┬──────┘
       │
       ↓
┌──────────────────┐      ┌─────────────┐
│   HelpScout      │─────→│  PostgreSQL │
│   Syncer         │      │  Database   │
│ (fault-tolerant) │      └─────────────┘
└──────────────────┘             │
       │                         │
       ↓                         ↓
┌──────────────────┐      ┌─────────────┐
│   OpenAI GPT-4   │←─────│   Tickets   │
│  Categorization  │      │  + Threads  │
└──────────────────┘      └─────────────┘
       │                         │
       ↓                         ↓
┌──────────────────┐      ┌─────────────┐
│   Statistical    │←─────│   Ticket    │
│   Analyzer       │      │  Analyses   │
└──────────────────┘      └─────────────┘
       │
       ↓
┌──────────────────┐
│  FastAPI Server  │
│   + REST API     │
└──────────────────┘
```

**Components:**

- **HelpScout Syncer** - Fetches tickets with duplicate detection, batch commits, error recovery
- **OpenAI Provider** - GPT-4 categorization with retry logic and comprehensive error handling
- **Statistical Analyzer** - Runs on LLM-categorized data for insights
- **FastAPI Server** - REST API with automatic error handling
- **PostgreSQL** - Stores tickets, threads, and analysis results

**What's NOT included** (kept simple):

- ❌ No Redis/background workers - everything runs in API process
- ❌ No webhooks - polling only for reliability
- ❌ No complex UI - just API (build your own frontend!)
- ❌ No migrations - uses SQLAlchemy create_all()
- ❌ No multiple LLM providers - OpenAI only

## 🛡️ Error Handling & Reliability

### Preflight Validation

Before startup, the system validates:

- ✅ Environment variables are set
- ✅ Python dependencies installed
- ✅ Database connectivity
- ✅ HelpScout API authentication
- ✅ OpenAI API key and quota

**If anything is wrong, you get actionable error messages:**

```
❌ FAIL - OpenAI API

  ❌ OpenAI API key is invalid

💡 Action required:
   1. Verify OPENAI_API_KEY is correct in .env
   2. Generate new key at: https://platform.openai.com/api-keys
   3. Ensure the key starts with 'sk-'
```

**Run preflight checks manually:**

```bash
python scripts/preflight_check.py
```

### Automatic Error Recovery

**HelpScout Syncer:**
- 3 retries with backoff for transient failures
- Per-page error handling (one bad page doesn't kill sync)
- Batch commits every 10 tickets for performance
- Transaction rollback on failures
- Detailed error messages for 401, 403, 429, 500, timeout, connection errors

**OpenAI Provider:**
- 3 retries with exponential backoff (2s, 4s, 8s)
- Auto-retry for rate limits and timeouts
- Immediate failure for permanent errors (auth, quota)
- 60s timeout for LLM requests
- Clear guidance for every error type

**Example error messages:**

```
HelpScout API rate limit exceeded (HTTP 429).
💡 Info: The app will automatically retry with backoff.
   If this persists, contact HelpScout support.
```

```
OpenAI API quota exceeded.
💡 Action required:
   1. Check usage at: https://platform.openai.com/usage
   2. Add billing/credits at: https://platform.openai.com/account/billing
   3. Verify your payment method is valid
```

### Health Monitoring

```bash
curl http://localhost:8000/api/health

{
  "status": "healthy",
  "database": "healthy",
  "timestamp": "2025-11-23T19:45:00.000000"
}
```

Use for Docker health checks, load balancers, or monitoring tools.

## 🧪 Testing

**Quick verification with mock data (no API keys needed):**

```bash
python scripts/test_with_mock_data.py
```

This creates 10 mock tickets, runs analysis, and verifies:
- ✅ Sync integrity (no duplicates)
- ✅ LLM categorization (category/subcategory structure)
- ✅ Statistical analysis (distribution, trending)
- ✅ Category breakdown

**Output:**

```
✅ ALL TESTS COMPLETED SUCCESSFULLY!

📋 SUMMARY:
  • Categories found: 7
  • Sentiment analysis: 7 categories
  • No duplicates: ✅
```

## 🔧 Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HELPSCOUT_API_KEY` | ✅ Yes | - | HelpScout API key |
| `OPENAI_API_KEY` | ✅ Yes | - | OpenAI API key (must start with `sk-`) |
| `DATABASE_URL` | No | `postgresql://...` | PostgreSQL connection string |
| `OPENAI_MODEL` | No | `gpt-5.1` | OpenAI model to use (gpt-5.1 or gpt-5.1-chat-latest) |
| `OPENAI_REASONING_EFFORT` | No | `medium` | Reasoning effort: none, low, medium, high |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| **Sync Configuration** ||||
| `SYNC_START_DATE` | No | - | Only sync tickets from this date (ISO: `2024-01-01`) |
| `MAX_TICKETS_PER_SYNC` | No | `1000` | Max tickets per sync operation |
| `AUTO_INITIAL_SYNC` | No | `true` | Run sync automatically on first startup |
| `AUTO_INITIAL_ANALYSIS` | No | `true` | Run analysis automatically after sync |
| `ANALYSIS_BATCH_SIZE` | No | `50` | Tickets to analyze per batch |

### Recommended Settings

**For fastest startup with minimal LLM costs:**

```bash
# Only sync recent tickets
SYNC_START_DATE=2024-11-01
MAX_TICKETS_PER_SYNC=100

# Use faster chat model with no reasoning
OPENAI_MODEL=gpt-5.1-chat-latest
OPENAI_REASONING_EFFORT=none
```

**For production with comprehensive analysis:**

```bash
# Sync all history
SYNC_START_DATE=
MAX_TICKETS_PER_SYNC=0  # unlimited

# Use best model with adaptive reasoning
OPENAI_MODEL=gpt-5.1
OPENAI_REASONING_EFFORT=medium  # or 'high' for complex tickets
ANALYSIS_BATCH_SIZE=50
```

## 📊 Data Model

### Tables

**tickets** - HelpScout conversations
- `helpscout_id` (unique), `number`, `subject`, `status`, `customer_*`
- `created_at`, `updated_at`, `closed_at`
- `tags` (JSON), `raw_data` (JSON)

**threads** - Individual messages in conversations
- `helpscout_id` (unique), `ticket_id` (FK)
- `type`, `body`, `body_plain`
- `created_by_*`, `is_customer`

**ticket_analyses** - LLM analysis results
- `ticket_id` (FK)
- `category`, `subcategory`
- `pain_points` (JSON), `topics` (JSON)
- `sentiment`, `urgency_score`
- `suggested_tags` (JSON), `summary`
- 🆕 `extracted_entities` (JSON) - products, error_codes, complaint_keywords, dates, urls
- `analyzed_at`, `llm_provider`, `llm_model`

**sync_states** - Track sync progress per mailbox
- `mailbox_id`, `last_sync_at`, `total_tickets_synced`

### Entity Extraction Details

The LLM automatically extracts the following entities from ticket conversations:

| Entity Type | Description | Examples |
|------------|-------------|----------|
| **products** | Product or feature names mentioned | "iOS app", "API v2", "Dashboard", "Stripe integration" |
| **error_codes** | Error codes or technical identifiers | "500 error", "ERR_TIMEOUT", "404", "Connection refused" |
| **complaint_keywords** | Key complaint indicators | "broken", "slow", "not working", "crash", "bug", "stuck" |
| **dates** | Time references from customer | "since yesterday", "Nov 15", "last week", "3 days ago" |
| **urls** | URLs or domains mentioned | "example.com", "api.stripe.com", "dashboard.app.com" |

**Use cases:**
- **Product managers**: Identify which products/features generate most support issues
- **Engineering teams**: Track error patterns and affected products
- **Support teams**: Find similar tickets by error code or product
- **Leadership**: Spot trending issues early (e.g., spike in "iOS app" + "crash" mentions)

## 🛠️ Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment
export DATABASE_URL="postgresql://helpscout:helpscout@localhost:5432/helpscout_insights"
export HELPSCOUT_API_KEY="your_key"
export OPENAI_API_KEY="your_key"

# Initialize database
python scripts/init_db.py

# Run migration for entity extraction (if upgrading from older version)
python scripts/add_extracted_entities_column.py

# Run API server
uvicorn src.api.main:app --reload --port 8000
```

### Manual Operations

```bash
# Run sync manually
docker compose exec api python scripts/run_sync.py

# Run setup (sync + analysis)
docker compose exec api python scripts/auto_setup.py

# Access database
docker compose exec postgres psql -U helpscout -d helpscout_insights

# View logs
docker compose logs -f api

# Restart services
docker compose restart api
```

## 📦 Dependencies

**Core (8 packages):**
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `sqlalchemy` - ORM
- `psycopg2-binary` - PostgreSQL driver
- `requests` - HTTP client
- `openai` - OpenAI API
- `pydantic` - Configuration
- `python-dotenv` - Environment variables

**Testing:**
- `pytest` - Test framework
- `httpx` - HTTP client for tests

**Deployment:**
- `docker` - Containerization
- `docker-compose` - Orchestration

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Keep it simple - align with core philosophy
4. Add tests if adding features
5. Update README if changing behavior
6. Submit a pull request

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [OpenAI](https://openai.com/) - LLM categorization
- [HelpScout](https://developer.helpscout.com/) - Support ticket API
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database ORM

## 📮 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/helpscout-ticket-insights/issues)
- **Questions**: Create an issue with the `question` label

## 💡 Philosophy

This tool follows these principles:

1. **Simple > Complex** - 2 services (Postgres + API) instead of 5
2. **Reliable > Feature-rich** - Every error has actionable guidance
3. **Direct > Async** - No background workers, just direct execution
4. **OpenAI only** - One provider done well beats many done poorly
5. **Test with mock data** - Verify before using real API keys

**Made with ❤️ for support teams who value simplicity and reliability**
