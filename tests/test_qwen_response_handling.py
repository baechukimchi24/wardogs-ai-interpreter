import sys
import types
import unittest
from unittest.mock import patch

from core import _parse_local_translation, TranslationEngine


class TestModelResponseHandling(unittest.TestCase):
    def test_valid_json(self):
        ko, replies = _parse_local_translation('{"ko":"옥상에 적이 둘 있어!", "replies":[{"en":"On my way!", "ko":"갈게!"}]}')
        self.assertEqual(ko, '옥상에 적이 둘 있어!')
        self.assertEqual(len(replies), 1)

    def test_fenced_json(self):
        ko, _ = _parse_local_translation('```json\n{"ko":"지원이 필요해!"}\n```')
        self.assertEqual(ko, '지원이 필요해!')

    def test_embedded_json(self):
        ko, _ = _parse_local_translation('result:\n{"ko":"적이 왼쪽에 있어!"}')
        self.assertEqual(ko, '적이 왼쪽에 있어!')

    def test_plain_translation(self):
        ko, choices = _parse_local_translation('지원이 필요해! 옥상에 적 두 명 있어!')
        self.assertIn('적 두 명', ko)
        self.assertEqual(choices, [])

    def test_translate_key_alternative(self):
        ko, _ = _parse_local_translation('{"translation":"지금 갈게!"}')
        self.assertEqual(ko, '지금 갈게!')

    def test_closed_think_tag(self):
        ko, _ = _parse_local_translation('<think>reasoning</think>{"ko":"다 같이 진입하자!"}')
        self.assertEqual(ko, '다 같이 진입하자!')

    def test_only_thinking_rejected(self):
        with self.assertRaises(ValueError):
            _parse_local_translation('<think>thinking without final answer')

    def test_english_only_rejected(self):
        with self.assertRaises(ValueError):
            _parse_local_translation('We need backup!')

    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            _parse_local_translation('')

    def test_model_call_disables_thinking_and_accepts_json(self):
        calls = []
        def fake_post(url, json, timeout):
            calls.append(json)
            return FakeResponse('{"ko":"엄폐해!"}')
        fake_mod = types.ModuleType('portable_llm')
        fake_mod.LOCAL_SERVER = types.SimpleNamespace(ensure_started=lambda _m, _c: 'http://127.0.0.1:1000')
        with patch.dict(sys.modules, {'portable_llm': fake_mod}), patch('requests.post', side_effect=fake_post):
            ko, replies = TranslationEngine('Local GGUF (offline)', portable_model='qwen35-4b-q4', portable_compute='cudaall').translate('Take cover!', [])
        self.assertEqual(ko, '엄폐해!')
        self.assertEqual(replies, [])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]['chat_template_kwargs']['enable_thinking'], False)
        self.assertEqual(calls[0]['reasoning_effort'], 'none')
        self.assertEqual(calls[0]['response_format']['type'], 'json_object')

    def test_retry_after_thinking_only(self):
        replies = iter([FakeResponse('', finish='length', reasoning='thinking for 220 tokens'), FakeResponse('지원이 필요해!')])
        fake_mod = types.ModuleType('portable_llm')
        fake_mod.LOCAL_SERVER = types.SimpleNamespace(ensure_started=lambda _m, _c: 'http://127.0.0.1:1000')
        with patch.dict(sys.modules, {'portable_llm': fake_mod}), patch('requests.post', side_effect=lambda *a, **kw: next(replies)) as req:
            ko, _ = TranslationEngine('Local GGUF (offline)').translate('Help me!', [])
        self.assertEqual(ko, '지원이 필요해!')
        self.assertEqual(req.call_count, 2)

    def test_retry_failure_reports_metadata_only(self):
        replies = iter([FakeResponse('', finish='length', reasoning='sensitive secret'), FakeResponse('', finish='length', reasoning='sensitive secret')])
        fake_mod = types.ModuleType('portable_llm')
        fake_mod.LOCAL_SERVER = types.SimpleNamespace(ensure_started=lambda _m, _c: 'http://127.0.0.1:1000')
        with patch.dict(sys.modules, {'portable_llm': fake_mod}), patch('requests.post', side_effect=lambda *a, **kw: next(replies)):
            with self.assertRaises(RuntimeError) as e:
                TranslationEngine('Local GGUF (offline)').translate('Help me!', [])
        self.assertIn('reasoning_chars=', str(e.exception))
        self.assertNotIn('sensitive secret', str(e.exception))

class FakeResponse:
    def __init__(self, content, finish='stop', reasoning=''):
        self._payload = {'choices':[{'message':{'content': content,'reasoning_content':reasoning},'finish_reason':finish}]}
    def raise_for_status(self):
        pass
    def json(self):
        return self._payload

if __name__ == '__main__':
    unittest.main()
