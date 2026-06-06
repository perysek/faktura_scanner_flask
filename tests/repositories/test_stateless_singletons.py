"""
Tests for the stateless-singleton freeze (improvement area #2).

Repositories attached to the Flask app are shared across gthread worker
threads. They are safe only while stateless; ``freeze_repository_singleton``
makes that structurally enforced — a frozen singleton raises on any attempt to
acquire per-instance state. Locally-instantiated repos stay mutable (a per-call
repo may legitimately hold state).
"""
import pytest

from repositories.base_repository import BaseRepository, freeze_repository_singleton


class _FakeRepo(BaseRepository):
    def __init__(self):
        super().__init__('fakes')


class _FakeStandalone:
    """Mimics the standalone `class X:` repos (no BaseRepository base)."""
    def __init__(self):
        self.table = 'x'  # construction-time state — set before freeze


class TestFreezeRepositorySingleton:
    """The freeze helper contract."""

    def test_blocks_setattr_after_freeze(self):
        repo = freeze_repository_singleton(_FakeRepo())
        with pytest.raises(AttributeError, match="frozen shared singleton"):
            repo._cache = {}  # the exact trap from improvement #2

    def test_preserves_construction_state_and_identity(self):
        repo = freeze_repository_singleton(_FakeRepo())
        assert repo.table_name == 'fakes'          # construction-time state kept
        assert isinstance(repo, _FakeRepo)         # IS-A original
        assert isinstance(repo, BaseRepository)
        assert type(repo).__name__ == '_FakeRepo'  # real name preserved

    def test_works_on_standalone_class(self):
        """Most singletons are standalone `class X:` — freeze must cover them."""
        repo = freeze_repository_singleton(_FakeStandalone())
        assert repo.table == 'x'
        with pytest.raises(AttributeError):
            repo.something = 1

    def test_idempotent(self):
        repo = freeze_repository_singleton(_FakeRepo())
        again = freeze_repository_singleton(repo)
        assert again is repo
        with pytest.raises(AttributeError):
            again.x = 1

    def test_unfrozen_repo_stays_mutable(self):
        """Locally-instantiated (non-singleton) repos may hold per-call state."""
        repo = _FakeRepo()
        repo._cache = {}  # allowed — not a shared singleton
        assert repo._cache == {}


class TestAppSingletonsAreFrozen:
    """Every app.*_repo singleton is frozen at attachment in create_app()."""

    def test_basrepository_singleton_is_frozen(self, app):
        with pytest.raises(AttributeError, match="frozen shared singleton"):
            app.invoice_repo._cache = {}

    def test_standalone_singleton_is_frozen(self, app):
        # service_repo is a standalone (class X:) repo — also frozen.
        with pytest.raises(AttributeError, match="frozen shared singleton"):
            app.service_repo._cache = {}

    def test_audit_repo_singleton_is_frozen(self, app):
        with pytest.raises(AttributeError, match="frozen shared singleton"):
            app.audit_repo._cache = {}

    def test_frozen_singleton_keeps_real_type_name(self, app):
        assert type(app.invoice_repo).__name__ == 'InvoiceRepository'
        assert isinstance(app.invoice_repo, BaseRepository)
