"""New subtitle-first, VAD, small model and placeholder regression tests."""
import sys
import types
import unittest
from unittest.mock import patch

from core import (BYTES_PER_FRAME, VoiceSegmenter, _parse_local_translation,
                  _valid_korean_subtitle, TranslationEngine, recommendations)
from portable_llm import MODEL_CATALOG
import opus_mt


class TestV09(unittest.TestCase):
    @staticmethod
    def frame(active):
        return bytes([1 if active else 0]) + bytes(BYTES_PER_FRAME - 1)

    def test_150ms_minimal_speech_and_300ms_endpoint(self):
        seg = VoiceSegmenter(detector=lambda frame: frame[0] == 1,
                             min_voice_ms=150, silence_end_ms=300)
        self.assertEqual(seg.min_voice_frames, 5)
        self.assertEqual(seg.silence_end_frames, 10)
        for _ in range(5): self.assertIsNone(seg.feed(self.frame(True)))
        for _ in range(9): self.assertIsNone(seg.feed(self.frame(False)))
        self.assertIsNotNone(seg.feed(self.frame(False)))

    def test_120ms_too_short_even_with_endpoint(self):
        seg = VoiceSegmenter(detector=lambda frame: frame[0] == 1)
        for _ in range(4): seg.feed(self.frame(True))
        for _ in range(10):
            self.assertIsNone(seg.feed(self.frame(False)))

    def test_vad_settings_customizable(self):
        seg = VoiceSegmenter(detector=lambda frame: frame[0] == 1,
                             min_voice_ms=240, silence_end_ms=450)
        self.assertEqual(seg.min_voice_frames, 8)
        self.assertEqual(seg.silence_end_frames, 15)

    def test_placeholder_not_accepted_as_translation(self):
        for bad in ('[한국어 번역]', '한국어 번역', '【번역】', '[translation]', '번역문:'):
            with self.subTest(bad=bad):
                self.assertFalse(_valid_korean_subtitle(bad))
                with self.assertRaises(ValueError):
                    _parse_local_translation(bad)

    def test_real_korean_accepted(self):
        self.assertTrue(_valid_korean_subtitle('옥상에 적 2명!'))
        self.assertEqual(_parse_local_translation('{"ko":"적이 온다!"}')[0], '적이 온다!')

    def test_selected_small_models_exist_in_catalog(self):
        spec1 = MODEL_CATALOG['qwen35-08b-q4']
        spec2 = MODEL_CATALOG['qwen35-2b-q4']
        self.assertEqual(spec1.repo, 'unsloth/Qwen3.5-0.8B-GGUF')
        self.assertEqual(spec2.filename, 'Qwen3.5-2B-Q4_K_M.gguf')

    def test_llm_prompt_asks_only_subtitle_not_replies(self):
        calls=[]
        class Resp:
            def raise_for_status(self): pass
            def json(self): return {'choices':[{'message':{'content':'{"ko":"지원이 필요해!"}'}}]}
        fake=types.ModuleType('portable_llm')
        fake.LOCAL_SERVER=types.SimpleNamespace(ensure_started=lambda *_:'http://127.0.0.1:4321')
        with patch.dict(sys.modules, {'portable_llm': fake}), patch('requests.post', side_effect=lambda *a,**kw:(calls.append(kw['json']) or Resp())):
            ko, replies = TranslationEngine('Local GGUF (offline)').translate('Need backup!', [])
        self.assertEqual(ko, '지원이 필요해!')
        self.assertEqual(replies, [])
        prompt=calls[0]['messages'][0]['content'].lower()
        self.assertIn('do not generate replies',prompt)
        self.assertEqual(calls[0]['max_tokens'],112)

    def test_fast_offline_argos_is_subtitle_only(self):
        fake_pkg=types.ModuleType('argostranslate')
        fake_t=types.ModuleType('argostranslate.translate')
        fake_t.translate=lambda text,src,target:'빨리 가!'
        with patch.dict(sys.modules, {'argostranslate':fake_pkg, 'argostranslate.translate':fake_t}):
            ko, replies=TranslationEngine('Argos (offline)').translate('Go now!',[])
        self.assertEqual(ko,'빨리 가!')
        self.assertEqual(replies, [])
        self.assertEqual(len(recommendations('Need backup')),3)

    def test_partial_gpu_16_modes_supported(self):
        from portable_llm import LocalServer
        for mode in ('cuda16','vulkan16'):
            with patch('portable_llm.model_installed', return_value=False):
                with self.assertRaisesRegex(FileNotFoundError, '모델 다운로드'):
                    LocalServer().ensure_started('qwen35-2b-q4', mode)

    def test_opus_missing_doesnt_require_download_at_startup(self):
        with patch.object(opus_mt, 'OPUS_DIR', opus_mt.ROOT / 'not-existing-model-test'):
            self.assertFalse(opus_mt.installed())


if __name__ == '__main__':
    unittest.main()
