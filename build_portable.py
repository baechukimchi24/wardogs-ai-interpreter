"""Build console-free Windows onedir distribution from GitHub Actions."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
cmd = [
    sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm',
    '--onedir', '--windowed', '--name', 'WARDOGS Interpreter',
    '--paths', str(ROOT), '--additional-hooks-dir', str(ROOT / 'hooks'),
    '--collect-all', 'ctranslate2',
    '--collect-all', 'faster_whisper',
    '--collect-all', 'argostranslate',
    '--collect-all', 'sounddevice',
    '--hidden-import', 'win32com.client',
    '--hidden-import', 'pythoncom',
    '--hidden-import', 'pywintypes',
    str(ROOT / 'exe_entry.py'),
]
subprocess.run(cmd, cwd=ROOT, check=True)

DIST = ROOT / 'dist' / 'WARDOGS Interpreter'
(DIST / 'bin').mkdir(parents=True, exist_ok=True)
for filename in ('process_loopback.exe', 'process_loopback.sha256'):
    shutil.copy2(ROOT / 'bin' / filename, DIST / 'bin' / filename)
for dirname in ('config', 'models', 'engines', 'logs'):
    (DIST / dirname).mkdir(exist_ok=True)
if (ROOT / 'licenses').exists():
    shutil.copytree(ROOT / 'licenses', DIST / 'licenses', dirs_exist_ok=True)
for filename in ('README_한국어.md', 'CHANGELOG_v1.1_한국어.md'):
    shutil.copy2(ROOT / filename, DIST / filename)
(DIST / '처음실행.txt').write_text(
    'WARDOGS AI Interpreter v1.1 Beta (Windows 11 x64)\n'
    'WARDOGS Interpreter.exe 더블클릭 → AI 모델 다운로드 및 적용 → 게임 실행 후 번역 시작.\n'
    '설정/차단 문구: [기본 설정 · 자막] 탭 / AI 모델: [AI 모델 관리] 탭.\n'
    '설치형 앱이 아닙니다. _internal, bin 등의 폴더를 유지하세요.\n'
    '오류 기록: logs/app-error.log\n',
    encoding='utf-8',
)
