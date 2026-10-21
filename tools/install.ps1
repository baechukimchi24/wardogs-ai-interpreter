# WARDOGS v0.9: one-action project-local installer; no Visual Studio required.
# Requires internet and Windows PowerShell 5.1+; the executable is precompiled.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
$log = Join-Path $root 'install.log'
try { Start-Transcript -Path $log -Append -ErrorAction Stop | Out-Null } catch { }
try {
    $tools = Join-Path $root '.tools'
    $pythonHome = Join-Path $root '.python'
    $cache = Join-Path $root '.uv-cache'
    $venv = Join-Path $root '.venv'
    $uv = Join-Path $tools 'uv.exe'
    $venvPython = Join-Path $venv 'Scripts\python.exe'
    $env:UV_UNMANAGED_INSTALL = $tools
    $env:UV_PYTHON_INSTALL_DIR = $pythonHome
    $env:UV_PYTHON_INSTALL_BIN = '0'
    $env:UV_NO_MODIFY_PATH = '1'
    $env:UV_CACHE_DIR = $cache
    $env:ARGOS_PACKAGES_DIR = Join-Path $root 'models\argos-packages'
    $env:ARGOS_DEVICE_TYPE = 'cpu'
    $env:XDG_DATA_HOME = Join-Path $root '.local-data'
    $env:XDG_CONFIG_HOME = Join-Path $root '.local-config'
    $env:XDG_CACHE_HOME = Join-Path $root '.local-cache'
    $env:HF_HOME = Join-Path $root '.cache\huggingface'
    New-Item -ItemType Directory -Path $tools -Force | Out-Null

    if (-not (Test-Path $uv)) {
        Write-Host '[1/5] Installing project-local uv...' -ForegroundColor Cyan
        # Astral's official bootstrap is not persisted to global PATH.
        $installer = Join-Path $tools 'uv-install.ps1'
        Invoke-WebRequest -Uri 'https://astral.sh/uv/install.ps1' -OutFile $installer -UseBasicParsing
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $installer
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path $uv)) { throw 'uv bootstrap failed in .tools folder.' }
    }

    Write-Host '[2/5] Preparing project-local Python 3.11...' -ForegroundColor Cyan
    & $uv python install 3.11 --no-bin
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 download failed.' }
    $base = Get-ChildItem -Path $pythonHome -Directory -Filter 'cpython-3.11.*-windows-x86_64-none' |
        Sort-Object Name -Descending |
        ForEach-Object { Join-Path $_.FullName 'python.exe' } |
        Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $base) { throw 'Project-local Python 3.11 not found after installation.' }
    $valid = $false
    if (Test-Path $venvPython) {
        & $venvPython (Join-Path $root 'tools\verify_install.py') venv
        $valid = ($LASTEXITCODE -eq 0)
    }
    if (-not $valid) {
        & $base -m venv --clear --without-pip $venv
        if ($LASTEXITCODE -ne 0) { throw 'Could not create .venv with standard Python venv.' }
    }
    & $venvPython (Join-Path $root 'tools\verify_install.py') venv
    if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment could not start.' }

    Write-Host '[3/5] Installing Python app and offline translation packages...' -ForegroundColor Cyan
    & $uv pip install --python $venvPython -r (Join-Path $root 'requirements.txt') -r (Join-Path $root 'requirements-optional.txt') pip
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
    & $venvPython (Join-Path $root 'tools\verify_install.py') modules
    if ($LASTEXITCODE -ne 0) { throw 'One of the required Python modules cannot be imported.' }

    Write-Host '[4/5] Verifying bundled Windows audio capture helper (no C++ build)...' -ForegroundColor Cyan
    $nativeExe = Join-Path $root 'bin\process_loopback.exe'
    $nativeHashFile = Join-Path $root 'bin\process_loopback.sha256'
    if (-not (Test-Path $nativeExe) -or -not (Test-Path $nativeHashFile)) {
        throw 'Bundled audio capture helper missing. Re-extract the complete ZIP; no Visual Studio is needed.'
    }
    $expectedHash = (Get-Content -LiteralPath $nativeHashFile -TotalCount 1 -ErrorAction Stop).Trim().ToUpperInvariant()
    $actualHash = (Get-FileHash -LiteralPath $nativeExe -Algorithm SHA256).Hash.ToUpperInvariant()
    if ($actualHash -ne $expectedHash) {
        throw 'Bundled capture exe SHA256 mismatch. Do not run it; re-download the ZIP.'
    }
    & $nativeExe --self-test
    if ($LASTEXITCODE -ne 0) { throw 'The bundled capture exe cannot run on this Windows PC.' }

    Write-Host '[5/5] Installing free English-to-Korean Argos starter model...' -ForegroundColor Cyan
    & $venvPython (Join-Path $root 'install_argos_ko.py')
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'Argos package download failed. You may still start the app and install Qwen GGUF via the one-click model button.'
    }
    & $venvPython (Join-Path $root 'tools\verify_install.py') full
    if ($LASTEXITCODE -ne 0) { throw 'Python verification failed.' }
    Write-Host '[OK] v0.9 portable installation finished. No Visual Studio needed.' -ForegroundColor Green
    Write-Host 'AI models are downloaded by choosing a model in the app and clicking one-click install.'
    exit 0
} catch {
    Write-Host ('[ERROR] ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Log: ' + $log) -ForegroundColor Yellow
    exit 1
} finally {
    try { Stop-Transcript | Out-Null } catch { }
}
