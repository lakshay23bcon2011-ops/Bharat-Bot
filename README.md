# Bharat English Corporate Automation Bot

This bot automates the process of completing assignments on the Bharat English Corporate platform.

## Features
- Automated Login
- Navigation to Writing, Reading, Listening, and Speaking sections
- AI-powered answering for Writing prompts and MCQs
- Automatic submission and progression

## Setup
1. Install system dependencies:
   - Ensure `ffmpeg` is installed and available in your system's PATH (required for audio chunking).
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
3. Configure `config.yaml` as needed.
4. Set your `GROQ_API_KEY`, `BET_USERNAME`, and `BET_PASSWORD` in the environment or `.env` file.

## Usage
Run the main orchestrator:
```bash
python main.py
```

## Modules
- `browser.py`: Handles all Playwright interactions.
- `ai_answerer.py`: Connects to Groq for generating answers.
- `speaker.py`: Text-to-Speech generation and browser injection.
- `transcriber.py`: Audio downloading and transcription via Groq/ffmpeg.
- `main.py`: The main loop that orchestrates the automation.
