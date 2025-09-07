# Claude-only LLM helpers (text + image)
import os, base64
from typing import List, Dict, Any
from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv()

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")
API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

_client = Anthropic(api_key=API_KEY)

def chat_llm(messages: List[Dict[str, str]]) -> str:
    """OpenAI-style messages -> Anthropic reply text."""
    system = ""
    turns: List[Dict[str, Any]] = []
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "system":
            system += content + "\n\n"
        elif role == "user":
            turns.append({"role": "user", "content": [{"type": "text", "text": content}]})
        elif role == "assistant":
            turns.append({"role": "assistant", "content": [{"type": "text", "text": content}]})

    print(f"[PranayAI] Using Anthropic model: {MODEL}")
    resp = _client.messages.create(
        model=MODEL,
        max_tokens=900,
        temperature=0.2,
        system=system.strip() or None,
        messages=turns if turns else [{"role": "user", "content": [{"type":"text","text":"Hello"}]}],
    )
    return "".join([b.text for b in resp.content if getattr(b, "type", "") == "text"]).strip()

def chat_llm_image(system_prompt: str, user_prompt: str, image_bytes: bytes, mime: str = "image/png") -> str:
    """Single-turn image + text -> reply text."""
    content = [
        {"type": "text", "text": user_prompt},
        {"type": "image", "source": {"type": "base64", "media_type": mime, "data": base64.b64encode(image_bytes).decode("utf-8")}},
    ]
    resp = _client.messages.create(
        model=MODEL,
        max_tokens=900,
        system=system_prompt or None,
        messages=[{"role": "user", "content": content}],
    )
    return "".join([b.text for b in resp.content if getattr(b, "type", "") == "text"]).strip()
