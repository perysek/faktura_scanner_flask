"""Regression guard: every custom Jinja helper a template calls must be registered.

A 500 hit /absences in production because templates/absences/management.html used
`{{ asset_url('js/absences.js') }}` while the asset_url() Jinja global lived only in
an uncommitted working-tree app.py — so the DEPLOYED app raised
`jinja2.exceptions.UndefinedError: 'asset_url' is undefined` on every render.

Root cause class: a template references a Jinja global that the built app does not
register. This test builds the real app and asserts that if any template calls
asset_url(), the app actually exposes asset_url in its Jinja environment. It stays
green whether the asset_url migration is finished (helper registered, templates use
it) or not yet started (no template uses it) — it only fails on the inconsistent
state that caused the outage.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = ROOT / 'templates'

# Custom Jinja globals this project may reference from templates. url_for is a
# Flask built-in and never needs registration, so it is not listed here.
CUSTOM_TEMPLATE_GLOBALS = ['asset_url']


def _templates_calling(name: str) -> list[str]:
    pattern = re.compile(rf'\b{re.escape(name)}\s*\(')
    hits = []
    for path in TEMPLATES_DIR.rglob('*.html'):
        if pattern.search(path.read_text(encoding='utf-8')):
            hits.append(str(path.relative_to(ROOT)).replace('\\', '/'))
    return sorted(hits)


def test_custom_template_globals_are_registered(app):
    """If a template calls a custom global, the built app must register it."""
    for name in CUSTOM_TEMPLATE_GLOBALS:
        callers = _templates_calling(name)
        if not callers:
            continue  # nobody uses it — nothing to register
        assert name in app.jinja_env.globals, (
            f"{len(callers)} template(s) call {name}() but the app does not "
            f"register a '{name}' Jinja global — they will 500 with "
            f"UndefinedError at render:\n" + "\n".join(callers)
            + f"\nRegister {name}() in create_app() (or switch the templates to "
            "url_for('static', filename=...))."
        )
