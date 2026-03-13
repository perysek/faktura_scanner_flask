# Testing Patterns

**Analysis Date:** 2026-03-13

## Test Framework

**Runner:**
- pytest (inferred from test structure, not explicitly in requirements.txt)
- Test files found in `tests/` directory
- No `pytest.ini` or `pyproject.toml` test configuration found

**Assertion Library:**
- Standard Python `assert` statements
- unittest.mock for mocking (`from unittest.mock import Mock, patch`)

**Run Commands:**
```bash
pytest                 # Run all tests
pytest tests/          # Run specific test directory
pytest -v             # Verbose output
pytest --cov          # Coverage report (if pytest-cov installed)
```

**Test Dependencies:**
- `pytest` (not in requirements.txt but implied by test structure)
- `unittest.mock` (standard library, used for mocking)
- `dateutil` (in requirements.txt, used for date calculations in tests)

## Test File Organization

**Location:**
- Co-located in parallel `tests/` directory structure
- Not next to source code
- Test directory mirrors source organization: `tests/repositories/analytics/test_analytics_repository.py` → `repositories/analytics/analytics_repository.py`

**Naming:**
- Test files: `test_[feature].py`
- Test classes: `Test[Feature]` (PascalCase)
- Test methods: `test_[behavior]()` (snake_case)

**Structure:**
```
tests/
├── __init__.py
├── repositories/
│   ├── __init__.py
│   └── analytics/
│       ├── __init__.py
│       └── test_analytics_repository.py
```

## Test Structure

**Suite Organization:**
```python
class TestDateRanges:
    """Test date range calculation for different periods"""

    def setup_method(self):
        """Set up test fixtures before each test"""
        self.repo = AnalyticsRepository()

    def test_current_month_ranges(self):
        """Current month should return this month vs. last month"""
        ref = date(2026, 2, 15)  # Feb 15, 2026
        current_start, current_end, prev_start, prev_end = self.repo.get_date_ranges('current_month', ref)

        assert current_start == date(2026, 2, 1)
        assert current_end == date(2026, 2, 28)
        assert prev_start == date(2026, 1, 1)
        assert prev_end == date(2026, 1, 31)
```

**Patterns:**

1. **Setup Pattern:**
   - Use `setup_method(self)` to initialize fixtures before each test
   - Instantiate repositories/services in setup
   - Example: `self.repo = AnalyticsRepository()`

2. **Teardown Pattern:**
   - No explicit teardown shown in current tests
   - Repositories handle database cleanup via connection management
   - Mock connections don't require cleanup

3. **Assertion Pattern:**
   - Direct `assert expected == actual` statements
   - Multiple assertions per test method (5-10 assertions per method observed)
   - Assertion description in docstrings, not assertion messages

## Mocking

**Framework:** `unittest.mock` (standard library)

**Patterns:**
```python
from unittest.mock import Mock, patch

@patch('repositories.analytics.analytics_repository.DatabaseConnection')
def test_get_revenue_summary_executes_correct_query(self, mock_db):
    """Revenue summary should query appointments and income_records"""
    mock_conn = Mock()
    mock_cursor = Mock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = {
        'total_appointments': 124,
        'unique_clients': 87,
        'total_revenue': 45600.00,
        'avg_ticket': 367.74,
        'total_commissions': 18240.00
    }
    mock_db.get_connection.return_value = mock_conn

    start = date(2026, 2, 1)
    end = date(2026, 2, 28)
    result = self.repo.get_revenue_summary(start, end)

    # Verify query was executed
    assert mock_cursor.execute.called
    query = mock_cursor.execute.call_args[0][0]
    assert 'appointments' in query.lower()
    assert 'income_records' in query.lower()
```

**What to Mock:**
- Database connections: `DatabaseConnection.get_connection()`
- External services: Email, OCR, API clients
- Repository methods when testing services
- Don't mock the class under test (test the real code)

**What NOT to Mock:**
- Model objects (dataclasses)
- Validators and utility functions
- Core business logic in services (unless testing error paths)
- Date/time unless testing specific date logic

## Fixtures and Factories

**Test Data:**
- No centralized fixture factories found
- Data created inline in test methods
- Example from `test_analytics_repository.py`:
  ```python
  def test_get_employee_performance_includes_cost_calculations(self, mock_db):
      """Employee performance should calculate Polish employer costs"""
      mock_conn = Mock()
      mock_cursor = Mock()
      mock_conn.cursor.return_value = mock_cursor
      mock_cursor.fetchall.return_value = [
          {
              'id': 1,
              'employee_name': 'Anna Kowalska',
              'base_salary': 4000.00,
              'cost_rate': 0.22,
              # ... more fields ...
          }
      ]
      mock_db.get_connection.return_value = mock_conn
  ```

**Location:**
- No `conftest.py` or `fixtures/` directory
- Fixtures created per test class in `setup_method()`
- Test data hardcoded with realistic Polish names and values

## Coverage

**Requirements:** No explicit coverage targets defined

**View Coverage:**
```bash
pytest --cov=repositories --cov-report=html
pytest --cov=services --cov-report=term-missing
```

**Current State:**
- Only `tests/repositories/analytics/` has test coverage
- Most application code (routes, services) has no automated tests
- Tests focus on repository layer (data access layer)

## Test Types

**Unit Tests:**
- Location: `tests/repositories/analytics/test_analytics_repository.py`
- Scope: Test single repository methods in isolation
- Approach: Mock database connections, verify query construction and result parsing
- Example: `test_current_month_ranges()` tests date calculation without database

**Integration Tests:**
- Not found in current codebase
- Would need database setup with fixtures
- No test database or setup scripts observed

**E2E Tests:**
- Not used in this codebase
- No Playwright, Selenium, or similar framework configured
- Manual testing via Flask development server

## Common Patterns

**Async Testing:**
- Not applicable (no async code in codebase)
- All operations are synchronous

**Error Testing:**
- Service methods raise `AppointmentError` exceptions
- Error handling tested by catching exceptions in routes
- No explicit error path tests in test suite
- Example pattern from `services/appointment_service.py`:
  ```python
  if not calculation:
      raise AppointmentError(
          "Pracownik nie może wykonać jednej lub więcej wybranych usług"
      )
  ```
- Would test with:
  ```python
  def test_create_appointment_raises_when_employee_cannot_perform_service(self):
      """Should raise AppointmentError if employee can't perform any service"""
      service = AppointmentBusinessService()
      with pytest.raises(AppointmentError) as exc_info:
          service.create_appointment(
              client_id=1, employee_id=1,
              service_ids=[999],  # Non-existent service
              appt_date=date.today(),
              start_time=time(10, 0)
          )
      assert "nie może wykonać" in str(exc_info.value)
  ```

**Date Testing:**
- Tests use fixed reference dates to avoid flakiness
- Example from `test_analytics_repository.py`:
  ```python
  def test_current_month_ranges(self):
      """Current month should return this month vs. last month"""
      ref = date(2026, 2, 15)  # Fixed date, not datetime.now()
      current_start, current_end, prev_start, prev_end = self.repo.get_date_ranges('current_month', ref)
      assert current_start == date(2026, 2, 1)
  ```

**Validation Testing:**
- Validators tested indirectly through service methods
- Example: `NIPValidator.validate()` and `IBANValidator.validate()` (in `utils/validators.py`)
- Would test with:
  ```python
  def test_nip_validator_rejects_invalid_nip(self):
      """Should reject NIP with invalid checksum"""
      assert not NIPValidator.validate("12345678901")

  def test_nip_validator_accepts_valid_nip(self):
      """Should accept NIP with correct checksum"""
      assert NIPValidator.validate("1234567890")  # Valid example
  ```

## Testing Best Practices Observed

1. **Test Class Organization:**
   - Group related tests in test classes
   - One responsibility per class
   - Clear, descriptive class names: `TestDateRanges`, `TestRevenueSummary`, `TestEmployeePerformance`

2. **Descriptive Test Names:**
   - Test method names describe the behavior being tested
   - Docstrings explain the assertion: `"""Current month should return this month vs. last month"""`

3. **Fixture Isolation:**
   - Each test method gets fresh fixtures via `setup_method()`
   - No shared mutable state between tests

4. **Mock Verification:**
   - Tests verify mocks were called: `assert mock_cursor.execute.called`
   - Tests inspect mock call arguments: `query = mock_cursor.execute.call_args[0][0]`

5. **Given/When/Then Not Explicitly Used:**
   - Tests follow implicit Given (setup) → When (action) → Then (assertion) pattern
   - Not using explicit comments or structure (could be improved)

## Test Coverage Gaps

**Not Tested:**
- Route handlers (no route tests)
- Service layer business logic (no service tests except through mocking)
- OCR pipeline
- Email handling
- Authentication/authorization
- Most of appointments/clients/services modules

**Priority for Adding Tests:**
1. Service layer (appointment creation, validation, pricing)
2. Authentication routes (login, logout, password reset)
3. API endpoints (CRUD operations, data validation)
4. Error handling paths (validation failures, conflicts)

## Running Tests

**Basic Execution:**
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/repositories/analytics/test_analytics_repository.py

# Run specific test class
pytest tests/repositories/analytics/test_analytics_repository.py::TestDateRanges

# Run specific test method
pytest tests/repositories/analytics/test_analytics_repository.py::TestDateRanges::test_current_month_ranges

# Verbose output
pytest -v

# Stop on first failure
pytest -x
```

**With Coverage:**
```bash
# Install pytest-cov if needed
pip install pytest-cov

# Generate coverage report
pytest --cov=repositories --cov=services --cov-report=html

# View coverage for specific module
pytest --cov=repositories.analytics --cov-report=term-missing
```

**Test Database Setup:**
- No test database configuration found
- Would need to add PostgreSQL fixture or use SQLite for tests
- Currently only unit tests with mocked database connections

---

*Testing analysis: 2026-03-13*
