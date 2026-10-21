"""Unit tests with no network, model or Windows GPU required."""
import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch, MagicMock

from core import TranslationEngine
from portable_llm import (MODEL_CATALOG, model_path, select_release_assets, find_compatible_release,
                          _extract_release_zip_flat, MODEL_CATALOG, LocalServer)
import zipfile


class MockResponse:
    def raise_for_status(self):
        pass
    def json(self):
        return {'choices': [{'message': {'content': json.dumps({
            'ko': '지원이 필요해! 옥상에 적 두 명!',
            'replies': [{'en': "I'm coming!", 'ko': '지금 갈게!'},
                        {'en': 'Copy.', 'ko': '알겠어.'},
                        {'en': 'Where exactly?', 'ko': '정확히 어디야?'}],
        }, ensure_ascii=False)}}]}


class PortableTests(TestCase):
    def test_catalog_only_vetted_models(self):
        self.assertEqual(len(MODEL_CATALOG), 5)
        for key, spec in MODEL_CATALOG.items():
            self.assertTrue(spec.filename.endswith('.gguf'))
            self.assertEqual(model_path(key).name, spec.filename)

    def test_translation_uses_local_port_only(self):
        with patch('portable_llm.LOCAL_SERVER.ensure_started', return_value='http://127.0.0.1:54422'):
            with patch('requests.post', return_value=MockResponse()) as post:
                korean, replies = TranslationEngine('Local GGUF (offline)', portable_model='qwen3-4b-q4',
                                                    portable_compute='cpu').translate('Enemy roof!', [])
        self.assertIn('옥상', korean)
        self.assertEqual(replies, [])
        self.assertEqual(post.call_args.args[0], 'http://127.0.0.1:54422/v1/chat/completions')
        self.assertFalse(post.call_args.kwargs['json']['stream'])
        self.assertEqual(post.call_args.kwargs['json']['response_format'], {'type': 'json_object'})

    def test_release_asset_detection(self):
        assets = [
            {'name': 'llama-b100-bin-win-cpu-x64.zip', 'browser_download_url': 'https://github.com/ggml-org/llama.cpp/releases/download/b100/llama-b100-bin-win-cpu-x64.zip'},
            {'name': 'llama-b100-bin-win-cuda-12.4-x64.zip', 'browser_download_url': 'https://github.com/ggml-org/llama.cpp/releases/download/b100/llama-b100-bin-win-cuda-12.4-x64.zip'},
            {'name': 'cudart-llama-bin-win-cuda-12.4-x64.zip', 'browser_download_url': 'https://github.com/ggml-org/llama.cpp/releases/download/b100/cudart-llama-bin-win-cuda-12.4-x64.zip'},
        ]
        self.assertEqual(len(select_release_assets(assets, 'cpu')), 1)
        self.assertEqual(len(select_release_assets(assets, 'cuda')), 2)

    def test_finds_valid_assets_in_older_prerelease(self):
        first = {'tag_name': 'b1002', 'assets': [
            {'name': 'llama-b1002-bin-win-cuda-13.4-x64.zip',
             'browser_download_url': 'https://github.com/ggml-org/llama.cpp/releases/download/b1002/llama-b1002-bin-win-cuda-13.4-x64.zip'}]}
        second = {'tag_name': 'b1001', 'assets': [
            {'name': 'llama-b1001-bin-win-cuda-13.4-x64.zip',
             'browser_download_url': 'https://github.com/ggml-org/llama.cpp/releases/download/b1001/llama-b1001-bin-win-cuda-13.4-x64.zip'},
            {'name': 'cudart-llama-bin-win-cuda-13.4-x64.zip',
             'browser_download_url': 'https://github.com/ggml-org/llama.cpp/releases/download/b1001/cudart-llama-bin-win-cuda-13.4-x64.zip'},
        ]}
        version, files = find_compatible_release([first, second], 'cuda')
        self.assertEqual(version, 'b1001')
        self.assertEqual(len(files), 2)

    def test_cuda_versions_must_match(self):
        files = [
            {'name': 'llama-b100-bin-win-cuda-13.4-x64.zip',
             'browser_download_url': 'https://github.com/ggml-org/llama.cpp/releases/download/b100/llama-b100-bin-win-cuda-13.4-x64.zip'},
            {'name': 'cudart-llama-bin-win-cuda-12.4-x64.zip',
             'browser_download_url': 'https://github.com/ggml-org/llama.cpp/releases/download/b100/cudart-llama-bin-win-cuda-12.4-x64.zip'},
        ]
        with self.assertRaises(RuntimeError):
            select_release_assets(files, 'cuda')

    def test_vulkan_asset_supported(self):
        files = [{'name': 'llama-b101-bin-win-vulkan-x64.zip',
                  'browser_download_url': 'https://github.com/ggml-org/llama.cpp/releases/download/b101/llama-b101-bin-win-vulkan-x64.zip'}]
        self.assertEqual(len(select_release_assets(files, 'vulkan')), 1)

    def test_release_extraction_flat_nested(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            archive = folder / 'release.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('bin/llama-server.exe', b'1' * 1024)
                z.writestr('../danger.txt', b'no')
                z.writestr('bin/ggml.dll', b'abc')
            _extract_release_zip_flat(archive, folder)
            self.assertTrue((folder / 'llama-server.exe').exists())
            self.assertTrue((folder / 'ggml.dll').exists())
            self.assertFalse((folder / 'danger.txt').exists())

    def test_missing_model_is_actionable(self):
        with patch('portable_llm.model_installed', return_value=False):
            with self.assertRaisesRegex(FileNotFoundError, '모델 다운로드'):
                LocalServer().ensure_started('qwen3-4b-q4', 'cpu')

    def test_reject_unknown_compute(self):
        with self.assertRaises(ValueError):
            LocalServer().ensure_started('qwen3-4b-q4', 'bad')
