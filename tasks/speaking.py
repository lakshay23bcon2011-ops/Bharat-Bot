import logging

def handle_speaking_task(browser, ai, speaker, config, logger):
    logger.info("Handling Speaking Task...")
    sel = config["selectors"]["exam"]
    
    for attempt in range(3):
        try:
            logger.info(f"--- Speaking Task Attempt {attempt+1} ---")
            prompt = browser.get_writing_prompt()
            if not prompt:
                logger.warning("Speaking prompt not found.")
                continue
                
            speech_text = ai.generate_speech_text(prompt)
            if not speech_text:
                logger.warning("AI failed to generate speech text.")
                continue
                
            wav_path = speaker.text_to_speech(speech_text)
            if not wav_path:
                logger.warning("Failed to generate TTS audio.")
                continue
                
            mic_sel = config["selectors"]["exam"].get("mic_button", "button[hint='Record']")
            if browser.element_exists(mic_sel):
                # 1. Prepare injection stream (sets window.injectedAudioStream)
                speaker.prepare_in_browser(browser.page, wav_path)
                
                # 2. Start recording (getUserMedia is triggered now and gets the injected stream!)
                logger.info("Clicking mic to start recording...")
                browser.click(mic_sel)
                
                # 3. Play the audio into the stream and wait for it to finish
                logger.info("Playing generated speech in browser context...")
                speaker.play_in_browser(browser.page)
                
                # 4. Stop recording
                stop_mic_sel = "button[aria-label='Stop recording'], button[aria-label*='stop'], button[aria-label*='recording'], button[aria-label*='record']"
                if browser.element_exists(stop_mic_sel):
                    logger.info("Clicking mic to stop recording...")
                    browser.click(stop_mic_sel)
                    browser.page.wait_for_timeout(1000) # Wait for page state update
                    
                # 5. Cleanup injection
                speaker.cleanup_in_browser(browser.page)
            else:
                logger.warning("Mic button not found on page.")
                continue

            check_sel = sel.get("check_button", "button:has-text('Check')")
            if browser.element_exists(check_sel):
                logger.info("Clicking Check button...")
                browser.click(check_sel)
            
            continue_sel = sel.get("continue_button", "button:has-text('Continue'), button:has-text('Submit'), button:has-text('Next')")
            if browser.element_exists(continue_sel, timeout=10000):
                logger.info("Clicking Continue/Submit/Next button...")
                browser.click(continue_sel)
                
            speaker.cleanup()
            logger.info("Speaking task completed.")
            return True
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {e}")
            speaker.cleanup()
            browser.page.wait_for_timeout(2000) # Only used for error backoff
            
    return False
