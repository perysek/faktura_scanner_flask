"""
Tests for AuditRepository.safe_log_event — the de-swallowing audit wrapper
(improvement area #7).

The old call sites used ``try: log_event(...) except Exception: pass``, so a
failed audit write was indistinguishable from a successful one. safe_log_event
guarantees a failure is either loud (logged at ERROR) or fatal (critical=True),
never silent. These tests lock that contract in.
"""
import logging

import pytest
from unittest.mock import patch

from repositories.audit_repository import AuditRepository


class TestSafeLogEvent:
    """Contract: never silently lose an audit write."""

    def test_returns_true_and_delegates_on_success(self):
        """Happy path: log_event is called with the kwargs, returns True."""
        repo = AuditRepository()
        with patch.object(repo, 'log_event') as mock_log:
            result = repo.safe_log_event(
                entity_type='login', action='LOGIN', user_id=1,
            )
        assert result is True
        mock_log.assert_called_once_with(
            entity_type='login', action='LOGIN', user_id=1,
        )

    def test_non_critical_failure_is_logged_and_swallowed(self, caplog):
        """Default (critical=False): failure logged at ERROR, returns False, no raise."""
        repo = AuditRepository()
        with caplog.at_level(logging.ERROR, logger='repositories.audit_repository'):
            with patch.object(repo, 'log_event', side_effect=RuntimeError('db down')):
                result = repo.safe_log_event(entity_type='login', action='LOGIN')
        assert result is False
        assert 'AUDIT WRITE FAILED' in caplog.text

    def test_critical_failure_reraises(self):
        """critical=True: the underlying exception propagates so the caller fails."""
        repo = AuditRepository()
        with patch.object(repo, 'log_event', side_effect=RuntimeError('db down')):
            with pytest.raises(RuntimeError, match='db down'):
                repo.safe_log_event(
                    critical=True, entity_type='invoice', action='UPDATE',
                )
