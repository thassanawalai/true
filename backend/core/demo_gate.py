"""Shared invitation gate for the entire demo, before mock identity selection.

Use HTTPS. Everyone given these credentials is an authorized demo operator and
can select any mock identity. This is deliberately not production authentication.
"""
import base64
import binascii
import hmac
import os
from starlette.responses import JSONResponse
from core.deployment import hosted


def settings():
    username = os.getenv('DEMO_ACCESS_USER', '')
    password = os.getenv('DEMO_ACCESS_PASSWORD', '')
    enabled = hosted() or bool(username or password)
    if enabled and (not username or ':' in username or len(password) < 24):
        raise ValueError('Set DEMO_ACCESS_USER and DEMO_ACCESS_PASSWORD (at least 24 characters).')
    return enabled, username, password


class DemoAccessGate:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        # Render probes only; no data, identities or application content here.
        if scope['path'] == '/healthz' and scope['method'] in ('GET', 'HEAD'):
            return await self.app(scope, receive, send)
        try:
            enabled, username, password = settings()
        except ValueError:
            return await JSONResponse({'detail': 'Demo access gate is not configured'}, status_code=503)(scope, receive, send)
        if enabled:
            valid = False
            try:
                authorization = dict(scope['headers']).get(b'authorization', b'').decode('ascii')
                scheme, encoded = authorization.split(' ', 1)
                if scheme.lower() == 'basic':
                    supplied_user, supplied_password = base64.b64decode(encoded, validate=True).decode('utf-8').split(':', 1)
                    valid = (hmac.compare_digest(supplied_user.encode(), username.encode()) &
                             hmac.compare_digest(supplied_password.encode(), password.encode()))
            except (ValueError, UnicodeError, binascii.Error):
                pass
            if not valid:
                response = JSONResponse({'detail': 'Demo invitation credentials required'}, status_code=401,
                    headers={'WWW-Authenticate': 'Basic realm="SOC demo", charset="UTF-8"', 'Cache-Control': 'no-store'})
                return await response(scope, receive, send)
        await self.app(scope, receive, send)
