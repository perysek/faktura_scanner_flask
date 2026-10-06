"""
BASE_URL — the origin every SMS link is built from (`{BASE_URL}/confirm/<token>` …).

Before this check an unset BASE_URL silently produced `http://localhost:5000/confirm/…` in real
client texts, and a raw-IP `http://` link is exactly what carriers and phone spam filters flag
(and it sends single-use tokens in clear text). Decision D5: ONE canonical HTTPS domain, and
refuse to start the SMS scheduler without it.
"""
import ipaddress
import logging
from typing import List
from urllib.parse import urlparse

_LOOPBACK_NAMES = {'localhost', 'localhost.localdomain', '0.0.0.0', '::', '::1'}


def sms_link_base_url_problems(base_url) -> List[str]:
    """Why `base_url` must not be used for links sent to real people. Empty list = fine."""
    raw = (base_url or '').strip()
    if not raw:
        return ['BASE_URL is not set']
    parsed = urlparse(raw)
    host = (parsed.hostname or '').lower()
    if not host:
        return [f'BASE_URL {raw!r} has no host']

    problems = []
    try:
        ip = ipaddress.ip_address(host)
        loopbackish = ip.is_loopback or ip.is_unspecified
    except ValueError:
        ip, loopbackish = None, host in _LOOPBACK_NAMES
    if loopbackish:
        problems.append(f'BASE_URL points at {host} — clients cannot open links to the server itself')
    elif ip is not None:
        problems.append(f'BASE_URL uses a raw IP address ({host}) — use the salon domain (a TLS '
                        'certificate cannot cover an IP, and IP links get flagged as spam)')
    if parsed.scheme != 'https':
        problems.append(f'BASE_URL scheme is {parsed.scheme!r}, not https — the links carry single-use tokens')
    return problems


def enforce_sms_base_url(base_url, *, scheduler_enabled: bool, production: bool) -> None:
    """Fail the boot when the SMS scheduler would text clients broken/insecure links.

    Only a production process that actually runs the scheduler is stopped — a second
    service on the same DB (e.g. the React preview) opts out with ENABLE_SMS_SCHEDULER=0,
    and local dev/tests legitimately use localhost. Everything else gets a loud warning.
    """
    problems = sms_link_base_url_problems(base_url)
    if not problems:
        return
    detail = '; '.join(problems)
    if scheduler_enabled and production:
        raise RuntimeError(
            f'Refusing to start: the SMS scheduler is enabled but {detail}. '
            'Set BASE_URL to the canonical https domain (e.g. https://www.my-way-solutions.com), '
            'or set ENABLE_SMS_SCHEDULER=0 on instances that must not send texts.')
    if production:
        logging.warning('SMS link base URL problem (manual sends would build bad links): %s', detail)
