# QuizAgent End-to-End Test Suite

This directory contains comprehensive end-to-end tests for the QuizAgent application.

## Overview

The test suite verifies all major functionality of the QuizAgent application:

- ✅ Database operations (initialization, saving, retrieving questions)
- ✅ Question generation and retrieval
- ✅ User history tracking
- ✅ Scoring system
- ✅ Coaching agent functionality
- ✅ Error reporting and validation
- ✅ Complete quiz flow from generation to completion
- ✅ Question filtering to prevent duplicates

## Prerequisites

1. **Install testing dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   This will install:
   - `pytest` - Testing framework
   - `pytest-mock` - Mocking utilities

2. **Environment Setup:**
   - No API key required for most tests (they use mocks)
   - Tests use temporary databases and files
   - All test data is cleaned up after tests complete

## Running Tests

### Option 1: Using the Test Runner Script (Recommended)

```bash
python run_tests.py
```

This script will:
- Check for required dependencies
- Run all tests with verbose output
- Provide a summary of results

### Option 2: Using pytest Directly

```bash
# Run all tests
pytest test_e2e.py -v

# Run specific test class
pytest test_e2e.py::TestDatabaseOperations -v

# Run with coverage (if pytest-cov is installed)
pytest test_e2e.py --cov=. --cov-report=html
```

### Option 3: Run Tests from Python

```bash
python test_e2e.py
```

## Test Structure

The test suite is organized into the following test classes:

### 1. `TestDatabaseOperations`
Tests database initialization, saving, retrieving, and querying questions.

**Tests:**
- Database initialization
- Saving questions
- Retrieving questions
- Getting questions by difficulty distribution
- Marking questions as invalid

### 2. `TestQuestionGeneration`
Tests question generation flow and database integration.

**Tests:**
- Question generation flow with mocked API

### 3. `TestUserHistory`
Tests user quiz history tracking and retrieval.

**Tests:**
- Saving user quiz history
- Retrieving previous questions

### 4. `TestScoring`
Tests the scoring system.

**Tests:**
- Scoring calculation for different difficulty levels
- Score calculation for complete quiz

### 5. `TestCoachingAgent`
Tests the Socratic method coaching agent.

**Tests:**
- Starting coaching session
- Getting coaching responses

### 6. `TestErrorReporting`
Tests error reporting and validation.

**Tests:**
- Error report verification
- Marking questions as invalid after report

### 7. `TestEndToEndFlow`
Comprehensive integration tests for complete workflows.

**Tests:**
- Complete quiz flow (generation → taking → scoring → history)
- Question filtering to prevent duplicates

## Test Data

- All tests use temporary files and databases
- Test data is automatically cleaned up after each test
- No modifications to production data
- Tests are isolated and can run in parallel

## Expected Output

When tests pass successfully, you should see:

```
======================================================================
🧪 QuizAgent End-to-End Test Suite
======================================================================

📋 Checking dependencies...
✅ All dependencies installed

🚀 Running tests...
----------------------------------------------------------------------

test_e2e.py::TestDatabaseOperations::test_database_initialization PASSED
test_e2e.py::TestDatabaseOperations::test_save_questions PASSED
...
[All test results]

----------------------------------------------------------------------
✅ All tests passed!

======================================================================
🎉 Test Suite Completed Successfully
======================================================================
```

## Troubleshooting

### Import Errors

If you encounter import errors:

1. **Ensure you're in the QuizAgent directory:**
   ```bash
   cd QuizAgent
   ```

2. **Check Python path:**
   ```bash
   python -c "import sys; print(sys.path)"
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Streamlit Import Errors

Tests mock Streamlit to avoid import errors. If you see Streamlit-related errors:

- Ensure `sys.modules['streamlit'] = Mock()` is called before importing QuizAgent
- Check that the mock is properly set up in the test

### Database Lock Errors

If you see database lock errors:

- Ensure tests are not running in parallel (remove `-n` flag if using pytest-xdist)
- Check that temporary databases are being cleaned up properly

### API Mock Errors

If API mocking fails:

- Ensure `unittest.mock` is imported correctly
- Check that patches are applied before API calls
- Verify mock return values match expected format

## Adding New Tests

To add new tests:

1. **Add test methods to appropriate test class:**
   ```python
   def test_new_feature(self):
       """Test description."""
       # Test implementation
       assert condition
   ```

2. **Use fixtures for setup/teardown:**
   ```python
   @pytest.fixture(autouse=True)
   def setup(self):
       # Setup code
       yield
       # Cleanup code
   ```

3. **Mock external dependencies:**
   ```python
   @patch('module.external_function')
   def test_with_mock(self, mock_function):
       mock_function.return_value = expected_value
       # Test code
   ```

## Continuous Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Tests
  run: |
    pip install -r requirements.txt
    python run_tests.py
```

## Test Coverage

To generate coverage reports:

```bash
pip install pytest-cov
pytest test_e2e.py --cov=. --cov-report=html
```

Coverage report will be generated in `htmlcov/index.html`.

## Notes

- Tests use temporary files and databases - no production data is modified
- API calls are mocked to avoid requiring actual API keys
- Tests are designed to be fast and isolated
- All test data is cleaned up automatically

---

**Happy Testing! 🧪**

