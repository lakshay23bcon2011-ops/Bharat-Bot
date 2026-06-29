import logging
import os
from groq import Groq

logger = logging.getLogger("BharatBot")

class AIAnswerer:
    def __init__(self, config: dict):
        ai_cfg = config.get("ai", {})
        self.model = ai_cfg.get("chat_model", "llama-3.3-70b-versatile")
        self.temperature = ai_cfg.get("temperature", 0.3)
        self.max_tokens = ai_cfg.get("max_tokens", 1000)
        self.client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        logger.info(f"AIAnswerer ready. Model: {self.model}")

    def _call_groq(self, system_prompt: str, user_prompt: str) -> str:
        models = [self.model, "llama-3.1-8b-instant", "gemma2-9b-it", "mixtral-8x7b-32768"]
        for idx, model_name in enumerate(models):
            try:
                response = self.client.chat.completions.create(
                    model=model_name,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt}
                    ]
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"Groq API call with model '{model_name}' failed: {e}")
                if idx < len(models) - 1:
                    logger.info("Retrying with fallback model...")
                else:
                    logger.error("All fallback models failed.")
        return ""

    def answer_writing(self, prompt: str) -> str:
        system_prompt = "You are an expert English writer. Write clear, formal but natural academic English responses. Use proper paragraphs. No headings or bullet points. 150-250 words."
        user_prompt = f"Write a response to the following writing task:\n\n{prompt}"
        return self._call_groq(system_prompt, user_prompt)

    def answer_mcq(self, question: str, options: list[str], context: str = "") -> str:
        options_text = "\n".join([f"  {i+1}. {opt}" for i, opt in enumerate(options)])
        context_section = f"\n\nContext/Passage/Audio Transcript:\n{context}\n" if context else ""
        system_prompt = (
            "You are an expert English language examiner scoring 100% on a professional English proficiency test.\n\n"
            "Task:\n"
            "1. Read the Context/Passage/Audio Transcript and the Question carefully.\n"
            "2. Analyze and think step-by-step about which option(s) are correct. Some questions may require selecting MULTIPLE options if the question asks for it (e.g., 'Select two...', 'Which of the following are...').\n"
            "3. For EACH correct option, output its option index/number wrapped in <option_number>...</option_number> tags (e.g., if option 2 and 4 are correct, output <option_number>2</option_number> and <option_number>4</option_number>).\n"
            "4. For EACH correct option, also output its exact text wrapped in <option_text>...</option_text> tags.\n\n"
            "Be extremely precise. Rely ONLY on the provided context."
        )
        user_prompt = f"Question: {question}{context_section}\nOptions:\n{options_text}\n\nSelect the correct option(s) and wrap them in the requested tags."
        answer = self._call_groq(system_prompt, user_prompt)
        logger.info(f"AI MCQ Raw Response:\n{answer}")
        return answer

    def generate_speech_text(self, prompt: str) -> str:
        system_prompt = "Generate a SPOKEN response — natural, conversational, 2-4 sentences. First person. Under 80 words."
        user_prompt = f"Provide a spoken response to this speaking task:\n\n{prompt}"
        return self._call_groq(system_prompt, user_prompt)
