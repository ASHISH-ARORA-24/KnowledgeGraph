"""
Ollama client — builds RAG prompts and sends them to the local Ollama LLM.

OLLAMA_URL points to the local Ollama server. No API key required — Ollama runs fully offline.
"""

import requests

OLLAMA_URL = "http://localhost:11434/api/generate"


def build_prompt(question: str, context_nodes: list[dict]) -> str:
    """Build a RAG prompt by injecting retrieved context nodes around the user's question."""
    context_sections = []
    for node in context_nodes:
        meta = node["metadata"]
        section = f"--- {meta['name']} ({meta['type']}) ---\n{node['document']}"
        context_sections.append(section)

    context_text = "\n\n".join(context_sections)

    return f"""You are a code assistant. Answer only from the context below.
Do not guess. If the answer is not in the context, say so.

CONTEXT:
{context_text}

QUESTION:
{question}"""


def ask_ollama(prompt: str, model: str = "llama3") -> str:
    """Send a prompt to Ollama and return the generated text response."""
    response = requests.post(
        OLLAMA_URL,
        json={"model": model, "prompt": prompt, "stream": False},
    )
    response.raise_for_status()
    return response.json()["response"]
