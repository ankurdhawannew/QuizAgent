#!/bin/bash
# Simple shell script to run QuizAgent end-to-end tests

set -e  # Exit on error

echo "======================================================================"
echo "🧪 QuizAgent End-to-End Test Suite"
echo "======================================================================"
echo ""

# Check if pytest is installed
if ! python -m pytest --version > /dev/null 2>&1; then
    echo "❌ pytest is not installed"
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
fi

# Check if test file exists
if [ ! -f "test_e2e.py" ]; then
    echo "❌ Test file not found: test_e2e.py"
    exit 1
fi

echo "🚀 Running tests..."
echo "----------------------------------------------------------------------"
echo ""

# Run pytest
python -m pytest test_e2e.py -v --tb=short --color=yes

# Capture exit code
EXIT_CODE=$?

echo ""
echo "----------------------------------------------------------------------"

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All tests passed!"
    echo ""
    echo "======================================================================"
    echo "🎉 Test Suite Completed Successfully"
    echo "======================================================================"
else
    echo "❌ Some tests failed"
    echo ""
    echo "======================================================================"
    echo "⚠️  Test Suite Completed with Failures"
    echo "======================================================================"
fi

exit $EXIT_CODE

