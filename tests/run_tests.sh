#!/bin/bash
# Script to run all tests for Service Launcher

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "Starting Service Launcher Test Suite..."

# 1. Check for virtual environment
if [ -d "../venv" ]; then
    source ../venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# 2. Install test dependencies if needed
if ! command -v pytest &> /dev/null; then
    echo "Installing test dependencies..."
    pip install -r requirements-test.txt
fi

# 3. Run unit tests (logic)
echo -e "\nRunning Unit Tests..."
python3 test_logic.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Unit Tests Passed!${NC}"
else
    echo -e "${RED}Unit Tests Failed!${NC}"
    exit 1
fi

# 4. Run API tests with pytest
echo -e "\nRunning API Tests..."
pytest test_api.py
if [ $? -eq 0 ]; then
    echo -e "${GREEN}API Tests Passed!${NC}"
else
    echo -e "${RED}API Tests Failed!${NC}"
    exit 1
fi

echo -e "\n${GREEN}All tests passed successfully!${NC}"
