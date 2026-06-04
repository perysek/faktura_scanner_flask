"""
AuditableMixin — opt-in, data-layer audit for write repositories (improvement #7, Step 3).

The audit log used to be *opt-in at the route layer*: a row was written only where a
developer remembered to call ``AuditRepository.log_event()``. Coverage was therefore
patchy by construction, and a refactor that dropped a call silently lost the trail.

This mixin moves auditing INTO the repository. A repo that mixes it in and sets
``audit_entity_type`` can call ``self._audit(...)`` from its own mutation methods, so
"the mutation happened" and "the mutation was audited" live in the same place and can't
drift apart.

Design decisions worth knowing:

* **Transaction-aware, atomic when wrapped.** The audit write goes through
  ``AuditRepository`` → ``BaseRepository._execute`` → ``safe_commit``. So when the
  mutation runs inside a ``managed_transaction`` the audit row defers and commits
  atomically with the data write. To *keep* that atomicity, a failed audit write
  **inside a transaction is re-raised** (rolling the whole unit back). **Outside** a
  transaction it is, by default, logged-and-swallowed (Step 1 ``safe_log_event``
  semantics) so a monitoring hiccup can't break an already-committed business op.
  Pass ``critical=True`` to force a re-raise even outside a transaction.

* **Context-safe.** ``current_user`` is read defensively — it is absent in background
  threads, scripts, and public (unauthenticated) flows, and reading it must never crash
  the mutation. No request/login context → ``(None, None)``.

* **Not a blanket "audit every write".** The mixin is a *tool*: the repo decides which
  methods matter (e.g. create / full update / delete) and skips high-frequency,
  low-forensic-value ones (counter bumps, last-visit timestamps).

Usage::

    class SellerRepository(AuditableMixin, BaseRepository):
        audit_entity_type = 'seller'

        def create(self, seller):
            new_id = self._execute_insert(query, params)
            self._audit('CREATE', new_id, label=seller.seller_name)
            return new_id
"""
import logging

from config.database import is_in_transaction
from repositories.audit_repository import AuditRepository

logger = logging.getLogger(__name__)


def _current_user_identity():
    """Return ``(user_id, user_name)`` for the active user, or ``(None, None)`` when
    there is no request/login context (background threads, public booking, scripts).

    Never raises: a missing app/request context or an anonymous user yields Nones.
    """
    try:
        from flask_login import current_user
        if getattr(current_user, 'is_authenticated', False):
            return getattr(current_user, 'id', None), getattr(current_user, 'full_name', None)
    except Exception:
        # No app/request context (e.g. scheduler thread) — current_user proxy raises.
        pass
    return None, None


class AuditableMixin:
    """Gives a repository a uniform ``_audit`` helper writing one ``audit_log`` row.

    Mix it in *before* ``BaseRepository`` (``class X(AuditableMixin, BaseRepository)``)
    and set ``audit_entity_type``. The mixin deliberately defines no ``__init__`` so the
    normal ``BaseRepository.__init__(table_name)`` chain is untouched.
    """

    #: e.g. 'seller', 'client'. Required — ``_audit`` refuses to log without it.
    audit_entity_type: str = None

    def _audit(self, action, entity_id, *, label=None, field_name=None,
               old=None, new=None, critical=False):
        """Write an audit_log row describing a mutation this repo just performed.

        Args:
            action: 'CREATE' | 'UPDATE' | 'DELETE' (free-form, matches existing usage).
            entity_id: primary key of the affected row.
            label: human-readable entity label (e.g. the seller's name).
            field_name / old / new: optional per-field change detail. ``old``/``new``
                are str-coerced so callers can pass raw values.
            critical: force re-raise on audit failure even outside a transaction.
        """
        if not self.audit_entity_type:
            raise ValueError(
                f"{type(self).__name__} uses AuditableMixin but did not set "
                f"audit_entity_type"
            )
        uid, uname = _current_user_identity()
        # Inside a managed_transaction the audit MUST fail loud so the surrounding
        # transaction rolls back (data + audit stay atomic). Outside one, honour the
        # caller's `critical` flag (default: log the failure, don't break the op).
        AuditRepository().safe_log_event(
            critical=critical or is_in_transaction(),
            entity_type=self.audit_entity_type,
            action=action,
            entity_id=entity_id,
            entity_label=label,
            field_name=field_name,
            old_value=None if old is None else str(old),
            new_value=None if new is None else str(new),
            user_id=uid,
            user_name=uname,
        )
