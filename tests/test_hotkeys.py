from unittest import TestCase
from overlay_hotkey import parse_hotkey, MOD_CONTROL, MOD_SHIFT

class OverlayKeyTests(TestCase):
    def test_single_key_f10(self):
        self.assertEqual(parse_hotkey('F10'), (0, 0x79))

    def test_ctrl_shift_combo(self):
        self.assertEqual(parse_hotkey('Ctrl+Shift+F8'), (MOD_CONTROL | MOD_SHIFT, 0x77))

    def test_no_gameplay_letter_hotkeys(self):
        with self.assertRaises(ValueError):
            parse_hotkey('W')
