"""
Widok administratora — a single server-side choke-point for hiding the
superuser-linked employee(s) and everything chaining to them.

Business rule (see plan super-user-ux-modifiers-...): the salon owner works as a
normal employee whose activity generates real cash flow, but that activity must
be invisible by default to EVERYONE — including the owner's own normal views.
The only way to reveal it is to log in as a superuser and tick the "Widok
administratora" checkbox, which flips a session-scoped flag.

Every employee-scoped query appends an exclusion clause from ``emp_exclusion_sql``
here. There are NO hand-rolled ``WHERE employee_id != …`` filters scattered around
the codebase — coverage is therefore a single grep for ``emp_exclusion_sql``. That
is deliberate: a pervasive negative filter leaks the moment one call site forgets
it, so all call sites route through this one helper.

No DB migration and no compensation-formula change: the hidden set is computed
live from ``employees JOIN users WHERE users.role = 'superuser'`` and every total
is calculated with the exact same formula as for any other employee — the owner's
row is simply omitted from the result set unless admin view is ON.

Second toggle — "Dane własne" (own data): a superuser with admin view ON can also
tick "Dane własne" to *invert* the choke-point from "exclude the owner" to "show
ONLY my own employee's data" across every page. It is only meaningful while admin
view is ON (enforced server-side: ``own_data_active`` requires ``admin_view_active``).
Both flags feed one resolver (``_scope_mode``) that the two SQL builders and the
route guard read, so the whole app follows the flip with no per-call-site change.
"""
import logging

from flask import g, session
from flask_login import current_user

from config.database import get_db_connection

logger = logging.getLogger(__name__)


def get_hidden_employee_ids() -> tuple:
    """Return the ids of every employee linked to a superuser account.

    This is an *intrinsic property of the data* — it does not depend on who is
    logged in — so it is computable even when logged out. The result is cached on
    ``flask.g`` for the duration of the request: one small query per request,
    reused by every repository that appends the exclusion clause.

    On any DB/context error the set is treated as empty and logged. That fails
    "open" (the owner would become visible), but the only condition that triggers
    it is the database being unreachable — in which case the page is already
    failing elsewhere — so it is preferable to 500-ing every authenticated page
    over a hiding nicety.
    """
    try:
        cached = g.get('_hidden_emp_ids', None)
    except RuntimeError:
        # No application context (e.g. a background thread) — nothing cached and
        # no request to hide data from; behave as "nothing to hide".
        return ()
    if cached is not None:
        return cached

    ids: tuple = ()
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT e.id FROM employees e "
                "JOIN users u ON u.id = e.user_id "
                "WHERE u.role = 'superuser'"
            )
            ids = tuple(r['id'] for r in cur.fetchall())
    except Exception:
        logger.warning("Could not resolve hidden (superuser-linked) employee ids; "
                       "treating the hidden set as empty for this request",
                       exc_info=True)
        ids = ()

    g._hidden_emp_ids = ids
    return ids


def is_superuser() -> bool:
    """True when the current request is an authenticated superuser."""
    try:
        return bool(current_user.is_authenticated
                    and getattr(current_user, 'role', None) == 'superuser')
    except Exception:
        return False


def admin_view_active() -> bool:
    """True only when a logged-in superuser has ticked "Widok administratora".

    The role re-check is the security boundary: a non-superuser who forges
    ``session['admin_view'] = True`` still gets False here, so secret data never
    reaches their views regardless of the cookie they send.
    """
    try:
        return is_superuser() and bool(session.get('admin_view', False))
    except Exception:
        return False


def hidden_ids_to_exclude() -> tuple:
    """The set to hide right now: empty when admin view is ON (reveal everything),
    otherwise the full hidden set."""
    return () if admin_view_active() else get_hidden_employee_ids()


def current_own_employee_id():
    """The employee id linked to the logged-in user, or None. Cached on ``flask.g``.

    Used by "Dane własne" to scope every employee-filtered view to just this
    person. Resolved via ``get_by_user_id`` — a PK-style lookup that is NOT itself
    scope-filtered — so it still returns the owner's own id even though that
    employee is otherwise hidden."""
    try:
        cached = g.get('_own_emp_id', '__unset__')
    except RuntimeError:
        return None
    if cached != '__unset__':
        return cached

    emp_id = None
    try:
        from config.auth_config import get_linked_employee
        emp = get_linked_employee(current_user)
        emp_id = emp['id'] if emp else None
    except Exception:
        emp_id = None
    g._own_emp_id = emp_id
    return emp_id


def own_data_active() -> bool:
    """True only when a superuser has admin view ON *and* has ticked "Dane własne".

    Depends on ``admin_view_active()``, so the "editable only when Widok
    administratora is on" rule is enforced server-side too: with admin view OFF the
    flag is inert no matter what the session cookie holds."""
    try:
        return admin_view_active() and bool(session.get('own_data', False))
    except Exception:
        return False


def _scope_mode() -> tuple:
    """Resolve the current employee-scope filter into one of three modes:

      ``('only', emp_id)``  — Dane własne ON: restrict to the logged-in user's own
                              employee (``emp_id`` may be None → match nothing).
      ``('exclude', ids)``  — default: hide the superuser-linked employee(s).
      ``('all', None)``     — Widok administratora ON (own-data OFF): no filter.

    Every scope decision in the app derives from this single function, so the two
    toggles compose here and nowhere else."""
    if own_data_active():
        return ('only', current_own_employee_id())
    ids = hidden_ids_to_exclude()
    return ('exclude', ids) if ids else ('all', None)


def emp_exclusion_sql(col_expr: str) -> tuple:
    """Append-ready employee-scope clause for an employee-id column/expression.

    Args:
        col_expr: the SQL expression identifying the employee, e.g.
            ``'a.employee_id'`` for a joined appointments alias, ``'e.id'`` for the
            employees table, or ``'cp.preferred_employee_id'`` for a preference row.
            This is ALWAYS a trusted, hard-coded column name — never user input.

    Returns ``(clause, params)`` where ``clause`` begins with ``' AND '`` and is
    ready to concatenate onto an existing ``WHERE`` (every query that uses it
    already has at least one predicate). Depending on the active toggles the clause
    is a ``NOT IN`` (hide the owner), a ``= %s`` (own-data: only me), or empty
    (admin view, reveal everything). The placeholder count always matches
    ``params``.
    """
    mode, val = _scope_mode()
    if mode == 'only':
        if val is None:
            return ' AND 1=0 ', []          # own-data but no linked employee → empty
        return f' AND {col_expr} = %s ', [val]
    if mode == 'exclude':
        placeholders = ','.join(['%s'] * len(val))
        return f' AND {col_expr} NOT IN ({placeholders}) ', list(val)
    return '', []                            # 'all' → no filter


def is_employee_hidden(employee_id: int) -> bool:
    """True when this employee must be treated as non-existent (404) for the
    current viewer.

    Route-level guard for per-employee *detail* / *analytics* / *balance* endpoints
    reached by explicit id (where a query-level filter would only empty the result
    rather than 404). Follows ``_scope_mode``: under "Dane własne" everyone *except*
    the logged-in user is hidden; by default only the superuser-linked employee(s)
    are; under plain admin view nobody is."""
    try:
        eid = int(employee_id)
    except (TypeError, ValueError):
        return False
    mode, val = _scope_mode()
    if mode == 'only':
        return eid != val                    # own-data: all but yourself are hidden
    if mode == 'exclude':
        return eid in val
    return False                             # 'all' → nothing hidden


def emp_exclusion_sql_inline(col_expr: str) -> str:
    """Param-free sibling of ``emp_exclusion_sql`` for complex multi-CTE queries.

    Returns just the clause (``' AND col NOT IN (3,7) '``, ``' AND col = 8 '``,
    ``' AND 1=0 '`` or ``''``) with the ids inlined, so it can be dropped into a
    query that already has many positional placeholders without disturbing their
    order — the analytics aggregates, where the same scoping recurs across several
    CTEs, are the reason this exists.

    Injection-safe by construction: the ids are this app's own ``employees.id``
    primary keys (hidden set or the logged-in user's own id), never user input, and
    each is forced through ``int()`` here so a non-integer can only raise, never
    reach the SQL text. Same ``_scope_mode`` source as everything else — one
    choke-point, second render style.
    """
    mode, val = _scope_mode()
    if mode == 'only':
        if val is None:
            return ' AND 1=0 '
        return f' AND {col_expr} = {int(val)} '
    if mode == 'exclude':
        id_list = ','.join(str(int(i)) for i in val)
        return f' AND {col_expr} NOT IN ({id_list}) '
    return ''
