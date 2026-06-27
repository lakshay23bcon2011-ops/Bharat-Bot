import logging
import os
import requests
from pathlib import Path
from groq import Groq

logger = logging.getLogger("BharatBot")

class Transcriber:
    def __init__(self, config: dict):
        ai_cfg = config.get("ai", {})
        self.model = ai_cfg.get("stt_model", "whisper-large-v3-turbo")
        self.temp_dir = config.get("paths", {}).get("temp_audio_dir", "./temp")
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        logger.info(f"Transcriber ready. Model: {self.model}")

    def download_audio(self, url: str, filename: str = "listening_audio.mp3") -> str | None:
        local_path = str(Path(self.temp_dir) / filename)
        try:
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192): f.write(chunk)
            return local_path
        except Exception as e:
            logger.error(f"Failed to download audio: {e}")
            return None

    def transcribe(self, audio_file_path: str) -> str:
        try:
            with open(audio_file_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    file=(Path(audio_file_path).name, audio_file.read()),
                    model=self.model,
                    language="en",
                    response_format="text",
                    temperature=0.0
                )
            return transcription.strip()
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""

    def download_and_transcribe(self, audio_url: str) -> str:
        local_path = self.download_audio(audio_url)
        return self.transcribe(local_path) if local_path else ""

    def cleanup(self):
        for f in Path(self.temp_dir).glob("*.mp3"): f.unlink()
        for f in Path(self.temp_dir).glob("*.wav"): f.unlink()
