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
                
            # Use virtual mic injection for speaking tasks
            speaker.inject_mic(browser, wav_path)
            
            # Click record button if it exists
            mic_sel = config["selectors"]["exam"].get("mic_button", "button[hint='Record']")
            if browser.element_exists(mic_sel):
                browser.click(mic_sel)
                # Wait for the duration of the audio + some buffer
                import wave
                with wave.open(wav_path, 'rb') as wf:
                    duration = wf.getnframes() / float(wf.getframerate())
                browser.wait(int(duration * 1000) + 2000)
                # Click stop if needed or wait for auto-stop
                if browser.element_exists(mic_sel):
                    browser.click(mic_sel)
            
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
