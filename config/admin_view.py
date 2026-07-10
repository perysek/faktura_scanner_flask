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


def emp_exclusion_sql(col_expr: str) -> tuple:
    """Append-ready exclusion clause for an employee-id column/expression.

    Args:
        col_expr: the SQL expression identifying the employee, e.g.
            ``'a.employee_id'`` for a joined appointments alias, ``'e.id'`` for the
            employees table, or ``'cp.preferred_employee_id'`` for a preference row.
            This is ALWAYS a trusted, hard-coded column name — never user input.

    Returns:
        ``(clause, params)`` where ``clause`` begins with ``' AND '`` and is ready
        to concatenate onto an existing ``WHERE`` (every query that uses it already
        has at least an ``is_deleted = FALSE`` predicate). Returns ``('', [])`` when
        there is nothing to hide, so the caller's SQL is unchanged in that case.
    """
    ids = hidden_ids_to_exclude()
    if not ids:
        return '', []
    placeholders = ','.join(['%s'] * len(ids))
    return f' AND {col_expr} NOT IN ({placeholders}) ', list(ids)


def is_employee_hidden(employee_id: int) -> bool:
    """True when this employee must be treated as non-existent for the current
    viewer — i.e. they are superuser-linked AND admin view is OFF.

    Route-level guard for per-employee *detail* / *analytics* endpoints reached by
    explicit id (where a query-level NOT IN would only empty the result rather than
    404). Returns False under admin view (nothing is hidden then)."""
    try:
        return int(employee_id) in hidden_ids_to_exclude()
    except (TypeError, ValueError):
        return False


def emp_exclusion_sql_inline(col_expr: str) -> str:
    """Param-free sibling of ``emp_exclusion_sql`` for complex multi-CTE queries.

    Returns just the clause (``' AND col NOT IN (3,7) '`` or ``''``) with the ids
    inlined, so it can be dropped into a query that already has many positional
    placeholders without disturbing their order — the analytics aggregates, where
    the same appointments/employees scoping recurs across several CTEs, are the
    reason this exists.

    Injection-safe by construction: the ids are this app's own ``employees.id``
    primary keys returned by :func:`get_hidden_employee_ids`, never user input, and
    each is forced through ``int()`` here so a non-integer can only raise, never
    reach the SQL text. Still one choke-point — same hidden-set source, second
    render style.
    """
    ids = hidden_ids_to_exclude()
    if not ids:
        return ''
    id_list = ','.join(str(int(i)) for i in ids)
    return f' AND {col_expr} NOT IN ({id_list}) '
