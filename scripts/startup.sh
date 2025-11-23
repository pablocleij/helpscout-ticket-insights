#!/bin/bash
set -e

echo "🚀 HelpScout Ticket Insights - Starting up..."

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL..."
until pg_isready -h postgres -U helpscout > /dev/null 2>&1; do
    sleep 1
done
echo "✓ PostgreSQL is ready"
echo ""

# Run preflight checks
echo "🔍 Running preflight checks..."
if ! python scripts/preflight_check.py; then
    echo ""
    echo "❌ Preflight checks failed. Please fix the issues above."
    echo "   Container will exit now."
    exit 1
fi
echo ""

# Initialize database schema
echo "📦 Initializing database..."
python scripts/init_db.py
echo "✓ Database initialized"

# Check if this is first run (no tickets in database)
if [ "${AUTO_INITIAL_SYNC:-true}" = "true" ]; then
    echo "🔍 Checking if initial sync is needed..."
    python -c "
from src.database import SessionLocal
from src.models import Ticket
db = SessionLocal()
ticket_count = db.query(Ticket).count()
db.close()
if ticket_count == 0:
    print('🎯 First run detected - triggering initial sync...')
    exit(0)
else:
    print('✓ Database already has tickets')
    exit(1)
" && python scripts/auto_setup.py || echo "⏭️  Skipping initial sync"
fi

echo "🌐 Starting API server..."
exec "$@"
