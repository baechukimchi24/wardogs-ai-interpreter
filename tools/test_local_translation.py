"""Test installed GGUF model and portable llama.cpp engines without downloading.

Run from TEST_LOCAL_TRANSLATION.bat. Does not alter the game or audio routing.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LOG_DIR = ROOT / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / 'local-translation-test.log'


def emit(*words):
    line = ' '.join(map(str, words))
    print(line, flush=True)
    with LOG_FILE.open('a', encoding='utf-8') as out:
        out.write(line + '\n')


def log_server_tail():
    file = LOG_DIR / 'llama-server.log'
    if file.exists():
        tail = file.read_text(encoding='utf-8', errors='replace').splitlines()[-35:]
        emit('\n--- llama-server.log last 35 lines ---')
        for ln in tail:
            emit(ln)
        emit('--- end ---')
    else:
        emit('No llama-server.log file yet.')


def main():
    from core import TranslationEngine
    import portable_llm as p

    with LOG_FILE.open('a', encoding='utf-8') as out:
        out.write('\n' + '=' * 68 + '\n' + datetime.now().isoformat() + '\n')
    emit('PROJECT:', ROOT)
    emit('PYTHON:', sys.executable)
    emit('LLAMA MODULE:', p.__file__)
    emit('TRANSLATION MODULE:', sys.modules['core'].__file__)

    model_key = next((key for key in ('qwen35-4b-q4', 'qwen3-4b-q4', 'exaone35-24b-q4')
                      if p.model_installed(key)), None)
    if not model_key:
        emit('[FAIL] No installed GGUF models passed the local signature check.')
        return 2
    model = p.model_path(model_key)
    emit('MODEL:', model_key, 'PATH:', model, 'MiB:', round(model.stat().st_size / (1024 * 1024)))
    emit('INSTALLED ENGINES:')
    for backend in ('cpu', 'vulkan', 'cuda'):
        emit(' ', backend.upper(), 'detected=', p.engine_installed(backend), 'path=', p.engine_path(backend))

    choices = {'1': ('cudaall', 'cuda'), '2': ('vulkan8', 'vulkan'),
               '3': ('cuda8', 'cuda'), '4': ('cpu', 'cpu')}
    emit('\n1. CUDA FULL GPU [recommended for test ONLY, close WARDOGS]')
    emit('2. Vulkan 8 layers')
    emit('3. CUDA 8 layers')
    emit('4. CPU only')
    emit('5. Exit without starting model')
    try:
        answer = input('Choice [1]: ').strip() or '1'
    except EOFError:
        answer = '1'
    if answer == '5':
        return 0
    if answer not in choices:
        emit('[FAIL] Select 1-5.')
        return 2
    compute, backend = choices[answer]
    if not p.engine_installed(backend):
        emit('[FAIL] Engine detection returned false:', backend)
        return 3

    ok, reason = p.engine_probe(backend)
    emit('ENGINE SPAWN PROBE:', ok, str(reason).replace('\n', ' ')[:300])
    if not ok:
        emit('[FAIL] Engine could not start. Check for missing DLLs.')
        return 4

    emit('Trying actual model load / one translation. Initial load can take >30 sec.')
    if compute == 'cudaall':
        emit('NOTE: CUDA full offload can use several GiB VRAM. Keep the game closed during this test.')
    try:
        started = time.monotonic()
        url = p.LOCAL_SERVER.ensure_started(model_key, compute)
        elapsed = time.monotonic() - started
        emit('[OK] MODEL LOADED. startup seconds:', round(elapsed, 2), 'URL:', url)
        started = time.monotonic()
        korean, replies = TranslationEngine('Local GGUF (offline)', portable_model=model_key,
                                            portable_compute=compute).translate(
            'We need backup! Two enemies on the roof!', [])
        took = time.monotonic() - started
        emit('[OK] TRANSLATION:', korean)
        emit('REPLY OPTIONS:', '; '.join(r.en for r in replies))
        emit('TRANSLATION SECONDS:', round(took, 2))
        if took > 6:
            emit('[WARN] This is TOO SLOW for realtime FPS captions. Try a smaller model or faster mode.')
        else:
            emit('[OK] This result may be usable for subtitles; test FPS and ongoing latency next.')
        return 0
    except Exception as exc:
        emit('[FAIL]', type(exc).__name__, str(exc))
        emit(traceback.format_exc()[-4000:])
        log_server_tail()
        return 1
    finally:
        p.LOCAL_SERVER.stop()
        emit('DIAGNOSTIC REPORT:', LOG_FILE)


if __name__ == '__main__':
    sys.exit(main())
