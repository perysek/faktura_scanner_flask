"""SMS review P0-5 — public pages must be routed to Flask on the React host.

Three lists have to agree or links break silently (HTTP 200 + the SPA's own shell, so no
alert fires): what Flask serves publicly, what the Vite dev proxy forwards, and what the
nginx snippet forwards in production. This file fails the build when they drift.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VITE = ROOT / 'frontend' / 'vite.config.ts'
ROUTER = ROOT / 'frontend' / 'src' / 'router.tsx'
NGINX = ROOT / 'deploy' / 'nginx' / 'public-links.conf'

# Served by Flask on the legacy host AND by the SPA on the React host: the one real
# collision. The employee PWA moved to /pracownik so /wizyty can belong to the SPA.
SPA_OWNED_COLLISION = {'wizyty'}


def vite_paths():
    src = VITE.read_text(encoding='utf-8')
    match = re.search(r'flaskPublicPaths\s*=\s*\[([^\]]*)\]', src)
    assert match, 'flaskPublicPaths array not found in vite.config.ts'
    return set(re.findall(r"'([^']+)'", match.group(1)))


def nginx_paths():
    src = NGINX.read_text(encoding='utf-8')
    match = re.search(r'location\s+~\s+\^/\(([^)]*)\)\(/\|\$\)', src)
    assert match, 'public-links location block not found in deploy/nginx/public-links.conf'
    return set(match.group(1).split('|'))


def flask_public_first_segments(app):
    segs = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint.split('.')[0] in ('public', 'booking') and 'GET' in rule.methods:
            first = rule.rule.strip('/').split('/')[0]
            if first != 'api':          # /api/* is already proxied wholesale
                segs.add(first)
    return segs


class TestRoutingListsAgree:
    def test_vite_proxy_and_nginx_snippet_forward_exactly_the_same_prefixes(self):
        assert vite_paths() == nginx_paths()

    def test_every_public_flask_page_is_routed_to_flask(self, app):
        """A new public Flask route that nobody added to the lists would be swallowed by the SPA."""
        missing = flask_public_first_segments(app) - SPA_OWNED_COLLISION - vite_paths()
        assert not missing, f'public Flask pages not routed on the React host: {sorted(missing)}'

    def test_static_is_routed_because_the_standalone_pages_load_assets_from_it(self):
        # booking/index.html → /static/css/output.css ; mobile_app.html → /static/js/mobile-app.js
        assert 'static' in vite_paths() and 'static' in nginx_paths()

    def test_no_spa_route_is_shadowed_by_a_flask_prefix(self):
        spa_firsts = {m.split('/')[0] for m in
                      re.findall(r"path:\s*'([^'*]+)'", ROUTER.read_text(encoding='utf-8'))}
        assert not (spa_firsts & vite_paths()), \
            f'SPA routes shadowed by Flask prefixes: {sorted(spa_firsts & vite_paths())}'

    def test_the_documented_collision_really_is_a_spa_route_and_not_in_the_lists(self):
        spa_firsts = {m.split('/')[0] for m in
                      re.findall(r"path:\s*'([^'*]+)'", ROUTER.read_text(encoding='utf-8'))}
        assert SPA_OWNED_COLLISION <= spa_firsts
        assert not (SPA_OWNED_COLLISION & vite_paths())

    def test_vite_key_is_a_whole_segment_regex(self):
        src = VITE.read_text(encoding='utf-8')
        assert "`^/(${flaskPublicPaths.join('|')})(/|$)`" in src


class TestEmployeePwaPath:
    @pytest.mark.parametrize('path', ['/pracownik', '/wizyty'])
    def test_both_paths_serve_the_employee_app(self, app, path):
        resp = app.test_client().get(path)
        assert resp.status_code == 200
        assert 'mobile-app.js' in resp.get_data(as_text=True)


class TestNginxSnippet:
    def test_proxies_to_flask_with_the_headers_the_app_relies_on(self):
        conf = NGINX.read_text(encoding='utf-8')
        assert 'proxy_pass http://' in conf
        assert 'proxy_set_header Host              $host;' in conf          # Turnstile checks the page host
        assert 'X-Forwarded-Proto $scheme' in conf                           # secure-cookie / url_for scheme
        assert 'CF-Connecting-IP  $http_cf_connecting_ip' in conf            # rate limiter's visitor IP

    def test_documents_how_to_apply_and_the_csp_requirement(self):
        conf = NGINX.read_text(encoding='utf-8')
        assert 'nginx -t' in conf and 'smoke_public_links.py' in conf
        assert 'challenges.cloudflare.com' in conf
