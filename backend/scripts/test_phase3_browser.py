"""Isolated browser fixtures + cleanup. See PHASE3_CHAT.md for runner setup."""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import sys
import time

backend = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend))
sys.path.insert(0, str(backend / 'tests'))
from test_chat_rooms import ChatAPI

ChatAPI.setUpClass()
try:
    body = base64.urlsafe_b64encode(json.dumps({'uid': str(ChatAPI.users['a1']['id']), 'exp': int(time.time()) - 5}).encode()).rstrip(b'=').decode()
    expired = body + '.' + hmac.new(os.environ['DEMO_SESSION_SECRET'].encode(), body.encode(), hashlib.sha256).hexdigest()
    fixture = {'marker': ChatAPI.marker, 'users': ChatAPI.users, 'expired_token': expired}
    env = dict(os.environ, PHASE3_BROWSER_FIXTURE=json.dumps(fixture, default=str))
    result = subprocess.run([os.getenv('NODE_BINARY', 'node'), str(backend.parent / 'frontend/tests/phase3.browser.mjs')], env=env)
finally:
    ChatAPI().tearDown()
    ChatAPI.tearDownClass()
sys.exit(result.returncode)
