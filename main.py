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
    # Wait for the page to render ANY task element before checking specifics
    task_indicator = "textarea, button[aria-label='Play audio'], button[hint='Play audio'], audio, div.cursor-pointer.shadow-md, .option, .choice, div[role='button'].answer, li.answer, button[aria-label='Record'], button[hint='Record'], .mic-button"
    if not browser.element_exists(task_indicator, timeout=10000):
        return "unknown"
        
    # Now that the page is rendered, use short timeouts (500ms) to identify which one it is
    if browser.element_exists("textarea", timeout=500): return "writing"
    
    if browser.element_exists("button[aria-label='Play audio']", timeout=500) or browser.element_exists("button[hint='Play audio']", timeout=500) or browser.element_exists("audio", timeout=500): 
        return "listening"
    
    for s in ["div.cursor-pointer.shadow-md", ".option", ".choice", "div[role='button'].answer", "li.answer"]:
        if browser.element_exists(s, timeout=500): return "reading"
        
    if browser.element_exists("button[aria-label='Record']", timeout=500) or browser.element_exists("button[hint='Record']", timeout=500) or browser.element_exists(".mic-button", timeout=500): 
        return "speaking"
        
    return "unknown"

def main():
    logger = setup_logger()
    logger.info("Starting Bharat English Bot...")
    
    config = load_config("config.yaml")
    
    # Secure Credentials
    config["credentials"] = {
        "username": os.getenv("BET_USERNAME"),
        "password": os.getenv("BET_PASSWORD")
    }
    
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
        
        # Master Loop to continuously take tests
        tests_completed = 0
        while tests_completed < 15: # Limit to 15 tests for safety
            logger.info(f"=== Starting Test Session {tests_completed+1} ===")
            
            # Navigate to FluentEdge if we aren't already somewhere inside
            if "practice" not in browser.page.url:
                if browser.element_exists(sel["navigation"]["sidebar_ai_fluentedge"]):
                    browser.click(sel["navigation"]["sidebar_ai_fluentedge"], wait_for_nav=True)
                    browser.page.wait_for_load_state("networkidle")
            
            def robust_navigate(selector: str, log_name: str, use_locator_first: bool = False):
                logger.info(f"DEBUG: Attempting to click {log_name}...")
                for attempt in range(3):
                    old_url = browser.page.url
                    if use_locator_first:
                        try:
                            browser.page.locator(selector).first.click()
                        except Exception:
                            pass
                    else:
                        browser.click(selector, wait_for_nav=True)
                    
                    browser.page.wait_for_load_state("networkidle")
                    
                    if browser.page.url != old_url:
                        logger.info(f"DEBUG: Navigation successful for {log_name}. New URL: {browser.page.url}")
                        return True
                    logger.warning(f"DEBUG: Click {attempt+1} on {log_name} didn't navigate. Retrying...")
                return False
                
            # Dashboard Selection
            logger.info("DEBUG: Checking Dashboard buttons...")
            if browser.element_exists(sel["fluentedge"]["listening_start"]):
                robust_navigate(sel["fluentedge"]["listening_start"], "Dashboard Listening Start")
            else:
                logger.info("DEBUG: No Dashboard button found (maybe already on Level page).")
                
            logger.info(f"DEBUG: URL after Dashboard: {browser.page.url}")
    
            # Level selection
            logger.info("DEBUG: Checking Level buttons...")
            if browser.element_exists(sel["levels"]["start_button"]):
                robust_navigate(sel["levels"]["start_button"], "Level Start button")
            elif browser.element_exists(sel["levels"]["revisit_button"]):
                robust_navigate(sel["levels"]["revisit_button"], "Level Revisit button", use_locator_first=True)
            else:
                logger.info("DEBUG: No Level button found!")
                
            logger.info(f"DEBUG: URL after Level: {browser.page.url}")
            
            # Unit selection
            logger.info("DEBUG: Checking Unit buttons...")
            if browser.element_exists(sel["units"]["start_learning"]):
                robust_navigate(sel["units"]["start_learning"], "Unit Start Learning button")
            elif browser.element_exists(sel["units"]["review"]):
                robust_navigate(sel["units"]["review"], "Unit Review button", use_locator_first=True)
            else:
                logger.info("DEBUG: No Unit button found!")
                
            logger.info(f"DEBUG: URL after Unit: {browser.page.url}")
            
            # Lesson selection
            logger.info("DEBUG: Checking Lesson buttons...")
            if browser.element_exists(sel["lessons"]["practice_button"]):
                robust_navigate(sel["lessons"]["practice_button"], "Lesson Practice button", use_locator_first=True)
            elif browser.element_exists(sel["lessons"]["learn_button"]):
                robust_navigate(sel["lessons"]["learn_button"], "Lesson Learn button", use_locator_first=True)
            else:
                logger.info("DEBUG: No Lesson button found! Might be out of lessons.")
                break
                
            logger.info(f"DEBUG: URL before task loop: {browser.page.url}")
            
            # Task Loop
            tasks_completed = 0
            while tasks_completed < 20:
                task_type = detect_task_type(browser)
                logger.info(f"Task {tasks_completed+1} detected as: {task_type}")
                
                success = False
                if task_type == "writing":
                    success = handle_writing_task(browser, ai, config, logger)
                elif task_type == "reading":
                    success = handle_reading_task(browser, ai, config, logger)
                elif task_type == "listening":
                    success = handle_listening_task(browser, ai, transcriber, config, logger)
                elif task_type == "speaking":
                    success = handle_speaking_task(browser, ai, speaker, config, logger)
                else:
                    # Check for completion
                    exit_sel = config["selectors"]["exam"].get("exit_button")
                    close_sel = config["selectors"]["exam"].get("close_button")
                    if browser.element_exists(exit_sel, timeout=3000):
                        browser.click(exit_sel)
                        logger.info("Session finished gracefully via exit button.")
                        break
                    elif browser.element_exists(close_sel, timeout=3000):
                        browser.click(close_sel)
                        logger.info("Session finished gracefully via close button.")
                        break
                    else:
                        logger.warning("Unknown task type and no exit button. Assuming test is finished and we are back at the menu.")
                        break
                
                if success:
                    tasks_completed += 1
                    logger.info(f"Task {tasks_completed} successful.")
                    browser.page.wait_for_load_state("networkidle")
                else:
                    logger.error(f"Task {tasks_completed+1} failed after retries.")
                    break
                    
            tests_completed += 1
            logger.info(f"Finished test {tests_completed}. Moving to next test...")
                
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
    finally:
        browser.close()
        logger.info("Bot execution finished.")

if __name__ == "__main__":
    main()
