"""Run only safe Phase A/B suites, with fake config and outbound sockets blocked.

From backend: .venv/bin/python -B scripts/test_phase_ab_offline.py
Never use unrestricted unittest discovery against the configured demo database.
"""
import os
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
os.environ.update(DATABASE_URL='sqlite://', PYTHON_DOTENV_DISABLED='1',
                  APP_ENV='test', RENDER='false',
                  GEMINI_ENABLED='false', GEMINI_API_KEY='offline-runner-fake-key',
                  GEMINI_MODEL='offline-model', DEMO_SESSION_SECRET='offline-runner-secret-at-least-32-characters')
backend = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(backend), str(backend / 'tests')]
modules = ('test_gemini_offline', 'test_gemini_request_matrix',
           'test_gemini_timeout_transport', 'test_ai_evaluation', 'test_knowledge_base',
           'test_security_analysis', 'test_customer_logs_isolation', 'test_incident_experiment', 'test_research_evaluation',
           'test_render_demo')
with patch.object(socket.socket, 'connect', side_effect=AssertionError('Phase A/B runner prohibits network')):
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in modules)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
