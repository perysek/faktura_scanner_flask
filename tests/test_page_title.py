"""
Tests for the per-route mobile-header title (P08).

`page_title_for(endpoint)` (config/page_titles.py) maps a Flask endpoint to a
Polish label; the `inject_globals` context processor in app.py exposes it to
templates as `page_title`.

Pure-function tests import from `config.page_titles` (no app factory, no DB).
Integration tests use the shared `app` fixture (conftest), which stubs DB init.
"""
from config.page_titles import PAGE_TITLES, page_title_for


# ── Pure function ────────────────────────────────────────────────────────────

def test_known_endpoint_returns_label():
    assert page_title_for('main.clients_list') == 'Klienci'
    assert page_title_for('main.invoices_list') == 'Faktury'
    assert page_title_for('absence.my_absences') == 'Moje nieobecności'


def test_unmapped_endpoint_returns_empty_string():
    assert page_title_for('main.some_unmapped_view') == ''
    assert page_title_for('totally.unknown') == ''


def test_none_endpoint_returns_empty_string():
    # Called outside a request context, request.endpoint is None.
    assert page_title_for(None) == ''
    assert page_title_for('') == ''


def test_titles_are_nonempty_strings():
    for endpoint, label in PAGE_TITLES.items():
        assert isinstance(label, str) and label.strip(), endpoint


# ── Context processor integration ────────────────────────────────────────────

def test_context_processor_injects_known_title(app):
    """A request to a known route resolves to its page_title via the context
    processor's merged template context."""
    with app.test_request_context('/clients'):
        from flask import request
        endpoint = app.url_map.bind_to_environ(request.environ).match()[0]
        assert page_title_for(endpoint) == 'Klienci'
        merged = {}
        for proc in app.template_context_processors[None]:
            merged.update(proc())
        assert merged.get('page_title') == 'Klienci'


def test_context_processor_always_present(app):
    """page_title is always injected (empty string for an unmapped route)."""
    with app.test_request_context('/'):
        merged = {}
        for proc in app.template_context_processors[None]:
            merged.update(proc())
        assert 'page_title' in merged
