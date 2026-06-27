import logging
import os
import base64
from pathlib import Path
from groq import Groq

logger = logging.getLogger("BharatBot")

class Speaker:
    def __init__(self, config: dict):
        ai_cfg = config.get("ai", {})
        self.model = ai_cfg.get("tts_model", "canopylabs/orpheus-v1-english")
        self.voice = ai_cfg.get("tts_voice", "austin")
        self.temp_dir = config.get("paths", {}).get("temp_audio_dir", "./temp")
        Path(self.temp_dir).mkdir(parents=True, exist_ok=True)
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        logger.info(f"Speaker ready. Model: {self.model} | Voice: {self.voice}")

    def text_to_speech(self, text: str, filename: str = "speaking_output.wav") -> str | None:
        output_path = str(Path(self.temp_dir) / filename)
        try:
            response = self.client.audio.speech.create(
                model=self.model,
                voice=self.voice,
                input=f"[confident] {text}",
                response_format="wav"
            )
            response.write_to_file(output_path)
            return output_path
        except Exception as e:
            logger.error(f"TTS failed: {e}")
            return None

    def play_in_browser(self, page, wav_file_path: str) -> bool:
        try:
            with open(wav_file_path, "rb") as f: wav_data = f.read()
            wav_b64 = base64.b64encode(wav_data).decode("utf-8")
            wait_ms = int((len(wav_data) / 48000 / 2 / 2) * 1000) + 2000
            js_code = f"""
            (function() {{
                const audio = new Audio('data:audio/wav;base64,{wav_b64}');
                audio.play().catch(e => console.log(e));
            }})();
            """
            page.evaluate(js_code)
            page.wait_for_timeout(wait_ms)
            return True
        except Exception as e:
            logger.error(f"Browser playback failed: {e}")
            return False

    def cleanup(self):
        for f in Path(self.temp_dir).glob("speaking_output*.wav"): f.unlink()
