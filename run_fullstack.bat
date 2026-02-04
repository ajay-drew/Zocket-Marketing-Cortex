@echo off
REM Marketing Cortex - Full Stack Startup Script
REM This script starts both the backend (FastAPI) and frontend (React/Vite) simultaneously

echo ========================================
echo   Marketing Cortex - Starting Full Stack
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

REM Check if .env file exists
if not exist ".env" (
    echo [ERROR] .env file not found!
    echo Please copy env.example to .env and fill in your API keys
    pause
    exit /b 1
)

REM Check if frontend node_modules exists
if not exist "frontend\node_modules\" (
    echo [WARNING] Frontend node_modules not found!
    echo Installing frontend dependencies...
    cd frontend
    call npm install
    if errorlevel 1 (
        echo [ERROR] Failed to install frontend dependencies
        pause
        exit /b 1
    )
    cd ..
    echo     Frontend dependencies installed!
    echo.
)

REM Start Docker services (Neo4j only - Redis is Upstash serverless)
echo [1/4] Starting Docker services (Neo4j)...
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
echo [2/4] Waiting for services to initialize (3 seconds)...
timeout /t 3 /nobreak >nul
echo     Done!
echo.

REM Set backend port (matches src/config.py default)
set BACKEND_PORT=5469

REM Start backend in a new window
echo [3/4] Starting FastAPI backend (port %BACKEND_PORT%)...
echo.
start "Marketing Cortex - Backend" cmd /k "call .venv\Scripts\activate.bat && echo ======================================== && echo   Marketing Cortex Backend && echo ======================================== && echo Backend starting on http://localhost:%BACKEND_PORT% && echo API Docs: http://localhost:%BACKEND_PORT%/docs && echo Health: http://localhost:%BACKEND_PORT%/api/health && echo. && uvicorn src.main:app --reload --host 0.0.0.0 --port %BACKEND_PORT% --log-level info --access-log"
timeout /t 3 /nobreak >nul
echo     Backend started in new window!
echo.

REM Start frontend in a new window
echo [4/4] Starting React frontend (Vite)...
echo.
cd frontend
start "Marketing Cortex - Frontend" cmd /k "set VITE_API_URL=http://localhost:%BACKEND_PORT% && echo ======================================== && echo   Marketing Cortex Frontend && echo ======================================== && echo Frontend starting on http://localhost:3000 && echo Backend API: http://localhost:%BACKEND_PORT% && echo. && npm run dev"
cd ..
timeout /t 3 /nobreak >nul
echo     Frontend started in new window!
echo.

echo ========================================
echo   Full Stack Started Successfully!
echo ========================================
echo.
echo Backend:  http://localhost:%BACKEND_PORT%
echo API Docs: http://localhost:%BACKEND_PORT%/docs
echo Health:   http://localhost:%BACKEND_PORT%/api/health
echo Frontend: http://localhost:3000 (or check the frontend window)
echo.
echo Both services are running in separate windows.
echo Close those windows or press Ctrl+C in them to stop.
echo.
echo This window will remain open. Press any key to exit...
pause >nul
