"""
Tests: Explicit column projection — verify critical repos don't use SELECT *.
File-scanning and attribute-inspection tests (no DB required).
"""
import inspect


class TestColumnProjection:
    """Verify critical repos use explicit column lists, not SELECT *."""

    def _source(self, module):
        return inspect.getsource(module)

    # --- ClientRepository ---

    def test_client_repo_has_explicit_columns(self):
        from repositories.clients.client_repository import ClientRepository
        repo = ClientRepository.__new__(ClientRepository)
        assert repo._columns != '*', "ClientRepository still uses SELECT *"
        assert 'id' in repo._columns
        assert 'first_name' in repo._columns
        assert 'is_deleted' in repo._columns

    def test_client_repo_columns_match_schema(self):
        from repositories.clients.client_repository import ClientRepository
        repo = ClientRepository.__new__(ClientRepository)
        expected = {
            'id', 'first_name', 'last_name', 'phone', 'email', 'date_of_birth',
            'notes', 'preferences', 'first_visit_date', 'last_visit_date',
            'is_active', 'is_deleted', 'deleted_at', 'created_at', 'updated_at'
        }
        actual = {c.strip() for c in repo._columns.replace('(', '').replace(')', '').split(',')}
        assert actual == expected, f"Column mismatch: missing={expected - actual}, extra={actual - expected}"

    # --- EmployeeRepository ---

    def test_employee_repo_no_select_star(self):
        from repositories.employees import employee_repository
        source = self._source(employee_repository)
        # Strip comments
        lines = [l for l in source.split('\n') if not l.strip().startswith('#')]
        code = '\n'.join(lines)
        assert 'SELECT *' not in code, "SELECT * still present in employee_repository"

    # --- IncomeRepository ---

    def test_income_repo_no_select_star(self):
        from repositories.appointments import income_repository
        source = self._source(income_repository)
        lines = [l for l in source.split('\n') if not l.strip().startswith('#')]
        code = '\n'.join(lines)
        assert 'SELECT *' not in code, "SELECT * still present in income_repository"
