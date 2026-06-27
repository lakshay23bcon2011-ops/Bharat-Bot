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
        launch_args = ["--no-sandbox", "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"]
        
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
        self.page.goto(url, wait_until="networkidle")

    def go_to_base(self):
        self.go_to(self.browser_cfg.get("base_url", ""))

    def login(self) -> bool:
        logger.info("Attempting login...")
        try:
            self.go_to_base()
            login_sel = self.selectors.get("login", {})
            self.page.fill(login_sel["username_input"], self.creds["username"])
            self.page.fill(login_sel["password_input"], self.creds["password"])
            self.page.click(login_sel["signin_button"])
            self.page.wait_for_load_state("networkidle")
            error_sel = login_sel.get("error_message", ".error-message")
            if self.page.is_visible(error_sel):
                error_text = self.page.inner_text(error_sel)
                logger.error(f"Login failed. Error: {error_text}")
                return False
            logger.info("Login successful!")
            return True
        except Exception as e:
            logger.error(f"Login exception: {e}")
            return False

    def click(self, selector: str, wait_for_nav: bool = False):
        logger.debug(f"Clicking: {selector}")
        self.page.wait_for_selector(selector, state="visible")
        self.page.click(selector)
        if wait_for_nav: self.page.wait_for_load_state("networkidle")

    def fill_text(self, selector: str, text: str):
        logger.debug(f"Filling text into: {selector}")
        self.page.wait_for_selector(selector, state="visible")
        self.page.fill(selector, "")
        self.page.fill(selector, text)

    def get_text(self, selector: str, default: str = "") -> str:
        try:
            self.page.wait_for_selector(selector, state="visible", timeout=10000)
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

    def get_intercepted_audio_url(self, wait_seconds: int = 8) -> str | None:
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

    def find_and_click_option(self, option_text: str) -> bool:
        option_selectors = self.selectors.get("exam", {}).get("option_selectors", [".option", "div[role='button']", ".choice"])
        for selector in option_selectors:
            try:
                elements = self.page.query_selector_all(selector)
                for element in elements:
                    text = element.inner_text().strip()
                    if option_text.lower() in text.lower() or text.lower() in option_text.lower():
                        logger.info(f"Found matching option: '{text}' — clicking it.")
                        element.click()
                        return True
            except Exception: continue
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
        question_selectors = [".question", ".question-text", "h4.q-text", ".quiz-question"]
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
