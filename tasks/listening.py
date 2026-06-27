import logging

def handle_listening_task(browser, ai, transcriber, config, logger):
    logger.info("Handling Listening Task...")
    sel = config["selectors"]["exam"]
    
    for attempt in range(3):
        try:
            logger.info(f"--- Listening Task Attempt {attempt+1} ---")
            browser.setup_audio_interception()
            if not browser.element_exists(sel["play_audio"]):
                logger.warning("Play audio button not found.")
                continue
                
            audio_url = browser.get_audio_url_from_dom()
            browser.click(sel["play_audio"])
            
            if not audio_url:
                logger.info("Audio URL not found in DOM, waiting for network interception...")
                audio_url = browser.get_intercepted_audio_url(wait_seconds=5)
                
            if not audio_url:
                logger.warning("Failed to get audio URL from DOM or network.")
                continue
                
            transcription = transcriber.download_and_transcribe(audio_url)
            if not transcription:
                logger.warning("Failed to transcribe audio.")
                continue
                
            content = browser.get_reading_content()
            correct_option = ai.answer_mcq(content.get("question", ""), content.get("options", []), transcription)
            
            if not correct_option:
                logger.warning("AI failed to provide a correct option.")
                continue
                
            if not browser.find_and_click_option(correct_option):
                logger.warning(f"Failed to find and click option matching: {correct_option}")
                continue
                
            browser.click(sel["check_button"])
            
            if browser.element_exists(sel["continue_button"], timeout=10000):
                browser.click(sel["continue_button"])
                browser.remove_audio_interception()
                transcriber.cleanup()
                logger.info("Listening task completed.")
                return True
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {e}")
            browser.remove_audio_interception()
            browser.page.wait_for_timeout(2000) # Error backoff
            
    return False
