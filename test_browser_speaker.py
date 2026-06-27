import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add the current directory to sys.path to import modules
sys.path.append(os.getcwd())

from modules.browser import BrowserController
from modules.speaker import Speaker

class TestBrowserSpeaker(unittest.TestCase):
    def setUp(self):
        self.config = {
            "browser": {"headless": True, "slow_mo": 0},
            "credentials": {"username": "test", "password": "test"},
            "selectors": {"login": {"username_input": "#u", "password_input": "#p", "signin_button": "button"}},
            "ai": {"tts_model": "orpheus", "tts_voice": "austin"},
            "paths": {"temp_audio_dir": "./temp_test"}
        }
        os.environ["GROQ_API_KEY"] = "mock_key"
        
    def tearDown(self):
        import shutil
        if Path("./temp_test").exists():
            shutil.rmtree("./temp_test")

    @patch('modules.browser.sync_playwright')
    def test_browser_launch_with_virtual_mic(self, mock_playwright):
        # Setup mock playwright
        mock_pw_instance = MagicMock()
        mock_playwright.return_value.start.return_value = mock_pw_instance
        mock_browser = MagicMock()
        mock_pw_instance.chromium.launch.return_value = mock_browser
        
        # Test without mic file
        browser = BrowserController(self.config)
        browser.start()
        
        args = mock_pw_instance.chromium.launch.call_args[1]['args']
        self.assertIn("--use-fake-device-for-media-stream", args)
        self.assertNotIn("--use-file-for-fake-audio-capture=test.wav", str(args))
        
        # Test with mic file
        self.config["browser"]["virtual_mic_file"] = "test.wav"
        Path("test.wav").touch()
        
        browser = BrowserController(self.config)
        browser.start()
        
        args = mock_pw_instance.chromium.launch.call_args[1]['args']
        self.assertTrue(any("--use-file-for-fake-audio-capture=test.wav" in arg for arg in args))
        
        Path("test.wav").unlink()

    @patch('modules.speaker.Speaker.inject_mic')
    @patch('modules.browser.BrowserController')
    def test_speaker_injection_logic(self, mock_browser, mock_inject):
        speaker = Speaker(self.config)
        browser_inst = mock_browser()
        
        # Mock inject_mic behavior
        mock_inject.return_value = True
        
        result = speaker.inject_mic(browser_inst, "test.wav")
        self.assertTrue(result)
        mock_inject.assert_called_once_with(browser_inst, "test.wav")

if __name__ == "__main__":
    unittest.main()
