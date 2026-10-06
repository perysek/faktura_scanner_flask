"""
Cloudflare Turnstile — server-side verification ("siteverify").

The widget on /booking produces a single-use token (valid ~5 min); nothing it proves
counts until we ask Cloudflare to validate it with our *secret*. Four outcomes, because
the caller must treat them differently:

  PASSED       a human (as far as Cloudflare can tell) — proceed
  FAILED       missing/forged/expired/reused token, or solved for another host/action
               → 400, the visitor can simply retry
  UNAVAILABLE  we could not get a verdict (Cloudflare down/slow/unparsable, or OUR secret
               is wrong) → 503, **fail-closed**: without a verdict we cannot tell a human
               from a bot, and "open when the check is down" is exactly when bots strike
  SKIPPED      no secret configured at all → the feature is simply not switched on yet.
               Deliberately NOT fail-closed: it would break public booking in the window
               between deploying this code and setting the server env var. The other
               protections (exact phone match, validation, rate limits) still apply.

Hostname and action are checked too — `success: true` alone only says "someone solved
*a* widget", not "on our page, for this form" (Cloudflare's own guidance).

Cloudflare publishes always-pass / always-fail dummy keys for tests; those return a
fixed example hostname, so hostname/action are not enforced for them.
"""
import logging
from dataclasses import dataclass
from typing import Optional

import requests
from flask import current_app

SITEVERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
MAX_TOKEN_LENGTH = 2048                      # Cloudflare: tokens are at most 2048 characters
REQUEST_TIMEOUT_SECONDS = 5
# Cloudflare's published test secrets: 1x… always passes, 2x… always fails, 3x… "already spent".
_DUMMY_SECRET_PREFIXES = ('1x0000000000000000000000000000000', '2x0000000000000000000000000000000',
                          '3x0000000000000000000000000000000')
# Error codes that are OUR misconfiguration, not the visitor's fault.
_CONFIG_ERRORS = {'missing-input-secret', 'invalid-input-secret'}

PASSED, FAILED, UNAVAILABLE, SKIPPED = 'passed', 'failed', 'unavailable', 'skipped'

logger = logging.getLogger(__name__)
_warned_unconfigured = False


@dataclass(frozen=True)
class TurnstileResult:
    outcome: str
    error_codes: tuple = ()

    @property
    def ok(self) -> bool:
        """May the request proceed? (PASSED, or the feature isn't switched on.)"""
        return self.outcome in (PASSED, SKIPPED)


def is_dummy_secret(secret: str) -> bool:
    return bool(secret) and secret.startswith(_DUMMY_SECRET_PREFIXES)


def verify(token, *, remote_ip: Optional[str] = None, expected_hostname: Optional[str] = None,
           expected_action: Optional[str] = None, secret: Optional[str] = None,
           post=requests.post) -> TurnstileResult:
    """Ask Cloudflare whether `token` is a valid, fresh solution for OUR widget."""
    global _warned_unconfigured
    secret = secret if secret is not None else current_app.config.get('TURNSTILE_SECRET_KEY', '')
    if not secret:
        if not _warned_unconfigured:
            logger.warning('TURNSTILE_SECRET_KEY is not set — public booking is NOT bot-protected '
                           '(exact-match, validation and rate limits still apply).')
            _warned_unconfigured = True
        return TurnstileResult(SKIPPED)

    if not isinstance(token, str) or not token.strip():
        return TurnstileResult(FAILED, ('missing-input-response',))
    if len(token) > MAX_TOKEN_LENGTH:
        return TurnstileResult(FAILED, ('invalid-input-response',))

    payload = {'secret': secret, 'response': token}
    if remote_ip:
        payload['remoteip'] = remote_ip
    try:
        resp = post(SITEVERIFY_URL, data=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp.status_code >= 500:
            logger.error('Turnstile siteverify answered HTTP %s', resp.status_code)
            return TurnstileResult(UNAVAILABLE, ('http-%s' % resp.status_code,))
        body = resp.json()
    except (requests.RequestException, ValueError):
        logger.exception('Turnstile siteverify unreachable or unparsable')
        return TurnstileResult(UNAVAILABLE, ('unreachable',))
    if not isinstance(body, dict):
        return TurnstileResult(UNAVAILABLE, ('unparsable',))

    codes = tuple(body.get('error-codes') or ())
    if not body.get('success'):
        if _CONFIG_ERRORS & set(codes):
            logger.error('Turnstile rejected OUR secret (%s) — fix TURNSTILE_SECRET_KEY', codes)
            return TurnstileResult(UNAVAILABLE, codes)
        return TurnstileResult(FAILED, codes)

    if not is_dummy_secret(secret):
        if expected_hostname and (body.get('hostname') or '').lower() != expected_hostname.lower():
            return TurnstileResult(FAILED, ('hostname-mismatch',))
        if expected_action and body.get('action') != expected_action:
            return TurnstileResult(FAILED, ('action-mismatch',))
    return TurnstileResult(PASSED)
