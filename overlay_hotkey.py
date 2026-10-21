"""Windows RegisterHotKey-based overlay switch (no game hooks or keyboard injection).

A single configurable function key is enough for most players. Additional
modifier combinations are included for conflicts. Windows may refuse keys
reserved by the game/other apps; the UI always reports registration failures.
"""
from __future__ import annotations
import ctypes
import sys

HOTKEY_ID = 0x57D0
WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000

KEYS: dict[str, tuple[int, int]] = {
    **{f'F{n}': (0, 0x70 + n - 1) for n in range(6, 13)},
    'Pause': (0, 0x13),
    'Insert': (0, 0x2D),
    'Home': (0, 0x24),
    'End': (0, 0x23),
    'Ctrl+Shift+F8': (MOD_CONTROL | MOD_SHIFT, 0x77),
    'Ctrl+Shift+F9': (MOD_CONTROL | MOD_SHIFT, 0x78),
    'Ctrl+Alt+F9': (MOD_CONTROL | MOD_ALT, 0x78),
}


def parse_hotkey(label: str) -> tuple[int, int]:
    """Return modifier and virtual-key; reject unlisted conflict-prone keys."""
    if label not in KEYS:
        raise ValueError(f'지원하지 않는 단축키: {label}')
    return KEYS[label]


class GlobalHotkey:
    def __init__(self, callback):
        self.callback = callback
        self.registered = False
        self.label = ''
        if sys.platform == 'win32':
            from PySide6.QtCore import QAbstractNativeEventFilter

            class Listener(QAbstractNativeEventFilter):
                def nativeEventFilter(listener_self, event_type, message):
                    if not self.registered or bytes(event_type) not in (b'windows_generic_MSG', b'windows_dispatcher_MSG'):
                        return False, 0
                    # MSG starts with HWND, UINT, WPARAM, LPARAM.
                    class Msg(ctypes.Structure):
                        _fields_ = [
                            ('hwnd', ctypes.c_void_p),
                            ('message', ctypes.c_uint),
                            ('wParam', ctypes.c_size_t),
                            ('lParam', ctypes.c_ssize_t),
                        ]
                    msg = ctypes.cast(int(message), ctypes.POINTER(Msg)).contents
                    if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                        self.callback()
                        return True, 0
                    return False, 0

            self.listener = Listener()
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                app.installNativeEventFilter(self.listener)

    def register(self, label: str) -> tuple[bool, str]:
        self.unregister()
        modifiers, key = parse_hotkey(label)
        if sys.platform != 'win32':
            return False, '전역 단축키는 Windows에서만 동작합니다.'
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        user32.RegisterHotKey.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_uint]
        user32.RegisterHotKey.restype = ctypes.c_bool
        if not user32.RegisterHotKey(None, HOTKEY_ID, modifiers | MOD_NOREPEAT, key):
            return False, f'{label} 단축키 등록 실패: 다른 앱/게임이 사용 중일 수 있습니다. 다른 키를 선택하세요. (Win32 {ctypes.get_last_error()})'
        self.registered = True
        self.label = label
        return True, f'자막 토글 전역 단축키: {label}'

    def unregister(self):
        if self.registered and sys.platform == 'win32':
            ctypes.WinDLL('user32', use_last_error=True).UnregisterHotKey(None, HOTKEY_ID)
        self.registered = False
        self.label = ''

    def close(self):
        self.unregister()
        if hasattr(self, 'listener'):
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.removeNativeEventFilter(self.listener)
