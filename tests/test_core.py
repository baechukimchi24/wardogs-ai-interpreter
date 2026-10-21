import unittest
import numpy as np

from core import (
    BYTES_PER_FRAME, Reply, VoiceSegmenter, pcm48_stereo_to_16_mono,
    recommendations, _output_text_from_responses,
)


class TestInterpreterCore(unittest.TestCase):
    def test_pcm_conversion_exact_frame_size(self):
        # 30ms of 48 kHz stereo PCM must become 30ms of 16kHz mono PCM.
        t = np.arange(1440) / 48000
        tone = (12000 * np.sin(2 * np.pi * 500 * t)).astype("<i2")
        stereo = np.repeat(tone[:, None], 2, axis=1).tobytes()
        mono = pcm48_stereo_to_16_mono(stereo)
        self.assertEqual(len(mono), BYTES_PER_FRAME)
        self.assertGreater(np.max(np.abs(np.frombuffer(mono, dtype="<i2"))), 1000)

    def test_voice_silence_endpoint(self):
        def detector(frame):
            return frame[0] == 1
        seg = VoiceSegmenter(detector=detector)
        results = []
        for active in [False] * 6 + [True] * 14 + [False] * 25:
            result = seg.feed(bytes([1 if active else 0]) + bytes(BYTES_PER_FRAME - 1))
            if result:
                results.append(result)
        self.assertEqual(len(results), 1)
        self.assertGreater(len(results[0]), BYTES_PER_FRAME * 18)

    def test_ignore_non_speech(self):
        seg = VoiceSegmenter(detector=lambda _frame: False)
        for _ in range(80):
            self.assertIsNone(seg.feed(bytes(BYTES_PER_FRAME)))

    def test_replies_are_short(self):
        actual = recommendations("We need backup! Two enemies on the roof!")
        self.assertEqual(len(actual), 3)
        self.assertEqual(actual[0].en, "I'm coming!")
        self.assertTrue(all(isinstance(item, Reply) and item.ko for item in actual))

    def test_response_extraction(self):
        self.assertEqual(_output_text_from_responses({"output":[{"content":[{"type":"output_text","text":"{}"}]}]}), "{}")


if __name__ == "__main__":
    unittest.main()
