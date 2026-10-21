"""Local Windows diagnostics; never prints API keys or personal game audio."""
from pathlib import Path
import platform
import subprocess
import sys

print("=== WARDOGS INTERPRETER SYSTEM CHECK ===")
print("OS:", platform.platform())
print("Python:", sys.version.split()[0], "64-bit:", sys.maxsize > 2**32)
print("Native capture exe:", (Path(__file__).parent / "bin" / "process_loopback.exe").exists())

try:
    import psutil
    games = [(p.info['pid'], p.info['name']) for p in psutil.process_iter(['pid','name'])
             if (p.info['name'] or '').lower() == 'wardogsclient-win64-shipping.exe']
    print("WARDOGS game PID(s):", games or "none (launch the game first)")
except Exception as e:
    print("Process check error:", type(e).__name__, str(e)[:250])

try:
    gpu = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,driver_version',
                          '--format=csv,noheader'], capture_output=True, text=True, timeout=4)
    print("GPU:", gpu.stdout.strip() or gpu.stderr.strip()[:150])
except Exception as e:
    print("GPU info unavailable:", type(e).__name__)

try:
    import sounddevice as sd
    print("Playback devices:")
    apis = sd.query_hostapis()
    for i, dev in enumerate(sd.query_devices()):
        if dev['max_output_channels'] > 0:
            print(" ", i, dev['name'], '[' + apis[dev['hostapi']]['name'] + ']')
except Exception as e:
    print("Playback device error:", type(e).__name__, str(e)[:200])

try:
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    voice = win32com.client.Dispatch('SAPI.SpVoice')
    print("SAPI voices:")
    voices = voice.GetVoices()
    for i in range(voices.Count):
        item = voices.Item(i)
        print(" ", item.GetDescription(), 'language hex:', item.GetAttribute('Language'))
    pythoncom.CoUninitialize()
except Exception as e:
    print("Windows SAPI error:", type(e).__name__, str(e)[:200])

try:
    import ctranslate2
    print("CTranslate2 CUDA devices:", ctranslate2.get_cuda_device_count())
except Exception as e:
    print("CTranslate2 GPU check error:", type(e).__name__, str(e)[:200])
print("=== END ===")
