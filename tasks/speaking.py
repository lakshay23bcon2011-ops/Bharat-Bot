import logging

def handle_speaking_task(browser, ai, speaker, config):
    logger = logging.getLogger("BharatBot")
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
                
            speaker.play_in_browser(browser.page, wav_path)
            browser.wait(1500)
            
            if browser.element_exists(sel.get("continue_button", "button:has-text('Continue')")):
                browser.click(sel["continue_button"])
            elif browser.element_exists(sel.get("check_button", "button:has-text('Check')")):
                browser.click(sel["check_button"])
                
            speaker.cleanup()
            logger.info("Speaking task completed.")
            return True
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {e}")
            speaker.cleanup()
            browser.wait(2000)
            
    return False
