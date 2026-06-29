import time
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, Browser, Playwright

logger = logging.getLogger("BharatBot")

class BrowserController:
    def __init__(self, config: dict):
        self.config = config
        self.browser_cfg = config.get("browser", {})
        self.creds = config.get("credentials", {})
        self.selectors = config.get("selectors", {})
        self._playwright: Playwright = None
        self._browser: Browser = None
        self.page: Page = None
        self._intercepted_audio_url: str = None

    def start(self):
        logger.info("Starting browser...")
        self._playwright = sync_playwright().start()
        launch_args = ["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream", "--mute-audio"]
        
        # Check for virtual mic file
        mic_file = self.browser_cfg.get("virtual_mic_file")
        if mic_file and Path(mic_file).exists():
            launch_args.append(f"--use-file-for-fake-audio-capture={mic_file}")
            logger.info(f"Using virtual microphone file: {mic_file}")

        self._browser = self._playwright.chromium.launch(
            headless=self.browser_cfg.get("headless", False),
            slow_mo=self.browser_cfg.get("slow_mo", 50),
            args=launch_args
        )
        context = self._browser.new_context(accept_downloads=True)
        self.page = context.new_page()
        self.page.add_init_script("""
            window.injectedAudioStream = null;
            if (navigator.mediaDevices) {
                const originalGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
                navigator.mediaDevices.getUserMedia = async function(constraints) {
                    if (constraints && constraints.audio && window.injectedAudioStream) {
                        console.log("Injected custom audio stream into getUserMedia!");
                        return window.injectedAudioStream;
                    }
                    return originalGetUserMedia(constraints);
                };
            }
        """)
        self.page.set_default_timeout(self.browser_cfg.get("timeout", 30000))
        logger.info("Browser started successfully.")

    def close(self):
        logger.info("Closing browser...")
        if self.page: self.page.close()
        if self._browser: self._browser.close()
        if self._playwright: self._playwright.stop()
        logger.info("Browser closed.")

    def go_to(self, url: str):
        logger.info(f"Navigating to: {url}")
        for attempt in range(3):
            try:
                self.page.goto(url, wait_until="commit")
                return
            except Exception as e:
                logger.warning(f"Navigation attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    self.page.wait_for_timeout(3000)
                else:
                    raise e

    def go_to_base(self):
        self.go_to(self.browser_cfg.get("base_url", ""))

    def login(self) -> bool:
        logger.info("Attempting login...")
        try:
            self.go_to_base()
            login_sel = self.selectors.get("login", {})
            self.page.wait_for_selector(login_sel["username_input"], timeout=30000)
            self.page.fill(login_sel["username_input"], self.creds["username"])
            self.page.fill(login_sel["password_input"], self.creds["password"])
            self.page.click(login_sel["signin_button"])
            
            # Wait for either URL to change to practice or home (success) or error selector to appear
            error_sel = login_sel.get("error_message", ".error-message")
            for _ in range(90):
                if "practice" in self.page.url or "home" in self.page.url:
                    logger.info("Login successful!")
                    return True
                if self.page.is_visible(error_sel):
                    error_text = self.page.inner_text(error_sel)
                    logger.error(f"Login failed. Error: {error_text}")
                    return False
                self.page.wait_for_timeout(500)
                
            logger.error("Login timed out. Current URL: " + self.page.url)
            return False
        except Exception as e:
            logger.error(f"Login exception: {e}")
            return False

    def click(self, selector: str, wait_for_nav: bool = False):
        logger.debug(f"Clicking: {selector}")
        self.page.wait_for_selector(selector, state="visible")
        self.page.click(selector)
        if wait_for_nav: self.page.wait_for_load_state("load")

    def fill_text(self, selector: str, text: str):
        logger.debug(f"Filling text into: {selector}")
        self.page.wait_for_selector(selector, state="visible")
        self.page.fill(selector, "")
        self.page.fill(selector, text)

    def get_text(self, selector: str, default: str = "") -> str:
        try:
            self.page.wait_for_selector(selector, state="visible", timeout=500)
            return self.page.inner_text(selector).strip()
        except Exception:
            return default

    def element_exists(self, selector: str, timeout: int = 5000) -> bool:
        try:
            self.page.wait_for_selector(selector, state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def get_all_text_of(self, selector: str) -> list[str]:
        elements = self.page.query_selector_all(selector)
        return [el.inner_text().strip() for el in elements if el.inner_text().strip()]

    def wait(self, milliseconds: int):
        self.page.wait_for_timeout(milliseconds)

    def setup_audio_interception(self):
        self._intercepted_audio_url = None
        self._audio_listener = lambda response: self._handle_audio_response(response)
        self.page.on("response", self._audio_listener)

    def _handle_audio_response(self, response):
        url = response.url
        content_type = response.headers.get("content-type", "")
        is_audio = any(ext in url.lower() for ext in [".mp3", ".wav", ".ogg", ".webm", ".m4a", ".aac"]) or "audio/" in content_type
        if is_audio and response.status == 200:
            logger.info(f"🎵 Intercepted audio URL: {url}")
            self._intercepted_audio_url = url

    def get_audio_url_from_dom(self) -> str:
        try:
            element = self.page.query_selector("audio")
            if element:
                src = element.get_attribute("src")
                if src:
                    logger.info(f"🎵 Found audio URL in DOM: {src}")
                    return src
        except Exception:
            pass
        return None

    def get_intercepted_audio_url(self, wait_seconds: int = 8) -> str:
        start_time = time.time()
        while time.time() - start_time < wait_seconds:
            if self._intercepted_audio_url: return self._intercepted_audio_url
            self.page.wait_for_timeout(500)
        return None

    def remove_audio_interception(self):
        if hasattr(self, "_audio_listener"):
            self.page.remove_listener("response", self._audio_listener)
            delattr(self, "_audio_listener")
        self._intercepted_audio_url = None

    def find_and_click_option(self, target_text: str) -> bool:
        import re
        import difflib
        option_selectors = self.selectors.get("exam", {}).get("option_selectors", [".option", "div[role='button']", ".choice"])
        
        # Resolve all matching elements for option selectors on the page
        options_elements = []
        for sel in option_selectors:
            elements = self.page.query_selector_all(sel)
            if elements:
                options_elements = elements
                break
                
        if not options_elements:
            logger.warning("No option elements found on the page.")
            return False
            
        clicked_any = False
        
        # 1. Parse all <option_number> tags
        num_matches = re.findall(r'<option_number>\s*(\d+)\s*</option_number>', target_text, re.IGNORECASE)
        if num_matches:
            for num_str in num_matches:
                idx = int(num_str) - 1
                if 0 <= idx < len(options_elements):
                    try:
                        logger.info(f"Clicking option index {idx+1} based on <option_number> tag: '{options_elements[idx].inner_text().strip()}'")
                        options_elements[idx].click()
                        clicked_any = True
                    except Exception as e:
                        logger.error(f"Failed to click option index {idx+1}: {e}")
            if clicked_any:
                return True
                
        # 2. Parse all <option_text> tags
        text_matches = re.findall(r'<option_text>(.*?)</option_text>', target_text, re.IGNORECASE | re.DOTALL)
        if text_matches:
            for text_target in text_matches:
                target_clean = " ".join(text_target.strip().lower().split())
                best_element = None
                best_ratio = 0.0
                best_match_text = ""
                
                for idx, el in enumerate(options_elements):
                    el_text = " ".join(el.inner_text().strip().lower().split())
                    if target_clean in el_text or el_text in target_clean:
                        best_ratio = 1.0
                        best_element = el
                        best_match_text = el.inner_text().strip()
                        break
                    
                    ratio = difflib.SequenceMatcher(None, target_clean, el_text).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_element = el
                        best_match_text = el.inner_text().strip()
                        
                if best_element and best_ratio > 0.5:
                    try:
                        logger.info(f"Clicking matched option (ratio {best_ratio:.2f}) from <option_text> tag: '{best_match_text}'")
                        best_element.click()
                        clicked_any = True
                    except Exception as e:
                        logger.error(f"Failed to click matched option: {e}")
            if clicked_any:
                return True
                
        # 3. Fallback: Parse index numbers from the raw text (e.g. if the AI returned "Option 3" or just "3")
        clean_response = target_text.strip().lower()
        num_match = re.search(r'\b\d+\b', clean_response)
        if num_match:
            idx = int(num_match.group()) - 1
            if 0 <= idx < len(options_elements):
                try:
                    logger.info(f"Fallback: Clicking option index {idx+1} based on number in response: '{options_elements[idx].inner_text().strip()}'")
                    options_elements[idx].click()
                    return True
                except Exception:
                    pass

        # 4. Fallback: Try to match the raw response text against the option texts
        target_clean = " ".join(clean_response.split())
        best_element = None
        best_ratio = 0.0
        best_match_text = ""
        for el in options_elements:
            el_text = " ".join(el.inner_text().strip().lower().split())
            if target_clean in el_text or el_text in target_clean:
                best_ratio = 1.0
                best_element = el
                best_match_text = el.inner_text().strip()
                break
            
            ratio = difflib.SequenceMatcher(None, target_clean, el_text).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_element = el
                best_match_text = el.inner_text().strip()
                
        if best_element and best_ratio > 0.5:
            try:
                logger.info(f"Fallback: Clicking matched option (ratio {best_ratio:.2f}) from raw response: '{best_match_text}'")
                best_element.click()
                return True
            except Exception:
                pass
                
        # 5. Ultimate Fallback: Just click the first option so we don't get stuck
        try:
            logger.warning(f"No match found for response. Clicking first option as ultimate fallback.")
            options_elements[0].click()
            return True
        except Exception as e:
            logger.error(f"Ultimate fallback click failed: {e}")
            
        return False

    def get_writing_prompt(self) -> str:
        prompt_selectors = [".question-text", ".writing-prompt", "p.prompt", ".task-description", "h3.question", ".exam-question"]
        for selector in prompt_selectors:
            text = self.get_text(selector)
            if text: return text
        return self.page.inner_text("body")[:1000]

    def get_reading_content(self) -> dict:
        result = {"passage": "", "question": "", "options": []}
        passage_selectors = [".passage", ".reading-text", ".article-text", "article", ".content-body"]
        for sel in passage_selectors:
            text = self.get_text(sel)
            if text:
                result["passage"] = text
                break
        question_selectors = ["p.text-base.font-medium", ".question", ".question-text", "h4.q-text", ".quiz-question"]
        for sel in question_selectors:
            text = self.get_text(sel)
            if text:
                result["question"] = text
                break
        option_selectors = self.selectors.get("exam", {}).get("option_selectors", [".option", "div[role='button']", ".choice"])
        for sel in option_selectors:
            texts = self.get_all_text_of(sel)
            if texts:
                result["options"] = texts
                break
        return result
