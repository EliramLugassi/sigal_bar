"""Helper utilities for interacting with OpenAI's API."""

import os
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables (expects OPENAI_API_KEY in .env)
load_dotenv()

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Path to architecture file relative to repo root
ARCH_PATH = Path(__file__).resolve().parent.parent / "gpt_architecture.txt"
with open(ARCH_PATH, "r", encoding="utf-8") as f:
    ARCH_TEXT = f.read()

def ask_gpt(question: str, context: Optional[Dict[str, str]] = None) -> str:
    """Send a question plus dynamic context to OpenAI and return the reply."""
    context_lines = []
    if context:
        for key, value in context.items():
            context_lines.append(f"{key}: {value}")
    context_text = "\n".join(context_lines)

    user_content = f"Context:\n{context_text}\n\nQuestion:\n{question.strip()}"

    response = _client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": ARCH_TEXT},
            {"role": "user", "content": user_content},
        ],
        max_tokens=500,
    )

    return response.choices[0].message.content.strip()
