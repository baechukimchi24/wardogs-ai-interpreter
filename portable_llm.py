"""Project-local GGUF model downloads and a managed llama.cpp subprocess.

No Ollama, global Python changes, microphone routing or injected game code.
An engine executable is downloaded only when explicitly requested by the user.
"""
from __future__ import annotations
from app_paths import APP_ROOT
from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import socket
import subprocess
import tempfile
import hashlib
import threading
import time
import zipfile

import requests

ROOT = APP_ROOT
MODELS_DIR = ROOT / 'models'
ENGINES_DIR = ROOT / 'engines'
RELEASES_API = 'https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=15'
# Known official releases with Windows binaries. Used if the GitHub releases API
# is rate-limited or returns unexpected metadata. Never mix releases or CUDA versions.
PINNED_RELEASE_TAGS = ('b11755', 'b11750')


@dataclass(frozen=True)
class ModelSpec:
    key: str
    label: str
    repo: str
    filename: str
    size_gb: float
    license_note: str


MODEL_CATALOG: dict[str, ModelSpec] = {
    'qwen3-4b-q4': ModelSpec(
        'qwen3-4b-q4', 'Qwen3 4B (Q4_K_M · 약 2.5GB · Apache 2.0)',
        'Qwen/Qwen3-4B-GGUF', 'Qwen3-4B-Q4_K_M.gguf', 2.5, 'Apache-2.0'),
    'qwen35-08b-q4': ModelSpec(
        'qwen35-08b-q4', 'Qwen3.5 0.8B (Q4_K_M · 약 0.5GB · Apache 2.0)',
        'unsloth/Qwen3.5-0.8B-GGUF', 'Qwen3.5-0.8B-Q4_K_M.gguf', 0.54, 'Apache-2.0'),
    'qwen35-2b-q4': ModelSpec(
        'qwen35-2b-q4', 'Qwen3.5 2B (Q4_K_M · 약 1.28GB · Apache 2.0)',
        'unsloth/Qwen3.5-2B-GGUF', 'Qwen3.5-2B-Q4_K_M.gguf', 1.28, 'Apache-2.0'),
    'qwen35-4b-q4': ModelSpec(
        'qwen35-4b-q4', 'Qwen3.5 4B (Q4_K_M · 약 2.7GB · Apache 2.0)',
        'unsloth/Qwen3.5-4B-GGUF', 'Qwen3.5-4B-Q4_K_M.gguf', 2.74, 'Apache-2.0'),
    'exaone35-24b-q4': ModelSpec(
        'exaone35-24b-q4', 'EXAONE 3.5 2.4B (Q4_K_M · 약 1.6GB · 연구/비상업)',
        'bartowski/EXAONE-3.5-2.4B-Instruct-GGUF',
        'EXAONE-3.5-2.4B-Instruct-Q4_K_M.gguf', 1.64,
        'EXAONE AI Model License 1.1 - NC (연구 목적/비상업적 조건 확인 필수)'),
}


def model_path(key: str) -> Path:
    if key not in MODEL_CATALOG:
        raise ValueError('목록에 없는 번역 모델입니다.')
    return MODELS_DIR / MODEL_CATALOG[key].filename


def model_installed(key: str) -> bool:
    path = model_path(key)
    # Avoid accepting a tiny interrupted/HTML download as a GGUF model.
    
    if not path.is_file() or path.stat().st_size <= 100 * 1024 * 1024:
        return False
    with path.open('rb') as handle:
        return handle.read(4) == b'GGUF'


def download_model(key: str, notify=lambda _message: None) -> Path:
    """Download exactly one vetted GGUF file via the HF SDK (resumable/cached)."""
    if key not in MODEL_CATALOG:
        raise ValueError('알 수 없는 모델입니다.')
    spec = MODEL_CATALOG[key]
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if model_installed(key):
        notify(f'이미 설치됨: {spec.label}')
        return model_path(key)
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError('모델 다운로드 기능이 없습니다. setup_windows.bat을 한 번 더 실행하세요.') from exc
    notify(f'다운로드 시작: {spec.label} (인터넷 연결 필요, 시간이 걸릴 수 있음)')
    result = Path(hf_hub_download(
        repo_id=spec.repo, filename=spec.filename,
        local_dir=str(MODELS_DIR),
    ))
    if result.resolve() != model_path(key).resolve() or not model_installed(key):
        raise RuntimeError('다운로드 파일 검증 실패. 모델을 다시 다운로드하세요.')
    notify(f'모델 다운로드 완료: {spec.label}')
    return result


def engine_path(backend: str) -> Path:
    if backend not in ('cpu', 'cuda', 'vulkan'):
        raise ValueError('지원하지 않는 실행 엔진입니다.')
    return ENGINES_DIR / backend / 'llama-server.exe'


def engine_installed(backend: str) -> bool:
    """Identify a completed portable installation, including small PE launchers.

    Windows llama.cpp releases can ship a tiny (e.g. 9216-byte) PE launcher
    whose implementation resides in adjacent DLLs. The old 100 KB minimum
    incorrectly classified a *working* executable as missing. This predicate
    checks the successful-install marker, adjacent DLLs and PE signature;
    engine_probe() separately verifies that Windows can actually spawn it.
    """
    folder = engine_path(backend).parent
    path = engine_path(backend)
    if not (path.is_file() and (folder / '.installed').is_file()
            and any(folder.glob('ggml*.dll'))):
        return False
    try:
        # A real 9 KB Windows launcher is legitimate; reject empty/tiny files.
        if path.stat().st_size < 4096:
            return False
        with path.open('rb') as handle:
            return handle.read(2) == b'MZ'
    except OSError:
        return False


def _asset_url(asset: dict) -> bool:
    return bool(re.fullmatch(
        r'https://github\.com/ggml-org/llama\.cpp/releases/download/[^/]+/[^/]+',
        str(asset.get('browser_download_url', ''))))


def _select_asset(assets: list[dict], pattern: str) -> dict:
    found = [a for a in assets if re.fullmatch(pattern, a.get('name', ''), re.IGNORECASE) and _asset_url(a)]
    if len(found) != 1:
        raise RuntimeError(f'공식 Windows 실행 파일 누락: {pattern}')
    return found[0]


def select_release_assets(assets: list[dict], backend: str) -> list[dict]:
    """Select SAME-RELEASE engine+runtime, never mix incompatible CUDA versions.

    v0.6 used only releases/latest and fixed two CUDA versions. Pre-releases
    and asset naming/availability can differ, so callers now scan releases.
    """
    if backend == 'cpu':
        return [_select_asset(assets, r'llama-[^-]+-bin-win-cpu-x64\.zip')]
    if backend == 'vulkan':
        return [_select_asset(assets, r'llama-[^-]+-bin-win-vulkan-x64\.zip')]
    if backend == 'cuda':
        candidates = []
        for asset in assets:
            match = re.fullmatch(r'llama-[^-]+-bin-win-cuda-(1[23]\.\d+)-x64\.zip', asset.get('name', ''))
            if not match or not _asset_url(asset):
                continue
            version = match.group(1)
            try:
                runtime = _select_asset(assets, rf'cudart-llama-bin-win-cuda-{re.escape(version)}-x64\.zip')
            except RuntimeError:
                continue
            # RTX 50 (Blackwell): prefer modern 13.x, otherwise 12.4 fallback.
            version_major, version_minor = (int(x) for x in version.split('.'))
            candidates.append(((version_major, version_minor), asset, runtime))
        if not candidates:
            raise RuntimeError('CUDA 실행 파일과 DLL이 동일한 버전으로 제공되는 릴리스가 없습니다.')
        _ver, binary, runtime = max(candidates, key=lambda group: group[0])
        return [binary, runtime]
    raise ValueError('지원하지 않는 백엔드입니다.')


def find_compatible_release(releases: list[dict], backend: str) -> tuple[str, list[dict]]:
    """Find usable Windows assets in multiple releases; skip incomplete releases."""
    for release in releases:
        assets = release.get('assets') or []
        if release.get('draft') or not isinstance(assets, list):
            continue
        try:
            selection = select_release_assets(assets, backend)
        except RuntimeError:
            continue
        return str(release.get('tag_name', 'unknown')), selection
    raise RuntimeError(
        '최근 공식 llama.cpp 릴리스 15개에서도 필요한 Windows 실행 파일을 찾지 못했습니다. '
        '네트워크/프록시 확인 후 재시도하거나 Vulkan/CPU 엔진을 선택하세요.'
    )


def pinned_release_assets(backend: str, tag: str = 'b11755') -> list[dict]:
    """Known official upstream release URLs; bypass GitHub API rate limiting."""
    if not re.fullmatch(r'b[0-9]+', tag):
        raise ValueError('허용되지 않은 릴리스 태그')
    base = f'https://github.com/ggml-org/llama.cpp/releases/download/{tag}/'
    if backend == 'cpu':
        names = [f'llama-{tag}-bin-win-cpu-x64.zip']
    elif backend == 'vulkan':
        names = [f'llama-{tag}-bin-win-vulkan-x64.zip']
    elif backend == 'cuda':
        # 12.4 is present on official Windows x64 releases, including this tag.
        # The same version must be used for engine and bundled libraries.
        names = [f'llama-{tag}-bin-win-cuda-12.4-x64.zip',
                 'cudart-llama-bin-win-cuda-12.4-x64.zip']
    else:
        raise ValueError('지원하지 않는 엔진')
    return [{'name': name, 'browser_download_url': base + name} for name in names]


def engine_probe(backend: str, folder: Path | None = None) -> tuple[bool, str]:
    """Actually spawn llama-server without loading a model; verify DLL/EXE startup.

    This is not a GPU model benchmark. A successful probe does not prove that
    a particular model can fit in VRAM. The in-app demo checks that next.
    """
    folder = folder or engine_path(backend).parent
    exe = folder / 'llama-server.exe'
    if not exe.is_file():
        return False, f'{exe} 파일 없음'
    if not list(folder.glob('ggml*.dll')):
        return False, f'{folder}에 ggml*.dll 없음'
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    try:
        outcome = subprocess.run([str(exe), '--version'], cwd=str(folder),
                                 stdin=subprocess.DEVNULL, capture_output=True,
                                 text=True, errors='replace', timeout=25,
                                 creationflags=flags)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f'실행 실패: {exc}'
    response = (outcome.stdout + '\n' + outcome.stderr).strip()[-1200:]
    if outcome.returncode != 0:
        return False, f'실행 종료 코드 {outcome.returncode}: {response}'
    return True, f'실행 파일 정상 (모델 로딩은 데모에서 확인): {response[:250]}'



def _download_archive(session: requests.Session, asset: dict, target: Path, notify):
    url = asset['browser_download_url']
    expected_size = asset.get('size')
    digest = str(asset.get('digest') or '')
    hasher = hashlib.sha256()
    with session.get(url, stream=True, timeout=(20, 180), allow_redirects=True) as response:
        response.raise_for_status()
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' in content_type:
            raise RuntimeError('GitHub가 ZIP 대신 HTML을 반환했습니다. 네트워크/보안 프로그램을 확인하세요.')
        size = int(response.headers.get('Content-Length') or 0)
        downloaded = 0
        next_mark = 10
        with target.open('wb') as output:
            for block in response.iter_content(chunk_size=1024 * 1024):
                if not block:
                    continue
                output.write(block)
                hasher.update(block)
                downloaded += len(block)
                if size and downloaded * 100 >= next_mark * size:
                    notify(f'엔진 파일 {asset["name"]}: {min(100, downloaded * 100 // size)}%')
                    next_mark = (downloaded * 100 // size // 10 + 1) * 10
    if target.stat().st_size < 10000 or not zipfile.is_zipfile(target):
        raise RuntimeError('유효한 ZIP을 다운로드하지 못했습니다. 다운로드 차단 여부를 확인하세요.')
    if isinstance(expected_size, int) and expected_size > 0 and expected_size != downloaded:
        raise RuntimeError(f'ZIP 크기 불일치 ({downloaded:,}/{expected_size:,}바이트)')
    if digest.startswith('sha256:') and hasher.hexdigest().lower() != digest[7:].lower():
        raise RuntimeError('공식 SHA256 검증 실패. 손상된 ZIP을 삭제했습니다.')


def _extract_release_zip_flat(source: Path, destination: Path):
    """Flatten trusted-format executables and libraries with traversal/size checks."""
    allowed = {'.dll', '.exe'}
    with zipfile.ZipFile(source) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            name = Path(member.filename.replace('\\', '/')).name
            if not name or Path(name).suffix.lower() not in allowed:
                continue
            if member.file_size > 2 * 1024 * 1024 * 1024:
                raise RuntimeError(f'비정상적으로 큰 배포 파일: {name}')
            with archive.open(member) as content, (destination / name).open('wb') as output:
                shutil.copyfileobj(content, output)


def install_engine(backend: str, notify=lambda _message: None, *, force: bool = False) -> Path:
    """Install official Windows llama.cpp exe + libraries and smoke-test startup.

    First try release metadata; when GitHub REST API is blocked, retry known
    official release asset URLs directly. Failed attempts never destroy an
    existing working engine, and do not write a success marker.
    """
    if backend not in ('cpu', 'cuda', 'vulkan'):
        raise ValueError('지원하지 않는 백엔드입니다.')
    if not force and engine_installed(backend):
        healthy, reason = engine_probe(backend)
        if healthy:
            notify(f'{backend.upper()} 엔진 실행 가능: {reason}')
            return engine_path(backend)
        notify(f'기존 엔진 재설치 필요: {reason}')
    headers = {'User-Agent': 'WardogsInterpreterPortable/0.7.1-engine-repair',
               'Accept': 'application/vnd.github+json'}
    failures: list[str] = []
    choices: list[tuple[str, list[dict]]] = []
    with requests.Session() as session:
        try:
            if os.environ.get('WARDOGS_ENGINE_DIRECT') == '1':
                raise RuntimeError('복구 모드: 공식 릴리스 직링크 사용')
            notify('GitHub 릴리스 메타데이터 확인 중…')
            res = session.get(RELEASES_API, headers=headers, timeout=(15, 35))
            res.raise_for_status()
            releases = res.json()
            if not isinstance(releases, list):
                raise RuntimeError('릴리스 JSON이 배열이 아닙니다.')
            tag, assets = find_compatible_release(releases, backend)
            choices.append((tag, assets))
        except Exception as exc:
            failures.append(f'GitHub API: {exc}')
            notify(f'릴리스 API 사용 불가. 공식 파일 직접 다운로드로 전환: {exc}')
        for tag in PINNED_RELEASE_TAGS:
            if not any(known_tag == tag for known_tag, _ in choices):
                choices.append((tag, pinned_release_assets(backend, tag)))
        ENGINES_DIR.mkdir(parents=True, exist_ok=True)
        for tag, assets in choices:
            notify(f'공식 {tag} {backend.upper()} 엔진 설치 시도')
            try:
                with tempfile.TemporaryDirectory(prefix='llama-', dir=ENGINES_DIR) as tmp:
                    work = Path(tmp)
                    new = work / 'runtime'
                    new.mkdir()
                    for number, asset in enumerate(assets, 1):
                        notify(f'[{number}/{len(assets)}] {asset["name"]} 다운로드')
                        archive = work / f'{number}.zip'
                        _download_archive(session, asset, archive, notify)
                        _extract_release_zip_flat(archive, new)
                    ok, reason = engine_probe(backend, new)
                    if not ok:
                        raise RuntimeError(f'다운로드된 엔진은 실행 불가: {reason}')
                    (new / '.installed').write_text(f'{tag}\n{backend}\nverified\n', encoding='utf-8')
                    final = ENGINES_DIR / backend
                    # Preserve a previously working engine until the new one passes the probe.
                    old = ENGINES_DIR / (backend + '.previous')
                    if old.exists():
                        shutil.rmtree(old)
                    if final.exists():
                        final.rename(old)
                    try:
                        shutil.move(str(new), str(final))
                    except Exception:
                        if old.exists() and not final.exists():
                            old.rename(final)
                        raise
                    if old.exists():
                        shutil.rmtree(old)
                    notify(f'{backend.upper()} 엔진 설치 + 실행 검증 완료: {reason}')
                    return engine_path(backend)
            except Exception as exc:
                failures.append(f'{tag}: {type(exc).__name__}: {exc}')
                notify(f'{tag} 설치 실패: {exc}')
                continue
    raise RuntimeError('\n'.join([
        f'공식 {backend.upper()} 엔진 다운로드 또는 실행 검증에 실패했습니다.',
        *failures[-8:],
        'CPU 또는 Vulkan 엔진을 선택해 먼저 테스트하거나 logs\\engine-repair.log를 확인하세요.',
    ]))


class LocalServer:
    """Manage a single loopback-only llama-server for one chosen GGUF model."""
    def __init__(self):
        self._lock = threading.RLock()
        self._process: subprocess.Popen | None = None
        self._log = None
        self._url = ''
        self._signature = None

    def stop(self):
        with self._lock:
            if self._process is not None:
                if self._process.poll() is None:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                self._process = None
            if self._log:
                self._log.close()
                self._log = None
            self._url = ''
            self._signature = None

    def _ready(self, url: str) -> bool:
        try:
            res = requests.get(url + '/health', timeout=0.75)
            return res.status_code == 200
        except requests.RequestException:
            return False

    def ensure_started(self, model_key: str, compute: str) -> str:
        """compute: cpu, cuda8, cudaall; bound to 127.0.0.1 only."""
        if compute not in ('cpu', 'cuda8', 'cuda16', 'cudaall', 'vulkan8', 'vulkan16'):
            raise ValueError('잘못된 모델 실행 모드입니다.')
        if not model_installed(model_key):
            raise FileNotFoundError('번역 모델이 설치되지 않았습니다. 프로그램의 [모델 다운로드] 버튼을 누르세요.')
        backend = 'cpu' if compute == 'cpu' else 'vulkan' if compute.startswith('vulkan') else 'cuda'
        binary = engine_path(backend)
        if not engine_installed(backend):
            raise FileNotFoundError(f'포터블 {backend.upper()} 엔진이 없습니다. [엔진 다운로드] 버튼을 누르세요.')
        signature = (model_key, compute)
        with self._lock:
            if (self._signature == signature and self._process is not None
                    and self._process.poll() is None and self._ready(self._url)):
                return self._url
            self.stop()
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sk:
                sk.bind(('127.0.0.1', 0))
                port = sk.getsockname()[1]
            url = f'http://127.0.0.1:{port}'
            layers = '0' if compute == 'cpu' else '8' if compute.endswith('8') else '16' if compute.endswith('16') else '999'
            args = [str(binary), '--model', str(model_path(model_key)),
                    '--host', '127.0.0.1', '--port', str(port),
                    '--n-gpu-layers', layers, '--ctx-size', '1536',
                    '--threads', '4', '--parallel', '1', '--batch-size', '128']
            logs = ROOT / 'logs'
            logs.mkdir(exist_ok=True)
            self._log = (logs / 'llama-server.log').open('wb')
            flags = (getattr(subprocess, 'CREATE_NO_WINDOW', 0) |
                     getattr(subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0))
            try:
                self._process = subprocess.Popen(
                    args, cwd=str(binary.parent), stdout=self._log,
                    stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                    creationflags=flags)
                self._signature = signature
                self._url = url
                until = time.monotonic() + 65
                while time.monotonic() < until:
                    if self._process.poll() is not None:
                        raise RuntimeError('로컬 엔진이 종료됐습니다. logs\\llama-server.log를 확인하세요.')
                    if self._ready(url):
                        return url
                    time.sleep(0.4)
                raise TimeoutError('모델 준비가 65초 내에 끝나지 않았습니다. logs\\llama-server.log 확인')
            except Exception:
                self.stop()
                raise


LOCAL_SERVER = LocalServer()
