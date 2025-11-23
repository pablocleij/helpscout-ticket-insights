# HelpScout Ticket Insights

> **Open-source tool** that syncs HelpScout tickets, stores them locally, and runs periodic LLM analyses to surface top pain-points, trends, and actionable insights.

[![CI](https://github.com/yourusername/helpscout-ticket-insights/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/helpscout-ticket-insights/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🎯 Goals

- **Zero-friction onboarding**: Clone → fill `.env` → `docker compose up` → done
- **Incremental sync**: Webhook + polling fallback for real-time updates
- **LLM-powered insights**: Automatically identify pain points, topics, sentiment, and urgency
- **Simple UI**: Clean web interface to view aggregated insights
- **Pluggable LLM providers**: OpenAI by default, easy to add Anthropic or others
- **Light footprint**: Postgres + Redis, runs on a single server

## ✨ Features

- ⚡ **Zero-config startup** - automatic database setup, migrations, and first sync
- 🔄 **Smart sync** - incremental updates with configurable date range
- 🤖 **Dual analysis** - LLM + statistical categorization for comprehensive insights
- 📊 **Auto-categorization** - automatically detects categories, subcategories, and patterns
- 📈 **Time-based filtering** - analyze tickets from specific date ranges
- 🔔 **Webhook support** for real-time ticket processing
- 🏷️ **Smart tagging** suggestions from LLM
- 🌐 **REST API** for integrations
- 🐳 **Docker-first** - single command deployment

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- HelpScout account with API access
- OpenAI API key (or Anthropic for Claude)

### Installation

1. **Clone the repository**

```bash
git clone https://github.com/yourusername/helpscout-ticket-insights.git
cd helpscout-ticket-insights
```

2. **Configure environment**

```bash
cp .env.example .env
```

Edit `.env` and fill in **just these two required fields**:

```bash
# Required - get from HelpScout API settings
HELPSCOUT_API_KEY=your_helpscout_api_key

# Required - get from OpenAI
OPENAI_API_KEY=your_openai_api_key

# Optional - sync only tickets from this date onwards (saves time & LLM costs)
SYNC_START_DATE=2024-01-01

# Optional - limit initial sync (0 = unlimited)
SYNC_INITIAL_LIMIT=1000
```

3. **Start everything**

```bash
docker compose up -d
```

**That's it!** 🎉 The system will automatically:
- ✅ Wait for database to be ready
- ✅ Run migrations
- ✅ Sync your HelpScout tickets (from `SYNC_START_DATE` if set)
- ✅ Analyze tickets with LLM
- ✅ Generate statistical categories
- ✅ Aggregate insights
- ✅ Start the web UI

4. **Access the dashboard**

Open http://localhost:8000 in your browser (wait 2-3 minutes for first sync to complete)

**View logs:**
```bash
docker compose logs -f api
```

## 📋 Usage

### View Insights

Visit http://localhost:8000 to see:
- **LLM-extracted insights**: Top pain points, topics, sentiment, urgency
- **Auto-detected categories**: Statistical analysis finds patterns automatically
- **Frequent tags**: Most common HelpScout tags
- **Time-based trends**: Analyze specific date ranges
- **Recent tickets**: Browse and search your synced tickets

### Automatic Categorization

The system uses **dual analysis** for comprehensive insights:

1. **LLM Analysis** (OpenAI/Anthropic):
   - Identifies specific pain points
   - Extracts topics and themes
   - Determines sentiment and urgency
   - Suggests relevant tags

2. **Statistical Analysis** (No LLM needed):
   - Automatically detects main categories from keywords
   - Clusters similar tickets by tags
   - Finds common subject line patterns
   - Builds hierarchical category structure

This approach gives you **instant insights** without waiting for LLM analysis on every ticket, while still providing deep analysis where it matters.

### API Endpoints

```bash
# Get aggregated insights
GET /api/insights?days=7

# List recent tickets with analysis
GET /api/tickets?days=7&limit=50

# Get single ticket details
GET /api/tickets/{ticket_id}

# Trigger manual sync
POST /api/sync

# Trigger manual analysis
POST /api/analyze

# Check sync status
GET /api/sync-status

# Get auto-detected categories
GET /api/categories?days=30

# Health check
GET /health
```

Full API documentation: http://localhost:8000/docs

### Manual Operations

```bash
# Run sync manually
docker compose exec api python scripts/run_sync.py

# Run analysis on pending tickets
docker compose exec api python -c "from src.database import get_db_context; from src.analyzer.pipeline import AnalysisPipeline; from src.database import get_db_context; db = get_db_context(); pipeline = AnalysisPipeline(db); pipeline.analyze_pending_tickets()"

# Access database
docker compose exec postgres psql -U helpscout -d helpscout_insights
```

### Webhook Setup

1. In HelpScout, go to **Manage → Apps**
2. Create a new **Custom App**
3. Set webhook URL to: `https://your-domain.com/webhooks/helpscout`
4. Subscribe to events: `conversation.created`, `conversation.updated`
5. Copy the webhook secret to your `.env` file

## 🏗️ Architecture

```
┌─────────────┐
│  HelpScout  │
│     API     │
└──────┬──────┘
       │
       ↓
┌──────────────────┐      ┌─────────────┐
│  Syncer Worker   │─────→│  Postgres   │
│  (Incremental)   │      │  Database   │
└──────────────────┘      └─────────────┘
       │                         │
       ↓                         ↓
┌──────────────────┐      ┌─────────────┐
│  Analysis Worker │←─────│   RQ Jobs   │
│  (LLM Pipeline)  │      │   (Redis)   │
└──────────────────┘      └─────────────┘
       │
       ↓
┌──────────────────┐
│  FastAPI Server  │
│   + Web UI       │
└──────────────────┘
```

### Components

- **Syncer**: Fetches tickets from HelpScout API (initial + incremental)
- **Analyzer**: LLM pipeline for extracting insights
- **Aggregator**: Computes top pain points and trends
- **API**: FastAPI server with REST endpoints
- **Worker**: Background job processor (RQ)
- **Scheduler**: Periodic tasks (sync every 6h, aggregate nightly)
- **UI**: Simple web dashboard

## 🛠️ Development

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set up database
export DATABASE_URL="postgresql://helpscout:helpscout@localhost:5432/helpscout_insights"
alembic upgrade head

# Run API server
uvicorn src.api.main:app --reload

# Run worker
python -m src.workers.worker
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_api.py -v
```

### Code Quality

```bash
# Format code
black src tests
isort src tests

# Lint
flake8 src tests --max-line-length=100
```

## 🔧 Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HELPSCOUT_API_KEY` | Yes | - | HelpScout API key |
| `OPENAI_API_KEY` | Yes* | - | OpenAI API key |
| **Sync Configuration** ||||
| `SYNC_START_DATE` | No | - | Only sync tickets from this date (ISO format: `2024-01-01`) |
| `SYNC_INITIAL_LIMIT` | No | `0` | Max tickets on first sync (`0` = unlimited, respects `MAX_TICKETS_PER_SYNC`) |
| `AUTO_INITIAL_SYNC` | No | `true` | Run sync automatically on first startup |
| `AUTO_INITIAL_ANALYSIS` | No | `true` | Run analysis automatically after sync |
| `SYNC_INTERVAL_HOURS` | No | `6` | Hours between automatic syncs |
| `MAX_TICKETS_PER_SYNC` | No | `1000` | Max tickets per sync operation |
| **Analysis Configuration** ||||
| `LLM_PROVIDER` | No | `openai` | LLM provider (`openai`, `anthropic`) |
| `ANALYSIS_BATCH_SIZE` | No | `50` | Tickets to analyze per batch |
| `ANALYSIS_LOOKBACK_DAYS` | No | `7` | Days to include in insights |
| `ENABLE_AUTO_CATEGORIZATION` | No | `true` | Enable statistical category extraction |
| `CATEGORY_MIN_OCCURRENCES` | No | `2` | Min occurrences for a category |
| `TOP_INSIGHTS_LIMIT` | No | `10` | Number of top items to show |

*Required if using OpenAI. For Anthropic, set `ANTHROPIC_API_KEY` instead.

#### Key Settings for Quick Start

For the **fastest startup** with **minimal LLM costs**:

```bash
# Only sync recent tickets
SYNC_START_DATE=2024-11-01

# Limit initial sync
SYNC_INITIAL_LIMIT=100

# Enable auto-categorization (free, no LLM needed)
ENABLE_AUTO_CATEGORIZATION=true
```

### LLM Providers

**OpenAI (default)**

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview
```

**Anthropic Claude**

```bash
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## 📊 Data Model

### Key Tables

- **tickets**: HelpScout conversations
- **threads**: Individual messages in conversations
- **ticket_analyses**: LLM analysis results
- **aggregated_insights**: Pre-computed top pain points and topics
- **sync_states**: Track sync progress per mailbox

## 🤝 Contributing

Contributions welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/)
- LLM integration via [OpenAI](https://openai.com/) and [Anthropic](https://anthropic.com/)
- HelpScout API: [docs.helpscout.com](https://developer.helpscout.com/)

## 📮 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/helpscout-ticket-insights/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/helpscout-ticket-insights/discussions)

## 🗺️ Roadmap

- [ ] Embedding-based semantic search
- [ ] Multi-language support
- [ ] Slack/Discord notifications for high-urgency tickets
- [ ] Customer segmentation analysis
- [ ] Export to CSV/JSON
- [ ] More LLM providers (Azure OpenAI, local models)
- [ ] Advanced visualizations (charts, trends)
- [ ] Custom analysis prompts per mailbox

---

**Made with ❤️ for support teams everywhere**
