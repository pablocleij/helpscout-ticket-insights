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
- 📊 **Statistical insights** - distribution, trending, cross-analysis on LLM data
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

```bash
# Health check
GET /api/health

# List recent tickets with analysis
GET /api/tickets?days=7&limit=50

# Get single ticket details
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
- `analyzed_at`, `llm_provider`, `llm_model`

**sync_states** - Track sync progress per mailbox
- `mailbox_id`, `last_sync_at`, `total_tickets_synced`

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
