"""No audio/GPU dependency: simulated game VAD and ASR results."""
import unittest
from speech_filter import SpeechNoiseFilter, normalized, DEFAULT_IGNORED

class NoiseFilterTests(unittest.TestCase):
    def test_game_voice_chat_prefix_hallucination_exact(self):
        f = SpeechNoiseFilter()
        for line in ('Game voice chat.', ' GAME   VOICE  CHAT! ', 'game voice chat'):
            self.assertIsNotNone(f.reject(line))
        self.assertIsNone(f.reject('Game voice chat is not working'))

    def test_isolated_fire_block_but_longer_callouts_pass(self):
        f = SpeechNoiseFilter()
        self.assertIsNotNone(f.reject('Fire!'))
        self.assertIsNone(f.reject('Friendly fire!'))
        self.assertIsNone(f.reject('Fire in the hole!'))

    def test_fire_filter_can_be_disabled(self):
        f = SpeechNoiseFilter(block_single_fire=False, suppress_repeats=False)
        self.assertIsNone(f.reject('Fire.'))

    def test_user_exact_phrase_can_be_added(self):
        f = SpeechNoiseFilter(ignored='BEEP\nEnemy spotted\n', suppress_repeats=False)
        self.assertIsNotNone(f.reject('beep!'))
        self.assertIsNone(f.reject('Enemy spotted at B'))

    def test_repeat_suppression_only_on_third(self):
        now = [1.0]
        f = SpeechNoiseFilter(ignored='', block_single_fire=False, clock=lambda: now[0])
        self.assertIsNone(f.reject('Attack left'))
        now[0] = 3.0
        self.assertIsNone(f.reject('Attack left'))
        now[0] = 6.0
        self.assertIsNotNone(f.reject('Attack left'))
        now[0] = 20.0
        self.assertIsNone(f.reject('Attack left'))

    def test_long_callouts_not_repeat_suppressed(self):
        f = SpeechNoiseFilter(ignored='', block_single_fire=False)
        for _ in range(6):
            self.assertIsNone(f.reject('There are enemies moving to the left'))

    def test_repeats_can_be_switched_off(self):
        f = SpeechNoiseFilter(ignored='', block_single_fire=False, suppress_repeats=False)
        self.assertEqual([f.reject('push now') for _ in range(5)], [None]*5)

    def test_noise_filter_cannot_block_unrelated_normal_voice(self):
        f = SpeechNoiseFilter()
        lines = ['Need backup now', 'Enemy on the roof', 'I will revive you', 'Go left']
        self.assertTrue(all(f.reject(x) is None for x in lines))

    def test_default_ignored_is_editable(self):
        self.assertTrue(DEFAULT_IGNORED)
        self.assertEqual(normalized(' Fire! '), 'fire')

if __name__ == '__main__': unittest.main()
