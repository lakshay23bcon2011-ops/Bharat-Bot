import logging

def handle_speaking_task(browser, ai, speaker, config, logger):
    logger.info("Handling Speaking Task...")
    sel = config["selectors"]["exam"]
    
    for attempt in range(3):
        try:
            prompt = browser.get_writing_prompt()
            if not prompt:
                continue
                
            speech_text = ai.generate_speech_text(prompt)
            if not speech_text:
                continue
                
            wav_path = speaker.text_to_speech(speech_text)
            if not wav_path:
                continue
                
            # Click record button if it exists
            mic_sel = config["selectors"]["exam"].get("mic_button", "button[hint='Record']")
            if browser.element_exists(mic_sel):
                browser.click(mic_sel)
                # Play audio directly in the browser context (blocks until finished)
                speaker.play_in_browser(browser.page, wav_path)
                # Click stop if needed or wait for auto-stop
                if browser.element_exists(mic_sel):
                    browser.click(sel["check_button"])
            
            if browser.element_exists(sel.get("continue_button", "button:has-text('Continue')"), timeout=10000):
                browser.click(sel["continue_button"])
            elif browser.element_exists(sel.get("check_button", "button:has-text('Check')")):
                browser.click(sel["check_button"])
                
            speaker.cleanup()
            logger.info("Speaking task completed.")
            return True
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {e}")
            speaker.cleanup()
            browser.page.wait_for_timeout(2000) # Only used for error backoff
            
    return False
