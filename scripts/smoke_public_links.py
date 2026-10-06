#!/usr/bin/env python
"""Post-deploy smoke test for the PUBLIC pages Flask renders: the confirm/cancel/rate links in
client SMS, the employee start link, the online booking page, the employee PWA, and the
/static files those pages load.

    python scripts/smoke_public_links.py https://staging.my-way-solutions.com

Why it exists (SMS review P0-5): on the React host every one of those URLs used to return
HTTP 200 with the SPA's own "Nie znaleziono" shell. A status-code check cannot see that, so
this one asserts on what each page actually *is* — and that it is NOT the React shell.

Standard library only (runs on any box), no cookies, no writes, dummy tokens only: every
request is a harmless GET. Exit 0 = all green, 1 = at least one failure, 2 = usage error.
Do not point BASE_URL at a host until this is green against it.
"""
import argparse
import ssl
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import List, Optional

DUMMY_TOKEN = '00000000-0000-0000-0000-000000000000'
SPA_SHELL_MARKER = 'id="root"'            # frontend/index.html — only the React shell has it
USER_AGENT = 'MyWay-public-links-smoke/1.0 (post-deploy check)'


@dataclass(frozen=True)
class Check:
    label: str
    path: str
    status: int
    contains: Optional[str] = None
    content_type: Optional[str] = None


CHECKS = [
    # Unknown tokens must reach Flask's own "invalid link" page — a correct host answers 404.
    Check('confirm link', f'/confirm/{DUMMY_TOKEN}', 404, contains='Nieprawidłowy link'),
    Check('cancel link', f'/cancel/{DUMMY_TOKEN}', 404, contains='Nieprawidłowy link'),
    Check('rating link', f'/rate/{DUMMY_TOKEN}', 404, contains='Nieprawidłowy link'),
    Check('employee start link', f'/visit/{DUMMY_TOKEN}', 404, contains='Nieprawidłowy link'),
    Check('online booking page', '/booking', 200, contains='Rezerwacja wizyty'),
    Check('employee PWA', '/pracownik', 200, contains='mobile-app.js'),
    # The standalone pages load these; the SPA catch-all would answer with index.html.
    Check('booking stylesheet', '/static/css/output.css', 200, content_type='text/css'),
    Check('Flask API reachable', '/api/public/services', 200, content_type='application/json'),
]


@dataclass(frozen=True)
class Result:
    check: Check
    ok: bool
    detail: str


def fetch(url: str, timeout: float, user_agent: str = USER_AGENT):
    """GET url → (status, content_type, body). HTTP error statuses are results, not exceptions."""
    req = urllib.request.Request(url, headers={'User-Agent': user_agent, 'Accept': '*/*'})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
            return resp.status, resp.headers.get('Content-Type', ''), resp.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as err:
        return err.code, err.headers.get('Content-Type', '') if err.headers else '', \
            err.read().decode('utf-8', 'replace')


def evaluate(check: Check, status: int, content_type: str, body: str) -> Result:
    if SPA_SHELL_MARKER in body:
        return Result(check, False, f'HTTP {status} but the body is the React shell — the SPA is swallowing this path')
    if status != check.status:
        return Result(check, False, f'expected HTTP {check.status}, got {status}')
    if check.contains and check.contains not in body:
        return Result(check, False, f'HTTP {status} but the page does not contain "{check.contains}"')
    if check.content_type and check.content_type not in content_type.lower():
        return Result(check, False, f'expected Content-Type "{check.content_type}", got "{content_type}"')
    return Result(check, True, f'HTTP {status}' + (f', "{check.contains}"' if check.contains else '')
                  + (f', {check.content_type}' if check.content_type else ''))


def run(base_url: str, timeout: float = 10.0, user_agent: str = USER_AGENT) -> List[Result]:
    base = base_url.rstrip('/')
    results = []
    for check in CHECKS:
        try:
            status, content_type, body = fetch(base + check.path, timeout, user_agent)
            results.append(evaluate(check, status, content_type, body))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            results.append(Result(check, False, f'request failed: {exc}'))
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Smoke-test the public SMS/booking pages on a host.')
    parser.add_argument('base_url', help='e.g. https://staging.my-way-solutions.com')
    parser.add_argument('--timeout', type=float, default=10.0, help='seconds per request (default 10)')
    parser.add_argument('--user-agent', default=USER_AGENT, help='override if a WAF blocks the default')
    args = parser.parse_args(argv)
    if not args.base_url.startswith(('http://', 'https://')):
        print('base_url must start with http:// or https://', file=sys.stderr)
        return 2

    results = run(args.base_url, args.timeout, args.user_agent)
    for r in results:
        print(f"{'PASS' if r.ok else 'FAIL'}  {r.check.label:<22} {r.check.path:<44} {r.detail}")
    failed = [r for r in results if not r.ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed — "
          + ('ALL CHECKS PASSED' if not failed else 'NOT SAFE: public links are broken on this host'))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
