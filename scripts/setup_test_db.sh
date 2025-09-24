#!/bin/bash

# Setup script for test database with anime data

echo "🚀 Setting up test database..."

# Start PostgreSQL container
echo "Starting PostgreSQL container..."
docker compose -f docker-compose.test.yml up -d

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
sleep 5

# Run the SQL setup
echo "Creating anime database schema and data..."
PGPASSWORD=test_pass psql -h localhost -p 5434 -U test_user -d test_footfall -f scripts/setup_anime_db.sql

if [ $? -eq 0 ]; then
    echo "✅ Test database setup complete!"
    echo ""
    echo "Database contains:"
    echo "  - studios table: 10 anime studios"
    echo "  - anime table: 15 popular anime titles"
    echo ""
    echo "To switch to test database:"
    echo "  Uncomment test database section in .env"
    echo "  Comment out production database section"
else
    echo "❌ Failed to setup database"
    exit 1
fi