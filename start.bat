@echo off
setlocal enabledelayedexpansion

echo 🚀 Personal AI - Docker Setup
echo ==============================
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not installed. Please install Docker Desktop.
    exit /b 1
)

echo ✅ Docker is installed
echo.

REM Check if .env exists
if not exist .env (
    echo 📝 Creating .env file from .env.example...
    copy .env.example .env
    echo ✅ .env file created
) else (
    echo ℹ️  .env file already exists
)

echo.
echo 🏗️  Building Docker images...
docker compose build

echo.
echo 🚀 Starting all services...
docker compose up -d

echo.
echo ⏳ Waiting for services to be healthy...
timeout /t 5 /nobreak

echo.
echo ✅ All services started!
echo.
echo 📍 Access the application at:
echo    Frontend:  http://localhost:5173
echo    Backend:   http://localhost:8000
echo    Ollama:    http://localhost:11434
echo    Qdrant:    http://localhost:6333
echo.
echo 📚 Next steps:
echo    1. Open http://localhost:5173 in your browser
echo    2. Upload documents or start chatting
echo    3. Run 'docker compose exec ollama ollama pull llama3:8b' to pull models
echo.
echo To view logs: docker compose logs -f
echo To stop services: docker compose down
echo.
pause
