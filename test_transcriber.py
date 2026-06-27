import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add the current directory to sys.path to import modules
sys.path.append(os.getcwd())

from modules.transcriber import Transcriber

class TestTranscriber(unittest.TestCase):
    def setUp(self):
        self.config = {
            "ai": {"stt_model": "whisper-large-v3-turbo"},
            "paths": {"temp_audio_dir": "./temp_test"}
        }
        # Mock environment variable
        os.environ["GROQ_API_KEY"] = "mock_key"
        self.transcriber = Transcriber(self.config)

    def tearDown(self):
        import shutil
        if Path("./temp_test").exists():
            shutil.rmtree("./temp_test")

    @patch('os.path.getsize')
    @patch('modules.transcriber.Groq')
    def test_transcribe_small_file(self, mock_groq, mock_getsize):
        # Setup mock for small file
        mock_getsize.return_value = 5 * 1024 * 1024  # 5MB
        
        mock_client = MagicMock()
        mock_groq.return_value = mock_client
        self.transcriber.client = mock_client
        
        mock_client.audio.transcriptions.create.return_value = MagicMock(strip=lambda: "Mock transcription")

        # Create a dummy file
        dummy_file = "./temp_test/small.mp3"
        Path("./temp_test").mkdir(exist_ok=True)
        with open(dummy_file, "w") as f: f.write("dummy content")

        result = self.transcriber.transcribe(dummy_file)
        self.assertEqual(result, "Mock transcription")
        mock_client.audio.transcriptions.create.assert_called_once()

    @patch('os.path.getsize')
    @patch('subprocess.run')
    @patch('modules.transcriber.Transcriber._execute_transcription')
    def test_transcribe_large_file_chunking(self, mock_transcribe_call, mock_run, mock_getsize):
        # Setup mock for large file
        mock_getsize.return_value = 25 * 1024 * 1024  # 25MB
        
        # Mock transcribe to return parts
        mock_transcribe_call.side_effect = ["Part 1", "Part 2"]
        
        # Create dummy chunks to simulate ffmpeg output
        Path("./temp_test").mkdir(exist_ok=True)
        chunk1 = Path("./temp_test/chunk_001.mp3")
        chunk2 = Path("./temp_test/chunk_002.mp3")
        chunk1.touch()
        chunk2.touch()

        dummy_file = "./temp_test/large.mp3"
        with open(dummy_file, "w") as f: f.write("large dummy content")

        result = self.transcriber.transcribe(dummy_file)
        
        # Verify chunking was triggered
        self.assertEqual(result, "Part 1 Part 2")
        self.assertTrue(mock_run.called)
        
        # Verify chunks were cleaned up
        self.assertFalse(chunk1.exists())
        self.assertFalse(chunk2.exists())

if __name__ == "__main__":
    unittest.main()
