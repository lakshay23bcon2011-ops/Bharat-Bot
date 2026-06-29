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
        try:
            logger.info("Attempting TTS using Groq API...")
            output_path = str(Path(self.temp_dir) / filename)
            response = self.client.audio.speech.create(
                model=self.model,
                voice=self.voice,
                input=f"[confident] {text}",
                response_format="wav"
            )
            response.write_to_file(output_path)
            return output_path
        except Exception as e:
            logger.warning(f"Groq TTS failed or requires terms acceptance ({e}). Falling back to local gTTS...")
            try:
                from gtts import gTTS
                mp3_filename = filename.replace(".wav", ".mp3")
                output_path = str(Path(self.temp_dir) / mp3_filename)
                tts = gTTS(text=text, lang="en")
                tts.save(output_path)
                logger.info(f"Fallback gTTS generated speech successfully: {output_path}")
                return output_path
            except Exception as ge:
                logger.error(f"Fallback gTTS failed: {ge}")
                return None

    def prepare_in_browser(self, page, file_path: str) -> bool:
        try:
            mime_type = "audio/wav" if file_path.endswith(".wav") else "audio/mp3"
            with open(file_path, "rb") as f: audio_data = f.read()
            audio_b64 = base64.b64encode(audio_data).decode("utf-8")
            
            js_code = f"""
            (function() {{
                try {{
                    const mimeType = '{mime_type}';
                    const base64Data = '{audio_b64}';
                    const AudioContext = window.AudioContext || window.webkitAudioContext;
                    const ctx = new AudioContext();
                    
                    const audio = new Audio('data:' + mimeType + ';base64,' + base64Data);
                    audio.crossOrigin = "anonymous";
                    
                    const source = ctx.createMediaElementSource(audio);
                    const dest = ctx.createMediaStreamDestination();
                    source.connect(dest);
                    source.connect(ctx.destination);
                    
                    window.injectedAudioElement = audio;
                    window.injectedAudioStream = dest.stream;
                    window.injectedAudioContext = ctx;
                    console.log("Audio injection prepared successfully!");
                    return true;
                }} catch (e) {{
                    console.error("Failed to prepare audio injection:", e);
                    return false;
                }}
            }})()
            """
            return page.evaluate(js_code)
        except Exception as e:
            logger.error(f"Failed to prepare audio injection: {e}")
            return False

    def play_in_browser(self, page) -> bool:
        try:
            js_code = """
            new Promise((resolve) => {
                try {
                    const audio = window.injectedAudioElement;
                    if (!audio) {
                        console.error("No injected audio element found.");
                        resolve(false);
                        return;
                    }
                    
                    audio.onended = () => {
                        console.log("Audio playback ended.");
                        resolve(true);
                    };
                    audio.onerror = (e) => {
                        console.error("Audio playback error:", e);
                        resolve(false);
                    };
                    
                    if (window.injectedAudioContext && window.injectedAudioContext.state === 'suspended') {
                        window.injectedAudioContext.resume();
                    }
                    
                    audio.play().then(() => {
                        console.log("Audio playback started.");
                        // Safety timeout (30s)
                        setTimeout(() => resolve(true), 30000);
                    }).catch(e => {
                        console.error("Play error:", e);
                        resolve(false);
                    });
                } catch (e) {
                    console.error("Play execution error:", e);
                    resolve(false);
                }
            })
            """
            return page.evaluate(js_code)
        except Exception as e:
            logger.error(f"Failed to play audio injection: {e}")
            return False

    def cleanup_in_browser(self, page) -> bool:
        try:
            js_code = """
            (function() {
                try {
                    window.injectedAudioStream = null;
                    if (window.injectedAudioElement) {
                        window.injectedAudioElement.pause();
                        window.injectedAudioElement = null;
                    }
                    if (window.injectedAudioContext) {
                        window.injectedAudioContext.close();
                        window.injectedAudioContext = null;
                    }
                    console.log("Audio injection cleaned up.");
                    return true;
                } catch (e) {
                    console.error("Cleanup error:", e);
                    return false;
                }
            })()
            """
            return page.evaluate(js_code)
        except Exception as e:
            logger.error(f"Failed to clean up audio injection: {e}")
            return False

    def cleanup(self):
        for f in Path(self.temp_dir).glob("speaking_output*.wav"): f.unlink()
        for f in Path(self.temp_dir).glob("speaking_output*.mp3"): f.unlink()
