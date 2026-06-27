import logging

def handle_reading_task(browser, ai, config, logger):
    logger.info("Handling Reading Task...")
    sel = config["selectors"]["exam"]
    
    for attempt in range(3):
        try:
            content = browser.get_reading_content()
            if not content["question"] or not content["options"]:
                logger.warning(f"Attempt {attempt+1}: Question/Options not found.")
                with open("reading_debug.html", "w", encoding="utf-8") as f:
                    f.write(browser.page.content())
                continue
            
            correct_option = ai.answer_mcq(content["question"], content["options"], content["passage"])
            if not correct_option:
                continue
            
            if not browser.find_and_click_option(correct_option):
                logger.warning(f"Attempt {attempt+1}: Could not click option.")
                continue
            browser.click(sel["check_button"])
            
            if browser.element_exists(sel["continue_button"], timeout=10000):
                browser.click(sel["continue_button"])
                logger.info("Reading task completed.")
                return True
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {e}")
            browser.page.wait_for_timeout(2000) # Error backoff
            
    return False
