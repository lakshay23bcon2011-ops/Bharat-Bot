# Bharat English Corporate Automation Bot

This bot automates the process of completing assignments on the Bharat English Corporate platform.

## Features
- Automated Login
- Navigation to Writing, Reading, Listening, and Speaking sections
- AI-powered answering for Writing prompts and MCQs
- Automatic submission and progression

## Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
2. Configure `config.yaml` with your credentials.
3. Set your `OPENAI_API_KEY` in the environment or `.env` file.

## Usage
Run the main orchestrator:
```bash
python main.py
```

## Modules
- `browser.py`: Handles all Playwright interactions.
- `ai_answerer.py`: Connects to OpenAI for generating answers.
- `main.py`: The main loop that orchestrates the automation.
