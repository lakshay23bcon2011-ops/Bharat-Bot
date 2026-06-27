import logging

def handle_reading_task(browser, ai, config):
    logger = logging.getLogger("BharatBot")
    logger.info("Handling Reading Task...")
    sel = config["selectors"]["exam"]
    
    for attempt in range(3):
        try:
            content = browser.get_reading_content()
            if not content["question"] or not content["options"]:
                logger.warning(f"Attempt {attempt+1}: Question/Options not found.")
                continue
            
            correct_option = ai.answer_mcq(content["question"], content["options"], content["passage"])
            if not correct_option:
                continue
            
            if not browser.find_and_click_option(correct_option):
                logger.warning(f"Attempt {attempt+1}: Could not click option.")
                continue
            
            browser.wait(1000)
            browser.click(sel["check_button"])
            browser.wait(2000)
            
            if browser.element_exists(sel["continue_button"]):
                browser.click(sel["continue_button"])
                logger.info("Reading task completed.")
                return True
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {e}")
            browser.wait(2000)
            
    return False
