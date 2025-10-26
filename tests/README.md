# KaryaKarta Agent - Testing Guide

## Overview

Comprehensive test suite for the KaryaKarta Agent covering Phase 1 and Phase 2 refactoring. The tests ensure code quality, prevent regressions, and validate bug fixes.

## Test Structure

```
tests/
├── conftest.py              # Pytest fixtures and configuration
├── requirements-test.txt    # Test dependencies
├── unit/                    # Unit tests (isolated components)
│   ├── test_models.py      # Data model tests
│   ├── test_search_tool.py # SearchTool tests
│   └── test_scraper_tool.py # ScraperTool tests
└── integration/             # Integration tests (future)
    └── (to be implemented)
```

## Installation

Install test dependencies:

```bash
cd karyakarta-agent
pip install -r tests/requirements-test.txt
```

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test File
```bash
pytest tests/unit/test_models.py
```

### Run Specific Test Class
```bash
pytest tests/unit/test_search_tool.py::TestSearchToolValidation
```

### Run Specific Test
```bash
pytest tests/unit/test_search_tool.py::TestSearchToolValidation::test_validate_with_q_parameter
```

### Run with Coverage Report
```bash
pytest --cov=src --cov-report=html
# Open htmlcov/index.html in browser to view detailed coverage
```

### Run Only Unit Tests
```bash
pytest -m unit
```

### Run with Verbose Output
```bash
pytest -v
```

### Run and Stop on First Failure
```bash
pytest -x
```

## Test Categories

### Unit Tests (`-m unit`)
- Fast execution (< 1 second per test)
- Isolated components with mocking
- No external dependencies
- High coverage of edge cases

### Integration Tests (`-m integration`)
- Test component interactions
- May use real services (mocked in CI)
- Slower execution
- End-to-end scenarios

## Test Coverage

### Current Coverage

**Phase 1 & 2 Components:**
- ✅ Data Models (TaskRequest, TaskResponse, AgentMessage, ToolResult)
- ✅ SearchTool (with parameter handling fix)
- ✅ ScraperTool (with parameter handling fix)
- ✅ BaseTool abstract class functionality

**Coverage Goals:**
- Unit Tests: 90%+ coverage
- Critical Paths: 100% coverage
- Integration Tests: Major workflows

## Key Test Features

### 1. Parameter Handling Tests

Tests verify the bug fix for LangChain parameter passing:

```python
# Tests handle both parameter formats
def test_validate_with_nested_kwargs():
    tool = SearchTool()
    # LangChain passes: {'kwargs': {'q': 'query'}}
    assert tool.validate_params(kwargs={"q": "test"}) is True
```

### 2. Mock External Services

All tests use mocks to avoid real API calls:

```python
@patch('src.tools.search.GoogleSerperAPIWrapper')
def test_execute_successful_search(self, mock_wrapper):
    # No real API calls made
    mock_search = Mock()
    mock_search.run.return_value = "Mock results"
```

### 3. Edge Case Testing

Comprehensive edge case coverage:
- Empty/invalid parameters
- Very long inputs
- Special characters
- Unicode support
- Error conditions

## Fixtures

Common test fixtures available (from `conftest.py`):

- `mock_settings`: Mocked Settings configuration
- `mock_logger`: Mocked LoggingService
- `sample_task_request`: Sample TaskRequest
- `sample_agent_message_*`: Various AgentMessage types
- `sample_tool_result_*`: Success/failure ToolResults
- `mock_serper_api_response`: Mock Google search response
- `mock_playwright_*`: Mock Playwright components

## Writing New Tests

### Example Unit Test

```python
import pytest
from src.tools.my_tool import MyTool

class TestMyTool:
    """Tests for MyTool."""
    
    def test_initialization(self, mock_logger):
        """Test MyTool initialization."""
        tool = MyTool(logger=mock_logger)
        assert tool.logger == mock_logger
    
    def test_validation(self):
        """Test parameter validation."""
        tool = MyTool()
        assert tool.validate_params(param="value") is True
        assert tool.validate_params() is False
    
    @patch('src.tools.my_tool.ExternalAPI')
    def test_execution(self, mock_api):
        """Test successful execution."""
        mock_api.return_value.call.return_value = "result"
        tool = MyTool()
        result = tool.execute(param="value")
        assert result.success is True
```

### Testing Best Practices

1. **One assertion per test** (when possible)
2. **Clear test names** describing what is tested
3. **Use fixtures** for common setup
4. **Mock external dependencies**
5. **Test both success and failure paths**
6. **Include edge cases**

## Continuous Integration

Tests run automatically on:
- Pull requests
- Main branch commits
- Pre-deployment validation

### CI Configuration (GitHub Actions example)

```yaml
- name: Run tests
  run: |
    pip install -r tests/requirements-test.txt
    pytest --cov=src --cov-report=xml
```

## Bug Fixes Validated by Tests

### SearchTool Parameter Handling
**Issue:** LangChain passed `{'kwargs': {'q': 'query'}}` but tool expected `{'query': 'query'}`

**Fix:** 
- Accept both `query` and `q` parameter names
- Handle nested `kwargs` structure
- Add type guards for None checks

**Tests:**
- `test_validate_with_q_parameter`
- `test_validate_with_nested_kwargs`
- `test_execute_with_nested_kwargs`

### ScraperTool Parameter Handling
**Issue:** Potential similar issue with nested kwargs

**Fix:**
- Preemptive fix to handle nested kwargs
- Consistent with SearchTool implementation

**Tests:**
- `test_validate_with_nested_kwargs`
- `test_execute_with_nested_kwargs`

## Troubleshooting

### Import Errors
```bash
# Ensure you're in the correct directory
cd karyakarta-agent
# Check Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### Missing Dependencies
```bash
pip install -r tests/requirements-test.txt
```

### Pylance Errors
Pylance errors in test files are cosmetic - tests will run fine. They occur because pytest is not installed in the VSCode environment, only in the virtual environment.

## Future Test Additions

### Phase 3 Tests (Planned)
- Agent pooling tests
- Memory/session tests
- New tool tests (Calculator, Extractor, Places, Events)
- API endpoint integration tests
- WebSocket communication tests
- Performance/load tests

## Contributing

When adding new features:
1. Write tests first (TDD approach)
2. Ensure all tests pass before committing
3. Maintain >90% code coverage
4. Update this README if adding new test categories

## Contact

For questions about testing:
- Review existing tests for examples
- Check pytest documentation: https://docs.pytest.org
- Check conftest.py for available fixtures
