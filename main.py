import os
import sys
import logging
import yaml
from dotenv import load_dotenv
from pathlib import Path

from modules.logger_setup import setup_logger
from modules.browser import BrowserController
from modules.ai_answerer import AIAnswerer
from modules.transcriber import Transcriber
from modules.speaker import Speaker

load_dotenv()

def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f: return yaml.safe_load(f)

def handle_writing_task(browser, ai, config):
    logger = logging.getLogger("BharatBot")
    sel = config["selectors"]["exam"]
    prompt = browser.get_writing_prompt()
    if not prompt: return False
    essay = ai.answer_writing(prompt)
    if not essay: return False
    browser.fill_text(sel["textarea"], essay)
    browser.wait(1000)
    browser.click(sel["check_button"])
    browser.wait(2000)
    if browser.element_exists(sel["continue_button"]):
        browser.click(sel["continue_button"])
        return True
    return False

def handle_reading_task(browser, ai, config):
    logger = logging.getLogger("BharatBot")
    sel = config["selectors"]["exam"]
    content = browser.get_reading_content()
    if not content["question"] or not content["options"]: return False
    correct_option = ai.answer_mcq(content["question"], content["options"], content["passage"])
    if not correct_option: return False
    if not browser.find_and_click_option(correct_option): return False
    browser.wait(1000)
    browser.click(sel["check_button"])
    browser.wait(2000)
    if browser.element_exists(sel["continue_button"]):
        browser.click(sel["continue_button"])
        return True
    return False

def handle_listening_task(browser, ai, transcriber, config):
    logger = logging.getLogger("BharatBot")
    sel = config["selectors"]["exam"]
    browser.setup_audio_interception()
    if not browser.element_exists(sel["play_audio"]): return False
    browser.click(sel["play_audio"])
    audio_url = browser.get_intercepted_audio_url(wait_seconds=10)
    if not audio_url: return False
    transcription = transcriber.download_and_transcribe(audio_url)
    if not transcription: return False
    content = browser.get_reading_content()
    correct_option = ai.answer_mcq(content.get("question", ""), content.get("options", []), transcription)
    if not correct_option or not browser.find_and_click_option(correct_option): return False
    browser.wait(1000)
    browser.click(sel["check_button"])
    browser.wait(2000)
    if browser.element_exists(sel["continue_button"]): browser.click(sel["continue_button"])
    browser.remove_audio_interception()
    transcriber.cleanup()
    return True

def handle_speaking_task(browser, ai, speaker, config):
    logger = logging.getLogger("BharatBot")
    sel = config["selectors"]["exam"]
    prompt = browser.get_writing_prompt()
    if not prompt: return False
    speech_text = ai.generate_speech_text(prompt)
    if not speech_text: return False
    wav_path = speaker.text_to_speech(speech_text)
    if not wav_path: return False
    speaker.play_in_browser(browser.page, wav_path)
    browser.wait(1500)
    if browser.element_exists(sel.get("continue_button", "button:has-text('Continue')")):
        browser.click(sel["continue_button"])
    elif browser.element_exists(sel.get("check_button", "button:has-text('Check')")):
        browser.click(sel["check_button"])
    speaker.cleanup()
    return True

def detect_task_type(browser):
    if browser.element_exists("textarea", timeout=3000): return "writing"
    if browser.element_exists("button[hint='Play audio']", timeout=3000): return "listening"
    for s in [".option", ".choice", "div[role='button'].answer"]:
        if browser.element_exists(s, timeout=3000): return "reading"
    if browser.element_exists("button[hint='Record']", timeout=3000): return "speaking"
    return "unknown"

def main():
    logger = setup_logger()
    config = load_config("config.yaml")
    browser = BrowserController(config)
    ai = AIAnswerer(config)
    transcriber = Transcriber(config)
    speaker = Speaker(config)
    try:
        browser.start()
        if not browser.login(): return
        sel = config["selectors"]
        browser.click(sel["navigation"]["sidebar_ai_fluentedge"], wait_for_nav=True)
        browser.wait(2000)
        if browser.element_exists(sel["levels"]["start_button"]): browser.click(sel["levels"]["start_button"], wait_for_nav=True)
        elif browser.element_exists(sel["levels"]["revisit_button"]): browser.click(sel["levels"]["revisit_button"], wait_for_nav=True)
        browser.wait(1500)
        if browser.element_exists(sel["units"]["start_learning"]): browser.click(sel["units"]["start_learning"], wait_for_nav=True)
        elif browser.element_exists(sel["units"]["review"]): browser.click(sel["units"]["review"], wait_for_nav=True)
        browser.wait(1500)
        if browser.element_exists(sel["lessons"]["practice_button"]): browser.click(sel["lessons"]["practice_button"], wait_for_nav=True)
        browser.wait(2000)
        tasks_completed = 0
        while tasks_completed < 20:
            task_type = detect_task_type(browser)
            success = False
            if task_type == "writing": success = handle_writing_task(browser, ai, config)
            elif task_type == "reading": success = handle_reading_task(browser, ai, config)
            elif task_type == "listening": success = handle_listening_task(browser, ai, transcriber, config)
            elif task_type == "speaking": success = handle_speaking_task(browser, ai, speaker, config)
            else:
                exit_sel = config["selectors"]["exam"].get("exit_button")
                close_sel = config["selectors"]["exam"].get("close_button")
                if browser.element_exists(exit_sel, timeout=3000): browser.click(exit_sel); break
                elif browser.element_exists(close_sel, timeout=3000): browser.click(close_sel); break
                else: break
            if success: tasks_completed += 1; browser.wait(2000)
            else: break
    except Exception as e: logger.critical(f"Error: {e}")
    finally: browser.close()

if __name__ == "__main__": main()
