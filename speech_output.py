"""Windows SAPI TTS -> WAV -> a user-selected Windows playback endpoint.

Playback devices include hardware interfaces and third-party virtual outputs
(e.g., Muzychenko Virtual Audio Cable Line 1). The app never changes Windows'
default endpoint or the user's microphone/audio-interface routing.
"""
from __future__ import annotations
from concurrent.futures import Future
from dataclasses import dataclass
import os
import queue
import tempfile
import threading
import wave

import numpy as np
from scipy.signal import resample_poly
import sounddevice as sd


@dataclass
class PlaybackRequest:
    text: str
    language: str
    device: int


@dataclass(frozen=True)
class OutputEndpoint:
    label: str
    index: int
    key: str
    name: str
    api: str


def output_devices() -> list[OutputEndpoint]:
    """Enumerate *playback* endpoints; use a stable key for saved selections.

    PortAudio integer indices can change if other devices are connected. Keep
    the index only for the current session and persist API/name/occurrence.
    """
    devices = sd.query_devices()
    apis = sd.query_hostapis()
    endpoints: list[OutputEndpoint] = []
    duplicates: dict[tuple[str, str], int] = {}
    for i, dev in enumerate(devices):
        if int(dev["max_output_channels"]) <= 0:
            continue
        api = str(apis[int(dev["hostapi"])]["name"])
        name = str(dev["name"])
        identity = (api.casefold(), name.casefold())
        occurrence = duplicates.get(identity, 0)
        duplicates[identity] = occurrence + 1
        key = f"{identity[0]}|{identity[1]}|{occurrence}"
        endpoints.append(OutputEndpoint(
            label=f"{name}  [{api}]  (출력 ID {i})",
            index=i, key=key, name=name, api=api,
        ))
    # Prefer WASAPI for Windows 11, but allow any usable audio host API.
    endpoints.sort(key=lambda item: ("wasapi" not in item.api.casefold(), item.name.casefold(), item.api.casefold()))
    return endpoints


def _select_sapi_voice(voice, language: str) -> None:
    target = 0x0412 if language == "ko" else 0x0409
    tokens = voice.GetVoices()
    for i in range(tokens.Count):
        item = tokens.Item(i)
        langs = item.GetAttribute("Language")
        vals = [v.strip() for v in langs.split(";") if v.strip()]
        if any(int(v, 16) == target for v in vals):
            voice.Voice = item
            return
    raise RuntimeError(
        "Windows SAPI 한국어 음성이 설치되어 있지 않습니다. Windows 언어 및 음성 설정에서 한국어 음성을 추가하세요."
        if language == "ko" else "Windows SAPI 영어 음성이 설치되어 있지 않습니다. 영어 음성을 설치하세요."
    )


def synthesize_windows(text: str, language: str) -> tuple[np.ndarray, int]:
    """COM must be initialized on the caller thread. Returns mono float32 audio."""
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    fd, filename = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        _select_sapi_voice(voice, language)
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        stream.Open(filename, 3, False)  # SSFMCreateForWrite
        voice.AudioOutputStream = stream
        voice.Speak(text, 0)  # synchronous -> file
        stream.Close()
        with wave.open(filename, "rb") as wav:
            sample_rate = wav.getframerate()
            raw = wav.readframes(wav.getnframes())
            channels = wav.getnchannels()
            sampwidth = wav.getsampwidth()
        if sampwidth != 2:
            raise RuntimeError(f"SAPI generated unsupported sample width: {sampwidth}")
        samples = np.frombuffer(raw, dtype="<i2").reshape(-1, channels)
        mono = samples.astype(np.float32).mean(axis=1) / 32768.0
        return mono, sample_rate
    finally:
        try:
            os.unlink(filename)
        except OSError:
            pass
        pythoncom.CoUninitialize()


class SpeechPlayer:
    """Serial playback; caller supplies selected output device for EACH utterance."""
    def __init__(self, on_error=None):
        self.work = queue.Queue(maxsize=8)
        self.on_error = on_error or (lambda message: None)
        self.alive = True
        self.thread = threading.Thread(target=self._run, name="SAPI-audio-output", daemon=True)
        self.thread.start()

    def send(self, text: str, language: str, device: int) -> bool:
        if not text.strip() or device is None:
            return False
        try:
            self.work.put_nowait(PlaybackRequest(text.strip(), language, int(device)))
            return True
        except queue.Full:
            self.on_error("음성 재생 대기열이 가득 찼습니다.")
            return False

    def _run(self):
        while self.alive:
            task = self.work.get()
            if task is None:
                break
            try:
                samples, sr = synthesize_windows(task.text, task.language)
                device_info = sd.query_devices(task.device, kind="output")
                target_sr = int(device_info["default_samplerate"])
                if not target_sr:
                    target_sr = sr
                if target_sr != sr:
                    from math import gcd
                    g = gcd(target_sr, sr)
                    samples = resample_poly(samples, target_sr // g, sr // g).astype(np.float32)
                channels = min(2, int(device_info["max_output_channels"]))
                output = samples[:, None] if channels == 1 else np.repeat(samples[:, None], 2, axis=1)
                with sd.OutputStream(device=task.device, samplerate=target_sr,
                                     channels=channels, dtype="float32") as stream:
                    stream.write(np.ascontiguousarray(output, dtype=np.float32))
            except Exception as exc:
                self.on_error(f"TTS 장치 출력 실패: {exc}")

    def stop(self):
        self.alive = False
        try:
            self.work.put_nowait(None)
        except queue.Full:
            pass
