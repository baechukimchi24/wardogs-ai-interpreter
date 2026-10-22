"""Static Qt GUI wiring checks; Windows runtime verification remains necessary."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
class UiRegressions(unittest.TestCase):
    def test_three_tabs_configured(self):
        src = (ROOT/'main.py').read_text(encoding='utf-8')
        for tab in ("'실시간 대화'", "'기본 설정 · 자막'", "'AI 모델 관리'"):
            self.assertIn(tab, src)
        self.assertIn('self.setMinimumSize(740, 500)', src)
        self.assertIn('self.resize(1020, 700)', src)
    def test_noise_settings_persist(self):
        src = (ROOT/'main.py').read_text(encoding='utf-8')
        for key in ('ignored_phrases', 'block_single_fire', 'suppress_repeats', 'overlay_en_mode', 'overlay_ko_font'):
            self.assertIn('"'+key+'"', src)
    def test_prompts_no_longer_plant_game_voice_chat(self):
        src = (ROOT/'runtime.py').read_text(encoding='utf-8')
        self.assertNotIn('initial_prompt="Game voice chat.', src)
        self.assertLess(src.index('self.noise_filter.reject('), src.index('self.signals.recognized.emit(index, text)'))
    def test_portable_build_includes_hook_fix(self):
        src=(ROOT/'build_portable.py').read_text(encoding='utf-8')
        self.assertIn('--additional-hooks-dir',src)
        self.assertTrue((ROOT/'hooks'/'hook-webrtcvad.py').exists())
    def test_overlay_fixed_height_and_pagination(self):
        src=(ROOT/'main.py').read_text(encoding='utf-8')
        self.assertIn('self.resize(1000, 110)', src)
        self.assertIn('pages_for_text(korean', src)
        self.assertIn('self._page += 1', src)
if __name__ == '__main__':unittest.main()
