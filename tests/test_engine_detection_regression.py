"""Regression tests for the small llama.cpp Windows PE launcher bug."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import portable_llm


class SmallPELauncherRegression(unittest.TestCase):
    def test_9216_byte_pe_launcher_with_marker_and_dll_is_installed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(portable_llm, 'ENGINES_DIR', Path(tmp)):
                for backend in ('cpu', 'vulkan', 'cuda'):
                    with self.subTest(backend=backend):
                        folder = Path(tmp) / backend
                        folder.mkdir()
                        (folder / 'llama-server.exe').write_bytes(b'MZ' + b'\0' * 9214)
                        (folder / '.installed').write_text('b11755\nverified\n')
                        (folder / 'ggml-base.dll').write_bytes(b'dll')
                        self.assertTrue(portable_llm.engine_installed(backend))
                        (folder / '.installed').unlink()
                        self.assertFalse(portable_llm.engine_installed(backend))
                        (folder / '.installed').write_text('verified')
                        (folder / 'llama-server.exe').write_bytes(b'NO' + b'\0' * 9214)
                        self.assertFalse(portable_llm.engine_installed(backend))
                        (folder / 'llama-server.exe').write_bytes(b'MZ' + b'\0' * 9214)
                        (folder / 'ggml-base.dll').unlink()
                        self.assertFalse(portable_llm.engine_installed(backend))


if __name__ == '__main__':
    unittest.main()
