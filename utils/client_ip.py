"""The real visitor IP, for rate limiting and Turnstile's `remoteip`.

Production topology: browser → Cloudflare → nginx → gunicorn. `ProxyFix(x_for=1)` trusts
exactly one hop, and the last hop nginx saw is *Cloudflare's edge*, so `request.remote_addr`
is an edge address shared by thousands of visitors — keying a limiter on it would throttle
real customers together and let an attacker hide in the crowd.

Cloudflare puts the visitor's address in `CF-Connecting-IP`. A client could forge that
header against an origin reachable directly, so this is only safe because the origin
firewall admits Cloudflare's IP ranges alone (ufw: 22 CIDRs on 80/443 — see the
myway-cloudflare skill). It is the same trust pair as `ProxyFix`: **do not loosen the
firewall without revisiting both.** Off-Cloudflare (local dev, tests) the header is
absent and `remote_addr` is used.
"""
import ipaddress

from flask import request


def client_ip() -> str:
    raw = (request.headers.get('CF-Connecting-IP') or '').strip()
    if raw:
        try:
            return str(ipaddress.ip_address(raw))
        except ValueError:
            pass            # garbage header: ignore it rather than key a limiter on it
    return request.remote_addr or '0.0.0.0'
