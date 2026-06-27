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
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt}
                ]
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Groq API call failed: {e}")
            return ""

    def answer_writing(self, prompt: str) -> str:
        system_prompt = "You are an expert English writer. Write clear, formal but natural academic English responses. Use proper paragraphs. No headings or bullet points. 150-250 words."
        user_prompt = f"Write a response to the following writing task:\n\n{prompt}"
        return self._call_groq(system_prompt, user_prompt)

    def answer_mcq(self, question: str, options: list[str], context: str = "") -> str:
        options_text = "\n".join([f"  {i+1}. {opt}" for i, opt in enumerate(options)])
        context_section = f"\n\nContext/Passage:\n{context}\n" if context else ""
        system_prompt = "Reply with ONLY the exact text of the correct option — nothing else."
        user_prompt = f"Question: {question}{context_section}\nOptions:\n{options_text}\n\nWhich option is correct?"
        answer = self._call_groq(system_prompt, user_prompt)
        for option in options:
            if answer.lower() in option.lower() or option.lower() in answer.lower():
                return option
        return answer

    def generate_speech_text(self, prompt: str) -> str:
        system_prompt = "Generate a SPOKEN response — natural, conversational, 2-4 sentences. First person. Under 80 words."
        user_prompt = f"Provide a spoken response to this speaking task:\n\n{prompt}"
        return self._call_groq(system_prompt, user_prompt)
