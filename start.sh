#!/bin/bash

set -e

echo "🚀 Personal AI - Docker Setup"
echo "=============================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "✅ .env file created"
else
    echo "ℹ️  .env file already exists"
fi

echo ""
echo "🏗️  Building Docker images..."
docker compose build

echo ""
echo "🚀 Starting all services..."
docker compose up -d

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 5

echo ""
echo "✅ All services started!"
echo ""
echo "📍 Access the application at:"
echo "   Frontend:  http://localhost:5173"
echo "   Backend:   http://localhost:8000"
echo "   Ollama:    http://localhost:11434"
echo "   Qdrant:    http://localhost:6333"
echo ""
echo "📚 Next steps:"
echo "   1. Open http://localhost:5173 in your browser"
echo "   2. Upload documents or start chatting"
echo "   3. Run 'make pull-models' to pull Ollama models"
echo ""
echo "📖 For more commands, run: make help"
echo ""
echo "To view logs: docker compose logs -f"
echo "To stop services: docker compose down"
