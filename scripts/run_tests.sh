#!/bin/bash
# Test runner script for Marketing Cortex

set -e

echo "=========================================="
echo "Marketing Cortex Test Suite"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to run tests
run_tests() {
    local test_type=$1
    local test_path=$2
    local marker=$3
    
    echo -e "${BLUE}Running $test_type tests...${NC}"
    if [ -n "$marker" ]; then
        pytest "$test_path" -m "$marker" -v --tb=short
    else
        pytest "$test_path" -v --tb=short
    fi
    echo -e "${GREEN}✓ $test_type tests passed${NC}"
    echo ""
}

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Warning: Virtual environment not activated"
    echo "Consider activating it: source venv/bin/activate"
    echo ""
fi

# Run unit tests
run_tests "Unit" "tests/test_*.py" "unit"

# Run integration tests
run_tests "Integration" "tests/test_integration.py" "integration"

# Run E2E tests (optional, can be slow)
if [ "$1" == "--e2e" ]; then
    run_tests "E2E" "tests/test_e2e.py" "e2e"
fi

# Run with coverage if requested
if [ "$1" == "--coverage" ]; then
    echo -e "${BLUE}Running tests with coverage...${NC}"
    pytest tests/ -v --cov=src --cov-report=html --cov-report=term-missing
    echo -e "${GREEN}Coverage report generated in htmlcov/index.html${NC}"
    echo ""
fi

echo "=========================================="
echo -e "${GREEN}All tests completed!${NC}"
echo "=========================================="
