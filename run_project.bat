@echo off
REM Marketing Cortex - Project Startup Script
REM This script starts all services and the FastAPI application

echo ========================================
echo   Marketing Cortex - Starting Project
echo ========================================
echo.

REM Check if virtual environment exists
if not exist ".venv\" (
    echo [ERROR] Virtual environment not found!
    echo Please run: python -m venv .venv
    echo Then activate and install: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Activate virtual environment
echo [1/5] Activating virtual environment...
call .venv\Scripts\activate.bat
echo     Done!
echo.

REM Check if .env file exists
if not exist ".env" (
    echo [ERROR] .env file not found!
    echo Please copy env.example to .env and fill in your API keys
    pause
    exit /b 1
)

REM Start Docker services (Neo4j only - Redis is Upstash serverless)
echo [2/5] Starting Docker services (Neo4j)...
docker-compose up -d
if errorlevel 1 (
    echo [WARNING] Docker services failed to start
    echo Make sure Docker Desktop is running
    echo You can continue if using cloud services (Neo4j AuraDB)
    echo.
) else (
    echo     Docker services started!
    echo.
)

REM Wait for services to be ready
echo [3/5] Waiting for services to initialize (5 seconds)...
timeout /t 5 /nobreak >nul
echo     Done!
echo.

REM Test Redis connection (Upstash)
echo [4/5] Testing Upstash Redis connection...
python tests/test_redis_standalone.py
if errorlevel 1 (
    echo [WARNING] Upstash Redis test failed
    echo Check if REDIS_URL in .env is correct
    echo Make sure you're using the correct Upstash Redis URL
    echo.
) else (
    echo     Upstash Redis is working!
    echo.
)

REM Start FastAPI server
echo [5/5] Starting FastAPI server...
echo.
echo ========================================
echo   Server will start on http://localhost:8070
echo   API Docs: http://localhost:8070/docs
echo   Health Check: http://localhost:8070/api/v1/health
echo ========================================
echo.
echo Press Ctrl+C to stop the server
echo.

uvicorn src.main:app --reload --host 0.0.0.0 --port 8070
