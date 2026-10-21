"""Install-script regression checks for the Windows PowerShell 5.1 quoting failure."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InstallScriptTests(unittest.TestCase):
    def test_ps_installer_runs_python_files_not_inline_snippets(self):
        script = (ROOT / 'tools' / 'install.ps1').read_text(encoding='utf-8-sig')
        self.assertNotIn(' -c ', script)
        self.assertEqual(script.count("(Join-Path $root 'tools\\verify_install.py')"), 4)
        for action in ('venv', 'modules', 'full'):
            self.assertIn(f"verify_install.py') {action}", script)

    def test_repair_and_full_installer_work_with_extracted_folder(self):
        for name in ('INSTALL_AND_START.bat',):
            script = (ROOT / name).read_text(encoding='utf-8')
            self.assertIn('cd /d "%~dp0"', script)
            self.assertIn('tools\\install.ps1', script)
            self.assertNotIn('C:\\WardogsInterpreter', script)
        self.assertTrue((ROOT / 'tools' / 'verify_install.py').is_file())

    def test_prebuilt_helper_no_visual_studio_required(self):
        source = (ROOT / 'tools' / 'install.ps1').read_text(encoding='utf-8-sig')
        self.assertIn('process_loopback.sha256', source)
        self.assertIn('--self-test', source)
        self.assertNotIn('build_native.bat', source)
        self.assertNotIn('auto_build.bat', source)
        self.assertTrue((ROOT / 'bin' / 'process_loopback.exe').is_file())
        self.assertEqual((ROOT / 'bin' / 'process_loopback.exe').read_bytes()[:2], b'MZ')
        import hashlib
        expected = (ROOT / 'bin' / 'process_loopback.sha256').read_text().strip().lower()
        actual = hashlib.sha256((ROOT / 'bin' / 'process_loopback.exe').read_bytes()).hexdigest()
        self.assertEqual(actual, expected)

    def test_ui_has_explicit_model_apply_action(self):
        source = (ROOT / 'main.py').read_text(encoding='utf-8')
        self.assertIn('선택 모델 적용 및 번역 검증', source)
        self.assertIn('model_applied.connect(self.on_model_applied)', source)
        self.assertIn('def apply_current_model(self):', source)
        self.assertIn('self.applied_selection != ', source)



if __name__ == '__main__':
    unittest.main()
