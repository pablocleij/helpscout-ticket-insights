#!/bin/bash
set -e

echo "🚀 HelpScout Ticket Insights - Starting up..."

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL..."
while ! pg_isready -h postgres -U helpscout > /dev/null 2>&1; do
    sleep 1
done
echo "✓ PostgreSQL is ready"

# Wait for Redis to be ready
echo "⏳ Waiting for Redis..."
while ! redis-cli -h redis ping > /dev/null 2>&1; do
    sleep 1
done
echo "✓ Redis is ready"

# Run database migrations
echo "📦 Running database migrations..."
alembic upgrade head
echo "✓ Migrations complete"

# Check if this is first run (no tickets in database)
echo "🔍 Checking if initial setup is needed..."
python -c "
from src.database import SessionLocal
from src.models import Ticket
db = SessionLocal()
ticket_count = db.query(Ticket).count()
db.close()
exit(0 if ticket_count == 0 else 1)
" && IS_FIRST_RUN=true || IS_FIRST_RUN=false

if [ "$IS_FIRST_RUN" = true ]; then
    echo "🎯 First run detected - running initial setup..."

    # Check if auto sync is enabled
    if [ "${AUTO_INITIAL_SYNC:-true}" = "true" ]; then
        echo "📥 Running initial sync..."
        python scripts/auto_setup.py
        echo "✓ Initial setup complete"
    else
        echo "⏭️  Auto initial sync disabled (AUTO_INITIAL_SYNC=false)"
        echo "   Run manually: docker compose exec api python scripts/init_db.py"
    fi
else
    echo "✓ Database already initialized (found existing tickets)"
fi

echo "🌐 Starting API server..."
exec "$@"
