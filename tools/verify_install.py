"""Windows installation checks. Called as a .py file to avoid PowerShell 5.1 -c quoting bugs."""
import importlib
from pathlib import Path
import sys


def check_venv():
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError(f"Expected Python 3.11, found {sys.version.split()[0]}")
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("Not running in a Python virtual environment")
    root = Path(__file__).resolve().parents[1]
    expected_venv = (root / ".venv").resolve()
    if Path(sys.prefix).resolve() != expected_venv:
        raise RuntimeError(f"Wrong virtual environment: {sys.prefix}")
    print(f"Python virtual environment OK: {sys.version.split()[0]}")
    print(f"Executable: {sys.executable}")


def check_modules():
    for name in ("PySide6", "requests", "psutil", "sounddevice", "faster_whisper", "argostranslate", "huggingface_hub"):
        importlib.import_module(name)
    print("Required Python modules OK")


def main():
    check = sys.argv[1] if len(sys.argv) > 1 else "full"
    if check not in {"venv", "modules", "full"}:
        raise SystemExit("Usage: verify_install.py {venv|modules|full}")
    if check in {"venv", "full"}:
        check_venv()
    if check in {"modules", "full"}:
        check_modules()
    print(f"Verification completed: {check}")


if __name__ == "__main__":
    main()
