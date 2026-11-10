"""Real SDK timeout/header regressions with all network connections forbidden."""
import json
import os
import socket
import unittest
from unittest.mock import patch

import httpx
from google import genai
from google.genai import types
from services import gemini_support as provider


class GeminiTimeoutTransport(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {'GEMINI_API_KEY': 'offline-fake-key',
            'GEMINI_MODEL': 'offline-model', 'GEMINI_ENABLED': 'true'})
        environment.start(); self.addCleanup(environment.stop)
        network = patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden'))
        network.start(); self.addCleanup(network.stop)
        self.requests = []

    def capture(self, client, request, **kwargs):
        self.requests.append(request)
        return httpx.Response(200, request=request, json={'candidates': [{'finishReason': 'STOP',
            'content': {'role': 'model', 'parts': [{'text': 'ตรวจสอบการเข้าสู่ระบบและทบทวนสิทธิ์บัญชีจำลอง'}]}}]})

    def test_application_client_uses_15_seconds_and_explicit_12_second_server_deadline(self):
        with patch.object(httpx.Client, 'send', lambda client, request, **kwargs: self.capture(client, request, **kwargs)):
            answer = provider._generate('{"question":{"topics":["account_security"]},"mock_telemetry":[]}')
        self.assertIsNotNone(answer)
        self.assertEqual(len(self.requests), 1)
        request = self.requests[0]
        self.assertEqual(provider.HTTP_TIMEOUT_MS, 15000)
        self.assertEqual(provider.SERVER_DEADLINE_SECONDS, 12)
        self.assertEqual(request.headers['x-server-timeout'], '12')
        self.assertEqual(request.extensions['timeout'], {'connect': 15.0, 'read': 15.0, 'write': 15.0, 'pool': 15.0})
        self.assertGreater(provider.HTTP_TIMEOUT_MS / 1000, float(request.headers['x-server-timeout']))
        self.assertGreater(provider.DEADLINE_SECONDS, provider.HTTP_TIMEOUT_MS / 1000)
        self.assertEqual(json.loads(request.content)['generationConfig'], {'maxOutputTokens': provider.MAX_OUTPUT_TOKENS})

    def test_sdk_derives_header_in_seconds_unless_explicit_header_is_supplied(self):
        with patch.object(httpx.Client, 'send', lambda client, request, **kwargs: self.capture(client, request, **kwargs)):
            for headers in (None, {'X-Server-Timeout': '12'}):
                client = genai.Client(api_key='offline-fake-key', vertexai=False, enterprise=False,
                    http_options=types.HttpOptions(timeout=15001, headers=headers,
                        retry_options=types.HttpRetryOptions(attempts=1), client_args={'trust_env': False}, async_client_args={'trust_env': False}))
                try:
                    client.models.generate_content(model='offline-model', contents='synthetic',
                        config=types.GenerateContentConfig(automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)))
                finally:
                    client.close()
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.requests[0].headers['x-server-timeout'], '16')  # ceil(15001 ms / 1000)
        self.assertEqual(self.requests[1].headers['x-server-timeout'], '12')
        self.assertEqual(self.requests[1].extensions['timeout']['read'], 15.001)
        self.assertEqual(json.loads(self.requests[0].content), json.loads(self.requests[1].content))

    def test_transport_timeout_falls_back_after_one_attempt(self):
        requests = []
        def timeout(client, request, **kwargs):
            requests.append(request)
            raise httpx.ReadTimeout('synthetic transport timeout', request=request)
        with patch.object(httpx.Client, 'send', timeout):
            self.assertIsNone(provider.guidance({'question': {'topics': ['account_security']}, 'mock_telemetry': []}))
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].headers['x-server-timeout'], '12')
        self.assertEqual(requests[0].extensions['timeout']['read'], 15.0)


    def test_incident_structured_schema_and_key_header_on_sdk_wire(self):
        from services.incident_assessment import IncidentAnalysis, SYSTEM

        def structured(client, request, **kwargs):
            self.requests.append(request)
            return httpx.Response(200, request=request, json={'candidates': [{
                'finishReason': 'STOP', 'content': {'role': 'model', 'parts': [{'text': json.dumps({
                    'incident_type': 'SERVICE_DISRUPTION', 'impact': 'SIGNIFICANT', 'urgency': 'HIGH',
                    'reason': 'Several demo sites affected', 'recommendation': 'Confirm scope with SOC',
                })}]},
            }]})

        with patch.object(httpx.Client, 'send', structured):
            analysis = provider._generate('{"description":"Several demo sites affected"}', SYSTEM, IncidentAnalysis)
        self.assertEqual(analysis.incident_type, 'SERVICE_DISRUPTION')
        self.assertEqual(len(self.requests), 1)
        request = self.requests[0]
        self.assertEqual(request.headers['x-goog-api-key'], 'offline-fake-key')
        self.assertNotIn('offline-fake-key', str(request.url))
        body = json.loads(request.content)
        config = body['generationConfig']
        self.assertEqual(config['responseMimeType'], 'application/json')
        self.assertEqual(set(config['responseJsonSchema']['properties']),
                         {'incident_type', 'impact', 'urgency', 'reason', 'recommendation'})
        self.assertNotIn('tools', body)
