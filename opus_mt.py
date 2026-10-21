"""Optional Marian OPUS-MT English -> Korean CPU translator, project-local weights.

This model is independent of GGUF/llama.cpp. Download only on user request.
Never modifies system Python and never sends user transcripts to a server.
"""
from __future__ import annotations
from app_paths import APP_ROOT
from functools import lru_cache
from pathlib import Path
import re

ROOT = APP_ROOT
OPUS_DIR = ROOT / 'models' / 'opus-mt-en-ko'
OPUS_REPO = 'Helsinki-NLP/opus-mt-tc-big-en-ko'


def installed() -> bool:
    return (OPUS_DIR / 'config.json').is_file() and (OPUS_DIR / 'model.safetensors').is_file() \
        and (OPUS_DIR / 'source.spm').is_file() and (OPUS_DIR / 'target.spm').is_file()


def install(notify=lambda _text: None) -> Path:
    if installed():
        notify('OPUS-MT 영어→한국어 모델이 이미 설치되어 있습니다.')
        return OPUS_DIR
    from huggingface_hub import snapshot_download
    OPUS_DIR.mkdir(parents=True, exist_ok=True)
    notify('OPUS-MT CPU 번역 모델 다운로드 중 (약 420MB + 토크나이저)…')
    snapshot_download(repo_id=OPUS_REPO, local_dir=str(OPUS_DIR),
                      allow_patterns=['config.json', 'generation_config.json',
                                      'model.safetensors', 'source.spm', 'target.spm',
                                      'vocab.json', 'tokenizer_config.json', 'special_tokens_map.json'])
    if not installed():
        raise RuntimeError('OPUS-MT 모델 파일이 불완전합니다. 인터넷 연결 및 다운로드 로그를 확인하세요.')
    notify('OPUS-MT 다운로드 완료 (모델은 실제 번역 시 CPU에 로딩됩니다).')
    return OPUS_DIR


@lru_cache(maxsize=1)
def _load():
    if not installed():
        raise FileNotFoundError('OPUS-MT가 설치되지 않았습니다. [OPUS-MT 다운로드]를 누르세요.')
    import torch
    from transformers import MarianMTModel, MarianTokenizer
    torch.set_num_threads(min(torch.get_num_threads(), 2))  # avoid contending with the game
    tok = MarianTokenizer.from_pretrained(str(OPUS_DIR), local_files_only=True)
    model = MarianMTModel.from_pretrained(str(OPUS_DIR), local_files_only=True).to('cpu')
    model.eval()
    return tok, model


def translate(text: str) -> str:
    import torch
    tok, model = _load()
    tokens = tok(text.strip(), return_tensors='pt', truncation=True, max_length=160)
    with torch.inference_mode():
        out = model.generate(**tokens, num_beams=1, do_sample=False, max_new_tokens=72)
    answer = tok.batch_decode(out, skip_special_tokens=True)[0].strip()
    if not re.search(r'[가-힣]', answer):
        raise RuntimeError('OPUS-MT 번역 결과에 한국어가 없습니다.')
    return answer
