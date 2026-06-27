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

# Import task handlers
from tasks.writing import handle_writing_task
from tasks.reading import handle_reading_task
from tasks.listening import handle_listening_task
from tasks.speaking import handle_speaking_task

load_dotenv()

def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f: return yaml.safe_load(f)

def detect_task_type(browser):
    # Use semantic selectors for better detection
    if browser.element_exists("textarea", timeout=3000): return "writing"
    if browser.element_exists("button[hint='Play audio']", timeout=3000) or browser.element_exists("audio", timeout=1000): return "listening"
    
    # MCQ detection
    for s in [".option", ".choice", "div[role='button'].answer", "li.answer"]:
        if browser.element_exists(s, timeout=3000): return "reading"
        
    if browser.element_exists("button[hint='Record']", timeout=3000) or browser.element_exists(".mic-button", timeout=1000): return "speaking"
    return "unknown"

def main():
    logger = setup_logger()
    logger.info("Starting Bharat English Bot...")
    
    config = load_config("config.yaml")
    browser = BrowserController(config)
    ai = AIAnswerer(config)
    transcriber = Transcriber(config)
    speaker = Speaker(config)
    
    try:
        browser.start()
        if not browser.login():
            logger.error("Login failed. Exiting.")
            return
            
        sel = config["selectors"]
        
        # Navigate to FluentEdge
        browser.click(sel["navigation"]["sidebar_ai_fluentedge"], wait_for_nav=True)
        browser.wait(2000)
        
        # Level selection
        if browser.element_exists(sel["levels"]["start_button"]):
            browser.click(sel["levels"]["start_button"], wait_for_nav=True)
        elif browser.element_exists(sel["levels"]["revisit_button"]):
            browser.click(sel["levels"]["revisit_button"], wait_for_nav=True)
            
        browser.wait(1500)
        
        # Unit selection
        if browser.element_exists(sel["units"]["start_learning"]):
            browser.click(sel["units"]["start_learning"], wait_for_nav=True)
        elif browser.element_exists(sel["units"]["review"]):
            browser.click(sel["units"]["review"], wait_for_nav=True)
            
        browser.wait(1500)
        
        # Lesson selection
        if browser.element_exists(sel["lessons"]["practice_button"]):
            browser.click(sel["lessons"]["practice_button"], wait_for_nav=True)
            
        browser.wait(2000)
        
        # Task Loop
        tasks_completed = 0
        while tasks_completed < 20:
            task_type = detect_task_type(browser)
            logger.info(f"Task {tasks_completed+1} detected as: {task_type}")
            
            success = False
            if task_type == "writing":
                success = handle_writing_task(browser, ai, config)
            elif task_type == "reading":
                success = handle_reading_task(browser, ai, config)
            elif task_type == "listening":
                success = handle_listening_task(browser, ai, transcriber, config)
            elif task_type == "speaking":
                success = handle_speaking_task(browser, ai, speaker, config)
            else:
                # Check for completion
                exit_sel = config["selectors"]["exam"].get("exit_button")
                close_sel = config["selectors"]["exam"].get("close_button")
                if browser.element_exists(exit_sel, timeout=3000):
                    browser.click(exit_sel)
                    logger.info("Session finished.")
                    break
                elif browser.element_exists(close_sel, timeout=3000):
                    browser.click(close_sel)
                    logger.info("Session finished.")
                    break
                else:
                    logger.warning("Unknown task type and no exit button. Stopping.")
                    break
            
            if success:
                tasks_completed += 1
                logger.info(f"Task {tasks_completed} successful.")
                browser.wait(2000)
            else:
                logger.error(f"Task {tasks_completed+1} failed after retries.")
                break
                
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
    finally:
        browser.close()
        logger.info("Bot execution finished.")

if __name__ == "__main__":
    main()
