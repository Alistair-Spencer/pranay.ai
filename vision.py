# vision.py
import base64, os
from anthropic import Anthropic

def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("utf-8")

def build_system_prompt(core: str, mode_text: str, context: str) -> str:
    return f"{core}\n\n{mode_text}\n\n{context}If you use the context, cite the source in brackets."

def ask_with_image(system_prompt: str, user_text: str, image_bytes: bytes, media_type: str = "image/png", temperature: float = 0.4) -> str:
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")
    resp = client.messages.create(
        model=model,
        max_tokens=1200,
        temperature=temperature,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {"type": "input_image", "source": {"type": "base64", "media_type": media_type, "data": _b64(image_bytes)}},
            ],
        }],
    )
    # Join text blocks
    parts = []
    for blk in resp.content:
        if blk.type == "text":
            parts.append(blk.text)
    return "\n".join(parts).strip()
