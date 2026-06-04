"""
Tests for AuditableMixin (improvement #7 Step 3) and its first wiring into
SellerRepository.

The mixin's contract:
  * builds a uniform audit_log payload from (action, entity_id, label, field, old/new)
  * str-coerces old/new; reads current_user defensively (None outside a login context)
  * is transaction-aware: forces ``critical=True`` inside a managed_transaction (so a
    failed audit rolls the unit back), stays non-critical outside one
  * refuses to log if ``audit_entity_type`` is unset

SellerRepository wiring: create/update/update_name/update_address/delete emit a
'seller' audit row, and only when a row actually changed.
"""
from unittest.mock import Mock, patch

import pytest
from flask import g

from repositories.auditable import AuditableMixin


class _DummyRepo(AuditableMixin):
    audit_entity_type = 'widget'


class TestAuditableMixinPayload:
    def test_builds_payload_and_str_coerces_values(self, app):
        with app.app_context():
            with patch('repositories.auditable.AuditRepository') as MockAudit:
                _DummyRepo()._audit('UPDATE', 5, label='W5',
                                    field_name='price', old=10, new=20)
                kw = MockAudit.return_value.safe_log_event.call_args.kwargs
                assert kw['entity_type'] == 'widget'
                assert kw['action'] == 'UPDATE'
                assert kw['entity_id'] == 5
                assert kw['entity_label'] == 'W5'
                assert kw['field_name'] == 'price'
                assert kw['old_value'] == '10'   # int -> str
                assert kw['new_value'] == '20'
                # None stays None (not the string 'None')
                _DummyRepo()._audit('CREATE', 9)
                kw2 = MockAudit.return_value.safe_log_event.call_args.kwargs
                assert kw2['old_value'] is None and kw2['new_value'] is None

    def test_reads_authenticated_user(self, app):
        with app.app_context():
            mock_user = Mock(is_authenticated=True, id=7, full_name='Anna Nowak')
            with patch('flask_login.current_user', mock_user), \
                 patch('repositories.auditable.AuditRepository') as MockAudit:
                _DummyRepo()._audit('UPDATE', 1)
                kw = MockAudit.return_value.safe_log_event.call_args.kwargs
                assert kw['user_id'] == 7
                assert kw['user_name'] == 'Anna Nowak'

    def test_no_login_context_yields_none_user(self, app):
        """Outside a request/login context current_user access raises — must not crash."""
        with app.app_context():
            with patch('repositories.auditable.AuditRepository') as MockAudit:
                _DummyRepo()._audit('UPDATE', 1)
                kw = MockAudit.return_value.safe_log_event.call_args.kwargs
                assert kw['user_id'] is None and kw['user_name'] is None

    def test_missing_entity_type_raises(self, app):
        class _NoType(AuditableMixin):
            pass
        with app.app_context():
            with pytest.raises(ValueError, match="audit_entity_type"):
                _NoType()._audit('CREATE', 1)


class TestAuditableMixinTransactionAwareness:
    """critical is forced inside a transaction (atomic rollback), honoured outside."""

    def test_critical_forced_inside_transaction(self, app):
        with app.app_context():
            with patch('repositories.auditable.AuditRepository') as MockAudit:
                g._in_transaction = True
                try:
                    _DummyRepo()._audit('UPDATE', 1)
                finally:
                    g._in_transaction = False
                assert MockAudit.return_value.safe_log_event.call_args.kwargs['critical'] is True

    def test_not_critical_outside_transaction(self, app):
        with app.app_context():
            with patch('repositories.auditable.AuditRepository') as MockAudit:
                _DummyRepo()._audit('UPDATE', 1)
                assert MockAudit.return_value.safe_log_event.call_args.kwargs['critical'] is False

    def test_critical_flag_forces_critical_outside_transaction(self, app):
        with app.app_context():
            with patch('repositories.auditable.AuditRepository') as MockAudit:
                _DummyRepo()._audit('DELETE', 1, critical=True)
                assert MockAudit.return_value.safe_log_event.call_args.kwargs['critical'] is True


class TestSellerRepositoryAuditWiring:
    """SellerRepository emits 'seller' audit rows on real mutations only."""

    def _conn(self, *, fetchone=None, rowcount=1):
        cursor = Mock()
        cursor.rowcount = rowcount
        if fetchone is not None:
            cursor.fetchone.return_value = fetchone
        conn = Mock()
        conn.cursor.return_value = cursor
        return conn

    def test_create_emits_seller_create_audit(self, app):
        from repositories.seller_repository import SellerRepository
        from database.models import Seller

        with app.app_context():
            conn = self._conn(fetchone={'id': 12})
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn), \
                 patch('repositories.auditable.AuditRepository') as MockAudit:
                new_id = SellerRepository().create(
                    Seller(seller_nip='1234567890', seller_name='ACME Sp. z o.o.',
                           address='ul. X 1', invoice_count=0))
                assert new_id == 12
                kw = MockAudit.return_value.safe_log_event.call_args.kwargs
                assert kw['entity_type'] == 'seller'
                assert kw['action'] == 'CREATE'
                assert kw['entity_id'] == 12
                assert kw['entity_label'] == 'ACME Sp. z o.o.'

    def test_update_name_emits_audit_with_field(self, app):
        from repositories.seller_repository import SellerRepository

        with app.app_context():
            conn = self._conn(rowcount=1)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn), \
                 patch('repositories.auditable.AuditRepository') as MockAudit:
                ok = SellerRepository().update_name(5, 'Nowa Nazwa')
                assert ok is True
                kw = MockAudit.return_value.safe_log_event.call_args.kwargs
                assert kw['action'] == 'UPDATE'
                assert kw['field_name'] == 'seller_name'
                assert kw['new_value'] == 'Nowa Nazwa'

    def test_no_audit_when_no_row_changed(self, app):
        from repositories.seller_repository import SellerRepository

        with app.app_context():
            conn = self._conn(rowcount=0)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn), \
                 patch('repositories.auditable.AuditRepository') as MockAudit:
                ok = SellerRepository().update_address(999, 'ul. Y 2')
                assert ok is False
                MockAudit.return_value.safe_log_event.assert_not_called()

    def test_delete_emits_seller_delete_audit(self, app):
        from repositories.seller_repository import SellerRepository

        with app.app_context():
            conn = self._conn(rowcount=1)
            with patch('config.database.DatabaseConnection.get_connection', return_value=conn), \
                 patch('repositories.auditable.AuditRepository') as MockAudit:
                ok = SellerRepository().delete(7)
                assert ok is True
                kw = MockAudit.return_value.safe_log_event.call_args.kwargs
                assert kw['entity_type'] == 'seller'
                assert kw['action'] == 'DELETE'
                assert kw['entity_id'] == 7
