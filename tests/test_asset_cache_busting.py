"""Regression test for static-asset cache busting (asset_url template global).

Bug history
-----------
Adding ``Absences.cancelApproved`` to the existing ``static/js/absences.js``
made browsers throw ``Absences.cancelApproved is not a function``: every
``<script>`` tag used ``url_for('static', ...)`` with a stable, un-versioned
URL, and nginx serves /static as immutable / max-age=1y. Returning users kept
the year-cached old file — the ``Absences`` object loaded, but without the new
method. (``is not a function`` rather than ``is not defined`` proves the object
loaded from a stale copy.)

The fix generalises the CSS-only ``ASSET_VERSION`` into ``asset_url(filename)``,
which appends ``?v=<content-hash>`` per file. The URL changes exactly when that
file's bytes change, so caches invalidate automatically on the next deploy.

These tests would FAIL against the old ``url_for('static', ...)`` markup (no
``?v=``) and PASS with ``asset_url``.
"""
import os


def _asset_url(app):
    """Fetch the registered template global."""
    return app.jinja_env.globals['asset_url']


def test_asset_url_appends_version_query(app):
    """An existing static file must get a cache-busting ?v= param."""
    asset_url = _asset_url(app)
    with app.test_request_context():
        url = asset_url('js/absences.js')
    assert '/static/js/absences.js' in url
    assert 'v=' in url, f'expected a ?v= cache-bust, got: {url}'


def test_asset_url_hash_tracks_file_content(app):
    """The version must change when the file's content changes.

    This is the heart of the bug: content changed (new JS method) but the URL
    did not, so the browser never re-fetched. Drive distinct mtimes so the
    (filename, mtime) cache invalidates deterministically.
    """
    asset_url = _asset_url(app)
    rel = 'js/__cache_bust_probe__.js'
    path = os.path.join(app.static_folder, rel)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write('// version one')
        os.utime(path, (1000, 1000))
        with app.test_request_context():
            url1 = asset_url(rel)

        with open(path, 'w', encoding='utf-8') as f:
            f.write('// version two — entirely different bytes')
        os.utime(path, (2000, 2000))
        with app.test_request_context():
            url2 = asset_url(rel)
    finally:
        if os.path.exists(path):
            os.remove(path)

    assert 'v=' in url1 and 'v=' in url2
    assert url1 != url2, 'cache-bust hash must change when file content changes'


def test_asset_url_missing_file_does_not_raise(app):
    """A missing asset falls back to an un-versioned URL, never a 500."""
    asset_url = _asset_url(app)
    with app.test_request_context():
        url = asset_url('js/__definitely_missing__.js')
    assert '/static/js/__definitely_missing__.js' in url
