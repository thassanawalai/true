"""Real SDK request ablation through MockTransport; NEVER calls Google.

Successful mock serialization does not imply live server/model acceptance.
Uses synthetic constants and fake authentication only, without reading .env.
"""
import json
import socket
import unittest
from unittest.mock import patch

import httpx
from google import genai
from google.genai import types
from services import gemini_support as provider

MODEL = 'gemini-3.5-flash-lite'
SYNTHETIC_INPUT = json.dumps({'data_kind': 'verified_static_demo_telemetry',
    'question': {'category': 'logs', 'topics': ['account_security']},
    'recent_topics': [], 'mock_telemetry': []})


def serialize(config, contents=SYNTHETIC_INPUT):
    captured = []
    def handler(request):
        # Never print headers or actual payloads. Test key is fake regardless.
        assert request.headers['x-goog-api-key'] == 'offline-matrix-fake-key'
        assert request.url.path == '/v1beta/models/' + MODEL + ':generateContent'
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={'candidates': [{'finishReason': 'STOP',
            'content': {'role': 'model', 'parts': [{'text': 'ตรวจสอบบัญชีจำลองและทบทวนการเข้าสู่ระบบ'}]}}]})
    with patch.object(socket.socket, 'connect', side_effect=AssertionError('Offline matrix prohibits network')):
        client = genai.Client(api_key='offline-matrix-fake-key', vertexai=False, enterprise=False,
            http_options=types.HttpOptions(async_client_args={'trust_env': False}, httpx_client=httpx.Client(transport=httpx.MockTransport(handler)),
                timeout=6000, retry_options=types.HttpRetryOptions(attempts=1)))
        try:
            client.models.generate_content(model=MODEL, contents=contents, config=types.GenerateContentConfig(**config))
        finally:
            client.close()
    assert len(captured) == 1
    return captured[0]


def matrix():
    config = {}
    stages = [('minimal', None, None),
        ('system_instruction', 'system_instruction', provider.SYSTEM),
        ('max_output_tokens', 'max_output_tokens', provider.MAX_OUTPUT_TOKENS),
        ('automatic_function_calling_disabled', 'automatic_function_calling', types.AutomaticFunctionCallingConfig(disable=True))]
    for name, key, value in stages:
        if key:
            config[key] = value
        yield name, serialize(config)


class GeminiRequestMatrix(unittest.TestCase):
    def test_incremental_plain_text_sdk_transformations(self):
        previous = None
        for name, body in matrix():
            with self.subTest(stage=name):
                self.assertEqual(body['contents'], [{'parts': [{'text': SYNTHETIC_INPUT}], 'role': 'user'}])
                self.assertNotIn('tools', body)
                config = body.get('generationConfig', {})
                if name == 'minimal':
                    self.assertFalse(config)
                    self.assertNotIn('systemInstruction', body)
                elif name == 'system_instruction':
                    self.assertEqual(body['systemInstruction']['parts'][0]['text'], provider.SYSTEM)
                    self.assertFalse(config)
                elif name == 'max_output_tokens':
                    self.assertEqual(config, {'maxOutputTokens': provider.MAX_OUTPUT_TOKENS})
                elif name == 'automatic_function_calling_disabled':
                    self.assertEqual(body, previous)  # local SDK option; not on wire
                previous = body

    def test_direct_plain_text_shape_with_bounded_output(self):
        body = serialize({'system_instruction': provider.SYSTEM, 'max_output_tokens': provider.MAX_OUTPUT_TOKENS},
                         contents='ข้อมูลสังเคราะห์: suspicious login ควรตรวจอะไร?')
        self.assertEqual(body['generationConfig'], {'maxOutputTokens': provider.MAX_OUTPUT_TOKENS})
        self.assertEqual(body['contents'][0]['role'], 'user')
        self.assertLess(len(provider.SYSTEM), 600)

    def test_no_output_schema_mime_sampling_or_tools_reach_wire(self):
        body = list(matrix())[-1][1]
        for field in ('responseSchema', 'responseJsonSchema', 'responseMimeType',
                      'temperature', 'candidateCount', 'topP', 'topK'):
            self.assertNotIn(field, body['generationConfig'])
        self.assertNotIn('tools', body)
        # The sanitized INPUT remains JSON demo context; only OUTPUT is plain text.
        self.assertEqual(json.loads(body['contents'][0]['parts'][0]['text'])['data_kind'],
                         'verified_static_demo_telemetry')


if __name__ == '__main__':
    unittest.main()
