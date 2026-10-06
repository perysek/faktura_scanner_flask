"""scripts/smoke_public_links.py — the post-deploy check for SMS review P0-5.

The script must (a) pass on a host whose routing is right — proven against the REAL Flask app
served over a real socket — and (b) FAIL on the host that was actually broken: one that
answers every public URL with HTTP 200 and the React shell. A status-code-only check would
have called that healthy.
"""
import socket
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import MagicMock, patch

import pytest
from werkzeug.serving import make_server

from scripts import smoke_public_links as smoke

SPA_SHELL = ('<!doctype html><html><head><title>MyWay Nails &amp; Beauty</title></head>'
             '<body><div id="root"></div></body></html>')
INVALID = '<html><head><title>Nieprawidłowy link — MyWay Beauty Salon</title></head></html>'

CORRECT_HOST = {
    '/confirm/' + smoke.DUMMY_TOKEN: (404, 'text/html', INVALID),
    '/cancel/' + smoke.DUMMY_TOKEN: (404, 'text/html', INVALID),
    '/rate/' + smoke.DUMMY_TOKEN: (404, 'text/html', INVALID),
    '/visit/' + smoke.DUMMY_TOKEN: (404, 'text/html', INVALID),
    '/booking': (200, 'text/html', '<title>Rezerwacja wizyty — MyWay</title>'),
    '/pracownik': (200, 'text/html', '<script src="/static/js/mobile-app.js"></script>'),
    '/static/css/output.css': (200, 'text/css; charset=utf-8', 'body{margin:0}'),
    '/api/public/services': (200, 'application/json', '{"success": true, "services": []}'),
}


class _Handler(BaseHTTPRequestHandler):
    routes = {}
    default = (200, 'text/html', SPA_SHELL)

    def do_GET(self):
        status, ctype, body = self.routes.get(self.path, self.default)
        data = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@contextmanager
def stub_host(routes=None, default=None):
    attrs = {'routes': dict(routes or {})}
    if default is not None:
        attrs['default'] = default
    server = ThreadingHTTPServer(('127.0.0.1', 0), type('H', (_Handler,), attrs))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()


def _run(url, capsys):
    code = smoke.main([url, '--timeout', '3'])
    return code, capsys.readouterr().out


class TestAgainstStubHosts:
    def test_correct_host_passes_every_check(self, capsys):
        with stub_host(CORRECT_HOST, default=(404, 'text/html', 'nope')) as url:
            code, out = _run(url, capsys)
        assert code == 0, out
        result_lines = [l for l in out.splitlines() if l[:4] in ('PASS', 'FAIL')]
        assert [l[:4] for l in result_lines] == ['PASS'] * len(smoke.CHECKS)
        assert 'ALL CHECKS PASSED' in out

    def test_the_broken_react_host_is_caught_even_though_every_status_is_200(self, capsys):
        # The real failure of 2026-10-06: HTTP 200 + the SPA shell on every public URL.
        with stub_host({}) as url:                       # default = 200 + React shell for everything
            code, out = _run(url, capsys)
        assert code == 1
        assert [l[:4] for l in out.splitlines() if l[:4] in ('PASS', 'FAIL')] == ['FAIL'] * len(smoke.CHECKS)
        assert 'React shell' in out and 'NOT SAFE' in out

    def test_only_the_stylesheet_swallowed_is_pinpointed(self, capsys):
        broken = {**CORRECT_HOST, '/static/css/output.css': (200, 'text/html', SPA_SHELL)}
        with stub_host(broken, default=(404, 'text/html', 'nope')) as url:
            code, out = _run(url, capsys)
        assert code == 1
        failed = [l for l in out.splitlines() if l.startswith('FAIL')]
        assert len(failed) == 1 and '/static/css/output.css' in failed[0] and 'React shell' in failed[0]

    def test_wrong_status_is_a_failure_even_with_the_right_words(self, capsys):
        wrong = {**CORRECT_HOST, '/confirm/' + smoke.DUMMY_TOKEN: (200, 'text/html', INVALID)}
        with stub_host(wrong, default=(404, 'text/html', 'nope')) as url:
            code, out = _run(url, capsys)
        assert code == 1 and 'expected HTTP 404, got 200' in out

    def test_wrong_content_type_is_a_failure(self, capsys):
        wrong = {**CORRECT_HOST, '/static/css/output.css': (200, 'text/plain', 'body{}')}
        with stub_host(wrong, default=(404, 'text/html', 'nope')) as url:
            code, out = _run(url, capsys)
        assert code == 1 and 'expected Content-Type "text/css"' in out

    def test_unreachable_host_fails_cleanly(self, capsys):
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]                    # nothing listens here once closed
        code, out = _run(f'http://127.0.0.1:{port}', capsys)
        assert code == 1 and out.count('request failed') == len(smoke.CHECKS)

    def test_trailing_slash_in_the_base_url_is_fine(self, capsys):
        with stub_host(CORRECT_HOST, default=(404, 'text/html', 'nope')) as url:
            code, _ = _run(url + '/', capsys)
        assert code == 0

    def test_usage_error_is_exit_2(self, capsys):
        assert smoke.main(['not-a-url']) == 2


class TestAgainstTheRealFlaskApp:
    """The script passes on a host whose Flask side is correct — the actual app over a socket."""

    def test_real_app_passes_every_check(self, app, tmp_path, capsys):
        (tmp_path / 'css').mkdir()
        (tmp_path / 'js').mkdir()
        (tmp_path / 'css' / 'output.css').write_text('body{margin:0}', encoding='utf-8')   # build artefact (gitignored)
        (tmp_path / 'js' / 'mobile-app.js').write_text('// pwa', encoding='utf-8')
        app.static_folder = str(tmp_path)

        no_token = MagicMock()
        no_token.get_by_confirmation_token.return_value = None
        no_token.get_by_employee_token.return_value = None
        no_token.get_by_rating_token.return_value = None
        services = MagicMock()
        services.get_main_services.return_value = []

        server = make_server('127.0.0.1', 0, app, threaded=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with patch('routes.public_routes.AppointmentRepository', return_value=no_token), \
                 patch('routes.booking_routes.ServiceRepository', return_value=services):
                code, out = _run(f'http://127.0.0.1:{server.server_port}', capsys)
        finally:
            server.shutdown()
        assert code == 0, out
        assert 'ALL CHECKS PASSED' in out
