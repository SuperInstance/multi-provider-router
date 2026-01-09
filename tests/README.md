# Test Suite for Multi-Provider Router

This directory contains a comprehensive test suite for the multi-provider-router package.

## Test Structure

```
tests/
├── conftest.py                 # Shared fixtures and test configuration
├── test_providers.py           # Tests for all 5 provider implementations
├── test_routing.py             # Tests for routing decision engine and load balancer
├── test_fallback.py            # Tests for circuit breaker and failover logic
├── test_cache.py               # Tests for Redis caching system
├── test_rate_limiter.py        # Tests for rate limiting (token bucket)
├── test_health.py              # Tests for health monitoring
├── test_metrics.py             # Tests for Prometheus metrics collection
└── test_integration.py         # End-to-end integration tests
```

## Running Tests

### Run All Tests

```bash
# Using pytest directly
pytest

# Using the test runner script
python run_tests.py

# With verbose output
pytest -v

# With coverage report
pytest --cov=multi_provider_router --cov-report=html
```

### Run Specific Test Files

```bash
# Test providers
pytest tests/test_providers.py

# Test routing
pytest tests/test_routing.py

# Test fallback
pytest tests/test_fallback.py
```

### Run Tests by Category

```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Fast tests (exclude slow)
pytest -m "not slow"

# Provider tests
pytest -m providers

# Routing tests
pytest -m routing
```

### Run Tests Matching Pattern

```bash
# Run all GLM-related tests
pytest -k glm

# Run all tests with "fallback" in the name
pytest -k fallback
```

## Test Coverage

The test suite targets **80%+ code coverage**. To generate a coverage report:

```bash
# Terminal report
pytest --cov=multi_provider_router --cov-report=term-missing

# HTML report
pytest --cov=multi_provider_router --cov-report=html

# Open HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

## Test Categories

### Unit Tests (`@pytest.mark.unit`)
- Fast, isolated tests
- No external dependencies
- Mock all external services

### Integration Tests (`@pytest.mark.integration`)
- Test interactions between components
- May use external services (mocked)
- Slower than unit tests

### Slow Tests (`@pytest.mark.slow`)
- Long-running tests
- Performance tests
- Load tests

## Fixtures

The `conftest.py` file provides shared fixtures:

- `glm_config`, `openai_config`, `deepseek_config`, `claude_config`, `deepinfra_config` - Provider configurations
- `simple_request`, `complex_request`, `streaming_request` - Sample requests
- `sample_response` - Sample response
- `mock_httpx_client` - Mocked HTTP client
- `mock_redis` - Mocked Redis client
- Provider instances with mocked dependencies

## Writing New Tests

1. **Add test file** in `tests/` directory with `test_*.py` naming
2. **Use fixtures** from `conftest.py` for common test data
3. **Mark tests** appropriately:
   ```python
   @pytest.mark.unit
   def test_something():
       pass

   @pytest.mark.asyncio
   async def test_async_something():
       pass
   ```
4. **Mock external dependencies** (HTTP, Redis, etc.)
5. **Follow naming conventions**: `test_<functionality>_<scenario>`

## CI/CD Integration

The tests are designed to run in CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run tests
  run: |
    pytest --cov=multi_provider_router --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

## Troubleshooting

### Tests Fail with Import Errors

Make sure you've installed the package in development mode:

```bash
pip install -e ".[dev]"
```

### Async Tests Fail

Ensure `pytest-asyncio` is installed:

```bash
pip install pytest-asyncio
```

### Redis Connection Errors

Tests mock Redis by default. If you're testing with real Redis:

```bash
# Start Redis locally
docker run -p 6379:6379 redis
```

## Test Data

Tests use realistic but synthetic data:

- **API keys**: `test-*-key` (not real keys)
- **Requests**: Various complexity levels
- **Responses**: Mocked API responses
- **Costs**: Realistic pricing models

## Contributing

When adding new features:

1. Write tests first (TDD)
2. Ensure all tests pass: `pytest`
3. Maintain coverage > 80%
4. Add integration tests for complex flows
5. Mock external dependencies
6. Document any new fixtures

## Performance Benchmarks

To run performance benchmarks:

```bash
pytest tests/ -m slow --benchmark-only
```

Note: Benchmark tests require `pytest-benchmark`:

```bash
pip install pytest-benchmark
```
