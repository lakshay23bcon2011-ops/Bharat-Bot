import os
import sys
import logging
import json
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
    task_indicator = "textarea, button[aria-label='Play audio'], button[hint='Play audio'], audio, div.cursor-pointer.shadow-md, .option, .choice, div[role='button'].answer, li.answer, button[aria-label='Record'], button[hint='Record'], .mic-button, button[aria-label*='recording'], button[aria-label*='record']"
    if not browser.element_exists(task_indicator, timeout=10000):
        return "unknown"
        
    # Now that the page is rendered, use short timeouts (500ms) to identify which one it is
    if browser.element_exists("button[aria-label='Record']", timeout=500) or \
       browser.element_exists("button[hint='Record']", timeout=500) or \
       browser.element_exists(".mic-button", timeout=500) or \
       browser.element_exists("button[aria-label*='recording']", timeout=500) or \
       browser.element_exists("button[aria-label*='record']", timeout=500):
        return "speaking"
        
    if browser.element_exists("textarea", timeout=500): 
        return "writing"
    
    if browser.element_exists("button[aria-label='Play audio']", timeout=500) or \
       browser.element_exists("button[hint='Play audio']", timeout=500) or \
       browser.element_exists("button[aria-label='Play']", timeout=500): 
        return "listening"
    
    for s in ["div.cursor-pointer.shadow-md", ".option", ".choice", "div[role='button'].answer", "li.answer"]:
        if browser.element_exists(s, timeout=500): 
            return "reading"
        
    return "unknown"

COMPLETIONS_FILE = "session_completions.json"

def load_completions() -> dict:
    default_data = {
        "speaking": 0,
        "listening": 0,
        "reading": 0,
        "writing": 0
    }
    if Path(COMPLETIONS_FILE).exists():
        try:
            with open(COMPLETIONS_FILE, "r") as f:
                data = json.load(f)
                for k in default_data:
                    if k not in data:
                        data[k] = 0
                return data
        except Exception:
            return default_data
    return default_data

def save_completions(data: dict):
    try:
        with open(COMPLETIONS_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Failed to save completions file: {e}")

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
        while tests_completed < 200: # Limit to 200 tests for safety
            logger.info(f"=== Starting Test Session {tests_completed+1} ===")
            
            # Navigate to FluentEdge if we aren't already somewhere inside
            if "practice" not in browser.page.url:
                if browser.element_exists(sel["navigation"]["sidebar_ai_fluentedge"]):
                    browser.click(sel["navigation"]["sidebar_ai_fluentedge"], wait_for_nav=True)
                    browser.page.wait_for_load_state("load")
            
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
                    
                    browser.page.wait_for_load_state("load")
                    
                    if browser.page.url != old_url:
                        logger.info(f"DEBUG: Navigation successful for {log_name}. New URL: {browser.page.url}")
                        return True
                    logger.warning(f"DEBUG: Click {attempt+1} on {log_name} didn't navigate. Retrying...")
                return False
                
            # Dashboard Selection
            logger.info("DEBUG: Checking Dashboard buttons...")
            dashboard_clicked = False
            current_skill = None
            
            completions_data = load_completions()
            logger.info(f"Current Section Progress: Speaking: {completions_data['speaking']}/30, Listening: {completions_data['listening']}/30, Reading: {completions_data['reading']}/30, Writing: {completions_data['writing']}/30")
            
            # Decide which skill to click based on the 30-lesson limit
            skills_to_check = []
            if completions_data["speaking"] < 30:
                skills_to_check.append(("speaking_start", "speaking"))
            if completions_data["listening"] < 30:
                skills_to_check.append(("listening_start", "listening"))
            if completions_data["reading"] < 30:
                skills_to_check.append(("reading_start", "reading"))
            if completions_data["writing"] < 30:
                skills_to_check.append(("writing_start", "writing"))
                
            if not skills_to_check:
                logger.info("All sections have completed 30 lessons! Exiting bot.")
                break
                
            for button_key, skill_name in skills_to_check:
                if browser.element_exists(sel["fluentedge"][button_key]):
                    if robust_navigate(sel["fluentedge"][button_key], f"Dashboard {skill_name.capitalize()}"):
                        dashboard_clicked = True
                        current_skill = skill_name
                        break
            
            if not dashboard_clicked:
                logger.info("DEBUG: No Dashboard button found (maybe already on Level page).")
                # Detect current skill from URL
                url = browser.page.url
                if "Speaking" in url or "sectionId=2" in url:
                    current_skill = "speaking"
                elif "Listening" in url or "sectionId=3" in url:
                    current_skill = "listening"
                elif "Reading" in url or "sectionId=1" in url:
                    current_skill = "reading"
                elif "Writing" in url or "sectionId=4" in url:
                    current_skill = "writing"
                
            logger.info(f"DEBUG: URL after Dashboard: {browser.page.url}")
    
            # Level selection
            logger.info("DEBUG: Checking Level buttons...")
            if browser.element_exists(sel["levels"]["start_button"]):
                robust_navigate(sel["levels"]["start_button"], "Level Start button")
            elif browser.element_exists(sel["levels"]["revisit_button"]):
                robust_navigate(sel["levels"]["revisit_button"], "Level Revisit button", use_locator_first=True)
            else:
                logger.info("DEBUG: No Level button found! Navigating back to FluentEdge to reset...")
                if browser.element_exists(sel["navigation"]["sidebar_ai_fluentedge"]):
                    browser.click(sel["navigation"]["sidebar_ai_fluentedge"], wait_for_nav=True)
                else:
                    browser.go_to_base()
                browser.page.wait_for_load_state("load")
                continue
                
            logger.info(f"DEBUG: URL after Level: {browser.page.url}")
            
            # Unit selection
            logger.info("DEBUG: Checking Unit buttons...")
            if browser.element_exists(sel["units"]["start_learning"]):
                robust_navigate(sel["units"]["start_learning"], "Unit Start Learning button")
            elif browser.element_exists(sel["units"]["review"]):
                robust_navigate(sel["units"]["review"], "Unit Review button", use_locator_first=True)
            else:
                logger.info("DEBUG: No Unit button found! Navigating back to FluentEdge to reset...")
                if browser.element_exists(sel["navigation"]["sidebar_ai_fluentedge"]):
                    browser.click(sel["navigation"]["sidebar_ai_fluentedge"], wait_for_nav=True)
                else:
                    browser.go_to_base()
                browser.page.wait_for_load_state("load")
                continue
                
            logger.info(f"DEBUG: URL after Unit: {browser.page.url}")
            
            # Lesson selection
            logger.info("DEBUG: Checking Lesson buttons...")
            lesson_clicked = False
            
            # Wait for lesson cards to render
            try:
                browser.page.wait_for_selector(".card, div.border, div.shadow-md, div.rounded-lg", timeout=10000)
            except Exception:
                pass
                
            # Find all cards on the page
            cards = browser.page.locator(".card, div.border, div.shadow-md, div.rounded-lg").all()
            
            # Filter cards that actually contain lesson titles (e.g. "01.", "02.", etc.)
            lesson_cards = []
            for card in cards:
                try:
                    text = card.inner_text()
                    lines = [l.strip() for l in text.split("\n") if l.strip()]
                    if lines and any(lines[0].startswith(f"{i:02d}") or lines[0] == str(i) for i in range(1, 100)):
                        lesson_cards.append(card)
                except Exception:
                    pass
                    
            logger.info(f"DEBUG: Found {len(lesson_cards)} valid lesson cards.")
            
            # Decide target lesson card based on completion count
            target_prefix = None
            if current_skill == "speaking":
                completions_data = load_completions()
                count = completions_data.get("speaking", 0)
                # If we have less than 6 completions, start at Lesson 6 (requested by user)
                if count < 6:
                    target_prefix = "06."
                else:
                    target_prefix = f"{count+1:02d}."
            
            target_card = None
            if target_prefix:
                for card in lesson_cards:
                    text = card.inner_text().strip()
                    if text.startswith(target_prefix) or target_prefix in text:
                        target_card = card
                        logger.info(f"DEBUG: Target lesson card matching '{target_prefix}' found!")
                        break
            
            # Fallback 1: Find the first card with "Practice" or "Retry" or "Keep going"
            if not target_card:
                for card in lesson_cards:
                    text = card.inner_text().strip()
                    if "Practice" in text or "Retry" in text or "Keep going" in text:
                        target_card = card
                        logger.info(f"DEBUG: Falling back to card: {text.splitlines()[0] if text.splitlines() else ''}")
                        break
            
            if target_card:
                # Click 'Practice', 'Retry', 'Done', or 'Keep going' button inside card
                for btn_text in ["Practice", "Retry", "Done", "Keep going"]:
                    btn = target_card.locator(f"button:has-text('{btn_text}')").first
                    if btn.is_visible():
                        logger.info(f"DEBUG: Clicking '{btn_text}' button inside lesson card...")
                        btn.click()
                        browser.page.wait_for_load_state("load")
                        lesson_clicked = True
                        break
                        
            # Fallback 2: Global selectors
            if not lesson_clicked:
                if browser.element_exists(sel["lessons"]["practice_button"]):
                    robust_navigate(sel["lessons"]["practice_button"], "Lesson Practice button", use_locator_first=True)
                    lesson_clicked = True
                elif browser.element_exists(sel["lessons"]["learn_button"]):
                    robust_navigate(sel["lessons"]["learn_button"], "Lesson Learn button", use_locator_first=True)
                    lesson_clicked = True
                else:
                    logger.info("DEBUG: No Lesson button found! Might be out of lessons. Navigating back to FluentEdge to reset...")
                    if browser.element_exists(sel["navigation"]["sidebar_ai_fluentedge"]):
                        browser.click(sel["navigation"]["sidebar_ai_fluentedge"], wait_for_nav=True)
                    else:
                        browser.go_to_base()
                    browser.page.wait_for_load_state("load")
                    continue
                
            logger.info(f"DEBUG: URL before task loop: {browser.page.url}")
            
            # Task Loop
            tasks_completed = 0
            lesson_success = False
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
                    # If we are still on the practice/exam URL but task_type is unknown,
                    # we should wait and retry rather than immediately assuming we finished.
                    if "practice/exam" in browser.page.url:
                        logger.warning("Still in exam page but task type is unknown. Waiting 5s and retrying...")
                        browser.page.wait_for_timeout(5000)
                        continue

                    # Check for completion
                    exit_sel = config["selectors"]["exam"].get("exit_button")
                    close_sel = config["selectors"]["exam"].get("close_button")
                    if browser.element_exists(exit_sel, timeout=3000):
                        browser.click(exit_sel)
                        logger.info("Session finished gracefully via exit button.")
                        lesson_success = True
                        break
                    elif browser.element_exists(close_sel, timeout=3000):
                        browser.click(close_sel)
                        logger.info("Session finished gracefully via close button.")
                        lesson_success = True
                        break
                    else:
                        logger.warning("Unknown task type and no exit button. Assuming test is finished and we are back at the menu.")
                        lesson_success = True
                        break
                
                if success:
                    tasks_completed += 1
                    logger.info(f"Task {tasks_completed} successful.")
                    browser.page.wait_for_load_state("load")
                else:
                    logger.error(f"Task {tasks_completed+1} failed after retries.")
                    try:
                        browser.page.screenshot(path=f"task_failed_{tasks_completed+1}.png")
                        logger.info(f"Saved failure screenshot to task_failed_{tasks_completed+1}.png")
                    except Exception as se:
                        logger.error(f"Failed to capture screenshot: {se}")
                    # Try to exit the exam if we are stuck
                    exit_sel = config["selectors"]["exam"].get("exit_button")
                    close_sel = config["selectors"]["exam"].get("close_button")
                    if browser.element_exists(exit_sel, timeout=3000):
                        browser.click(exit_sel)
                    elif browser.element_exists(close_sel, timeout=3000):
                        browser.click(close_sel)
                    break
                    
            if lesson_success:
                tests_completed += 1
                logger.info(f"Finished test {tests_completed} successfully.")
                if current_skill:
                    completions_data = load_completions()
                    completions_data[current_skill] += 1
                    save_completions(completions_data)
                    logger.info(f"Progress updated: {current_skill} completion count is now {completions_data[current_skill]}/30.")
            else:
                logger.info("Test session did not complete successfully.")
                
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
    finally:
        browser.close()
        logger.info("Bot execution finished.")

if __name__ == "__main__":
    main()
