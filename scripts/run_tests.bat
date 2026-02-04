@echo off
REM Test runner script for Marketing Cortex (Windows)

echo ==========================================
echo Marketing Cortex Test Suite
echo ==========================================
echo.

REM Check if virtual environment is activated
if "%VIRTUAL_ENV%"=="" (
    echo Warning: Virtual environment not activated
    echo Consider activating it: venv\Scripts\activate
    echo.
)

REM Run unit tests
echo Running Unit tests...
pytest tests\test_*.py -m unit -v --tb=short
if %ERRORLEVEL% NEQ 0 (
    echo Unit tests failed!
    exit /b 1
)
echo Unit tests passed!
echo.

REM Run integration tests
echo Running Integration tests...
pytest tests\test_integration.py -m integration -v --tb=short
if %ERRORLEVEL% NEQ 0 (
    echo Integration tests failed!
    exit /b 1
)
echo Integration tests passed!
echo.

REM Run E2E tests if requested
if "%1"=="--e2e" (
    echo Running E2E tests...
    pytest tests\test_e2e.py -m e2e -v --tb=short
    if %ERRORLEVEL% NEQ 0 (
        echo E2E tests failed!
        exit /b 1
    )
    echo E2E tests passed!
    echo.
)

REM Run with coverage if requested
if "%1"=="--coverage" (
    echo Running tests with coverage...
    pytest tests\ -v --cov=src --cov-report=html --cov-report=term-missing
    echo Coverage report generated in htmlcov\index.html
    echo.
)

echo ==========================================
echo All tests completed!
echo ==========================================
