"""Capture and recognition threads. Never reads game memory or injects a hook."""
from __future__ import annotations
from app_paths import APP_ROOT
from collections import deque
from pathlib import Path
import os
import queue
import subprocess
import threading
import time
import traceback

import numpy as np
from PySide6.QtCore import QObject, Signal

from core import TranslationEngine, VoiceSegmenter, pcm48_stereo_to_16_mono, recommendations, offline_fallback
from speech_filter import SpeechNoiseFilter

ROOT = APP_ROOT
NATIVE = ROOT / "bin" / "process_loopback.exe"
NATIVE_FRAME_BYTES = 48000 * 2 * 2 * 30 // 1000   # 5760 bytes, exactly 30ms


def _offer(work: queue.Queue, item):
    """Keep live speech current by dropping oldest work if inference lags."""
    try:
        work.put_nowait(item)
    except queue.Full:
        try:
            work.get_nowait()
        except queue.Empty:
            pass
        try:
            work.put_nowait(item)
        except queue.Full:
            pass


class Signals(QObject):
    status = Signal(str)
    error = Signal(str)
    recognized = Signal(int, str)
    translated = Signal(int, str, object)
    download_done = Signal(str)
    model_applied = Signal(str, str, str)
    replies_ready = Signal(int, object)


class Interpreter:
    def __init__(self, signals: Signals):
        self.signals = signals
        self.active = threading.Event()
        self.capture_process: subprocess.Popen | None = None
        self.session = 0
        self.counter = 0
        self.lock = threading.Lock()
        self.replies_enabled = False  # Adjustable without restarting game capture.
        self.fast_backlog_fallback = True  # Favor prompt subtitles when LLM queue grows.
        self.dropped_clips = 0
        self.noise_filter = SpeechNoiseFilter()
        self.filtered_clips = 0

    def start(self, pid: int, vad_level: int, model_name: str, mode: str, api_key: str,
              portable_model: str = "qwen3-4b-q4", portable_compute: str = "cpu",
              min_voice_ms: int = 150, silence_end_ms: int = 300,
              recommendations_enabled: bool = False, fast_backlog_fallback: bool = True,
              ignored_phrases: str | None = None, block_single_fire: bool = True,
              suppress_repeats: bool = True):
        if self.active.is_set():
            return
        if not NATIVE.exists():
            raise FileNotFoundError(f"{NATIVE}가 없습니다. ZIP의 bin 폴더를 확인하세요.")
        self.session += 1
        this_session = self.session
        self.active.set()
        self.counter = 0
        self.dropped_clips = 0
        self.filtered_clips = 0
        self.noise_filter = SpeechNoiseFilter(ignored_phrases, block_single_fire, suppress_repeats)
        self.replies_enabled = bool(recommendations_enabled)
        self.fast_backlog_fallback = bool(fast_backlog_fallback)
        clips: queue.Queue = queue.Queue(maxsize=16)
        # Crucial: recognized text is NEVER dropped because a translation is slow.
        # Backpressure on recognition is preferable to silent subtitle loss.
        sentences: queue.Queue = queue.Queue(maxsize=128)
        reply_queue: queue.Queue = queue.Queue(maxsize=32)
        threads = [
            threading.Thread(target=self._capture,
                             args=(pid, vad_level, clips, this_session, min_voice_ms, silence_end_ms),
                             daemon=True),
            threading.Thread(target=self._recognize,
                             args=(model_name, clips, sentences, reply_queue, this_session), daemon=True),
            threading.Thread(target=self._translate,
                             args=(mode, api_key, sentences, this_session, portable_model, portable_compute),
                             daemon=True),
            threading.Thread(target=self._recommend, args=(reply_queue, this_session), daemon=True),
        ]
        for thread in threads:
            thread.start()
        self.signals.status.emit(f"게임 오디오 연결 중 · PID {pid} · 자막 우선 모드")

    def stop(self):
        self.active.clear()
        self.session += 1
        process = self.capture_process
        self.capture_process = None
        if process and process.poll() is None:
            process.terminate()
        self.signals.status.emit("중지됨")

    def _is_current(self, session: int) -> bool:
        return self.active.is_set() and session == self.session

    def _capture(self, pid: int, vad_level: int, clips: queue.Queue, session: int,
                 min_voice_ms: int = 150, silence_end_ms: int = 300):
        proc = None
        try:
            proc = subprocess.Popen([str(NATIVE), str(pid)], stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    bufsize=0, creationflags=subprocess.CREATE_NO_WINDOW)
            self.capture_process = proc
            detector = VoiceSegmenter(aggressiveness=vad_level,
                                      min_voice_ms=min_voice_ms,
                                      silence_end_ms=silence_end_ms)
            self.signals.status.emit("게임 소리 수집 중 · 음성 감지 대기")
            while self._is_current(session):
                buf = bytearray()
                while len(buf) < NATIVE_FRAME_BYTES and self._is_current(session):
                    data = proc.stdout.read(NATIVE_FRAME_BYTES - len(buf))
                    if not data:
                        break
                    buf.extend(data)
                if len(buf) < NATIVE_FRAME_BYTES:
                    break
                mono = pcm48_stereo_to_16_mono(bytes(buf))
                utterance = detector.feed(mono)
                if utterance is not None:
                    if clips.full():
                        self.dropped_clips += 1
                        self.signals.status.emit(
                            f"음성 인식 대기 초과: 오래된 오디오 {self.dropped_clips}개 폐기 "
                            "(작은 Whisper 모델 또는 VAD 설정 조정을 권장)")
                    _offer(clips, utterance)
            if self._is_current(session):
                detail = proc.stderr.read(4000).decode("utf-8", errors="replace").strip()
                # Normal stderr has a READY marker; exclude it from failure detail.
                detail = detail.replace("READY 48000 2 s16le", "").strip()
                if detail:
                    self.signals.error.emit(f"프로세스 오디오 수집 종료: {detail}")
                else:
                    self.signals.error.emit("워독스 프로세스가 종료되었거나 오디오 스트림이 끊겼습니다.")
                self.active.clear()
                self.signals.status.emit("오디오 수집 종료")
        except Exception as exc:
            if self._is_current(session):
                self.signals.error.emit(f"오디오 캡처 오류: {exc}")
                self.active.clear()
        finally:
            if proc and proc.poll() is None:
                proc.terminate()
            if self.capture_process is proc:
                self.capture_process = None

    def _recognize(self, model_name: str, clips: queue.Queue, sentences: queue.Queue,
                   reply_queue: queue.Queue, session: int):
        try:
            from faster_whisper import WhisperModel
            try:
                self.signals.status.emit(f"Whisper {model_name} · NVIDIA GPU 모델 준비 중")
                model = WhisperModel(model_name, device="cuda", compute_type="int8_float16",
                                     cpu_threads=4, num_workers=1)
                device = "GPU"
            except Exception as gpu_error:
                if not self._is_current(session):
                    return
                self.signals.error.emit("CUDA 사용 불가 → CPU 모드로 전환합니다. "
                                        "CUDA 12/cuDNN 9 설치 여부를 확인하세요. "
                                        f"({str(gpu_error)[:180]})")
                model = WhisperModel(model_name, device="cpu", compute_type="int8",
                                     cpu_threads=4, num_workers=1)
                device = "CPU"
            if self._is_current(session):
                self.signals.status.emit(f"음성 인식 준비 완료 ({model_name}, {device})")
            while self._is_current(session):
                try:
                    payload = clips.get(timeout=0.2)
                except queue.Empty:
                    continue
                samples = np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0
                segments, _info = model.transcribe(
                    samples, language="en", beam_size=1, best_of=1,
                    condition_on_previous_text=False, vad_filter=False,
                    no_speech_threshold=0.45,
                    initial_prompt="Sniper, objective, revive, ammunition, backup, medic, rooftop, flank."
                )
                segments = list(segments)
                text = " ".join(seg.text.strip() for seg in segments).strip()
                # Short tactical phrases such as "No", "Go", "OK" are valid.
                if not text or not any(ch.isalnum() for ch in text):
                    continue
                reason = self.noise_filter.reject(
                    text,
                    avg_logprob=min((getattr(seg, 'avg_logprob', 0) for seg in segments), default=0),
                    no_speech_prob=max((getattr(seg, 'no_speech_prob', 0) for seg in segments), default=0),
                )
                if reason:
                    self.filtered_clips += 1
                    # Only the counter/reason is shown; don't spam raw transcripts.
                    if self.filtered_clips <= 3 or self.filtered_clips % 10 == 0:
                        self.signals.status.emit(f'게임 효과음 의심 음성 무시: {self.filtered_clips}회 ({reason})')
                    continue
                if not self._is_current(session):
                    return
                with self.lock:
                    self.counter += 1
                    index = self.counter
                self.signals.recognized.emit(index, text)
                # Never discard a recognized sentence silently.
                while self._is_current(session):
                    try:
                        sentences.put((index, text), timeout=0.2)
                        backlog = sentences.qsize()
                        if backlog >= 2:
                            self.signals.status.emit(f"한국어 자막 번역 대기: {backlog}개 문장")
                        break
                    except queue.Full:
                        self.signals.status.emit("자막 대기열 포화 · 번역 모델을 경량 모델로 바꿔주세요")
                if self.replies_enabled:
                    _offer(reply_queue, (index, text))
        except Exception as exc:
            if self._is_current(session):
                self.signals.error.emit(f"음성 인식 오류: {exc}")

    def _translate(self, mode: str, api_key: str, sentences: queue.Queue, session: int,
                   portable_model: str, portable_compute: str):
        engine = TranslationEngine(mode, api_key, portable_model, portable_compute)
        recent: deque[str] = deque(maxlen=3)
        while self._is_current(session):
            try:
                index, text = sentences.get(timeout=0.25)
            except queue.Empty:
                continue
            try:
                # During bursts of recognized speech, avoid chaining slow LLM requests.
                # This is an intentional speed-versus-context tradeoff. The queued
                # sentence keeps its original index and is never replaced with a label.
                if (self.fast_backlog_fallback and sentences.qsize() >= 1
                        and mode not in ('Argos (offline)',)):
                    korean = offline_fallback(text)
                    self.signals.status.emit('연속 대사 감지: 빠른 Argos 자막으로 밀림 최소화')
                else:
                    # Subtitle only. Never request English replies from the LLM here.
                    korean, _ = engine.translate(text, list(recent))
            except Exception as exc:
                # A working Argos starter model was installed on first run.
                self.signals.status.emit(f"{mode} 응답 지연/오류 → Argos 대체 자막 사용")
                # No raw player transcripts are written to logs.
                import logging
                logging.warning("Subtitle fallback (%s): %s", mode, type(exc).__name__)
                try:
                    korean = offline_fallback(text)
                except Exception as fallback_error:
                    self.signals.error.emit(f"Argos 보조 번역 실패: {fallback_error}")
                    korean = "[번역 실패: 영어 원문을 확인하세요]"
            recent.append(text)
            if self._is_current(session):
                self.signals.translated.emit(index, korean, [])
                if sentences.qsize():
                    self.signals.status.emit(f"한국어 자막 번역 대기: {sentences.qsize()}개 문장")

    def _recommend(self, reply_queue: queue.Queue, session: int):
        """Cheap rule-based suggestions. Never competes for GGUF inference time."""
        while self._is_current(session):
            try:
                index, text = reply_queue.get(timeout=0.25)
            except queue.Empty:
                continue
            if self.replies_enabled and self._is_current(session):
                self.signals.replies_ready.emit(index, recommendations(text))
