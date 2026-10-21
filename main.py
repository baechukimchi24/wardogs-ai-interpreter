"""WARDOGS Interpreter -- external Windows 11 audio companion.
No screen scraping, injection, keyboard automation, or unattended microphone sending.
"""
from __future__ import annotations
from app_paths import APP_ROOT
import html
import json
import os
from pathlib import Path
import sys
ROOT_FOLDER = APP_ROOT
os.environ.setdefault('ARGOS_PACKAGES_DIR', str(ROOT_FOLDER / 'models' / 'argos-packages'))
os.environ.setdefault('ARGOS_DEVICE_TYPE', 'cpu')
os.environ.setdefault('XDG_DATA_HOME', str(ROOT_FOLDER / '.local-data'))
os.environ.setdefault('XDG_CONFIG_HOME', str(ROOT_FOLDER / '.local-config'))
os.environ.setdefault('XDG_CACHE_HOME', str(ROOT_FOLDER / '.local-cache'))
os.environ.setdefault('HF_HOME', str(ROOT_FOLDER / '.cache' / 'huggingface'))
import threading
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from core import Reply, TranslationEngine, recommendations, offline_fallback
from runtime import Interpreter, Signals, NATIVE
from speech_output import SpeechPlayer, output_devices
from overlay_hotkey import GlobalHotkey, KEYS
from opus_mt import installed as opus_installed, install as install_opus
from portable_llm import (MODEL_CATALOG, MODELS_DIR, model_installed, engine_installed,
                          download_model, install_engine, LOCAL_SERVER)

GAME_EXE = "WardogsClient-Win64-Shipping.exe"
SETTINGS = APP_ROOT / "config" / "settings.json"
DEVICE_KEY_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class Overlay(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus |
                         Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        layout = QVBoxLayout(self)
        self.label = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self.label.setObjectName("OverlayCaption")
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.label)
        self.resize(1000, 108)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def update_subtitle(self, en: str, ko: str, screen_index: int):
        screens = QGuiApplication.screens()
        if not screens:
            return
        screen = screens[min(max(screen_index, 0), len(screens) - 1)]
        rect = screen.availableGeometry()
        self.resize(min(1000, rect.width() - 40), 110)
        self.move(rect.x() + (rect.width() - self.width()) // 2,
                  rect.y() + rect.height() - self.height() - 40)
        self.label.setText(f"{en}\n{ko}")
        self.show()
        self.raise_()
        self.timer.start(6500)


class TranscriptCard(QFrame):
    def __init__(self, index: int, english: str, speak):
        super().__init__()
        self.setObjectName("TranscriptCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.speak = speak
        layout = QVBoxLayout(self)
        layout.setSpacing(7)
        stamp = datetime.now().strftime("%H:%M:%S")
        self.header = QLabel(f"<b>EN</b> <span style='color:#9ca3af'>{stamp}</span>")
        self.header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.header)
        en = QLabel(english)
        en.setWordWrap(True)
        en.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        en.setObjectName("English")
        layout.addWidget(en)
        self.korean = QLabel("번역 중…")
        self.korean.setWordWrap(True)
        self.korean.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.korean.setObjectName("Korean")
        layout.addWidget(self.korean)
        self.choices = QHBoxLayout()
        self.choices.setSpacing(8)
        layout.addLayout(self.choices)

    def finish(self, ko: str):
        self.korean.setText(ko)

    def clear_replies(self):
        self.set_replies([])

    def set_replies(self, choices: list[Reply]):
        while self.choices.count():
            item = self.choices.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for choice in choices[:3]:
            label = f"▶ {choice.en}\n{choice.ko}"
            button = QPushButton(label)
            button.setToolTip(f"선택한 영어만 영어 TTS로 송출: {choice.en}")
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            button.setMinimumHeight(56)
            button.clicked.connect(lambda _checked=False, text=choice.en: self.speak(text))
            self.choices.addWidget(button)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WARDOGS AI Interpreter — 실시간 영어 통역")
        self.resize(1100, 900)
        self.signals = Signals()
        self.runtime = Interpreter(self.signals)
        self.player = SpeechPlayer(self.signals.error.emit)
        self.overlay = Overlay()
        self.overlay_hotkey = None
        self.cards: dict[int, TranscriptCard] = {}
        self.last_english: dict[int, str] = {}
        self.pending_translations: dict[int, tuple[str, list[Reply]]] = {}
        self.pending_replies: dict[int, list[Reply]] = {}
        self.demo_index = 0
        self.applied_selection = None
        self.applied_label = '없음 (선택 후 적용)'
        self.state = self.load_settings()
        self.create_ui()
        self.refresh_audio_devices(initial=True)
        self.signals.status.connect(self.set_status)
        self.signals.error.connect(self.set_error)
        self.signals.recognized.connect(self.new_english)
        self.signals.translated.connect(self.new_translation)
        self.signals.download_done.connect(self.on_download_done)
        self.signals.model_applied.connect(self.on_model_applied)
        self.signals.replies_ready.connect(self.new_replies)
        self.restore_settings()
        self.overlay_hotkey = GlobalHotkey(self.toggle_overlay_hotkey)
        self.register_overlay_hotkey()
        self.portable_model_combo.currentIndexChanged.connect(self.on_local_selection_changed)
        self.portable_compute_combo.currentIndexChanged.connect(self.on_local_selection_changed)
        self.find_process()
        # External REPAIR_ENGINE.bat installs binaries outside this GUI process.
        # The old UI updated only when a dropdown changed, so its status could
        # stay falsely "not installed" while the files were already present.
        self.engine_state_timer = QTimer(self)
        self.engine_state_timer.timeout.connect(self.update_model_state)
        self.engine_state_timer.start(3000)

    def create_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(20, 16, 20, 14)
        outer.setSpacing(12)
        heading = QLabel("WARDOGS  |  AI INTERPRETER  v0.9")
        heading.setObjectName("Heading")
        outer.addWidget(heading)
        subtitle = QLabel("게임 오디오만 인식 · 기본은 한국어 자막 · 영어 답변은 버튼을 눌러야 송출")
        subtitle.setObjectName("Muted")
        outer.addWidget(subtitle)

        game_row = QHBoxLayout()
        self.process_label = QLabel("프로세스 탐색 중…")
        game_row.addWidget(self.process_label, 1)
        refresh = QPushButton("프로세스 새로고침")
        refresh.clicked.connect(self.find_process)
        game_row.addWidget(refresh)
        self.start_button = QPushButton("▶ 번역 시작")
        self.start_button.setObjectName("Primary")
        self.start_button.clicked.connect(self.start)
        game_row.addWidget(self.start_button)
        self.stop_button = QPushButton("■ 중지")
        self.stop_button.clicked.connect(self.stop)
        game_row.addWidget(self.stop_button)
        outer.addLayout(game_row)

        group = QGroupBox("기능 설정")
        grid = QGridLayout(group)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        self.model_combo = QComboBox()
        self.model_combo.addItems(["small.en", "base.en", "medium.en"])
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["Argos (offline)", "Local GGUF (offline)",
                                    "OPUS-MT (offline)", "Google (online)", "OpenAI"])
        self.vad_combo = QComboBox()
        for i, lbl in enumerate(["0 (민감)", "1", "2 (권장)", "3 (소음 억제)"]):
            self.vad_combo.addItem(lbl, i)
        self.min_voice_ms = QSpinBox()
        self.min_voice_ms.setRange(60, 900)
        self.min_voice_ms.setSingleStep(30)
        self.min_voice_ms.setSuffix(" ms")
        self.min_voice_ms.setValue(150)
        self.min_voice_ms.setToolTip("잡힌 음성이 이 길이 이상일 때 인식합니다. 너무 낮으면 효과음 오인식 증가")
        self.end_silence_ms = QSpinBox()
        self.end_silence_ms.setRange(150, 1200)
        self.end_silence_ms.setSingleStep(30)
        self.end_silence_ms.setSuffix(" ms")
        self.end_silence_ms.setValue(300)
        self.end_silence_ms.setToolTip("말이 끊긴 뒤 기다리는 시간. 낮추면 빠르지만 긴 문장이 쪼개질 수 있습니다")
        self.api_key = QLineEdit()
        self.api_key.setPlaceholderText("OpenAI를 사용할 경우에만 입력 (저장하지 않음)")
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setText(os.environ.get("OPENAI_API_KEY", ""))
        grid.addWidget(QLabel("Whisper 모델"), 0, 0)
        grid.addWidget(self.model_combo, 0, 1)
        grid.addWidget(QLabel("번역 방식"), 0, 2)
        grid.addWidget(self.engine_combo, 0, 3)
        grid.addWidget(QLabel("음성 감지 민감도"), 1, 0)
        grid.addWidget(self.vad_combo, 1, 1)
        grid.addWidget(QLabel("선택적 API 키"), 1, 2)
        grid.addWidget(self.api_key, 1, 3)
        grid.addWidget(QLabel("최소 음성 길이"), 12, 0)
        grid.addWidget(self.min_voice_ms, 12, 1)
        grid.addWidget(QLabel("음성 종료 대기"), 12, 2)
        grid.addWidget(self.end_silence_ms, 12, 3)
        self.portable_model_combo = QComboBox()
        for key, spec in MODEL_CATALOG.items():
            self.portable_model_combo.addItem(spec.label, key)
        self.portable_compute_combo = QComboBox()
        self.portable_compute_combo.addItem("CPU 전용 (VRAM 보호 · 기본 추천)", "cpu")
        self.portable_compute_combo.addItem("CUDA GPU 일부 사용 (8 레이어)", "cuda8")
        self.portable_compute_combo.addItem("CUDA GPU 일부 사용 (16 레이어)", "cuda16")
        self.portable_compute_combo.addItem("Vulkan GPU 일부 사용 (8 레이어 · CUDA 대안)", "vulkan8")
        self.portable_compute_combo.addItem("Vulkan GPU 일부 사용 (16 레이어)", "vulkan16")
        self.portable_compute_combo.addItem("CUDA GPU 최대 사용 (게임 중 비추천)", "cudaall")
        self.download_engine_button = QPushButton("로컬 엔진 다운로드")
        self.download_engine_button.clicked.connect(self.download_portable_engine)
        self.download_model_button = QPushButton("선택 모델 + 엔진 준비 (원클릭)")
        self.download_model_button.clicked.connect(self.download_portable_model)
        grid.addWidget(QLabel("오프라인 AI 번역 모델"), 7, 0)
        grid.addWidget(self.portable_model_combo, 7, 1)
        grid.addWidget(self.portable_compute_combo, 7, 2, 1, 2)
        grid.addWidget(self.download_engine_button, 8, 1)
        grid.addWidget(self.download_model_button, 8, 2, 1, 2)
        self.opus_button = QPushButton("OPUS-MT 경량 번역 모델 다운로드 (CPU)")
        self.opus_button.setToolTip("Helsinki-NLP 영어→한국어 전용 모델. llama.cpp 없이 CPU로 동작합니다.")
        self.opus_button.clicked.connect(self.download_opus_model)
        grid.addWidget(self.opus_button, 13, 1, 1, 3)
        self.model_state_label = QLabel("로컬 엔진 및 모델 설치 상태 확인 중…")
        self.model_state_label.setObjectName("Muted")
        self.model_state_label.setWordWrap(True)
        grid.addWidget(self.model_state_label, 9, 0, 1, 4)
        self.apply_model_button = QPushButton('선택 모델 적용 및 번역 검증')
        self.apply_model_button.setToolTip('선택된 엔진을 실행하고 모델로 한국어 번역 테스트를 완료해야 적용됩니다.')
        self.apply_model_button.clicked.connect(self.apply_current_model)
        grid.addWidget(self.apply_model_button, 10, 1, 1, 3)

        self.english_output = QComboBox()
        self.english_output.setToolTip("추천 답변 버튼 클릭 시에만 영어 TTS를 보낼 Windows 재생 장치")
        self.korean_output = QComboBox()
        self.korean_output.setToolTip("한국어 통역 TTS용 별도 재생 장치 (기본 OFF)")
        grid.addWidget(QLabel("영어 TTS 출력 장치"), 2, 0)
        grid.addWidget(self.english_output, 2, 1, 1, 2)
        refresh_audio = QPushButton("출력 장치 새로고침")
        refresh_audio.clicked.connect(self.refresh_audio_devices)
        grid.addWidget(refresh_audio, 2, 3)
        grid.addWidget(QLabel("한국어 TTS 출력 장치"), 3, 0)
        grid.addWidget(self.korean_output, 3, 1, 1, 3)
        self.ko_tts = QCheckBox("한국어 실시간 통역 TTS 활성화 (기본 꺼짐)")
        self.recommend_toggle = QCheckBox("영어 답변 추천 표시 (기본 OFF · 자막과 별도 처리)")
        grid.addWidget(self.recommend_toggle, 14, 0, 1, 4)
        self.fast_fallback = QCheckBox("연속 발화로 자막이 밀리면 Argos 빠른 번역 사용 (기본 ON)")
        self.fast_fallback.setChecked(True)
        self.fast_fallback.setToolTip("연속 대사가 쌓일 때 한국어 표시 속도를 위해 빠른 Argos 번역을 선택합니다. 게임 은어의 정확도는 줄 수 있습니다.")
        grid.addWidget(self.fast_fallback, 15, 0, 1, 4)
        self.overlay_toggle = QCheckBox("게임 화면 위 자막 오버레이 (테두리 없는 창 모드 권장)")
        grid.addWidget(self.ko_tts, 4, 0, 1, 4)
        grid.addWidget(self.overlay_toggle, 5, 0, 1, 4)
        self.screens = QComboBox()
        for i, s in enumerate(QGuiApplication.screens()):
            self.screens.addItem(f"모니터 {i + 1}: {s.name()} ({s.geometry().width()}×{s.geometry().height()})", i)
        grid.addWidget(QLabel("자막 대상 모니터"), 6, 0)
        grid.addWidget(self.screens, 6, 1, 1, 3)
        self.hotkey_combo = QComboBox()
        for hotkey in KEYS:
            self.hotkey_combo.addItem(hotkey, hotkey)
        self.hotkey_combo.setToolTip("이 키를 누를 때마다 자막 오버레이 ON/OFF. 게임에서 사용하지 않는 키를 고르세요.")
        self.hotkey_state_label = QLabel("전역 단축키 등록 대기")
        self.hotkey_state_label.setObjectName("Muted")
        grid.addWidget(QLabel("자막 표시 토글 단축키"), 11, 0)
        grid.addWidget(self.hotkey_combo, 11, 1)
        grid.addWidget(self.hotkey_state_label, 11, 2, 1, 2)
        outer.addWidget(group)

        actions = QHBoxLayout()
        test = QPushButton("영어 송출 테스트 (클릭하면 재생)")
        test.clicked.connect(lambda: self.speak_english("Can you hear me?"))
        actions.addWidget(test)
        demo = QPushButton("번역 UI 데모")
        demo.clicked.connect(self.run_demo)
        actions.addWidget(demo)
        actions.addStretch()
        outer.addLayout(actions)

        self.error_label = QLabel("")
        self.error_label.setObjectName("Error")
        self.error_label.setWordWrap(True)
        outer.addWidget(self.error_label)
        outer.addWidget(QLabel("최근 게임 대화 및 추천 답변"))
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        container = QWidget()
        self.message_layout = QVBoxLayout(container)
        self.message_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.message_layout.setSpacing(10)
        self.scroll.setWidget(container)
        outer.addWidget(self.scroll, stretch=1)
        self.status_label = QLabel("대기 중")
        self.status_label.setObjectName("Muted")
        outer.addWidget(self.status_label)
        self.notice = QLabel("Muzychenko VAC의 Line 1 등 원하는 '재생/출력' 장치를 선택하세요. 이 프로그램은 Windows 기본 출력, 마이크, 오인페 및 VAC 라우팅을 변경하지 않습니다.")
        self.notice.setObjectName("Muted")
        self.notice.setWordWrap(True)
        outer.addWidget(self.notice)
        self.overlay_toggle.toggled.connect(self.overlay_enabled)
        self.hotkey_combo.currentIndexChanged.connect(self.on_hotkey_changed)
        for control in (self.model_combo, self.engine_combo, self.vad_combo,
                        self.portable_model_combo, self.portable_compute_combo, self.english_output, self.korean_output, self.screens):
            control.currentIndexChanged.connect(self.save_settings)
        for control in (self.overlay_toggle, self.ko_tts, self.recommend_toggle, self.fast_fallback):
            control.toggled.connect(self.save_settings)
        self.recommend_toggle.toggled.connect(self.set_recommendations_enabled)
        self.min_voice_ms.valueChanged.connect(self.save_settings)
        self.end_silence_ms.valueChanged.connect(self.save_settings)

    def selected_backend(self) -> str:
        mode = self.portable_compute_combo.currentData()
        return 'cpu' if mode == 'cpu' else 'vulkan' if str(mode).startswith('vulkan') else 'cuda'

    def register_overlay_hotkey(self):
        if self.overlay_hotkey is None:
            return
        try:
            success, message = self.overlay_hotkey.register(self.hotkey_combo.currentData())
        except Exception as exc:
            success, message = False, f'전역 단축키 오류: {exc}'
        self.hotkey_state_label.setText(message)
        if not success:
            self.set_error(message)

    def on_hotkey_changed(self, *_args):
        self.register_overlay_hotkey()
        self.save_settings()

    def toggle_overlay_hotkey(self):
        now_enabled = not self.overlay_toggle.isChecked()
        self.overlay_toggle.setChecked(now_enabled)
        self.set_status(f'게임 자막 오버레이: {"ON" if now_enabled else "OFF"} (단축키: {self.hotkey_combo.currentText()})')

    def update_model_state(self):
        model_key = self.portable_model_combo.currentData()
        backend = self.selected_backend()
        engine_ok = engine_installed(backend)
        model_ok = model_installed(model_key)
        self.model_state_label.setText(
            f"엔진 상태: CPU {'준비됨' if engine_installed('cpu') else '다운로드 필요'} / "
            f"CUDA {'준비됨' if engine_installed('cuda') else '다운로드 필요'} / "
            f"Vulkan {'준비됨' if engine_installed('vulkan') else '다운로드 필요'}\n"
            f"OPUS-MT: {'준비됨' if opus_installed() else '다운로드 필요'}  |  "
            f"선택 GGUF: {'다운로드됨' if model_ok else '다운로드 필요'}  |  "
            f"현재 적용: {getattr(self, 'applied_label', '없음 (선택 후 적용)')}"
        )

    def on_local_selection_changed(self, *_args):
        if self.applied_selection != (self.portable_model_combo.currentData(), self.portable_compute_combo.currentData()):
            self.applied_selection = None
            self.applied_label = '없음 (선택 후 적용)'
        self.update_model_state()

    def apply_current_model(self):
        if self.engine_combo.currentText() == 'OPUS-MT (offline)':
            if not opus_installed():
                self.set_error('OPUS-MT 모델을 먼저 다운로드해 주세요.')
                return
            if self.runtime.active.is_set():
                self.set_error('실시간 통역을 중지한 뒤 모델을 검증해 주세요.')
                return
            self.apply_model_button.setEnabled(False)
            self.set_status('OPUS-MT CPU 모델 번역 검증 중…')
            def verify_opus():
                try:
                    korean, _ = TranslationEngine('OPUS-MT (offline)').translate('We need backup!', [])
                    if not any('가' <= c <= '힣' for c in korean):
                        raise RuntimeError('한국어 번역 결과 없음')
                    self.signals.model_applied.emit('opus-mt', 'cpu', 'OK')
                except Exception as exc:
                    self.signals.model_applied.emit('opus-mt', 'cpu', 'FAIL: ' + str(exc)[:220])
            threading.Thread(target=verify_opus, daemon=True).start()
            return
        model_key = self.portable_model_combo.currentData()
        compute = self.portable_compute_combo.currentData()
        backend = self.selected_backend()
        if not model_installed(model_key) or not engine_installed(backend):
            self.set_error('선택한 모델 또는 엔진이 없습니다. [선택 모델 + 엔진 준비]를 먼저 실행하세요.')
            return
        if self.runtime.active.is_set():
            self.set_error('실시간 통역을 중지한 후 다른 모델을 적용해 주세요.')
            return
        self.apply_model_button.setEnabled(False)
        self.set_status('선택한 모델 로딩 및 한국어 번역 검증 중… (최초 실행은 시간이 걸릴 수 있음)')
        def worker():
            try:
                korean, _ = TranslationEngine('Local GGUF (offline)', portable_model=model_key,
                                              portable_compute=compute).translate('We need backup!', [])
                if not korean or not any('가' <= c <= '힣' for c in korean):
                    raise RuntimeError('번역 응답에 한국어가 없습니다.')
                self.signals.model_applied.emit(model_key, compute, 'OK')
            except Exception as exc:
                self.signals.model_applied.emit(model_key, compute, 'FAIL: ' + str(exc)[:250])
        threading.Thread(target=worker, daemon=True).start()

    def on_model_applied(self, model_key: str, compute: str, result: str):
        self.apply_model_button.setEnabled(True)
        if result != 'OK':
            self.applied_selection = None
            self.applied_label = '적용 실패'
            self.set_error('모델 적용 실패: ' + result[6:])
        elif model_key == 'opus-mt':
            self.applied_label = 'OPUS-MT / CPU (번역 검증 통과)'
            self.applied_selection = None
            self.set_status('OPUS-MT 모델 적용 성공: 한국어 번역 검증 완료')
        elif (model_key, compute) == (self.portable_model_combo.currentData(), self.portable_compute_combo.currentData()):
            self.applied_selection = (model_key, compute)
            self.applied_label = f'{MODEL_CATALOG[model_key].label.split(" (")[0]} / {compute} (번역 검증 통과)'
            self.set_status('모델 적용 성공: 한국어 번역 테스트 통과')
            self.save_settings()
        else:
            self.set_status('이전 선택 모델 검증 완료. 현재 선택된 모델은 다시 적용해 주세요.')
        self.update_model_state()

    def download_opus_model(self):
        if opus_installed():
            QMessageBox.information(self, "OPUS-MT 준비됨", "OPUS-MT 모델은 이미 다운로드되어 있습니다.")
            return
        if QMessageBox.question(self, "OPUS-MT 다운로드", "약 420MB의 번역 모델을 받습니다. 라이선스: CC BY 4.0. 계속할까요?") != QMessageBox.StandardButton.Yes:
            return
        self._begin_download("OPUS-MT 영어→한국어 모델 다운로드 중…", install_opus)

    def set_recommendations_enabled(self, enabled: bool):
        self.runtime.replies_enabled = bool(enabled)
        if not enabled:
            for card in self.cards.values():
                card.clear_replies()

    def _begin_download(self, title: str, action):
        self.download_engine_button.setEnabled(False)
        self.download_model_button.setEnabled(False)
        self.apply_model_button.setEnabled(False)
        self.opus_button.setEnabled(False)
        self.set_status(title)
        def background():
            try:
                action(lambda update: self.signals.status.emit(update))
                self.signals.download_done.emit('완료')
            except Exception as exc:
                self.signals.error.emit(f'다운로드 실패: {exc}')
                self.signals.download_done.emit('실패')
        threading.Thread(target=background, daemon=True).start()

    def on_download_done(self, result: str):
        self.download_engine_button.setEnabled(True)
        self.download_model_button.setEnabled(True)
        self.apply_model_button.setEnabled(True)
        self.opus_button.setEnabled(True)
        self.update_model_state()
        self.set_status(f'로컬 AI 설치 작업 {result}')

    def download_portable_engine(self):
        backend = self.selected_backend()
        if engine_installed(backend):
            QMessageBox.information(self, '이미 준비됨', f'{backend.upper()} 포터블 엔진이 이미 설치되어 있습니다.')
            return
        message = (f'공식 llama.cpp GitHub에서 Windows {backend.upper()} 엔진을 내려받아\n'
                   f'현재 프로젝트의 engines\\{backend} 폴더에 설치합니다.\n'
                   'Ollama나 다른 프로그램은 설치하지 않습니다.\n'
                   '다운로드 크기는 릴리스에 따라 달라질 수 있습니다. 진행할까요?')
        if QMessageBox.question(self, '로컬 엔진 다운로드', message) != QMessageBox.StandardButton.Yes:
            return
        self._begin_download(f'{backend.upper()} 엔진 설치 준비…',
                             lambda notify: install_engine(backend, notify))

    def download_portable_model(self):
        model_key = self.portable_model_combo.currentData()
        spec = MODEL_CATALOG[model_key]
        backend = self.selected_backend()
        missing_engine = not engine_installed(backend)
        missing_model = not model_installed(model_key)
        if not missing_engine and not missing_model:
            QMessageBox.information(self, '준비 완료', '선택한 번역 모델과 실행 엔진 모두 설치되어 있습니다.')
            return
        required = []
        if missing_engine:
            required.append(f'- llama.cpp {backend.upper()} 포터블 실행 엔진')
        if missing_model:
            required.append(f'- {spec.label}')
        message = ('프로젝트 폴더 안에 아래 항목을 다운로드합니다.\n'
                   + '\n'.join(required)
                   + f'\n\n모델 저장 경로: {MODELS_DIR}\n'
                   + f'모델 라이선스: {spec.license_note}\n\n'
                   + '공식 GitHub / Hugging Face에서 내려받습니다. 계속할까요?')
        if QMessageBox.question(self, '로컬 AI 통합 다운로드', message) != QMessageBox.StandardButton.Yes:
            return
        def install_both(notify):
            if missing_engine:
                install_engine(backend, notify)
            if missing_model:
                download_model(model_key, notify)
        self._begin_download('모델 및 실행 엔진 다운로드 준비…', install_both)

    def refresh_audio_devices(self, _checked=False, initial=False):
        """Re-enumerate render endpoints without rerouting the user's microphone.

        Preserve the selected endpoint by stable API/name key, rather than by
        a volatile PortAudio integer device index. No device is auto-selected
        for English playback if the previously chosen endpoint has vanished.
        """
        previous = {
            "english": self.english_output.currentData(DEVICE_KEY_ROLE),
            "korean": self.korean_output.currentData(DEVICE_KEY_ROLE),
        }
        if initial:
            previous = {"english": None, "korean": "default"}
        try:
            endpoints = output_devices()
        except Exception as exc:
            if not initial:
                self.set_error(f"출력 장치 조회 실패: {exc}")
            return
        for combo, first_label, first_value, first_key, saved_key in (
            (self.english_output, "영어 출력 장치 선택 (미선택)", None, None, previous["english"]),
            (self.korean_output, "시스템 기본 스피커", "default", "default", previous["korean"]),
        ):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(first_label, first_value)
            combo.setItemData(0, first_key, DEVICE_KEY_ROLE)
            for endpoint in endpoints:
                combo.addItem(endpoint.label, endpoint.index)
                combo.setItemData(combo.count() - 1, endpoint.key, DEVICE_KEY_ROLE)
            selection = self._find_device_by_key(combo, saved_key)
            combo.setCurrentIndex(selection if selection >= 0 else 0)
            combo.blockSignals(False)
        if not initial:
            self.save_settings()
            self.set_status("Windows 출력 장치 목록을 새로고침했습니다. (새 장치가 안 보이면 앱을 다시 실행하세요.)")

    @staticmethod
    def _find_device_by_key(combo: QComboBox, key) -> int:
        if key is None:
            return 0
        for i in range(combo.count()):
            if combo.itemData(i, DEVICE_KEY_ROLE) == key:
                return i
        return -1

    @staticmethod
    def _find_legacy_audio_choice(combo: QComboBox, old_label: str) -> int:
        """Migrate beta-1 settings that included mutable '(ID n)' suffixes."""
        if not old_label:
            return -1
        old_name = old_label.split(" [", 1)[0].strip()
        for i in range(combo.count()):
            if combo.itemText(i) == old_label:
                return i
        for i in range(1, combo.count()):
            if combo.itemText(i).split("  [", 1)[0].strip() == old_name:
                return i
        return -1

    def restore_settings(self):
        mapping = {
            "model": self.model_combo, "mode": self.engine_combo,
            "screen": self.screens,
        }
        for key, combo in mapping.items():
            target = self.state.get(key)
            if target is not None:
                for i in range(combo.count()):
                    value = combo.itemText(i) if key != "screen" else combo.itemData(i)
                    if value == target:
                        combo.setCurrentIndex(i)
                        break
        for name, combo in (("english_output", self.english_output),
                            ("korean_output", self.korean_output)):
            # New stable name+host-API key first, then old saved display label.
            key = self.state.get(name + "_key")
            found = self._find_device_by_key(combo, key) if key is not None else -1
            if found < 0:
                found = self._find_legacy_audio_choice(combo, self.state.get(name, ""))
            if found >= 0:
                combo.setCurrentIndex(found)
        self.vad_combo.setCurrentIndex(int(self.state.get("vad", 2)))
        portable_key = self.state.get("portable_model", "qwen3-4b-q4")
        index = self.portable_model_combo.findData(portable_key)
        if index >= 0:
            self.portable_model_combo.setCurrentIndex(index)
        compute = self.state.get("portable_compute", "cpu")
        index = self.portable_compute_combo.findData(compute)
        if index >= 0:
            self.portable_compute_combo.setCurrentIndex(index)
        self.update_model_state()
        saved_hotkey = self.state.get("overlay_hotkey", "F10")
        position = self.hotkey_combo.findData(saved_hotkey)
        self.hotkey_combo.blockSignals(True)
        self.hotkey_combo.setCurrentIndex(position if position >= 0 else self.hotkey_combo.findData('F10'))
        self.hotkey_combo.blockSignals(False)
        self.ko_tts.setChecked(bool(self.state.get("ko_tts", False)))
        self.recommend_toggle.setChecked(bool(self.state.get("recommendations", False)))
        self.fast_fallback.setChecked(bool(self.state.get("fast_backlog_fallback", True)))
        self.min_voice_ms.setValue(int(self.state.get("min_voice_ms", 150)))
        self.end_silence_ms.setValue(int(self.state.get("end_silence_ms", 300)))
        self.overlay_toggle.setChecked(bool(self.state.get("overlay", False)))

    def load_settings(self) -> dict:
        try:
            return json.loads(SETTINGS.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, ValueError):
            return {}

    def save_settings(self, *_args):
        # API keys are deliberately excluded from saved settings.
        state = {
            "model": self.model_combo.currentText(), "mode": self.engine_combo.currentText(),
            "portable_model": self.portable_model_combo.currentData(),
            "portable_compute": self.portable_compute_combo.currentData(),
            "vad": self.vad_combo.currentIndex(),
            "min_voice_ms": self.min_voice_ms.value(),
            "end_silence_ms": self.end_silence_ms.value(),
            "recommendations": self.recommend_toggle.isChecked(),
            "fast_backlog_fallback": self.fast_fallback.isChecked(),
            "english_output": self.english_output.currentText(),
            "english_output_key": self.english_output.currentData(DEVICE_KEY_ROLE),
            "korean_output": self.korean_output.currentText(),
            "korean_output_key": self.korean_output.currentData(DEVICE_KEY_ROLE),
            "overlay_hotkey": self.hotkey_combo.currentData(),
            "ko_tts": self.ko_tts.isChecked(), "overlay": self.overlay_toggle.isChecked(),
            "screen": self.screens.currentData(),
        }
        try:
            SETTINGS.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def find_process(self):
        import psutil
        matches = []
        for p in psutil.process_iter(["pid", "name"]):
            try:
                if (p.info.get("name") or "").lower() == GAME_EXE.lower():
                    matches.append(p.info["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self.pid = max(matches) if matches else None
        if matches:
            self.process_label.setText(f"● {GAME_EXE}  ·  PID {self.pid}")
        else:
            self.process_label.setText(f"○ {GAME_EXE} 실행 중이지 않음 (게임 실행 후 새로고침)")
        self.start_button.setEnabled(bool(matches))

    def start(self):
        if not self.pid:
            self.find_process()
            if not self.pid:
                return
        if not NATIVE.exists():
            self.set_error("프로세스별 캡처 실행 파일이 없습니다. 전체 ZIP을 다시 압축 해제하세요.")
            return
        if self.engine_combo.currentText() == "OPUS-MT (offline)" and not opus_installed():
            self.set_error("OPUS-MT 모델이 없습니다. [OPUS-MT 경량 번역 모델 다운로드]를 눌러 주세요.")
            return
        if self.engine_combo.currentText() == "Local GGUF (offline)":
            compute = self.portable_compute_combo.currentData()
            backend = self.selected_backend()
            if not engine_installed(backend) or not model_installed(self.portable_model_combo.currentData()):
                self.set_error("선택한 로컬 실행 엔진 또는 GGUF 모델이 없습니다. [선택 모델 + 엔진 준비]를 눌러 주세요.")
                return
        if (self.engine_combo.currentText() == 'Local GGUF (offline)' and
                self.applied_selection != (self.portable_model_combo.currentData(), self.portable_compute_combo.currentData())):
            self.set_error('로컬 AI 모델을 선택한 뒤 [선택 모델 적용 및 번역 검증]을 먼저 눌러 주세요.')
            return
        self.error_label.clear()
        try:
            self.runtime.start(self.pid, self.vad_combo.currentData(),
                               self.model_combo.currentText(), self.engine_combo.currentText(),
                               self.api_key.text().strip(), self.portable_model_combo.currentData(),
                               self.portable_compute_combo.currentData(),
                               min_voice_ms=self.min_voice_ms.value(),
                               silence_end_ms=self.end_silence_ms.value(),
                               recommendations_enabled=self.recommend_toggle.isChecked(),
                               fast_backlog_fallback=self.fast_fallback.isChecked())
            self.start_button.setEnabled(False)
        except Exception as exc:
            self.set_error(str(exc))

    def stop(self):
        self.runtime.stop()
        LOCAL_SERVER.stop()
        self.start_button.setEnabled(bool(self.pid))
        self.overlay.hide()

    def set_status(self, message: str):
        self.status_label.setText(message)
        if "종료" in message or "중지" in message:
            self.start_button.setEnabled(bool(self.pid))

    def set_error(self, message: str):
        self.error_label.setText("⚠ " + message[:550])

    def new_english(self, index: int, english: str):
        self.last_english[index] = english
        card = TranscriptCard(index, english, self.speak_english)
        self.cards[index] = card
        self.message_layout.insertWidget(0, card)
        # Different worker threads may deliver Qt signals in either order.
        if index in self.pending_translations:
            ko, replies = self.pending_translations.pop(index)
            self.new_translation(index, ko, replies)
        if index in self.pending_replies:
            self.new_replies(index, self.pending_replies.pop(index))
        while len(self.cards) > 80:
            first_key = next(iter(self.cards))
            dead = self.cards.pop(first_key)
            self.last_english.pop(first_key, None)
            self.pending_translations.pop(first_key, None)
            self.pending_replies.pop(first_key, None)
            dead.deleteLater()

    def new_replies(self, index: int, replies: list[Reply]):
        if not self.recommend_toggle.isChecked():
            return
        if index in self.cards:
            self.cards[index].set_replies(replies)
        elif len(self.pending_replies) < 120:
            self.pending_replies[index] = replies

    def new_translation(self, index: int, korean: str, replies: list[Reply]):
        if index in self.cards:
            self.cards[index].finish(korean)
            if self.recommend_toggle.isChecked() and replies:
                self.cards[index].set_replies(replies)
        elif len(self.pending_translations) < 120:
            self.pending_translations[index] = (korean, replies)
            return
        if self.overlay_toggle.isChecked():
            self.overlay.update_subtitle(self.last_english.get(index, ""), korean,
                                         self.screens.currentData() or 0)
        if self.ko_tts.isChecked() and not korean.startswith("["):
            device = self.korean_output.currentData()
            if device == "default":
                import sounddevice as sd
                device = sd.default.device[1]
            if device is not None and int(device) >= 0:
                self.player.send(korean, "ko", int(device))

    def speak_english(self, english: str):
        output = self.english_output.currentData()
        if output is None:
            QMessageBox.warning(self, "출력 장치를 선택하세요",
                                "영어 TTS를 송출할 Windows 재생 장치를 선택하세요.\n"
                                "Muzychenko VAC 사용자라면 'Line 1 (Virtual Audio Cable)'의 출력 항목을 선택할 수 있습니다.")
            return
        if self.player.send(english, "en", int(output)):
            self.set_status(f"선택한 장치로 영어 TTS 송출 예약: {english}")

    def overlay_enabled(self, enabled: bool):
        if not enabled:
            self.overlay.hide()

    def run_demo(self):
        # No game, capture helper or GPU is required for this particular test.
        self.error_label.clear()
        self.demo_index -= 1
        index = self.demo_index
        text = "We need backup! Two enemies on the roof!"
        self.new_english(index, text)
        mode = self.engine_combo.currentText()
        key = self.api_key.text().strip()
        portable_model = self.portable_model_combo.currentData()
        portable_compute = self.portable_compute_combo.currentData()
        def translate_demo():
            try:
                ko, replies = TranslationEngine(mode, key, portable_model, portable_compute).translate(text, [])
            except Exception as exc:
                self.signals.error.emit(f"데모 번역 엔진 오류 (Argos 대체 시도): {str(exc)[:210]}")
                try:
                    ko, replies = offline_fallback(text), []
                except Exception:
                    ko, replies = "[번역 실패 — 설정 확인 필요]", []
            self.signals.translated.emit(index, ko, [])
            if self.recommend_toggle.isChecked():
                self.signals.replies_ready.emit(index, recommendations(text))
        threading.Thread(target=translate_demo, daemon=True).start()

    def closeEvent(self, event):
        self.runtime.stop()
        self.player.stop()
        LOCAL_SERVER.stop()
        if self.overlay_hotkey is not None:
            self.overlay_hotkey.close()
        self.overlay.close()
        self.save_settings()
        event.accept()


STYLE = """
QWidget { background:#121925; color:#e9eef6; font-size:13px; }
QMainWindow { background:#121925; }
QLabel#Heading { font-size:22px; font-weight:700; color:#b8d5ff; }
QLabel#Muted { color:#95a7be; font-size:12px; }
QLabel#Error { color:#ffb3a9; }
QGroupBox { border:1px solid #38475d; border-radius:10px; margin-top:13px; padding:13px 8px 8px; font-weight:600; }
QGroupBox::title { subcontrol-origin:margin; left:14px; padding:0 5px; }
QPushButton { background:#25334b; border:1px solid #425570; border-radius:7px; padding:7px 10px; text-align:center; }
QPushButton:hover { background:#354b6a; }
QPushButton:disabled { color:#768399; background:#202733; }
QPushButton#Primary { background:#2463ae; color:white; font-weight:700; }
QComboBox,QLineEdit { background:#1d293a; border:1px solid #455772; border-radius:6px; padding:7px; }
QComboBox QAbstractItemView { background:#1b2a3d; selection-background-color:#365d8d; }
QFrame#TranscriptCard { background:#1a2636; border:1px solid #39485c; border-radius:10px; }
QFrame#TranscriptCard QLabel { background:transparent; }
QLabel#English { font-size:14px; color:#f1f5fa; }
QLabel#Korean { font-size:17px; color:#98d8fc; font-weight:600; }
QScrollArea { border:0; background:transparent; }
QScrollArea > QWidget > QWidget { background:#121925; }
QLabel#OverlayCaption { background:rgba(0,0,0,205); color:white; border-radius:12px; font-size:23px; font-weight:700; padding:10px; }
"""


def main():
    if sys.platform != "win32":
        raise SystemExit("이 프로그램은 Windows 11 전용입니다.")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
