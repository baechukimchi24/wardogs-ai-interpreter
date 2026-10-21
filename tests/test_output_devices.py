"""Cross-platform tests for output-only enumeration and stable saved keys.

The Windows TTS/PortAudio integration still needs a real Windows/VAC test.
"""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "speech_output.py"


def import_with_fake_sounddevice(devices):
    fake = types.ModuleType("sounddevice")
    fake.query_devices = lambda: devices
    fake.query_hostapis = lambda: [{"name": "MME"}, {"name": "Windows WASAPI"}]
    spec = importlib.util.spec_from_file_location("speech_output_testable", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"sounddevice": fake, "speech_output_testable": module}):
        spec.loader.exec_module(module)
    # The saved module holds a direct reference to the fake SD module.
    return module


class OutputDevicesTest(unittest.TestCase):
    def test_vac_line1_is_enumerated_as_playback_only(self):
        devices = [
            {"name": "Line 1 (Virtual Audio Cable)", "max_output_channels": 0, "hostapi": 1},
            {"name": "Speakers", "max_output_channels": 2, "hostapi": 0},
            {"name": "Line 1 (Virtual Audio Cable)", "max_output_channels": 2, "hostapi": 1},
            {"name": "Line 1 (Virtual Audio Cable)", "max_output_channels": 2, "hostapi": 0},
        ]
        endpoints = import_with_fake_sounddevice(devices).output_devices()
        self.assertEqual([d.index for d in endpoints], [2, 3, 1])
        self.assertIn("Line 1 (Virtual Audio Cable)", endpoints[0].label)
        self.assertIn("WASAPI", endpoints[0].api)

    def test_saved_key_survives_device_index_shifts(self):
        line1 = {"name": "Line 1 (Virtual Audio Cable)", "max_output_channels": 2, "hostapi": 1}
        first = import_with_fake_sounddevice([line1]).output_devices()[0]
        second = import_with_fake_sounddevice([
            {"name": "New Headset", "max_output_channels": 2, "hostapi": 0}, line1,
        ]).output_devices()[0]
        self.assertEqual(first.key, second.key)
        self.assertNotEqual(first.index, second.index)

    def test_multiple_identically_named_outputs_get_different_keys(self):
        identical = {"name": "Line 1 (Virtual Audio Cable)", "max_output_channels": 2, "hostapi": 1}
        endpoints = import_with_fake_sounddevice([identical, identical]).output_devices()
        self.assertNotEqual(endpoints[0].key, endpoints[1].key)


if __name__ == "__main__":
    unittest.main()
