"""Local Ollama model access.

Behaviour is intentionally unchanged from v1 (same prompts, single-turn chat);
LLM upgrades such as tool calling and memory are planned separately.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = (
    "You are JARVIS, a helpful desktop AI "
    "assistant. Respond clearly and briefly. "
    "Do not claim to have performed actions "
    "unless a command handler confirmed them."
)

STUDY_PROMPT = """
You are JARVIS, a friendly AI study tutor for a second-year
Artificial Intelligence and Data Science engineering student.

Follow these rules:
1. Explain concepts in simple English.
2. Use headings and bullet points where helpful.
3. For exam questions, write clear, exam-ready answers.
4. Include examples for programming concepts.
5. For 5-mark questions, provide a suitable medium-length answer.
6. Never invent facts when you are unsure.
7. Help the student understand the concept instead of only
   giving the final answer.

Student's question:
{question}
"""


class LocalLLM:
    def __init__(self, model: str):
        self.model = model

    def chat(self, user_text: str) -> str:
        try:
            import ollama

            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_text},
                ],
            )
            return response["message"]["content"]

        except Exception as error:
            log.warning("Ollama chat failed: %s", error)
            return (
                "I couldn't connect to the local AI model. "
                "Check whether Ollama is running and the model "
                f"{self.model} is installed. Details: {error}"
            )

    def study(self, question: str) -> str:
        question = str(question or "").strip()

        if not question:
            return "Please ask me a study question."

        try:
            import ollama

            response = ollama.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are JARVIS Study Assistant, a helpful engineering tutor.",
                    },
                    {"role": "user", "content": STUDY_PROMPT.format(question=question)},
                ],
            )
            return response["message"]["content"].strip()

        except Exception as error:
            return f"Study Assistant error: {error}"

    def status(self) -> dict:
        """Health check only: is Ollama reachable and is the model pulled?"""

        try:
            import ollama

            listing = ollama.list()
            models = listing.get("models", []) if isinstance(listing, dict) else listing.models
            names = {
                (m.get("model") or m.get("name")) if isinstance(m, dict) else m.model
                for m in models
            }
            installed = any(name and name.split(":latest")[0] == self.model.split(":latest")[0] for name in names)
            return {
                "online": True,
                "model": self.model,
                "model_installed": installed,
                "message": "Ready" if installed else f"Run: ollama pull {self.model}",
            }
        except ImportError:
            return {"online": False, "model": self.model, "message": "ollama package not installed"}
        except Exception as error:
            return {"online": False, "model": self.model, "message": f"Ollama not running ({error.__class__.__name__})"}
