import logging

def handle_writing_task(browser, ai, config, logger):
    logger.info("Handling Writing Task...")
    sel = config["selectors"]["exam"]
    
    # Retry logic
    for attempt in range(3):
        try:
            prompt = browser.get_writing_prompt()
            if not prompt:
                logger.warning(f"Attempt {attempt+1}: Prompt not found.")
                continue
            
            essay = ai.answer_writing(prompt)
            if not essay:
                logger.warning(f"Attempt {attempt+1}: AI failed to generate essay.")
                continue
            browser.fill_text(sel["textarea"], essay)
            browser.click(sel["check_button"])
            
            if browser.element_exists(sel["continue_button"], timeout=10000):
                browser.click(sel["continue_button"])
                logger.info("Writing task completed.")
                return True
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {e}")
            browser.page.wait_for_timeout(2000) # Error backoff
            
    return False
