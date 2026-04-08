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


class TestColumnProjectionCustomMethods:
    """Verify custom query methods do not use SELECT * — not just the _columns attribute."""

    def _get_source(self, module_path: str) -> str:
        """Read file source directly to check raw SQL strings."""
        import os
        # Resolve relative to project root (where pytest is run from)
        with open(module_path, 'r', encoding='utf-8') as f:
            return f.read()

    def test_client_repo_no_select_star_in_custom_methods(self):
        """All ClientRepository custom methods must use explicit column list."""
        import re
        source = self._get_source('repositories/clients/client_repository.py')
        # Strip comment-only lines before scanning
        lines = [l for l in source.split('\n') if not l.strip().startswith('#')]
        code = '\n'.join(lines)
        matches = re.findall(r'SELECT \*', code)
        assert len(matches) == 0, (
            f"Found {len(matches)} SELECT * occurrences in client_repository.py: {matches}"
        )

    def test_user_repo_no_select_star_in_custom_methods(self):
        """UserRepository simple query methods must use explicit column list."""
        import re
        source = self._get_source('repositories/users/user_repository.py')
        lines = [l for l in source.split('\n') if not l.strip().startswith('#')]
        code = '\n'.join(lines)
        matches = re.findall(r'SELECT \*', code)
        assert len(matches) == 0, (
            f"Found {len(matches)} SELECT * occurrences in user_repository.py: {matches}"
        )

    def test_client_repo_search_uses_columns(self):
        """search() must use SELECT {self._columns}, not SELECT *."""
        import re
        source = self._get_source('repositories/clients/client_repository.py')
        search_block = re.search(r'def search\(.*?\n(?=    def |\Z)', source, re.DOTALL)
        assert search_block, "search() method not found"
        assert 'SELECT *' not in search_block.group(), "search() still uses SELECT *"

    def test_client_repo_find_by_email_uses_columns(self):
        """find_by_email() must use SELECT {self._columns}, not SELECT *."""
        import re
        source = self._get_source('repositories/clients/client_repository.py')
        block = re.search(r'def find_by_email\(.*?\n(?=    def |\Z)', source, re.DOTALL)
        assert block, "find_by_email() method not found"
        assert 'SELECT *' not in block.group(), "find_by_email() still uses SELECT *"

    def test_client_repo_get_active_clients_uses_columns(self):
        """get_active_clients() must use SELECT {self._columns}, not SELECT *."""
        import re
        source = self._get_source('repositories/clients/client_repository.py')
        block = re.search(r'def get_active_clients\(.*?\n(?=    def |\Z)', source, re.DOTALL)
        assert block, "get_active_clients() method not found"
        assert 'SELECT *' not in block.group(), "get_active_clients() still uses SELECT *"

    def test_client_repo_get_recent_clients_uses_columns(self):
        """get_recent_clients() must use SELECT {self._columns}, not SELECT *."""
        import re
        source = self._get_source('repositories/clients/client_repository.py')
        block = re.search(r'def get_recent_clients\(.*?\n(?=    def |\Z)', source, re.DOTALL)
        assert block, "get_recent_clients() method not found"
        assert 'SELECT *' not in block.group(), "get_recent_clients() still uses SELECT *"

    def test_user_repo_get_by_email_uses_columns(self):
        """get_by_email() must use SELECT {self._columns}, not SELECT *."""
        import re
        source = self._get_source('repositories/users/user_repository.py')
        block = re.search(r'def get_by_email\(.*?\n(?=    def |\Z)', source, re.DOTALL)
        assert block, "get_by_email() method not found"
        assert 'SELECT *' not in block.group(), "get_by_email() still uses SELECT *"

    def test_user_repo_get_by_role_uses_columns(self):
        """get_by_role() must use SELECT {self._columns}, not SELECT *."""
        import re
        source = self._get_source('repositories/users/user_repository.py')
        block = re.search(r'def get_by_role\(.*?\n(?=    def |\Z)', source, re.DOTALL)
        assert block, "get_by_role() method not found"
        assert 'SELECT *' not in block.group(), "get_by_role() still uses SELECT *"

    def test_user_repo_get_active_users_uses_columns(self):
        """get_active_users() must use SELECT {self._columns}, not SELECT *."""
        import re
        source = self._get_source('repositories/users/user_repository.py')
        block = re.search(r'def get_active_users\(.*?\n(?=    def |\Z)', source, re.DOTALL)
        assert block, "get_active_users() method not found"
        assert 'SELECT *' not in block.group(), "get_active_users() still uses SELECT *"
